
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.graph.queries import (
    record_observation,
    get_claim_provenance,
    get_claim_provenance_with_telemetry,
    get_claim_evidence,
)
from app.services.custody_service import run_demo, reset_demo


app = FastAPI(
    title="Custody — Graph-Backed Memory Security",
    description=(
        "Graph-backed provenance and memory security "
        "for AI agents using FalkorDB."
    ),
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

if FRONTEND_DIR.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


# Request schemas
class QueryRequest(BaseModel):
    claim_id: str = "claim_001"
    mode: str = "custody"


class RunDemoRequest(BaseModel):
    mode: str = "custody"
    scenario_id: str = "scenario_001"


class ObservationRequest(BaseModel):
    agent_id: str
    session_id: str
    claim: Dict[str, Any]
    source_id: str


# Homepage
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_homepage(request: Request):
    template_path = TEMPLATES_DIR / "index.html"
    frontend_path = FRONTEND_DIR / "index.html"

    if template_path.is_file():
        return HTMLResponse(
            content=template_path.read_text(encoding="utf-8")
        )

    if frontend_path.is_file():
        return FileResponse(str(frontend_path))

    return HTMLResponse(
        content=(
            "<h1>Custody API is running</h1>"
            "<p>Open <a href='/docs'>/docs</a> to inspect the API.</p>"
        )
    )


# Health check
@app.get("/health", tags=["system"])
def health_check():
    try:
        from app.graph.client import get_graph

        graph = get_graph()
        graph.query("RETURN 1")

        return {
            "status": "ok",
            "service": "custody",
            "graph": "connected",
        }

    except Exception as exc:
        return {
            "status": "degraded",
            "service": "custody",
            "graph": "error",
            "detail": str(exc),
        }


# Reset and reseed demo
@app.post("/demo/reset", tags=["demo"])
def handle_reset():
    try:
        result = reset_demo()

        if result.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Graph reset failed"),
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not reset demo: {exc}",
        ) from exc


# Run demo
@app.post("/demo/run", tags=["demo"])
def handle_run_demo(body: RunDemoRequest):
    mode = body.mode.strip().lower()

    if mode not in {"off", "naive", "custody"}:
        raise HTTPException(
            status_code=400,
            detail="mode must be off, naive, or custody",
        )

    try:
        result = run_demo(
            mode=mode,
            scenario_id=body.scenario_id,
        )

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=result["error"],
            )

        # Keep session fields available for frontend versions
        # that expect either nested or top-level session values.
        sessions = result.get("sessions", {})

        if isinstance(sessions, dict):
            result.setdefault(
                "researcher_session",
                sessions.get("researcher", ""),
            )
            result.setdefault(
                "assistant_session",
                sessions.get("assistant", ""),
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Demo execution failed: {exc}",
        ) from exc


# Evaluate one claim
@app.post("/evaluate", tags=["demo"])
def evaluate_claim(req: QueryRequest):
    claim_id = req.claim_id
    mode = req.mode.strip().lower()

    if mode not in {"off", "naive", "custody"}:
        raise HTTPException(
            status_code=400,
            detail="mode must be off, naive, or custody",
        )

    try:
        telemetry = get_claim_provenance_with_telemetry(claim_id)
        evidence = get_claim_evidence(claim_id)

        records = telemetry.get("records", [])
        contradicting = evidence.get("contradicting", [])
        supporting = evidence.get("supporting", [])

        # These modes intentionally demonstrate different policies.
        if mode == "off":
            return {
                "mode": "off",
                "claim_id": claim_id,
                "decision": "UNENFORCED",
                "reason_code": "POLICY_GUARD_DISABLED",
                "trust_tier": "unknown",
                "latency_ms": telemetry.get("latency_ms", 0.0),
                "cypher_query": (
                    "-- Guard disabled: no trust-policy traversal"
                ),
                "explanation": (
                    "No graph trust policy applied. "
                    "The claim is not checked by the custody guard."
                ),
            }

        if mode == "naive":
            return {
                "mode": "naive",
                "claim_id": claim_id,
                "decision": "ACCEPTED_NAIVE",
                "reason_code": "STORED_IN_MEMORY",
                "trust_tier": "unverified",
                "latency_ms": telemetry.get("latency_ms", 0.0),
                "cypher_query": (
                    "MATCH (c:Claim {id: $claim_id}) RETURN c"
                ),
                "explanation": (
                    "Demonstration baseline: the claim is accepted "
                    "without checking its provenance or contradictions."
                ),
            }

        # Custody mode evaluates evidence and source provenance.
        if contradicting:
            decision = "CONFLICTING"
            reason_code = "CONTRADICTED_BY_POLICY"
            explanation = (
                "Claim flagged because verified evidence contradicts it."
            )

        elif not records or records[0].get("trust_tier") == "untrusted":
            decision = "UNTRUSTED"
            reason_code = "UNVERIFIED_SOURCE_ORIGIN"
            explanation = (
                "Claim originates from an untrusted or unknown source."
            )

        else:
            decision = "SUPPORTED"
            reason_code = "VERIFIED_BY_GRAPH"
            explanation = (
                "The available graph evidence supports the claim."
            )

        return {
            "mode": "custody",
            "claim_id": claim_id,
            "decision": decision,
            "reason_code": reason_code,
            "trust_tier": (
                records[0].get("trust_tier", "unknown")
                if records
                else "unknown"
            ),
            "latency_ms": telemetry.get("latency_ms", 0.0),
            "cypher_query": telemetry.get("cypher_query", ""),
            "contradicting_evidence": contradicting,
            "supporting_evidence": supporting,
            "explanation": explanation,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Claim evaluation failed: {exc}",
        ) from exc


# Record a graph observation
@app.post("/observations", tags=["graph"])
def add_observation(body: ObservationRequest):
    try:
        record_observation(
            agent_id=body.agent_id,
            session_id=body.session_id,
            claim=body.claim,
            source_id=body.source_id,
        )

        return {
            "status": "recorded",
            "claim_id": body.claim.get("id"),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not record observation: {exc}",
        ) from exc


# Look up claim provenance
@app.get("/claims/{claim_id}/provenance", tags=["graph"])
def get_provenance(claim_id: str):
    try:
        rows = get_claim_provenance(claim_id)

        return {
            "claim_id": claim_id,
            "provenance": rows,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Provenance lookup failed: {exc}",
        ) from exc


# Claim provenance with query telemetry
@app.get(
    "/claims/{claim_id}/provenance/telemetry",
    tags=["graph"],
)
def get_provenance_telemetry(claim_id: str):
    try:
        result = get_claim_provenance_with_telemetry(claim_id)

        return {
            "claim_id": claim_id,
            **result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Provenance telemetry failed: {exc}",
        ) from exc
