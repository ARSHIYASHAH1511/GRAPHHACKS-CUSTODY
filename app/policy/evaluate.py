
def evaluate_claim(claim, provenance, evidence):
    """
    Classify a claim using its source information
    and the evidence retrieved for it.
    """

    claim_id = claim.get("id", "unknown")
    source_id = provenance.get("source_id")

    supporting = [
        item for item in evidence
        if item.get("type") == "support"
        and item.get("verified") is True
    ]

    contradicting = [
        item for item in evidence
        if item.get("type") == "contradict"
        and item.get("verified") is True
    ]

    if contradicting:
        status = "conflicting"
        reason_code = "VERIFIED_CONTRADICTION"
        explanation = (
            "Verified evidence contradicts this claim."
        )

    elif not supporting:
        if provenance.get("trust_tier") == "untrusted":
            status = "untrusted"
            reason_code = "UNTRUSTED_SOURCE_NO_SUPPORT"
            explanation = (
                "The source is untrusted and no verified "
                "supporting evidence was found."
            )
        else:
            status = "unknown"
            reason_code = "INSUFFICIENT_EVIDENCE"
            explanation = (
                "There is not enough verified evidence "
                "to establish this claim."
            )

    else:
        status = "supported"
        reason_code = "VERIFIED_SUPPORT"
        explanation = (
            "Verified supporting evidence was found, "
            "with no verified contradiction in the "
            "evidence retrieved."
        )

    evidence_ids = [
        item["id"]
        for item in supporting + contradicting
        if item.get("id")
    ]

    return {
        "claim_id": claim_id,
        "source_id": source_id,
        "status": status,
        "reason_code": reason_code,
        "evidence_ids": evidence_ids,
        "explanation": explanation,
    }
