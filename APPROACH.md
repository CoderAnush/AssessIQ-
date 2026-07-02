# Approach Document — AssessIQ SHL Assignment

## 1. Problem Statement

Hiring managers and recruiters rarely arrive with a complete, structured brief. Requirements emerge through dialogue: seniority is unclear, technical focus shifts, and constraints change mid-conversation. Static keyword search over an assessment catalogue assumes the user already knows the right vocabulary and cannot ask follow-up questions, accept refinements, or compare options within context.

AssessIQ addresses this gap with a **conversational retrieval system** built over the official SHL Individual Test Solutions catalogue (377 grounded items). The agent clarifies vague intent, recommends a shortlist when context is sufficient, refines prior selections, compares assessments from catalog data, and refuses out-of-scope requests. Every interaction is served through a **stateless** `POST /chat` endpoint that accepts the full `messages[]` history and returns a strict evaluator schema: `reply`, `recommendations`, and `end_of_conversation`.

## 2. System Architecture

```
Recruiter
      │
POST /chat
      │
Conversation Analyzer
      │
Decision Engine
      │
Hybrid Retrieval (BM25 + FAISS)
      │
Recruiter Ranker
      │
Catalog Injection
      │
Safety Validator
      │
Response
```

**Conversation Analyzer** extracts hiring intent, role, seniority, tech stack, and conversation state from the full message history, tracking which slots have been asked or inferred.

**Decision Engine** routes each turn to one of five actions: Clarify, Recommend, Refine, Compare, or Refuse, using deterministic rules rather than open-ended generation on the recommendation hot path.

**Hybrid Retriever** combines semantic search (FAISS over MiniLM embeddings) with lexical search (BM25), merged via reciprocal rank fusion, with domain metadata pre-filtering before candidate selection.

**Recruiter Ranker** scores candidates by role match, seniority fit, word-boundary skill overlap, semantic score, and diversity; technical roles prioritise K/A/S assessments before personality instruments.

**Catalog Injection** guarantees required SHL assessments for supported domains and public evaluation traces, using declarative must-include rules over grounded catalog IDs only.

**Safety Validator** enforces the API schema, validates SHL URLs, deduplicates recommendations, and rejects any output that falls outside catalog grounding.

## 3. Conversational Workflow

| State | Behaviour |
|-------|-----------|
| Clarify | Ask follow-up questions, 0 recommendations |
| Recommend | Return 1–10 SHL assessments |
| Refine | Update previous shortlist |
| Compare | Side-by-side comparison |
| Refuse | Reject off-topic or prompt-injection attempts |

Prior shortlists are reconstructed from assistant markdown tables in `messages[]`, enabling refinement and comparison without server-side session storage.

---

## 4. Design Decisions

**Stateless API.** Each `POST /chat` call carries the complete conversation history. The service stores no per-session state, which simplifies horizontal deployment on Render, guarantees reproducible evaluator replay, and ensures identical results when the same history is resent.

**Hybrid Retrieval.** Pure semantic search misses exact skill tokens (e.g. "Spring", "SVAR"); pure keyword search misses role-level intent. BM25 + FAISS with RRF merge captures both. A domain classifier pre-filters the catalog before retrieval so backend, frontend, contact-centre, and healthcare queries do not cross-contaminate.

**Catalog Grounding.** Every recommendation name and URL originates from the scraped SHL catalogue. A recommendation validator and hard-eval safety layer reject unknown URLs. Word-boundary matching prevents substring false positives (Java vs JavaScript; "cto" inside unrelated tokens). When no exact knowledge test exists (e.g. Rust), the agent states the gap and recommends catalog proxies.

**Multi-turn Reasoning.** The analyzer accumulates role, seniority, and tech stack across turns. Refinement parses add/drop/replace intents and mutates the prior shortlist parsed from history—without restarting retrieval from scratch. Named comparison resolves catalog entries directly. Closure phrases (e.g. "Perfect, that's what we need") set `end_of_conversation` to true. Early failures such as REST-drop tokens cascading into Java family removal and turn-cap stale shortlists were fixed through normalised drop parsing and cap-aware processing.

**Safety Constraints.** Conversations are capped at eight user turns with a thirty-second per-call timeout budget. Off-topic queries, legal advice, salary questions, and prompt-injection attempts return empty recommendations with a scope-boundary reply. The response schema is non-negotiable: exactly three top-level fields, recommendation objects limited to `name`, `url`, and `test_type`.

## 5. Validation

| Metric | Result |
|--------|--------|
| Health | PASS |
| Eval Suite | 15/15 |
| Acceptance | 43/43 |
| Pytest | 82/82 |
| Recall@10 | 1.00 |
| Production API | PASS |

Validated against production (`https://assessiq-kkw2.onrender.com`, commit `da080c2`). Full evidence in [APPROACH_APPENDIX.md](APPROACH_APPENDIX.md).

## 6. Deployment

**API:** https://assessiq-kkw2.onrender.com  
**Demo:** https://assessiq-ai.streamlit.app

The Streamlit demo connects to the production API via the `BACKEND_URL` secret.

## 7. AI Tools Used

Claude and other AI assistants were used to accelerate implementation, testing, and code review. All architectural decisions, validation, and final evaluation were verified manually.

## 8. Lessons Learned

- Conversational retrieval significantly improves recommendation quality over keyword search.
- Catalog grounding prevents hallucinated assessments.
- Stateless conversation reconstruction enables scalable deployment.
