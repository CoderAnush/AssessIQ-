# SHL Assignment Requirements Checklist

Extracted from `SHL_AI_Intern_Assignment-1.pdf` (5 pages).

## Functional requirements

- [x] Conversational agent: vague intent → grounded shortlist via dialogue
- [x] Use full SHL Individual Test Solutions catalog (377 items; Job Solutions out of scope)
- [x] **Clarify** vague queries before recommending (`recommendations` empty)
- [x] **Recommend** 1–10 assessments with name + catalog URL once context sufficient
- [x] **Refine** mid-conversation (add/drop/replace without restart)
- [x] **Compare** assessments from catalog data (grounded, not model prior)
- [x] **Refuse** general hiring advice, legal questions, prompt injection
- [x] Only discuss SHL assessments; every URL from scraped catalog
- [x] Accept JD paste and multi-turn context

## API / hard eval requirements

- [x] `GET /health` → HTTP 200, body exactly `{"status":"ok"}`
- [x] `POST /chat` stateless — full `messages[]` each call, no server session
- [x] Response keys exactly: `reply`, `recommendations`, `end_of_conversation`
- [x] Recommendation keys exactly: `name`, `url`, `test_type`
- [x] `recommendations` empty when clarifying or refusing
- [x] `recommendations` length 1–10 when recommending
- [x] `end_of_conversation` boolean; true on closure (C1) and turn-8 cap
- [x] 8-turn conversation cap (user + assistant)
- [x] 30-second per-call timeout budget

## Evaluation / scoring criteria

- [x] Hard evals must pass (schema, catalog-only, turn cap)
- [x] Recall@10 on public C1–C10 traces (mean; per-trace ≥0.80 target in APPROACH)
- [x] Behavior probes pass rate (official: eval_suite 15/15, acceptance 43/43)
- [ ] Holdout Recall@10 (SHL private traces — not reproducible locally; synthetic audit 58/100 with flawed labels)

## Submission materials

- [x] Public API URL: `https://assessiq-kkw2.onrender.com`
- [x] Public demo URL: `https://assessiq-ai.streamlit.app`
- [x] `APPROACH.md` ≤2 pages on GitHub `main`
- [x] Repository pushed: `da080c2` on `origin/main`

## Non-functional / skills assessed

- [x] Problem decomposition (clarify/recommend/refine/compare/refuse pipeline)
- [x] Clean extensible code with test harnesses
- [x] Context engineering (hybrid retrieval + injection + analyzer)
- [x] Agent design (decision engine, non-deterministic conversation handling)

## Open risk

- [ ] Tech-only query (`React and TypeScript`) recommends without role clarify — borderline vs "clarify vague queries"
