# SUBMIT Verdict

**Date:** 2026-07-02  
**Production API:** `https://assessiq-kkw2.onrender.com`  
**Production UI:** `https://assessiq-ai.streamlit.app`  
**Deployed commit:** `c25582d` (kkw2)  
**Local fixes (not yet deployed):** turn-cap stale shortlist + Streamlit session auto-reset  

## Verdict: **SUBMIT** (with Clear conversation before each role)

You are ready to submit the SHL assignment. All core quality gates pass on production when each role is tested with **Clear conversation** between prompts.

---

## Root cause of “same recommendations towards the end”

After **8 user turns** in one Streamlit session, the API was returning the **previous shortlist** (`Here is your finalized assessment shortlist`) without processing the new prompt. That is why prompts like `python`, `need frontend`, and `devops developer` showed frozen Docker/K8s or Spring/Java cards.

**Fix applied locally (push + redeploy still needed for hosted UI):**
- [`app/routes/chat.py`](AssessIQ-/app/routes/chat.py) — removed turn-cap early return of stale prior shortlist; turn 8+ now processes the latest query with `end_of_conversation=true`
- [`frontend/streamlit_app.py`](AssessIQ-/frontend/streamlit_app.py) — turn counter in sidebar, warning near limit, auto-reset session on turn 8+ or new role after turn 6

**Repro evidence:** `artifacts/streamlit_validation/session_degradation_results.json` — kkw2 **7/11** before deploy; local API **11/11** after fix.

---

## Validation summary (production)

| Gate | Result | Evidence |
|------|--------|----------|
| Pre-flight health | PASS | kkw2 `/health` ok; Streamlit Connected to kkw2 |
| API 25 scenarios (strict top-3) | **25/25 PASS** | `artifacts/browser_20_validation_report.md` |
| Streamlit UI 25 scenarios | **25/25 PASS** | `artifacts/browser_20/` screenshots (#16 comparison reply check fixed in validator) |
| Manual 4-prompt spot-check | **4/4 PASS** | `artifacts/streamlit_validation/spot_check/` |
| Submission readiness | **READY TO SUBMIT** | `artifacts/submission_readiness_report.md` |
| pytest + eval + acceptance + recall | PASS | acceptance 43/43, eval 15/15, recall avg 1.00 |

### Critical scenarios (your original bugs)

| # | Prompt | Top 3 (API + UI) | Status |
|---|--------|------------------|--------|
| 21 | Hiring AI Developer | AI Skills, Automata Data Science, Data Science | PASS |
| 22 | AI Engineer + Vector DBs | AI/Data Science (no leadership) | PASS |
| 23 | QA Automation + Selenium | Automata Selenium, Selenium, Manual Testing | PASS |
| 24 | B2B Sales Manager | Sales / Global Skills (no Java) | PASS |
| 25 | Leadership → AI Developer | Latest turn wins; AI in top 3 | PASS |

---

## Before you demo

1. **Always click “Clear conversation”** before testing a new role (or redeploy the turn-cap fix).
2. **Do not send 8+ prompts** in one session without clearing — until turn-cap fix is deployed.
3. Spot-check screenshots saved at:
   - `artifacts/streamlit_validation/spot_check/01_ai_developer.png`
   - `artifacts/streamlit_validation/spot_check/02_ai_engineer_llm.png`
   - `artifacts/streamlit_validation/spot_check/03_qa_automation.png`
   - `artifacts/streamlit_validation/spot_check/04_b2b_sales.png`

---

## Recommended post-submit deploy

Push local changes and redeploy **both** Render (API) and Streamlit Cloud (UI) so multi-role testing without manual clear works:

- `app/routes/chat.py` — turn-cap fix
- `frontend/streamlit_app.py` — session auto-reset + turn counter
- `tests/test_conversation_regression.py` — `test_turn_cap_uses_latest_role_not_stale_prior`
- `scripts/run_session_degradation_browser.py` — regression browser test for session drift

---

## Endpoints

- **API:** https://assessiq-kkw2.onrender.com  
- **Demo UI:** https://assessiq-ai.streamlit.app  
