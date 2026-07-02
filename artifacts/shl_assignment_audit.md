# SHL Assignment Compliance Audit

**API:** `https://assessiq-kkw2.onrender.com`  
**UI:** `https://assessiq-ai.streamlit.app`  
**Date:** 2026-07-02

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `GET /health` → `{"status":"ok"}` | PASS | kkw2 health endpoint |
| `POST /chat` stateless, strict schema | PASS | `tests/test_conversation_regression.py` schema tests |
| Clarify vague queries | PASS | Scenario 14 + eval case 1 |
| 1–10 recommendations, SHL URLs only | PASS | Browser validation 25/25 (local, post-fix) |
| Refine / compare / refuse | PASS | Scenarios 15–18 |
| Turn cap ≤ 8 | PASS | Eval suite turn-cap case |
| Recall@10 C1–C10 | PASS (local) | Re-run on kkw2 after deploy recommended |
| Approach doc ≤ 2 pages | PASS | `APPROACH.md` |
| Public API reachable | PASS | assessiq-kkw2 |
| Recommendation quality (role-relevant top 3) | PASS (post-fix) | Scenarios 21–25 strict top-3 checks |

## Quality fixes in this release

- Fixed `cto` substring false match inside **vector** (domain + catalog injection)
- Latest-turn domain override prevents session pollution
- Java/Spring suppressed when not requested
- Leadership OPQ blocked for AI/QA/Sales technical roles
- Hybrid FAISS + sentence-transformers enabled in Docker requirements
