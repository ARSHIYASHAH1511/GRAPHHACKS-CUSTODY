# Custody: Graph Context Architecture

## System Overview
Custody uses FalkorDB to implement memory security and provenance tracking for AI agents. Rather than treating conversational memory as an unverified flat log, Custody stores claims, sources, evidence, and decisions as an interconnected graph.

## Graph Schema Topology

### Node Types
- **Claim**: Declarative statements extracted from tool runs or agent conversations (`id`, `text`, `status`, `created_at`).
- **Source**: Origin entities providing information (`id`, `kind`, `trust_tier`, `description`).
- **Evidence**: Verified baseline rules or conflicting documentation (`id`, `content`, `evidence_type`).
- **Session**: Logical agent interaction contexts (`id`, `agent_id`, `created_at`).
- **Agent**: Logical agent identifiers (`id`, `role`).
- **Decision**: Persisted trust verdicts evaluated by the policy engine (`id`, `outcome`, `reason_code`, `created_at`).

### Core Traversals & Cypher Queries
1. **Provenance Verification**:
   ```cypher
   MATCH (c:Claim {id: $claim_id})-[:ORIGINATED_FROM]->(s:Source)
   OPTIONAL MATCH (sess:Session)-[:OBSERVED]->(c)
   RETURN c.id, c.text, s.id, s.trust_tier, collect(sess.id)