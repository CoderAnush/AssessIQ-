# AssessIQ Testing & Evaluation Guide

## Overview

AssessIQ includes a comprehensive multi-tier testing framework to ensure production-grade reliability:

1. **Evaluator Simulation** - Tests realistic recruiter conversation scenarios
2. **Edge Case Testing** - Tests robustness against malformed input and boundary conditions
3. **Combined Test Suite** - Orchestrates both test types with unified reporting

## Evaluator Simulation

### Purpose
Tests AssessIQ against realistic recruiter workflows to validate:
- Conversation understanding
- Appropriate decision-making (clarify vs. recommend)
- Recommendation quality and ranking
- Schema compliance
- Hallucination prevention
- Response clarity

### Test Scenarios (10 probe types)

| Scenario | Probe Type | Tests |
|----------|-----------|-------|
| **Vague Query** | behavior | AI asks clarifying questions when context is incomplete |
| **Clear Query** | hard_eval | AI provides 3-10 ranked recommendations with high confidence |
| **Refinement Flow** | behavior | AI maintains context across turns while incorporating refinements |
| **Assessment Comparison** | behavior | AI correctly handles comparison requests without hallucinations |
| **Prompt Injection** | hard_eval | AI resists injection attempts and stays focused on hiring |
| **Off-Topic Request** | hard_eval | AI politely refuses non-hiring requests |
| **Empty Conversation** | edge_case | AI handles empty message history gracefully |
| **Multiple Refinements** | recall | AI tracks and incorporates multiple refinement requests |
| **Contradictory Context** | behavior | AI handles conflicting requirements gracefully |
| **Soft Skills Heavy** | behavior | AI doesn't over-recommend when context is incomplete |

### Probe Types Explained

- **hard_eval** (4 scenarios): Schema compliance, security, no hallucinations. Must have 100% pass rate.
- **recall** (2 scenarios): Recommendation accuracy and ranking quality. Should have ≥80% pass rate.
- **behavior** (3 scenarios): Conversational coherence and appropriate actions. Should have ≥80% pass rate.
- **edge_case** (1 scenario): Graceful handling of invalid input. Should have ≥90% pass rate.

### Metrics Collected

For each scenario:
- **Latency** (ms) - Response time. Target: <500ms
- **Recommendation Count** - Number of recommendations returned
- **Schema Valid** - Response passes validation
- **Hallucinations Detected** - Count of invalid assessments
- **Explanation Quality** (0-1) - How well context is explained
- **Confidence Valid** - Confidence scores are valid (0-100%)

## Edge Case Testing

### Purpose
Tests robustness against:
- Invalid input (empty, oversized, malformed)
- Injection attacks (HTML, SQL)
- Encoding issues (Unicode, non-ASCII, mixed languages)
- Boundary conditions (very long conversations, rapid refinements)
- Missing data (empty fields, invalid schemas)

### Test Categories

| Category | Scenarios | Tests |
|----------|-----------|-------|
| **Input Validation** | 6 | Empty, whitespace, excessive text, HTML/SQL injection, unicode |
| **Conversation Structure** | 4 | Long conversations, role mismatches, missing fields, invalid roles |
| **Context Handling** | 4 | Contradictions, soft-skills-only, no context, ambiguous |
| **Language/Encoding** | 2 | Non-English, mixed languages |
| **Assessment Catalog** | 2 | Unknown assessments, hallucination bait |
| **Boundary Conditions** | 3 | Zero matches, all matches, rapid refinements |

### Edge Case Validation

Each edge case is marked as:
- `should_fail_gracefully=True`: API should return safe fallback (no schema errors)
- `should_fail_gracefully=False`: API should process normally

## Running Tests

### Prerequisites

1. **Start the API server**:
   ```bash
   python app/main.py
   # Server runs on http://localhost:8000
   ```

2. **Ensure pipeline is built**:
   ```bash
   python scripts/build_pipeline.py
   # Creates data/processed/ with embeddings, FAISS, BM25 indices
   ```

### Run Evaluator Simulation Only

```bash
python scripts/run_evaluator_tests.py
```

