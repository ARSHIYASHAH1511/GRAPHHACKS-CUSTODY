"""
Cross-session and end-to-end tests for the Custody demo service.

Tests verify:
- Researcher records provenance into FalkorDB in Session A.
- Assistant retrieves that provenance in Session B (separate session object).
- Custody mode produces the expected deterministic decision.
- Naive mode passes through without a provenance gate.
- Off mode passes through unconditionally.
- Same fixture always returns the same result (repeatability).
"""
import pytest

from app.graph.seed import seed_demo_data
from app.graph.queries import get_claim_provenance
from app.agents.researcher import ResearcherAgent
from app.agents.assistant import AssistantAgent
from app.services.custody_service import run_demo, reset_demo


@pytest.fixture(autouse=True)
def fresh_graph():
    """Re-seed the graph before each test for a clean, deterministic state."""
    reset_demo()
    yield


# ── Test 1: Researcher records provenance correctly ──────────────────────────

def test_researcher_records_provenance():
    """
    Researcher running in Session A must persist the claim and its source
    to FalkorDB. The provenance should survive beyond the Researcher's
    Python object lifetime.
    """
    researcher = ResearcherAgent(session_id="test_sess_a")
    obs = researcher.research_claim("claim_001")

    assert obs["recorded"] is True
    assert obs["source_id"] == "source_untrusted"
    assert obs["session_id"] == "test_sess_a"

    # Verify the graph actually holds this provenance
    prov = get_claim_provenance("claim_001")
    assert len(prov) > 0
    assert prov[0]["source_id"] == "source_untrusted"
    assert prov[0]["trust_tier"] == "untrusted"


# ── Test 2: Cross-session — Assistant reads Session A data in Session B ───────

def test_cross_session_provenance():
    """
    After the Researcher records claim_001 in Session A, a brand-new
    AssistantAgent instance (Session B) must be able to retrieve and evaluate
    it from FalkorDB — not from any in-memory Python state.
    """
    # Session A
    ResearcherAgent(session_id="sess_a_cross").research_claim("claim_001")

    # Session B — new object, different session ID
    assistant = AssistantAgent(session_id="sess_b_cross")
    result = assistant.evaluate("claim_001", mode="custody")

    assert result["mode"] == "custody"
    # claim_001 has a contradiction from source_policy → conflicting
    assert result["decision"] in ("conflicting", "untrusted")
    assert result["session_id"] == "sess_b_cross"
    # Provenance came from FalkorDB, not in-process memory
    assert len(result["provenance"]) > 0


# ── Test 3: Custody mode blocks an untrusted+contradicted claim ───────────────

def test_custody_blocks_untrusted_contradicted_claim():
    """
    claim_001 originates from an untrusted source and has verified
    contradicting evidence. Custody mode must flag it as conflicting or untrusted.
    """
    result = run_demo(mode="custody", scenario_id="scenario_001")

    evals = result["evaluations"]
    assert len(evals) == 1
    decision = evals[0]["decision"]
    assert decision in ("conflicting", "untrusted"), (
        f"Expected conflicting or untrusted, got: {decision}"
    )


# ── Test 4: Custody mode supports a well-evidenced claim ─────────────────────

def test_custody_supports_verified_claim():
    """
    claim_002 originates from a verified source and has supporting evidence
    with no contradiction. Custody mode must return 'supported'.
    """
    result = run_demo(mode="custody", scenario_id="scenario_002")

    evals = result["evaluations"]
    assert len(evals) == 1
    assert evals[0]["decision"] == "supported"


# ── Test 5: Naive mode passes through without provenance check ────────────────

def test_naive_mode_passes_through():
    """
    Naive mode must not invoke the policy engine. It should allow
    the claim through regardless of source trust.
    """
    result = run_demo(mode="naive", scenario_id="scenario_001")

    evals = result["evaluations"]
    assert evals[0]["decision"] == "allowed_naive"
    assert evals[0]["reason_code"] == "NAIVE_NO_PROVENANCE_CHECK"
    # No provenance path returned
    assert evals[0]["provenance"] == []


# ── Test 6: Off mode passes through unconditionally ──────────────────────────

def test_off_mode_passes_through():
    """
    Guard OFF must not check provenance and must return allowed_no_guard.
    """
    result = run_demo(mode="off", scenario_id="scenario_001")

    evals = result["evaluations"]
    assert evals[0]["decision"] == "allowed_no_guard"
    assert evals[0]["reason_code"] == "GUARD_DISABLED"


# ── Test 7: Repeatability — same fixture, same result ────────────────────────

def test_repeatability():
    """
    Running the same scenario twice with custody mode must produce identical
    decisions. The graph is deterministic.
    """
    result_1 = run_demo(mode="custody", scenario_id="scenario_001")
    reset_demo()
    result_2 = run_demo(mode="custody", scenario_id="scenario_001")

    decision_1 = result_1["evaluations"][0]["decision"]
    decision_2 = result_2["evaluations"][0]["decision"]
    assert decision_1 == decision_2, (
        f"Non-deterministic: first run={decision_1}, second run={decision_2}"
    )


# ── Test 8: Invalid mode raises an error ─────────────────────────────────────

def test_invalid_mode_returns_error():
    result = run_demo(mode="magic", scenario_id="scenario_001")
    assert "error" in result


# ── Test 9: Invalid scenario returns error ────────────────────────────────────

def test_invalid_scenario_returns_error():
    result = run_demo(mode="custody", scenario_id="nonexistent_scenario")
    assert "error" in result
