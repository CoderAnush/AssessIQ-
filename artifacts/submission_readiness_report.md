# Submission Readiness Report

**Generated:** 2026-07-02T03:48:31.060656+00:00
**Backend:** `https://assessiq-nkp2.onrender.com`
**Production:** `https://assessiq-nkp2.onrender.com`
**Verdict:** **NOT READY**

## Blockers
- eval_suite
- ui_30
- smoke_frontend
- c1_c10_recall
- production_health

## Gate Results

| Gate | Pass | Notes |
|------|------|-------|
| Local /health | YES | {"status":"ok"} |
| pytest | YES |  None, but tests/test_integration.py::test_simple_chat returned True, which will be an error in a future version of pyte |
| eval_suite | NO |  out of 15 cases  CASE: Malformed request handling PASS (0.51s)  Summary: 12 passed, 3 failed out of 15 cases  ========= |
| acceptance | YES | xecuting Scenario 41... Scenario 41: PASS (Recommendations generated) Executing Scenario 42... Scenario 42: PASS (Recomm |
| comprehensive_54 | YES | RY ================================================================================ Total: 54 / Passed: 54 / Failed: 0 S |
| ui_30 | NO | nPool(host='assessiq-nkp2.onrender.com', port=443): Max retries exceeded with url: /chat (Caused by NewConnectionError(' |
| smoke_frontend | NO | nectionError: HTTPSConnectionPool(host='assessiq-nkp2.onrender.com', port=443): Max retries exceeded with url: /chat (Ca |
| c1_c10_recall | NO | urred:  Traceback (most recent call last):   File "C:\Users\anush\Desktop\SHL\AssessIQ-\scripts\run_c1_c10_recall.py", l |
| Production /health | NO | HTTPSConnectionPool(host='assessiq-nkp2.onrender.com', port=443): Max retries exceeded with url: /health (Caused by Name |