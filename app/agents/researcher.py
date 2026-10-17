"""
Researcher Agent — Session A

Responsibilities:
- Read a synthetic task (scenario).
- Call deterministic mock tools to gather information.
- Record claims and their source provenance into FalkorDB.
- Never mark a claim as verified purely because a tool returned it.
"""
import uuid
import time
from typing import Dict, Any

from app.tools.mock_tools import (
    lookup_claim,
    get_source_metadata,
    get_conflicting_evidence,
    get_supporting_evidence,
)
from app.graph.queries import record_observation
from app.graph.seed import seed_demo_data


class ResearcherAgent:
    """Agent A: investigates a claim and persists its provenance."""

    AGENT_ID = "agent_researcher"

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"sess_researcher_{uuid.uuid4().hex[:8]}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def research_claim(self, claim_id: str) -> Dict[str, Any]:
        """
        Look up a claim, gather evidence, and record it in FalkorDB.

        Returns a structured observation dict that the custody service
        can hand to the Assistant in the next session.
        """
        # Step 1: retrieve the raw claim from the mock tool
        claim_data = lookup_claim(claim_id)
        if "error" in claim_data:
            return {"error": claim_data["error"], "claim_id": claim_id}

        source_id = claim_data["source_id"]

        # Step 2: fetch source metadata (trust tier, kind, description)
        source_meta = get_source_metadata(source_id)

        # Step 3: gather supporting and conflicting evidence from fixtures
        supporting = get_supporting_evidence(claim_id)
        conflicting = get_conflicting_evidence(claim_id)

        # Step 4: persist the observation to FalkorDB
        #         record_observation creates Agent, Session, Claim, Source nodes
        #         and the STARTED / OBSERVED / ORIGINATED_FROM edges.
        record_observation(
            agent_id=self.AGENT_ID,
            session_id=self.session_id,
            claim={
                "id": claim_data["id"],
                "text": claim_data["text"],
                "status": claim_data["status"],
            },
            source_id=source_id,
        )

        return {
            "claim_id": claim_id,
            "text": claim_data["text"],
            "source_id": source_id,
            "source_trust_tier": source_meta.get("trust_tier"),
            "session_id": self.session_id,
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
            # The Researcher does NOT mark the claim as verified here.
            "recorded": True,
            "timestamp": time.time(),
        }

    def run_scenario(self, scenario_claim_ids: list) -> list:
        """
        Run through a list of claim IDs, recording each one.
        Used by the service layer to drive the full demo.
        """
        results = []
        for cid in scenario_claim_ids:
            obs = self.research_claim(cid)
            results.append(obs)
        return results
