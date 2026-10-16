from typing import Dict, Any, List
from app.graph.client import get_graph

def _get_column_names(header) -> List[str]:
    """Safely extracts column name strings from FalkorDB response headers."""
    names = []
    for col in header:
        if isinstance(col, (list, tuple)) and len(col) > 1:
            name = col[1]
        else:
            name = col
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        names.append(str(name))
    return names

def record_observation(agent_id: str, session_id: str, claim: Dict[str, Any], source_id: str):
    graph = get_graph()
    query = """
    MERGE (a:Agent {id: $agent_id})
    MERGE (sess:Session {id: $session_id, agent_id: $agent_id})
    MERGE (a)-[:STARTED]->(sess)
    MERGE (s:Source {id: $source_id})
    MERGE (c:Claim {id: $claim_id})
      ON CREATE SET c.text = $claim_text, c.status = $claim_status, c.created_at = timestamp()
    MERGE (sess)-[:OBSERVED]->(c)
    MERGE (c)-[:ORIGINATED_FROM]->(s)
    RETURN c.id AS claim_id
    """
    params = {
        "agent_id": agent_id,
        "session_id": session_id,
        "source_id": source_id,
        "claim_id": claim["id"],
        "claim_text": claim["text"],
        "claim_status": claim.get("status", "pending")
    }
    return graph.query(query, params).result_set

def get_claim_provenance(claim_id: str) -> List[Dict[str, Any]]:
    graph = get_graph()
    query = """
    MATCH (c:Claim {id: $claim_id})-[:ORIGINATED_FROM]->(s:Source)
    OPTIONAL MATCH (sess:Session)-[:OBSERVED]->(c)
    RETURN c.id AS claim_id, c.text AS text, s.id AS source_id, 
           s.trust_tier AS trust_tier, s.kind AS source_kind,
           collect(sess.id) AS observed_in_sessions
    """
    res = graph.query(query, {"claim_id": claim_id})
    if not res.result_set:
        return []
    
    col_names = _get_column_names(res.header)
    return [dict(zip(col_names, row)) for row in res.result_set]

def get_claim_evidence(claim_id: str) -> Dict[str, List[Dict[str, Any]]]:
    graph = get_graph()
    query = """
    MATCH (c:Claim {id: $claim_id})
    OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(sup:Evidence)-[:ORIGINATED_FROM]->(sup_src:Source)
    OPTIONAL MATCH (c)-[:CONTRADICTED_BY]->(con:Evidence)-[:ORIGINATED_FROM]->(con_src:Source)
    RETURN 
        collect(DISTINCT {id: sup.id, content: sup.content, source_id: sup_src.id, trust_tier: sup_src.trust_tier}) AS supporting,
        collect(DISTINCT {id: con.id, content: con.content, source_id: con_src.id, trust_tier: con_src.trust_tier}) AS contradicting
    """
    res = graph.query(query, {"claim_id": claim_id})
    if res.result_set:
        row = res.result_set[0]
        # In FalkorDB maps/dictionaries or collect results, filter empty entries
        raw_supporting = row[0] if isinstance(row[0], list) else []
        raw_contradicting = row[1] if isinstance(row[1], list) else []
        
        supporting = [item for item in raw_supporting if isinstance(item, dict) and item.get("id")]
        contradicting = [item for item in raw_contradicting if isinstance(item, dict) and item.get("id")]
        return {"supporting": supporting, "contradicting": contradicting}
    return {"supporting": [], "contradicting": []}
def record_decision(decision_id: str, outcome: str, reason_code: str, claim_id: str, session_id: str, evidence_ids: List[str] = None):
    """Records a Decision node and links it to Claim, Session, and any supporting/contradicting Evidence used."""
    graph = get_graph()
    query = """
    MATCH (c:Claim {id: $claim_id})
    MATCH (sess:Session {id: $session_id})
    MERGE (d:Decision {id: $decision_id})
      ON CREATE SET d.outcome = $outcome, d.reason_code = $reason_code, d.created_at = timestamp()
    MERGE (d)-[:EVALUATED]->(c)
    MERGE (d)-[:MADE_IN]->(sess)
    WITH d
    UNWIND (CASE WHEN $evidence_ids IS NULL OR size($evidence_ids) = 0 THEN [null] ELSE $evidence_ids END) AS ev_id
    OPTIONAL MATCH (e:Evidence {id: ev_id})
    FOREACH (_ IN CASE WHEN e IS NOT NULL THEN [1] ELSE [] END |
      MERGE (d)-[:USED_EVIDENCE]->(e)
    )
    RETURN d.id AS decision_id
    """
    params = {
        "decision_id": decision_id,
        "outcome": outcome,
        "reason_code": reason_code,
        "claim_id": claim_id,
        "session_id": session_id,
        "evidence_ids": evidence_ids or []
    }
    return graph.query(query, params).result_set