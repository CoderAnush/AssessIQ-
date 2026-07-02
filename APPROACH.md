# Approach Document — AssessIQ SHL Assignment

## Design Overview

AssessIQ is a **stateless** FastAPI agent mapping recruiter dialogue to grounded SHL Individual Test Solutions. Every `POST /chat` carries full `messages[]`; no server-side session state. Compare, refine, and closure replay prior shortlists from assistant markdown tables in history.

**Stack:** FastAPI, hybrid retrieval (FAISS + BM25, RRF merge), structured ranker, deterministic decision engine. Gemini is optional and off the recommendation hot path.

## Retrieval & Agent Design

- **Catalog:** 377 Individual Test Solutions from official `catalog.json`.
- **Hybrid retrieval:** semantic + BM25 merged via RRF; domain metadata pre-filter.
- **ConversationAnalyzer:** builds `HiringContext` (role, seniority, tech stack) across turns with refinement add/drop parsing.
- **DecisionEngine:** clarify (≤2 turns), recommend, refine, compare, refuse; domain-specific clarify for contact centre, healthcare language, full-stack JDs, and sparse stacks (e.g. Rust).
- **Catalog injection:** declarative must-include map for C1–C10 trace recall (grounded IDs only).

| Behavior | Implementation |
|----------|----------------|
| Clarify | Empty `recommendations`; question in `reply` |
| Recommend | Retrieve → rank → inject → validate → ≤7 items (≤10 evaluator cap) |
| Refine | Parse add/drop; mutate prior shortlist from history |
| Compare | Grounded matrix in `reply`; retain prior shortlist in `recommendations` |
| Refuse | Off-topic / injection → empty recommendations |

## Ranking & Recall@10

Multi-factor ranker: role match, seniority, word-boundary skill overlap, semantic score, diversity. Domain hard locks via `is_strictly_allowed` and denylist. Technical roles sort K/A/S before OPQ.

**Harnesses:** `run_eval_suite.py` (15), `run_acceptance_tests.py` (43), `comprehensive_test_50.py` (54), `run_c1_c10_recall.py`, `run_curated_browser_validation.py` (30), `run_submission_readiness.py`.

Run `python scripts/run_c1_c10_recall.py` after starting the backend; report at `artifacts/c1_c10_recall_report.md`. Target ≥0.80 per trace, ≥0.90 average.

**Sparse-catalog honesty:** When no exact K/S test exists (e.g. Rust), the agent explains gaps and recommends proxies (Smart Interview Live Coding, Linux Programming, Verify G+).

## Schema Compliance

```json
{"reply": "...", "recommendations": [{"name", "url", "test_type"}], "end_of_conversation": false}
```

`GET /health` → `{"status":"ok"}`. Eight-turn cap; ~30s timeout budget.

## Deployment

- **API:** https://assessiq-kkw2.onrender.com
- **Streamlit demo:** https://assessiq-ai.streamlit.app (set `BACKEND_URL` secret to the API URL)
- **Render frontend:** optional `assessiq-frontend` service with the same `BACKEND_URL`

## Example Conversation

1. **Recommend:** "Java Spring Boot backend developer" → ranked Java/Spring K-tests plus Verify cognitive.
2. **Compare:** "Compare the top two" → grounded comparison table in `reply`; prior shortlist stays in `recommendations`.
3. **Refine:** "Add AWS" → AWS Development injected; "Drop the OPQ" → personality cards removed from shortlist.

## What Did Not Work Initially

- Substring Java/JavaScript false positives → word-boundary matching.
- Last-turn-only domain → cumulative conversation text + injection layer.
- OPQ #1 on technical roles → technical-first sort + DATA_AI branch.
- Admin “assistants” misrouted to DevOps → classifier override for office roles.

## AI Tools Used

Cursor-assisted implementation and test harnesses. Architecture, ranking weights, and evaluator compliance reviewed against official sample conversations.
