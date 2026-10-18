import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.graph.seed import seed_demo_data
from app.graph.queries import (
    record_observation,
    get_claim_provenance,
    get_claim_provenance_with_telemetry,
    get_claim_evidence,
    get_multi_hop_provenance
)
from app.services.custody_service import run_demo, reset_demo

app = FastAPI(
    title="Custody — Graph-Backed Memory Security",
    description="Graph-backed provenance and memory security layer for AI agents using FalkorDB.",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent

# Serve static/frontend files if directory exists
_FRONTEND_DIR = BASE_DIR / "frontend"
_TEMPLATES_DIR = BASE_DIR / "app" / "templates"

if _FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


# Pydantic Schemas
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


# ── System Endpoints ─────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health_check():
    """Verify API status and FalkorDB connectivity."""
    try:
        from app.graph.client import get_graph
        g = get_graph()
        g.query("RETURN 1")
        graph_status = "connected"
    except Exception as e:
        graph_status = f"error: {e}"
    return {"status": "ok", "service": "custody", "graph": graph_status}


# ── Frontend Interface ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_homepage(request: Request):
    """Serves the dashboard HTML interface."""
    index_template = _TEMPLATES_DIR / "index.html"
    index_frontend = _FRONTEND_DIR / "index.html"
    
    if index_template.exists():
        return HTMLResponse(content=index_template.read_text(encoding="utf-8"))
    elif index_frontend.exists():
        return FileResponse(str(index_frontend))
    
    return HTMLResponse(content="<h1>Custody API is running. Check /docs</h1>")


# ── Demo & Evaluation Controls ───────────────────────────────────────────────

@app.post("/demo/reset", tags=["demo"])
def handle_reset():
    """Clear and re-seed the FalkorDB synthetic graph scenario."""
    try:
        result = reset_demo()
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/demo/run", tags=["demo"])
def handle_run_demo(body: RunDemoRequest):
    """Run full evaluation scenario for the UI dashboard."""
    try:
        result = run_demo(mode=body.mode, scenario_id=body.scenario_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        if "sessions" in result and isinstance(result["sessions"], dict):
            result["researcher_session"] = result["sessions"].get("researcher", "")
            result["assistant_session"] = result["sessions"].get("assistant", "")
            
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate", tags=["demo"])
def evaluate_claim(req: QueryRequest):
    """Evaluate a specific claim with telemetry and decision details."""
    claim_id = req.claim_id
    mode = req.mode.lower()
    
    telemetry = get_claim_provenance_with_telemetry(claim_id)
    evidence = get_claim_evidence(claim_id)
    
    records = telemetry.get("records", [])
    contradicting = evidence.get("contradicting", [])
    supporting = evidence.get("supporting", [])
    
    if mode == "off":
        return {
            "mode": "off",
            "claim_id": claim_id,
            "decision": "UNENFORCED",
            "reason_code": "POLICY_GUARD_DISABLED",
            "trust_tier": "unknown",
            "latency_ms": telemetry.get("latency_ms", 0.0),
            "cypher_query": telemetry.get("cypher_query", ""),
            "explanation": "No graph trust policy applied. Claim is accepted blindly."
        }

    if mode == "naive":
        return {
            "mode": "naive",
            "claim_id": claim_id,
            "decision": "ACCEPTED_NAIVE",
            "reason_code": "STORED_IN_MEMORY",
            "trust_tier": "unverified",
            "latency_ms": telemetry.get("latency_ms", 0.0),
            "cypher_query": telemetry.get("cypher_query", ""),
            "explanation": "Claim found in prior agent memory and trusted unconditionally without checking contradictory evidence or source tier."
        }

    if contradicting:
        decision = "CONFLICTING"
        reason_code = "CONTRADICTED_BY_POLICY"
        explanation = f"Flagged and quarantined: Claim is explicitly contradicted by verified evidence ({contradicting[0].get('id', 'ev')})."
    elif not records or records[0].get("trust_tier") == "untrusted":
        decision = "UNTRUSTED"
        reason_code = "UNVERIFIED_SOURCE_ORIGIN"
        explanation = "Rejected: Claim originates from an untrusted or unknown source without supporting evidence."
    else:
        decision = "SUPPORTED"
        reason_code = "VERIFIED_BY_GRAPH"
        explanation = "Accepted: Claim is verified by approved policy evidence."

    return {
        "mode": "custody",
        "claim_id": claim_id,
        "decision": decision,
        "reason_code": reason_code,
        "trust_tier": records[0].get("trust_tier") if records else "unknown",
        "latency_ms": telemetry.get("latency_ms", 0.0),
        "cypher_query": telemetry.get("cypher_query", ""),
        "contradicting_evidence": contradicting,
        "supporting_evidence": supporting,
        "explanation": explanation
    }


# ── Graph Observations & Provenance ──────────────────────────────────────────

@app.post("/observations", tags=["graph"])
def add_observation(body: ObservationRequest):
    """Record a claim observation into FalkorDB."""
    try:
        record_observation(
            agent_id=body.agent_id,
            session_id=body.session_id,
            claim=body.claim,
            source_id=body.source_id,
        )
        return {"status": "recorded", "claim_id": body.claim.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/claims/{claim_id}/provenance", tags=["graph"])
def get_provenance(claim_id: str):
    """Return the provenance path for a claim from FalkorDB."""
    rows = get_claim_provenance(claim_id)
    return {"claim_id": claim_id, "provenance": rows}
