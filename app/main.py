<<<<<<< HEAD
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
=======
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List

from app.graph.seed import seed_demo_data
from app.graph.queries import (
    get_claim_provenance,
    get_claim_provenance_with_telemetry,
    get_claim_evidence,
    get_multi_hop_provenance
)

app = FastAPI(title="Custody - Graph-Backed Memory Security")

class QueryRequest(BaseModel):
    claim_id: str = "claim_001"
    mode: str = "custody"  # Options: off, naive, custody

@app.get("/health")
def health():
    return {"status": "ok", "service": "custody"}

@app.post("/demo/reset")
def reset_demo():
    seed_demo_data()
    return {"status": "success", "message": "FalkorDB demo graph reset and re-seeded successfully."}

@app.post("/evaluate")
def evaluate_claim(req: QueryRequest):
    claim_id = req.claim_id
    mode = req.mode.lower()
    
    # 1. Fetch telemetry and provenance from FalkorDB
    telemetry = get_claim_provenance_with_telemetry(claim_id)
    evidence = get_claim_evidence(claim_id)
    
    records = telemetry.get("records", [])
    contradicting = evidence.get("contradicting", [])
    supporting = evidence.get("supporting", [])
    
    # Baseline: If mode is 'off'
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

    # Baseline: If mode is 'naive' (Accepts memory without graph provenance checks)
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

    # Active Guard: 'custody' mode (Enforces graph provenance & contradiction checks)
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

@app.get("/", response_class=HTMLResponse)
def index_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Custody — AI Agent Memory Security</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-8">
      <div class="max-w-4xl mx-auto space-y-6">
        
        <header class="border-b border-slate-800 pb-4 flex justify-between items-center">
          <div>
            <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-emerald-400">
              Custody
            </h1>
            <p class="text-slate-400 text-sm mt-1">Graph-Backed AI Agent Memory Security & Provenance Layer (FalkorDB)</p>
          </div>
          <button onclick="resetDb()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded border border-slate-700">
            Reset Graph Data
          </button>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="md:col-span-1 bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
            <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Run Evaluation</h2>
            
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Select Claim / Scenario</label>
              <select id="claim_id" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200">
                <option value="claim_001">claim_001 (Untrusted / Contradicted Port 8080)</option>
                <option value="claim_002">claim_002 (Verified TLS 1.3 Mandatory)</option>
                <option value="claim_301">claim_301 (Scenario 003: Memory Laundering)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Guard Mode</label>
              <select id="guard_mode" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200">
                <option value="custody">custody (Active FalkorDB Graph Defense)</option>
                <option value="naive">naive (Unvalidated Memory Trust)</option>
                <option value="off">off (No Verification)</option>
              </select>
            </div>

            <button onclick="runEvaluation()" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm rounded shadow">
              Run Evaluation
            </button>
          </div>

          <div class="md:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
            <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Decision & Telemetry</h2>
            
            <div id="result-box" class="space-y-3">
              <p class="text-slate-500 text-sm italic">Click "Run Evaluation" to query FalkorDB.</p>
            </div>
          </div>
        </div>

      </div>

      <script>
        async function runEvaluation() {
          const claim_id = document.getElementById('claim_id').value;
          const mode = document.getElementById('guard_mode').value;
          const resBox = document.getElementById('result-box');
          
          resBox.innerHTML = '<p class="text-slate-400 text-sm">Traversing FalkorDB graph...</p>';
          
          try {
            const res = await fetch('/evaluate', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ claim_id, mode })
            });
            const data = await res.json();
            
            let badgeColor = "bg-emerald-900 text-emerald-300 border-emerald-700";
            if (data.decision === "CONFLICTING") badgeColor = "bg-red-950 text-red-300 border-red-700";
            if (data.decision === "UNTRUSTED") badgeColor = "bg-amber-950 text-amber-300 border-amber-700";
            if (data.decision === "ACCEPTED_NAIVE") badgeColor = "bg-yellow-950 text-yellow-300 border-yellow-700";
            
            resBox.innerHTML = `
              <div class="flex items-center justify-between">
                <span class="px-2.5 py-1 text-xs font-bold rounded border ${badgeColor}">
                  ${data.decision}
                </span>
                <span class="text-xs font-mono bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded">
                  ${data.latency_ms} ms
                </span>
              </div>

              <div class="text-sm text-slate-200 mt-2 bg-slate-950 p-3 rounded border border-slate-800">
                <strong>Reason:</strong> ${data.explanation}
              </div>

              <div class="mt-4 p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Executed Cypher Traversal</div>
                <pre class="text-xs font-mono text-emerald-400 overflow-x-auto p-2 bg-black rounded">${data.cypher_query}</pre>
              </div>
            `;
          } catch(err) {
            resBox.innerHTML = `<p class="text-red-400 text-sm">Error: ${err.message}</p>`;
          }
        }

        async function resetDb() {
          if (!confirm('Reset FalkorDB demo graph data?')) return;
          const res = await fetch('/demo/reset', { method: 'POST' });
          const data = await res.json();
          alert(data.message);
        }
      </script>
    </body>
    </html>
    """
>>>>>>> upstream/main