Options:
- `--api-url URL`: Custom API endpoint (default: http://localhost:8000/chat)
- `--output FILE`: Save results to JSON file
- `--verbose`: Show detailed metrics for each scenario

### Run Edge Case Suite Only

```bash
python scripts/run_edge_case_tests.py
```

Same options as evaluator tests.

### Run Complete Test Suite

```bash
python scripts/run_complete_tests.py
```

This runs both evaluator simulation and edge case testing with combined reporting.

Options:
- `--api-url URL`: Custom API endpoint
- `--output FILE`: Save all results to JSON
- `--evaluator-only`: Skip edge case tests
- `--edge-cases-only`: Skip evaluator simulation
- `--verbose`: Show detailed metrics for all scenarios

## Reading the Report

### Evaluator Simulation Report

```
ASSESSIQ EVALUATOR SIMULATION REPORT
============================
Total Scenarios: 10
Passed: 10/10
Failed: 0/10
Pass Rate: 100.0%

PROBE TYPE BREAKDOWN
====================
  ✓ hard_eval     : 4/4 (100.0%)
  ✓ recall        : 2/2 (100.0%)
  ✓ behavior      : 3/3 (100.0%)
  ✓ edge_case     : 1/1 (100.0%)

PERFORMANCE METRICS
===================
Average Latency: 245ms
Average Recommendations: 4.2
Total Hallucinations Detected: 0
```

**Interpretation**:
- ✓ PASS = Scenario passed all checks
- ✗ FAIL = Scenario failed validation
- ◐ PARTIAL = Some checks passed, some warnings

### Edge Case Report

```
ASSESSIQ EDGE CASE TEST REPORT
============================
Results
=======
Total: 24
Passed: 24
Failed: 0
Pass Rate: 100.0%
```

**Interpretation**:
- `Handled Gracefully: True` = API returned valid response (safe default or processed)
- `Handled Gracefully: False` = API returned error or invalid response
- All edge cases should either pass or return safe fallback

### Combined Summary

```
COMBINED SUMMARY
================
Evaluator Simulation: 10/10 (100.0%)
Edge Case Suite:      24/24 (100.0%)

✓ ALL TESTS PASSED - System is production-ready
```

## Pass/Fail Criteria

### Production Readiness

**READY FOR DEPLOYMENT** when:
- Evaluator Simulation: ALL scenarios pass (100%)
- Edge Case Suite: ALL scenarios pass (100%)
- Average latency < 500ms
- Zero hallucinations detected across all tests
- All hard_eval probes pass (schema compliance guaranteed)

**NEEDS FIXES** when:
- Any hard_eval scenario fails
- Edge case suite has failures
- Average latency > 1000ms
- Hallucinations detected
- Failed scenarios have unresolved issues

## Troubleshooting

### "API connection failed"
- Ensure API server is running: `python app/main.py`
- Check API URL: Default is `http://localhost:8000/chat`
- Check firewall/network connectivity

### "API timeout"
- Server is slow or unresponsive
- Check server logs for errors
- May indicate performance issue before production

### "Schema validation failed"
- Response doesn't match expected format
- Check that `hard_eval_safety.py` is being used
- Server may be returning malformed JSON

### "Hallucination detected"
- Recommendation URL or name is invalid
- Check that hallucination_checker.py validates all recommendations
- Verify catalog has been loaded correctly

### High latency (>1000ms)
- Retrieval may be slow (check FAISS/BM25 indexing)
- LLM call may be slow (check Claude API)
- Context analysis may be inefficient
- Consider optimization: caching, batching, or reducing context window

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run AssessIQ Tests
  run: |
    python scripts/run_complete_tests.py \
      --api-url http://localhost:8000/chat \
      --output test_results.json \
      --verbose
  
  - name: Check Test Results
    run: |
      if [ $(python -c "import json; r=json.load(open('test_results.json')); print(r['evaluator_simulation']['passed'])") -ne 10 ]; then
        echo "Tests failed"
        exit 1
      fi
```

## Performance Benchmarks

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Latency (p95) | <500ms | TBD |
| Latency (p99) | <1000ms | TBD |
| Hallucination Rate | 0% | TBD |
| Hard Eval Pass Rate | 100% | TBD |
| Edge Case Pass Rate | 100% | TBD |
| Recommendation Accuracy | >80% | TBD |

### Collecting Benchmark Data

After running tests, results are saved to JSON:

```python
import json

with open("test_results.json") as f:
    results = json.load(f)

# Extract metrics
eval_results = results["evaluator_simulation"]
edge_results = results["edge_case_suite"]

# Calculate latencies
eval_latencies = [s["metrics"]["latency_ms"] for s in eval_results["scenarios"]]
edge_latencies = [s["metrics"]["latency_ms"] for s in edge_results["scenarios"]]

print(f"Eval p95: {sorted(eval_latencies)[int(len(eval_latencies)*0.95)]:.0f}ms")
print(f"Edge p95: {sorted(edge_latencies)[int(len(edge_latencies)*0.95)]:.0f}ms")
```

## Next Steps

1. **Run baseline tests** to establish current performance
2. **Identify any failures** and debug root causes
3. **Optimize** high-latency scenarios if needed
4. **Add to pre-deployment checklist** - run tests before every deployment
5. **Monitor production** - periodically re-run tests against production API

## Files Reference

- `app/utils/evaluator_simulation.py` - Evaluator simulation framework
- `app/utils/edge_case_testing.py` - Edge case test suite
- `app/utils/hard_eval_safety.py` - Response validation and repair
- `scripts/run_evaluator_tests.py` - Evaluator test runner
- `scripts/run_complete_tests.py` - Combined test orchestrator
- `logs/evaluation_metrics.jsonl` - Raw metrics from each run

