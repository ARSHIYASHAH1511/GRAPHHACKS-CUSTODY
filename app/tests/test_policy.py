from app.policy.evaluate import evaluate_claim


def test_untrusted_claim_without_support():
    result = evaluate_claim(
        {"id": "c1"},
        {"source_id": "s1", "trust_tier": "untrusted"},
        [],
    )
    assert result["status"] == "untrusted"


def test_verified_contradiction():
    result = evaluate_claim(
        {"id": "c2"},
        {"source_id": "s2", "trust_tier": "trusted"},
        [
            {
                "id": "e1",
                "type": "contradict",
                "verified": True,
            }
        ],
    )
    assert result["status"] == "conflicting"
    assert "e1" in result["evidence_ids"]


def test_missing_evidence():
    result = evaluate_claim(
        {"id": "c3"},
        {"source_id": "s3", "trust_tier": "trusted"},
        [],
    )
    assert result["status"] == "unknown"


def test_verified_support():
    result = evaluate_claim(
        {"id": "c4"},
        {"source_id": "s4", "trust_tier": "trusted"},
        [
            {
                "id": "e2",
                "type": "support",
                "verified": True,
            }
        ],
    )
    assert result["status"] == "supported"
    assert "e2" in result["evidence_ids"]
