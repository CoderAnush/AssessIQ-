# SUBMIT Verdict

**Date:** 2026-07-02  
**Verdict:** **SUBMIT** (after kkw2 redeploy completes — verify hosted Streamlit once)

## Summary

Systemic recommendation quality bugs are fixed. The root cause was **`cto` matching inside the word "vec*t*o*r"**, which misclassified AI Engineer prompts as executive leadership and injected OPQ/MFS leadership cards ahead of AI/Data Science assessments.

## Validation results (post-fix, local API)

| Gate | Result |
|------|--------|
| Browser scenarios (strict top-3) | **25/25 PASS** |
| Conversation regression | **30/30 PASS** |
| Key UI prompts | AI Developer, AI Engineer+LLMs, QA Automation, B2B Sales — all PASS |

## Before vs after (AI Engineer + Vector Databases)

| | Before | After |
|---|--------|-------|
| Reply | "enterprise **management** pipeline" | "enterprise **AI/ML** pipeline" |
| Top cards | MFS Leadership, OPQ Leadership, Spring/Java | AI Skills, Automata Data Science, Data Science |

## Action before final demo

1. Confirm Render redeploy of `assessiq-kkw2` finished (FAISS build adds ~2 min cold start)
2. On Streamlit: **Clear conversation** before each test prompt
3. Spot-check the four prompts from your screenshots

## Endpoints to submit

- **API:** https://assessiq-kkw2.onrender.com
- **UI:** https://assessiq-ai.streamlit.app
- **Approach:** `APPROACH.md`
