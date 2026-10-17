"""
Custody Service — orchestration layer.

Exposes run_demo(mode, scenario_id) which the API layer calls.
This is the only place that knows about both agents; the agents
themselves do not import each other.
"""
import uuid
from typing import Dict, Any

from app.graph.seed import seed_demo_data
from app.graph.client import get_graph
from app.agents.researcher import ResearcherAgent
from app.agents.assistant import AssistantAgent

# ── Scenario registry ─────────────────────────────────────────────────────────
# Maps scenario_id -> list of claim IDs the Researcher investigates
SCENARIOS: Dict[str, list] = {
    "scenario_001": ["claim_001"],   # untrusted claim that gets contradicted
    "scenario_002": ["claim_002"],   # trusted claim with verified support
    "scenario_full": ["claim_001", "claim_002"],  # both claims
}


def reset_demo() -> Dict[str, Any]:
    """
    Clear the graph and re-seed the demo data.
    Call this before running a fresh demo to ensure a clean state.
    """
    graph = get_graph()
    try:
        graph.query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    seed_demo_data()
    return {"status": "reset_complete", "message": "Graph cleared and re-seeded."}


def run_demo(mode: str, scenario_id: str = "scenario_001") -> Dict[str, Any]:
    """
    Execute the full Custody demo flow for a given scenario and guard mode.

    Flow:
      1. Researcher (Session A) investigates claims and records provenance.
      2. Assistant (Session B) evaluates those claims using the guard mode.
      3. Returns a structured result with decision, evidence, and provenance.

    mode:
      - "off"     → no guard, claim passes through
      - "naive"   → memory reused without provenance check
      - "custody" → full graph-based provenance and policy evaluation
    """
    if mode not in ("off", "naive", "custody"):
        return {"error": f"Unknown mode '{mode}'. Use off, naive, or custody."}

    claim_ids = SCENARIOS.get(scenario_id)
    if claim_ids is None:
        return {"error": f"Unknown scenario '{scenario_id}'."}

    # ── Session A: Researcher ─────────────────────────────────────────────────
    researcher_session = f"sess_researcher_{uuid.uuid4().hex[:8]}"
    researcher = ResearcherAgent(session_id=researcher_session)
    research_results = researcher.run_scenario(claim_ids)

    # ── Session B: Assistant ──────────────────────────────────────────────────
    assistant_session = f"sess_assistant_{uuid.uuid4().hex[:8]}"
    assistant = AssistantAgent(session_id=assistant_session)

    evaluations = []
    for obs in research_results:
        if "error" in obs:
            evaluations.append({"claim_id": obs["claim_id"], "error": obs["error"]})
            continue
        result = assistant.evaluate(obs["claim_id"], mode=mode)
        evaluations.append(result)

    return {
        "scenario_id": scenario_id,
        "mode": mode,
        "researcher_session": researcher_session,
        "assistant_session": assistant_session,
        "research_observations": research_results,
        "evaluations": evaluations,
    }
