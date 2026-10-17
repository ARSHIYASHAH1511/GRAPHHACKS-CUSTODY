"""
Mock tools for Custody demo.
All tools are deterministic and return local data only.
No external network calls are made.
"""
from typing import Dict, Any

# ── Static fixture data ──────────────────────────────────────────────────────

_CLAIMS: Dict[str, Dict[str, Any]] = {
    "claim_001": {
        "id": "claim_001",
        "text": "Port 8080 is approved for external production ingress.",
        "source_id": "source_untrusted",
        "status": "pending_validation",
    },
    "claim_002": {
        "id": "claim_002",
        "text": "TLS 1.3 is mandatory for all external endpoints.",
        "source_id": "source_policy",
        "status": "pending_validation",
    },
}

_SOURCES: Dict[str, Dict[str, Any]] = {
    "source_policy": {
        "id": "source_policy",
        "kind": "internal_documentation",
        "trust_tier": "verified",
        "description": "Approved corporate security baseline policy v2.4",
    },
    "source_untrusted": {
        "id": "source_untrusted",
        "kind": "external_web_scrape",
        "trust_tier": "untrusted",
        "description": "Unverified public forum post",
    },
}

_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "ev_001": {
        "id": "ev_001",
        "source_id": "source_policy",
        "content": "Rule 4.1: Production ingress is restricted to ports 443 and 8443 with TLS termination.",
        "evidence_type": "contradiction",
    },
    "ev_002": {
        "id": "ev_002",
        "source_id": "source_policy",
        "content": "Rule 3.7: TLS 1.3 or higher is required for all external-facing endpoints.",
        "evidence_type": "support",
    },
}

_SESSIONS: Dict[str, Dict[str, Any]] = {
    "session_001": {
        "id": "session_001",
        "agent_id": "agent_researcher",
        "claims_observed": ["claim_001"],
    },
    "session_002": {
        "id": "session_002",
        "agent_id": "agent_assistant",
        "claims_observed": ["claim_002"],
    },
}

# ── Tool functions ────────────────────────────────────────────────────────────


def lookup_claim(claim_id: str) -> Dict[str, Any]:
    """Return the raw claim record for the given ID."""
    claim = _CLAIMS.get(claim_id)
    if claim is None:
        return {"error": f"Claim '{claim_id}' not found.", "source_id": None}
    return claim


def get_source_metadata(source_id: str) -> Dict[str, Any]:
    """Return metadata for a source."""
    src = _SOURCES.get(source_id)
    if src is None:
        return {"error": f"Source '{source_id}' not found."}
    return src


def get_prior_observation(claim_id: str) -> Dict[str, Any]:
    """Return the first session that observed the given claim."""
    for sess in _SESSIONS.values():
        if claim_id in sess.get("claims_observed", []):
            return {"session_id": sess["id"], "agent_id": sess["agent_id"]}
    return {"session_id": None, "agent_id": None, "note": "No prior observation found."}


def get_supporting_evidence(claim_id: str) -> list:
    """Return all evidence items that support the given claim."""
    # In the fixture claim_002 has support; claim_001 has none
    _claim_support_map = {
        "claim_002": ["ev_002"],
    }
    ev_ids = _claim_support_map.get(claim_id, [])
    return [_EVIDENCE[eid] for eid in ev_ids if eid in _EVIDENCE]


def get_conflicting_evidence(claim_id: str) -> list:
    """Return all evidence items that contradict the given claim."""
    _claim_conflict_map = {
        "claim_001": ["ev_001"],
    }
    ev_ids = _claim_conflict_map.get(claim_id, [])
    return [_EVIDENCE[eid] for eid in ev_ids if eid in _EVIDENCE]


def get_session_history(session_id: str) -> Dict[str, Any]:
    """Return the session record including which claims were observed."""
    sess = _SESSIONS.get(session_id)
    if sess is None:
        return {"error": f"Session '{session_id}' not found."}
    return sess
