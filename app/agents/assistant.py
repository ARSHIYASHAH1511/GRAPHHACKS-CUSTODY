"""
Assistant Agent — Session B

Responsibilities:
- Receive a follow-up question in a new session (separate from the Researcher's).
- Retrieve provenance and evidence from FalkorDB via graph queries.
- Pass graph-derived data to the policy engine.
- Return only supported conclusions, or explicitly flag insufficient evidence.
- Record the final decision in FalkorDB.
- NEVER invent or assume facts not backed by graph data.
"""
import uuid
import time
from typing import Dict, Any

from app.graph.queries import (
    get_claim_provenance,
    get_claim_evidence,
    record_observation,
    record_decision,
)
from app.policy.evaluate import evaluate_claim


class AssistantAgent:
    """Agent B: evaluates a claim using graph provenance and policy engine."""

    AGENT_ID = "agent_assistant"

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"sess_assistant_{uuid.uuid4().hex[:8]}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, claim_id: str, mode: str = "custody") -> Dict[str, Any]:
        """
        Evaluate whether claim_id should be trusted.

        mode:
          - "off"     → skip all checks, pass through unconditionally
          - "naive"   → reuse memory without graph-based provenance check
          - "custody" → full graph-derived provenance + policy evaluation

        Returns a structured result including decision, evidence, and provenance.
        """
        if mode == "off":
            return self._off_mode(claim_id)

        if mode == "naive":
            return self._naive_mode(claim_id)

        # Default: full custody mode
        return self._custody_mode(claim_id)

    # ------------------------------------------------------------------
    # Private mode implementations
    # ------------------------------------------------------------------

    def _off_mode(self, claim_id: str) -> Dict[str, Any]:
        """
        Guard OFF — no provenance check, claim is passed through as-is.
        Represents a system with no memory security layer.
        """
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        record_decision(
            decision_id=decision_id,
            outcome="allowed_no_guard",
            reason_code="GUARD_DISABLED",
            claim_id=claim_id,
            session_id=self.session_id,
            evidence_ids=[],
        )
        return {
            "mode": "off",
            "claim_id": claim_id,
            "decision": "allowed_no_guard",
            "reason_code": "GUARD_DISABLED",
            "evidence": [],
            "provenance": [],
            "explanation": "Guard is disabled. Claim passed through without any provenance check.",
            "session_id": self.session_id,
            "decision_id": decision_id,
        }

    def _naive_mode(self, claim_id: str) -> Dict[str, Any]:
        """
        Naive mode — memory is reused but no graph traversal checks provenance.
        Simulates a system that stores prior observations but never verifies origin.
        """
        # Ensure a placeholder source exists for naive mode tracking
        from app.graph.client import get_graph
        g = get_graph()
        g.query(
            "MERGE (s:Source {id: 'source_unknown_naive'}) "
            "SET s.kind = 'unknown', s.trust_tier = 'unknown', s.description = 'Naive mode placeholder'"
        )
        # Record a new session observation (memory reuse without verification)
        record_observation(
            agent_id=self.AGENT_ID,
            session_id=self.session_id,
            claim={"id": claim_id, "text": "(recalled from memory)", "status": "recalled"},
            source_id="source_unknown_naive",
        )
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        record_decision(
            decision_id=decision_id,
            outcome="allowed_naive",
            reason_code="NAIVE_NO_PROVENANCE_CHECK",
            claim_id=claim_id,
            session_id=self.session_id,
            evidence_ids=[],
        )
        return {
            "mode": "naive",
            "claim_id": claim_id,
            "decision": "allowed_naive",
            "reason_code": "NAIVE_NO_PROVENANCE_CHECK",
            "evidence": [],
            "provenance": [],
            "explanation": (
                "Claim was recalled from memory and reused without any "
                "graph-based provenance check. Origin and trust not verified."
            ),
            "session_id": self.session_id,
            "decision_id": decision_id,
        }

    def _custody_mode(self, claim_id: str) -> Dict[str, Any]:
        """
        Custody mode — full graph-derived provenance + deterministic policy.
        This is the core of the Custody system.
        """
        # Step 1: retrieve provenance from FalkorDB (graph query)
        provenance_rows = get_claim_provenance(claim_id)

        if not provenance_rows:
            # Claim has no provenance in the graph → unknown
            policy_result = {
                "claim_id": claim_id,
                "source_id": None,
                "status": "unknown",
                "reason_code": "NO_PROVENANCE_IN_GRAPH",
                "evidence_ids": [],
                "explanation": "No provenance record found in FalkorDB for this claim.",
            }
        else:
            provenance = provenance_rows[0]  # first matching row

            # Step 2: retrieve supporting + contradicting evidence (graph traversal)
            evidence_data = get_claim_evidence(claim_id)

            # Step 3: normalise evidence format for the policy engine
            supporting_for_policy = [
                {
                    "id": e["id"],
                    "type": "support",
                    "verified": (e.get("trust_tier") == "verified"),
                }
                for e in evidence_data.get("supporting", [])
            ]
            contradicting_for_policy = [
                {
                    "id": e["id"],
                    "type": "contradict",
                    "verified": (e.get("trust_tier") == "verified"),
                }
                for e in evidence_data.get("contradicting", [])
            ]
            all_evidence = supporting_for_policy + contradicting_for_policy

            # Step 4: run deterministic policy (no LLM involved)
            policy_result = evaluate_claim(
                claim={"id": claim_id},
                provenance=provenance,
                evidence=all_evidence,
            )

        # Step 5: persist the decision in FalkorDB
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        record_decision(
            decision_id=decision_id,
            outcome=policy_result["status"],
            reason_code=policy_result["reason_code"],
            claim_id=claim_id,
            session_id=self.session_id,
            evidence_ids=policy_result.get("evidence_ids", []),
        )

        return {
            "mode": "custody",
            "claim_id": claim_id,
            "decision": policy_result["status"],
            "reason_code": policy_result["reason_code"],
            "evidence": policy_result.get("evidence_ids", []),
            "provenance": provenance_rows,
            "explanation": policy_result.get("explanation", ""),
            "session_id": self.session_id,
            "decision_id": decision_id,
        }
