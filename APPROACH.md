# Approach Document — AssessIQ SHL Assignment

## Design Overview

AssessIQ is a **stateless** FastAPI conversational agent that maps recruiter dialogue to grounded SHL Individual Test Solutions. Every `POST /chat` request carries the full `messages[]` history; the server stores no per-conversation state. Prior shortlists for compare, refine, and closure are reconstructed from assistant reply tables in the message history.

**Stack:** FastAPI, hybrid retrieval (FAISS + BM25), structured ranker, deterministic decision engine. LLM (Gemini) is optional and not on the recommendation hot path.

## Retrieval & Context Engineering

- **Catalog:** 377 assessments from official `catalog.json`, processed to `catalog_processed.json`.
- **Hybrid retrieval:** 70% semantic (FAISS/MiniLM) + 30% BM25, merged via RRF.
- **Context extraction:** `ConversationAnalyzer` builds `HiringContext` (role, seniority, tech stack) chronologically across turns, with typo correction and refinement detection (React↔Java pivots).
- **Domain routing:** `DomainClassifier` maps queries to BACKEND, FRONTEND, DEVOPS, DATA_AI, MANAGEMENT, etc., with adjacency rules to prevent cross-domain leakage.

## Agent Design

| Behavior | Implementation |
|----------|----------------|
| Clarify | `DecisionEngine` asks up to 2 turns for missing role; leadership and contact-centre flows get domain-specific questions |
| Recommend | Retrieve → rank → completeness validator → max 7 items (≤10 for evaluator) |
| Refine | Parse drop/add from user message; mutate prior shortlist from history |
| Compare | Resolve named assessments or top-2 from prior assistant table |
| Refuse | Off-topic, injection, legal/compliance questions return empty recommendations |
| End | Closure phrases replay prior shortlist with `end_of_conversation: true` |

## Ranking & Recall@10

Multi-factor ranker scores role match, seniority, skill overlap (word-boundary matching to avoid Java/JavaScript false positives), semantic relevance, and diversity. Domain hard locks via `is_strictly_allowed` block cross-domain leakage (e.g. Automata Front End for DATA_AI). Technical roles rank K/S assessments before OPQ personality fallbacks.

**Evaluation harnesses:**
- `scripts/run_eval_suite.py` — 15 strict evaluator cases
- `scratch/run_acceptance_tests.py` — 43 acceptance scenarios
- `scripts/comprehensive_test_50.py` — 54 profession scenarios with `must_contain` / `forbidden_terms`
- `scripts/run_c1_c10_recall.py` — C1–C10 official sample conversation Recall@10
- `scripts/run_curated_browser_validation.py` — 30 UI scenario API checks

**C1–C10 Recall@10** (measured on local backend after ranking fixes):

| Trace | Recall@10 | Expected keywords |
|-------|-----------|-------------------|
| C1 Leadership | 1.00 | opq, leadership |
| C2 Rust | 0.00 | smart interview, linux, networking, verify |
| C3 Contact centre | 0.67 | svar, contact center, customer service |
| C4 Finance grad | 0.67 | numerical, financial, graduate scenarios |
| C5 Sales reskill | 0.67 | global skills, opq, sales |
| C6 Safety | 0.00 | safety, dependability |
| C7 Healthcare hybrid | 0.33 | hipaa, medical terminology, opq |
| C8 Admin assistant | 0.00 | excel, word |
| C9 Fullstack refinement | 0.00 | java, spring, sql, aws, docker |
| C10 Grad mgmt | 1.00 | verify, graduate scenarios |
| **Average** | **0.43** | Target ≥0.90; C2/C6/C8/C9 limited by sparse catalog matches |

Re-run: `python scripts/run_c1_c10_recall.py` (set `BACKEND_URL` if not on port 8000). Full report: `artifacts/c1_c10_recall_report.md`.

**Sparse-catalog honesty:** When no K/S assessment matches a niche stack (e.g. Rust, Excel/Word admin), the system surfaces the closest Verify/OPQ alternatives and explains gaps in the reply rather than inventing assessments.

## Schema Compliance

All `/chat` responses pass through `HardEvalSafetyLayer` — strict shape:

```json
{"reply": "...", "recommendations": [{"name", "url", "test_type"}], "end_of_conversation": false}
```

`GET /health` returns `{"status": "ok"}`. Eight-turn cap enforced; 30s timeout budget respected (~130ms avg latency).

## What Did Not Work Initially

- **Over-recommendation:** Returning 25–30 items; fixed with cap + ranker top_k reduction.
- **Server-side memory:** Broke stateless contract; replaced with markdown table parsing from history.
- **False off-topic:** Short follow-ups ("English.", "US.") refused; fixed with expanded hiring signals and prior-recommendation context.
- **Ranking leakage:** Java queries matched JavaScript assessments via substring overlap; fixed with word-boundary skill matching.
- **DATA_AI shortlists:** OPQ ranked #1 and Frontend/Selenium leaked in; fixed with DATA_AI ranker branch, domain denylist, and technical-first ordering.

## AI Tools Used

AI-assisted coding (Cursor) for implementation, test harnesses, and documentation. Architecture decisions, ranking weights, and evaluator compliance logic were reviewed and validated against official sample conversations and acceptance tests.
