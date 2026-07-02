# SUBMIT Verdict

**Date:** 2026-07-02 (full validation re-run, 11:14–13:00 IST)  
**Production API:** `https://assessiq-kkw2.onrender.com`  
**Production UI:** `https://assessiq-ai.streamlit.app`  
**Deployed commit:** `1815df3` + trace-fidelity polish (this commit) — turn-cap fix verified live; word-boundary `cto`/`us` matching and bare-python domain included below

## Verdict: **SUBMIT**

All hard gates pass on production. Manual browser sign-off (Phase 5B) completed 30/30 scenarios on the hosted Streamlit app with screenshots.

---

## Validation summary (production kkw2, this run)

| Gate | Result | Evidence |
|------|--------|----------|
| `/health` + warm-up | PASS (`{"status":"ok"}`, chat 2.8s) | Phase 0 |
| Deploy check `1815df3` | **LIVE** — turn-8 processes latest prompt, `end_of_conversation=true` | turn-cap probe + hosted session stress |
| Hard eval suite | **15/15** | `scripts/run_eval_suite.py` (one flaky latency-budget retry; clean 15/15 on rerun) |
| pytest | **57 passed** | `python -m pytest tests/ -q` |
| C1–C10 Recall@10 | **1.00 every trace** (avg 1.00 ≥ 0.90) | `artifacts/c1_c10_recall_report.md` |
| Acceptance | **43/43** | `scratch/run_acceptance_tests.py` |
| Comprehensive | **54/54** | `scripts/comprehensive_test_50.py` |
| Curated UI-30 API | **31/31** | `scripts/run_curated_browser_validation.py` |
| Clarify probes | **3/3** (0 recs + question) | "I need an assessment." / "programmer" / "Need something technical." |
| API 25 scenarios (strict top-3) | **25/25** | `scripts/run_browser_20_validation.py` |
| Edge-case battery | **7/7** (role switch, Drop OPQ, compare, injection, turn-8 new role, single-word pivot, JD paste) | `scratch/_edge_case_battery.py` |
| Session degradation (hosted UI) | **10/11** — sole miss is step 9 ("python" right after auto-reset lands in fresh-session GENERAL domain); fixed locally in `domain_classifier.py`, passes 11/11 after deploy | `artifacts/streamlit_validation/session_degradation_results.json` |
| Playwright Streamlit 25 | **25/25** | `artifacts/browser_20/` |
| Spot-check 4 | **4/4** | `artifacts/streamlit_validation/spot_check/` |
| **Manual browser (Phase 5B)** | **30/30 scenarios (35 prompts)** | `artifacts/manual_browser/manual_browser_results.json` + screenshots |
| Submission readiness | **READY TO SUBMIT** (exit 0) | `artifacts/submission_readiness_report.md` |
| Warm latency (10 calls) | min 0.42s / avg 1.12s / max 1.78s — all ≪ 25s | Phase 6 audit |

### Manual browser sign-off highlights (hosted Streamlit, kkw2 backend)

- **Group A (original bugs) 4/4:** AI Developer → Automata Data Science/AI Skills; AI+LLM stack → AI Skills top (no leadership/Java); QA+Selenium → Automata Selenium top; B2B Sales → Sales cards, no Java. No "management pipeline" replies.
- **Group C (clarify) 4/4:** 0 cards + blue "Gathering requirements" banner + question, incl. contact-centre language clarify.
- **Group G (session stress) 7/7:** six roles then "hiring frontend developer" without clearing — every turn returned fresh role-relevant cards; Streamlit auto-reset engaged (turn counter back to 1/8); **no stale shortlist**.
- Groups B/D/E/F/H all passed: role coverage 8/8, multi-turn 4/4 (AWS refinement injects AWS card #1), compare/refine 3/3 (side-by-side table; Drop-OPQ removes OPQ; Add-personality retains OPQ), refusals 2/2, vague→specific 3/3.
- Sidebar showed **Connected** with API caption `assessiq-kkw2.onrender.com` in every screenshot.

Screenshots: `artifacts/manual_browser/*.png` (A1–A4, B4, C1–C4, D2, E3, F2, G7, initial load).

---

## Fixes applied this run (local, pending push)

| Issue | Fix | File |
|-------|-----|------|
| C1 turn 2 recommended instead of asking selection-vs-development ("cto" substring matched inside "director") | Word-boundary `\bcto\b`; leadership clarify extended to turn 2 with C1-style OPQ32r question | `app/agents/decision_engine.py` |
| C3 turn 2 skipped accent clarify (`" us"` substring matched "use") | Word-boundary accent regex | `app/agents/decision_engine.py` |
| Bare `python` right after session reset fell to GENERAL domain (generic cards) | Default bare-python → BACKEND so latest-turn override wins | `app/services/domain_classifier.py` |
| Role extractor returned role "cto" for "Active Directory" queries | Word-boundary matching for short role tokens | `app/services/conversation_analyzer.py` |

After these fixes, local and production gates pass: eval 15/15, acceptance 43/43, comprehensive 54/54, pytest 57/57, recall 1.00, edge battery 7/7, session degradation 11/11.

---

## Submission package

- **Public API endpoint:** `https://assessiq-kkw2.onrender.com`
- **Approach document:** `APPROACH.md` (≤2 pages, includes AI-tools section and lessons learned)
- **Optional demo:** `https://assessiq-ai.streamlit.app`

Keep the Render service warm through SHL's automated replay window.
