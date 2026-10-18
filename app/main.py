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