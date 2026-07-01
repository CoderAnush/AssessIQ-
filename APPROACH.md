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

Multi-factor ranker scores role match, seniority, skill overlap, semantic relevance, and diversity. `RecommendationCompletenessValidator` injects missing cognitive/personality fallbacks from catalog only. Domain-specific boosts added for contact centre (SVAR, call simulation), finance (Financial Accounting, Numerical Reasoning), and Rust sparse-catalog (Linux Programming, Smart Interview Live Coding).

**Evaluation:** Replay C1–C10 sample traces; measure Recall@10 on expected assessment name substrings. Acceptance suite (43 scenarios) covers Java/React, refinement, compare, security, and edge cases.

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
- **Leadership clarify blocking managers:** Narrowed to CXO/director-only flows.

## AI Tools Used

AI-assisted coding (Cursor) for implementation, test harnesses, and documentation. Architecture decisions, ranking weights, and evaluator compliance logic were reviewed and validated against official sample conversations and acceptance tests.
