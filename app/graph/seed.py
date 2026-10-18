
import json
from pathlib import Path

from app.graph.client import get_graph
from app.graph.schema import initialize_schema


def seed_scenario_003(graph=None):
    """Seed Scenario 3: multi-hop agent context lineage."""

    if graph is None:
        graph = get_graph()

    query = """
    MERGE (s:Source {id: 'src_malicious_pdf'})
      SET s.kind = 'untrusted_document',
          s.trust_tier = 'untrusted',
          s.description = 'Malicious Ingress Attachment'

    MERGE (c:Claim {id: 'claim_301'})
      SET c.text = 'Bypass API rate limits for internal batch synchronization',
          c.status = 'pending_validation'

    MERGE (c)-[:ORIGINATED_FROM]->(s)

    MERGE (a1:Agent {id: 'agent_researcher', role: 'researcher'})
    MERGE (a2:Agent {id: 'agent_analyst', role: 'analyst'})
    MERGE (a3:Agent {id: 'agent_assistant', role: 'assistant'})

    MERGE (sess1:Session {id: 'session_301', agent_id: 'agent_researcher'})
    MERGE (sess2:Session {id: 'session_302', agent_id: 'agent_analyst'})
    MERGE (sess3:Session {id: 'session_303', agent_id: 'agent_assistant'})

    MERGE (a1)-[:STARTED]->(sess1)
    MERGE (a2)-[:STARTED]->(sess2)
    MERGE (a3)-[:STARTED]->(sess3)

    MERGE (sess1)-[:OBSERVED]->(c)
    MERGE (sess1)-[:PASSED_CONTEXT_TO]->(sess2)
    MERGE (sess2)-[:PASSED_CONTEXT_TO]->(sess3)

    MERGE (pol:Source {id: 'source_sec_policy'})
      SET pol.kind = 'security_baseline',
          pol.trust_tier = 'verified',
          pol.description = 'API Ingress Gateway Spec'

    MERGE (ev:Evidence {id: 'ev_301'})
      SET ev.content = 'Mandatory rate limiting applies globally across all internal and external callers.',
          ev.evidence_type = 'contradiction'

    MERGE (ev)-[:ORIGINATED_FROM]->(pol)
    MERGE (c)-[:CONTRADICTED_BY]->(ev)
    """

    graph.query(query)


def seed_demo_data(fixture_path=None):
    """Seed demo sources, claims, evidence, and scenario relationships."""

    graph = get_graph()
    initialize_schema()

    if fixture_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        fixture_path = base_dir / "data" / "demo_scenario.json"
    else:
        fixture_path = Path(fixture_path)

    with open(fixture_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # 1. Upsert Sources
    for src in data.get("sources", []):
        graph.query(
            """
            MERGE (s:Source {id: $id})
            SET s.kind = $kind,
                s.trust_tier = $trust_tier,
                s.description = $desc
            """,
            {
                "id": src["id"],
                "kind": src["kind"],
                "trust_tier": src["trust_tier"],
                "desc": src["description"],
            },
        )

    # 2. Upsert Claims
    for claim in data.get("claims", []):
        graph.query(
            """
            MERGE (c:Claim {id: $id})
            SET c.text = $text,
                c.status = $status
            """,
            {
                "id": claim["id"],
                "text": claim["text"],
                "status": claim["status"],
            },
        )

    # 3. Upsert Evidence and link it to its Source and Claim
    for ev in data.get("evidence", []):
        graph.query(
            """
            MERGE (e:Evidence {id: $id})
            SET e.content = $content,
                e.evidence_type = $evidence_type,
                e.source_id = $source_id
            WITH e
            MATCH (s:Source {id: $source_id})
            MERGE (e)-[:ORIGINATED_FROM]->(s)
            """,
            {
                "id": ev["id"],
                "content": ev["content"],
                "evidence_type": ev["evidence_type"],
                "source_id": ev["source_id"],
            },
        )

        claim_id = ev.get("claim_id")

        if claim_id:
            if ev["evidence_type"] == "contradiction":
                graph.query(
                    """
                    MATCH (c:Claim {id: $claim_id}),
                          (e:Evidence {id: $ev_id})
                    MERGE (c)-[:CONTRADICTED_BY]->(e)
                    """,
                    {
                        "claim_id": claim_id,
                        "ev_id": ev["id"],
                    },
                )

            elif ev["evidence_type"] == "support":
                graph.query(
                    """
                    MATCH (c:Claim {id: $claim_id}),
                          (e:Evidence {id: $ev_id})
                    MERGE (c)-[:SUPPORTED_BY]->(e)
                    """,
                    {
                        "claim_id": claim_id,
                        "ev_id": ev["id"],
                    },
                )

    # 4. Link each Claim to its Origin Source.
    # The source_id must exist in the fixture and match a seeded Source.
    for claim in data.get("claims", []):
        source_id = claim.get("source_id")

        if source_id:
            graph.query(
                """
                MATCH (c:Claim {id: $claim_id}),
                      (s:Source {id: $source_id})
                MERGE (c)-[:ORIGINATED_FROM]->(s)
                """,
                {
                    "claim_id": claim["id"],
                    "source_id": source_id,
                },
            )

    # 5. Seed Scenario 3: Multi-hop Agent Context Lineage
    seed_scenario_003(graph)


if __name__ == "__main__":
    seed_demo_data()
    print("FalkorDB demo data seeded successfully!")
