import json
from app.graph.client import get_graph
from app.graph.schema import initialize_schema

def seed_demo_data(fixture_path: str = "data/demo_scenario.json"):
    graph = get_graph()
    initialize_schema()
    
    with open(fixture_path, "r") as f:
        data = json.load(f)

    # 1. Upsert Sources
    for src in data.get("sources", []):
        graph.query("""
        MERGE (s:Source {id: $id})
        SET s.kind = $kind, s.trust_tier = $trust_tier, s.description = $desc
        """, {"id": src["id"], "kind": src["kind"], "trust_tier": src["trust_tier"], "desc": src["description"]})

    # 2. Upsert Claims
    for claim in data.get("claims", []):
        graph.query("""
        MERGE (c:Claim {id: $id})
        SET c.text = $text, c.status = $status
        """, {"id": claim["id"], "text": claim["text"], "status": claim["status"]})

    # 3. Upsert Evidence & Link to Sources and Claims
    for ev in data.get("evidence", []):
        graph.query("""
        MERGE (e:Evidence {id: $id})
        SET e.content = $content, e.evidence_type = $evidence_type, e.source_id = $source_id
        WITH e
        MATCH (s:Source {id: $source_id})
        MERGE (e)-[:ORIGINATED_FROM]->(s)
        """, {"id": ev["id"], "content": ev["content"], "evidence_type": ev["evidence_type"], "source_id": ev["source_id"]})

        claim_id = ev.get("claim_id")
        if claim_id:
            if ev["evidence_type"] == "contradiction":
                graph.query("""
                MATCH (c:Claim {id: $claim_id}), (e:Evidence {id: $ev_id})
                MERGE (c)-[:CONTRADICTED_BY]->(e)
                """, {"claim_id": claim_id, "ev_id": ev["id"]})
            elif ev["evidence_type"] == "support":
                graph.query("""
                MATCH (c:Claim {id: $claim_id}), (e:Evidence {id: $ev_id})
                MERGE (c)-[:SUPPORTED_BY]->(e)
                """, {"claim_id": claim_id, "ev_id": ev["id"]})

    # 4. Link each Claim to its Origin Source
    for claim in data.get("claims", []):
        source_id = claim.get("source_id")
        if source_id:
            graph.query("""
            MATCH (c:Claim {id: $claim_id}), (s:Source {id: $source_id})
            MERGE (c)-[:ORIGINATED_FROM]->(s)
            """, {"claim_id": claim["id"], "source_id": source_id})

if __name__ == "__main__":
    seed_demo_data()
    print("FalkorDB demo data seeded successfully!")