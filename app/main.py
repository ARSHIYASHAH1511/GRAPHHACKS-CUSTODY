"""
Custody FastAPI backend.
Start with: uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.schemas import (
    RunDemoRequest,
    DemoResult,
    HealthResponse,
    ResetResponse,
    ObservationRequest,
    ProvenanceResponse,
)
from app.graph.queries import record_observation, get_claim_provenance
from app.services.custody_service import run_demo, reset_demo

app = FastAPI(
    title="Custody",
    description="Graph-backed memory security layer for AI agents.",
    version="0.1.0",
)

# ── Serve frontend ────────────────────────────────────────────────────────────
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend():
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Custody API running. See /docs"}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check():
    """Verify the API and FalkorDB are reachable."""
    try:
        from app.graph.client import get_graph
        g = get_graph()
        g.query("RETURN 1")
        graph_status = "connected"
    except Exception as e:
        graph_status = f"error: {e}"
    return {"status": "ok", "graph": graph_status}


# ── Demo controls ─────────────────────────────────────────────────────────────

@app.post("/demo/reset", response_model=ResetResponse, tags=["demo"])
def demo_reset():
    """Clear the graph and re-seed the synthetic scenario."""
    result = reset_demo()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result


@app.post("/demo/run", tags=["demo"])
def demo_run(body: RunDemoRequest):
    """
    Run the full two-agent demo.

    mode: off | naive | custody
    scenario_id: scenario_001 | scenario_002 | scenario_full
    """
    result = run_demo(mode=body.mode, scenario_id=body.scenario_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Observations ──────────────────────────────────────────────────────────────

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


# ── Provenance lookup ─────────────────────────────────────────────────────────

@app.get("/claims/{claim_id}/provenance", response_model=ProvenanceResponse, tags=["graph"])
def get_provenance(claim_id: str):
    """Return the provenance path for a claim from FalkorDB."""
    rows = get_claim_provenance(claim_id)
    return {"claim_id": claim_id, "provenance": rows}
