# Regression Report

**Backend:** `https://assessiq-kkw2.onrender.com`  
**Date:** 2026-07-02  
**Evaluator:** SHL automated audit (skeptical re-run)

| Suite | Result | Notes |
|-------|--------|-------|
| `pytest tests/` (local) | **82/82** | Schema + C1–C10 regression |
| `run_eval_suite.py` | **15/15** | All hard-eval cases |
| `run_acceptance_tests.py` | **43/43** | Production acceptance |
| `run_c1_c10_recall.py` | **10/10 @ 1.00** | Mean Recall@10 = 1.00 |
| `run_evaluator_tests.py` | **10/10** | Prior run on production |

## Skeptical re-probes (production)

| Probe | Expected | Observed | Verdict |
|-------|----------|----------|---------|
| Stateless identical replay | Same JSON | Identical hash | **PASS** |
| `GET /health` body | `{"status":"ok"}` only | Exact match | **PASS** |
| Clarify → 0 recs, `end=false` | 0 / false | 0 / false | **PASS** |
| C1 closure turn 4 | `end=true` | true, 7 recs | **PASS** |
| Drop OPQ (with rec history) | No OPQ in list | 6 recs, no OPQ | **PASS** |
| Contact centre senior | Clarify language | 0 recs, asks language | **PASS** |
| `React and TypeScript` alone | Clarify (no role) | **7 recs** | **RISK** |
| Turn 8 cap | `end=true` at cap | true on turn 8 | **PASS** (matches eval_suite) |
| Warm latency | ≤30s | ~1.1s | **PASS** |

## Regression verdict

Official regression suites: **ALL PASS**.  
One behavioral edge case flagged: tech-stack-only query recommends without role/seniority clarify.
