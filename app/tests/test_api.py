"""
API integration tests for Custody FastAPI endpoints.

Uses httpx TestClient — no live server required.
Tests verify documented response shapes, error handling, and mode behavior.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.custody_service import reset_demo

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_graph():
    """Re-seed the graph before each test for a clean, deterministic state."""
    reset_demo()
    yield


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_returns_ok():
    """GET /health must return status ok and graph connected."""
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "connected" in body["graph"]


# ── Demo reset ────────────────────────────────────────────────────────────────

def test_demo_reset_succeeds():
    """POST /demo/reset must clear and re-seed the graph without error."""
    res = client.post("/demo/reset")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "reset_complete"
    assert "message" in body


# ── Demo run — valid modes ────────────────────────────────────────────────────

def test_demo_run_custody_mode_blocks_untrusted_claim():
    """
    POST /demo/run with mode=custody and scenario_001 must return a decision
    of conflicting or untrusted for claim_001.
    """
    res = client.post("/demo/run", json={"mode": "custody", "scenario_id": "scenario_001"})
    assert res.status_code == 200
    body = res.json()

    assert body["mode"] == "custody"
    assert body["scenario_id"] == "scenario_001"
    assert "evaluations" in body
    assert len(body["evaluations"]) == 1

    decision = body["evaluations"][0]["decision"]
    assert decision in ("conflicting", "untrusted"), f"Unexpected decision: {decision}"


def test_demo_run_custody_mode_supports_verified_claim():
    """
    POST /demo/run with mode=custody and scenario_002 must return supported
    for claim_002 (verified source, supporting evidence).
    """
    res = client.post("/demo/run", json={"mode": "custody", "scenario_id": "scenario_002"})
    assert res.status_code == 200
    body = res.json()

    assert body["evaluations"][0]["decision"] == "supported"


def test_demo_run_naive_mode_passes_through():
    """Naive mode must return allowed_naive without a provenance check."""
    res = client.post("/demo/run", json={"mode": "naive", "scenario_id": "scenario_001"})
    assert res.status_code == 200
    body = res.json()
    assert body["evaluations"][0]["decision"] == "allowed_naive"
    assert body["evaluations"][0]["provenance"] == []


def test_demo_run_off_mode_passes_through():
    """Off mode must return allowed_no_guard unconditionally."""
    res = client.post("/demo/run", json={"mode": "off", "scenario_id": "scenario_001"})
    assert res.status_code == 200
    body = res.json()
    assert body["evaluations"][0]["decision"] == "allowed_no_guard"
    assert body["evaluations"][0]["reason_code"] == "GUARD_DISABLED"


def test_demo_run_full_scenario_returns_two_evaluations():
    """scenario_full must return evaluations for both claims."""
    res = client.post("/demo/run", json={"mode": "custody", "scenario_id": "scenario_full"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["evaluations"]) == 2


# ── Demo run — error cases ────────────────────────────────────────────────────

def test_demo_run_invalid_mode_returns_400():
    """An unknown mode must return HTTP 400."""
    res = client.post("/demo/run", json={"mode": "magic", "scenario_id": "scenario_001"})
    assert res.status_code == 400


def test_demo_run_invalid_scenario_returns_400():
    """An unknown scenario must return HTTP 400."""
    res = client.post("/demo/run", json={"mode": "custody", "scenario_id": "nonexistent"})
    assert res.status_code == 400


# ── Observations ──────────────────────────────────────────────────────────────

def test_post_observation_records_claim():
    """POST /observations must persist a claim and return status recorded."""
    payload = {
        "agent_id": "agent_test",
        "session_id": "sess_api_test",
        "claim": {"id": "claim_api_001", "text": "API test claim.", "status": "pending"},
        "source_id": "source_policy",
    }
    res = client.post("/observations", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "recorded"
    assert body["claim_id"] == "claim_api_001"


# ── Provenance lookup ─────────────────────────────────────────────────────────

def test_provenance_returns_data_for_known_claim():
    """GET /claims/{claim_id}/provenance must return provenance rows for a seeded claim."""
    # Seed the claim first via the researcher flow
    client.post("/demo/run", json={"mode": "custody", "scenario_id": "scenario_001"})

    res = client.get("/claims/claim_001/provenance")
    assert res.status_code == 200
    body = res.json()
    assert body["claim_id"] == "claim_001"
    assert len(body["provenance"]) > 0
    assert body["provenance"][0]["source_id"] == "source_untrusted"


def test_provenance_returns_empty_for_unknown_claim():
    """GET /claims/{claim_id}/provenance must return an empty list for an unknown claim."""
    res = client.get("/claims/claim_nonexistent/provenance")
    assert res.status_code == 200
    body = res.json()
    assert body["provenance"] == []


# ── Response structure consistency ────────────────────────────────────────────

def test_all_modes_return_same_response_shape():
    """
    All three modes must return the same top-level keys so the frontend
    can render any result without mode-specific branches.
    """
    required_keys = {"mode", "claim_id", "decision", "reason_code", "evidence", "provenance", "explanation"}

    for mode in ("off", "naive", "custody"):
        res = client.post("/demo/run", json={"mode": mode, "scenario_id": "scenario_001"})
        assert res.status_code == 200
        body = res.json()
        eval_keys = set(body["evaluations"][0].keys())
        missing = required_keys - eval_keys
        assert not missing, f"Mode '{mode}' evaluation missing keys: {missing}"
