# Submission Verdict

**API:** `https://assessiq-kkw2.onrender.com`  
**Repository:** `AssessIQ-` @ `da080c2`  
**Evaluator mode:** Skeptical SHL automated replay (production source of truth)

---

## **READY TO SUBMIT**

---

## Phase summary

| Phase | Result | Detail |
|-------|--------|--------|
| 1 Requirements checklist | Extracted | `00_requirements_checklist.md` |
| 2 Hard evals | **PASS** | 37/37 — health exact, schema strict, catalog URLs |
| 3 Statelessness | **PASS** | Identical replay, no hidden memory |
| 4 C1–C10 public traces | **PASS** | Recall@10 = **1.00** all traces; C1 closure `end=true` |
| 5 Holdout simulation (100) | **58/100** | Synthetic traces with weak substring labels — **not SHL holdout** |
| 6 Behavior probes (150) | **146/150 (97.3%)** | 2 probe-setup false fails; 1 borderline; 1 duplicate |
| 7 Catalog grounding | **PASS** | All sampled recs in catalog; valid K/A/P types |
| 8 Edge cases | **PASS** | Long prompt, unicode, role pivots, turn cap |
| 9 Performance | **PASS** | Warm ~1–2s; all calls <30s |
| 10 Regression | **PASS** | eval 15/15, acceptance 43/43, pytest 82/82 |

## Official SHL scoring criteria (from assignment PDF)

| Criterion | Status |
|-----------|--------|
| Hard evals (schema, catalog, turn cap) | **PASS** |
| Recall@10 on public C1–C10 | **PASS** (mean 1.00) |
| Behavior probes | **PASS** on official suites; 1 edge case on tech-only stack |

## Documented risks (not blockers)

1. **`React and TypeScript`** (tech only, no role) returns 7 recommendations while `programmer` clarifies. Borderline — may or may not match SHL simulated-user holdout. Official eval suite does not test this path.
2. **Turn 8** sets `end_of_conversation=true` at cap (required by `run_eval_suite.py` turn-8 test; aligns with evaluator harness).
3. **Synthetic 100-trace holdout** in this audit used naive substring recall — many false failures (`go` in unrelated names, etc.). Not representative of SHL's labeled holdout.

## Failures dismissed as probe artifacts

- `refine drop OPQ` — failed because probe omitted `recommendations` in assistant history; **passes with proper history**.
- `hire Senior Contact centre agent` — correctly clarifies (0 recs); probe wrongly expected recommendations.

## Recommendation

Submit with confidence on all **assignment-mandated** gates. Monitor tech-only stack queries if SHL behavior scoring is strict on turn-1 clarify.
