# Custody — Demo Script (2.5 min)

## Setup (before recording)
1. `docker compose up -d` — FalkorDB running
2. `uvicorn app.main:app --reload --port 8000`
3. Open `http://localhost:8000` in browser
4. Open `http://localhost:3000` (FalkorDB Browser) side by side

---

## 0:00 – 0:25 | The Problem

*Say:*
> "AI agents read from many sources — web pages, emails, tool outputs. If an untrusted source injects a misleading claim, it can end up in the agent's persistent memory. A later agent in a completely different session reads that memory and treats it as fact. In-session filters can't catch this because the taint came from a prior session."

Show the scenario on screen:
- `claim_001`: "Port 8080 is approved for external production ingress."
- Source: `source_untrusted` — an unverified public forum post.

---

## 0:25 – 0:55 | Off Mode (attack succeeds)

1. Select **Mode: off**, Scenario: **scenario_001**
2. Click Reset, then Run
3. Result: `decision = allowed_no_guard`

*Say:*
> "With no guard, the claim passes through unconditionally. The agent would use this to open port 8080. Our approved policy explicitly forbids this."

---

## 0:55 – 1:25 | Naive Mode (attack still succeeds)

1. Select **Mode: naive**, Scenario: **scenario_001**
2. Click Run
3. Result: `decision = allowed_naive`, provenance: empty

*Say:*
> "Naive mode simulates systems that store memory but never check where it came from. The claim was recalled and reused. No graph traversal happened. The attack still succeeds."

---

## 1:25 – 2:00 | Custody Mode (attack blocked)

1. Select **Mode: custody**, Scenario: **scenario_001**
2. Click Run
3. Result: `decision = conflicting`, evidence: `ev_001`

*Say:*
> "Custody runs a graph query in FalkorDB. It traverses: Claim → ORIGINATED_FROM → source_untrusted, then checks for evidence. It finds ev_001: a verified contradiction from our approved policy. Decision: conflicting. The agent cannot use this claim."

Point to the Provenance Path panel:
- `Session → Claim: claim_001 → ORIGINATED_FROM → Source: source_untrusted [untrusted]`

*Say:*
> "This path is why FalkorDB is essential. Remove the graph, and Custody can't make this decision. The data is persisted across sessions in FalkorDB — not in Python memory."

---

## 2:00 – 2:20 | Positive Case

1. Select **Mode: custody**, Scenario: **scenario_002**
2. Click Run
3. Result: `decision = supported`, evidence: `ev_002`

*Say:*
> "claim_002 — TLS 1.3 is mandatory — originates from our verified policy source and has supporting evidence. Custody marks it supported. Same guard, different graph relationships, different decision."

---

## 2:20 – 2:30 | Close

*Say:*
> "Custody is a graph-backed provenance layer. FalkorDB stores claims, sources, and evidence across sessions. Deterministic Cypher queries — not the LLM — decide what the agent can trust. Thank you."

---

## Fallback plan
If the live demo fails, show the API directly:
```bash
curl -X POST http://localhost:8000/demo/run \
  -H "Content-Type: application/json" \
  -d '{"mode": "custody", "scenario_id": "scenario_001"}'
```
