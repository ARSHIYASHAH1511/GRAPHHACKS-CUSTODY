import time
from typing import Dict, Any, List
from app.graph.client import get_graph
from app.graph.seed import seed_demo_data
from app.agents.researcher import ResearcherAgent
from app.agents.assistant import AssistantAgent


SCENARIO_CLAIM_MAP = {
    "scenario_001": ["claim_001"],
    "scenario_002": ["claim_002"],
    "scenario_full": ["claim_001", "claim_002"],
    "scenario_003": ["claim_301"],
}

CUSTODY_CYPHER_QUERY = """
MATCH (c:Claim {id: $claim_id})
OPTIONAL MATCH path = (c)-[r:ORIGINATED_FROM|CONTRADICTED_BY|SUPPORTED_BY|OBSERVED|PASSED_MEMORY_TO*1..4]-(n)
RETURN c, r, n, path
""".strip()


def reset_demo() -> Dict[str, Any]:
    """Resets and re-seeds the FalkorDB graph with synthetic scenarios."""
    try:
        seed_demo_data()
        return {"status": "reset_complete", "message": "Graph reset and re-seeded successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_demo(mode: str, scenario_id: str) -> Dict[str, Any]:
    """
    Runs a test scenario through the Researcher and Assistant agents,
    evaluating claims using FalkorDB multi-hop provenance traversal.
    """
    mode_name = (mode or "").strip().lower()
    if mode_name not in {"off", "naive", "custody"}:
        return {"error": f"Unsupported mode: {mode}"}

    if scenario_id not in SCENARIO_CLAIM_MAP:
        return {"error": f"Unknown scenario: {scenario_id}"}

    claim_ids = SCENARIO_CLAIM_MAP[scenario_id]

    # Initialize logical agents
    researcher = ResearcherAgent()
    assistant = AssistantAgent()

    # Step 1: Researcher agent records observation claims into FalkorDB
    researcher.run_scenario(claim_ids)

    # Step 2: Assistant agent evaluates memory claims with latency tracking
    start_time = time.perf_counter()

    evaluations: List[Dict[str, Any]] = []
    for claim_id in claim_ids:
        # Evaluate claim based on Guard Mode (off, naive, custody)
        eval_result = assistant.evaluate_claim(
            claim_id=claim_id,
            mode=mode_name,
            researcher_session_id=researcher.session_id,
        )
        evaluations.append(eval_result)

    # Measure FalkorDB query & policy evaluation latency in milliseconds
    elapsed_time = time.perf_counter() - start_time
    latency_ms = round(elapsed_time * 1000, 2)

    # Select displayed Cypher query based on active mode
    if mode_name == "custody":
        displayed_cypher = CUSTODY_CYPHER_QUERY
    elif mode_name == "naive":
        displayed_cypher = "MATCH (c:Claim {id: $claim_id}) RETURN c"
    else:
        displayed_cypher = "-- Mode: OFF (No Graph Traversal Executed)"

    return {
        "mode": mode_name,
        "scenario_id": scenario_id,
        "sessions": {
            "researcher": researcher.session_id,
            "assistant": assistant.session_id,
        },
        "evaluations": evaluations,
        "cypher_query": displayed_cypher,
        "latency_ms": latency_ms,
    }
