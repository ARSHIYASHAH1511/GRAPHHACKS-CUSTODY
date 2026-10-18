from app.graph.seed import seed_demo_data
from app.graph.queries import (
    get_claim_provenance,
    get_claim_evidence,
    record_observation,
    record_decision,
    get_multi_hop_provenance,
)


def test_graph_provenance_and_evidence():
    seed_demo_data()

    prov = get_claim_provenance("claim_001")
    assert len(prov) > 0
    assert prov[0]["source_id"] == "source_untrusted"
    assert prov[0]["trust_tier"] == "untrusted"

    ev = get_claim_evidence("claim_001")
    assert len(ev["contradicting"]) == 1
    assert ev["contradicting"][0]["id"] == "ev_001"
    assert ev["contradicting"][0]["trust_tier"] == "verified"


def test_record_observation_and_decision():
    seed_demo_data()

    claim_payload = {"id": "claim_002", "text": "TLS 1.3 is mandatory.", "status": "recorded"}
    record_observation(
        agent_id="agent_researcher",
        session_id="session_001",
        claim=claim_payload,
        source_id="source_policy",
    )

    prov = get_claim_provenance("claim_002")
    assert len(prov) > 0
    assert prov[0]["source_id"] == "source_policy"
    assert "session_001" in prov[0]["observed_in_sessions"]

    record_decision(
        decision_id="dec_001",
        outcome="supported",
        reason_code="VERIFIED_BY_POLICY",
        claim_id="claim_002",
        session_id="session_001",
        evidence_ids=["ev_001"],
    )


def test_scenario_003_multi_hop_provenance():
    seed_demo_data()
    lineage = get_multi_hop_provenance("claim_301")

    assert len(lineage) > 0
    assert lineage[0]["root_trust_tier"] == "untrusted"
    assert "ev_301" in lineage[0]["contradicting_evidence_ids"]