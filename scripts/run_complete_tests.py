#!/usr/bin/env python3
"""
Master test runner - executes complete evaluator simulation and edge case suite.
Generates combined comprehensive report for production deployment verification.
"""

import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.evaluator_simulation import EvaluatorSimulation
from app.utils.edge_case_testing import EdgeCaseTestSuite


def main():
    """Run complete test suite."""
    parser = argparse.ArgumentParser(description="Run AssessIQ complete test suite")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/chat",
        help="API endpoint URL (default: http://localhost:8000/chat)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--evaluator-only",
        action="store_true",
        help="Run only evaluator simulation (skip edge cases)"
    )
    parser.add_argument(
        "--edge-cases-only",
        action="store_true",
        help="Run only edge case suite (skip evaluator simulation)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output"
    )
    args = parser.parse_args()

    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "ASSESSIQ COMPLETE TEST SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    print(f"Start time:     {datetime.now().isoformat()}")
    print(f"API endpoint:   {args.api_url}")
    print()

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "api_url": args.api_url,
        "evaluator_simulation": None,
        "edge_case_suite": None,
    }

    # Run evaluator simulation
    if not args.edge_cases_only:
        print("=" * 70)
        print("EVALUATOR SIMULATION")
        print("=" * 70)
        try:
            eval_results = EvaluatorSimulation.run_all_scenarios()
            eval_report = EvaluatorSimulation.generate_report(eval_results)
            print(eval_report)
            all_results["evaluator_simulation"] = eval_results
        except Exception as e:
            print(f"✗ Evaluator simulation failed: {e}")
            all_results["evaluator_simulation"] = {"error": str(e)}

        print()

    # Run edge case suite
    if not args.evaluator_only:
        print("=" * 70)
        print("EDGE CASE TEST SUITE")
        print("=" * 70)
        try:
            edge_results = EdgeCaseTestSuite.run_all_edge_cases(args.api_url)
            edge_report = EdgeCaseTestSuite.generate_report(edge_results)
            print(edge_report)
            all_results["edge_case_suite"] = edge_results
        except Exception as e:
            print(f"✗ Edge case suite failed: {e}")
            all_results["edge_case_suite"] = {"error": str(e)}

        print()

    # Generate combined summary
    print("=" * 70)
    print("COMBINED SUMMARY")
    print("=" * 70)

    eval_summary = all_results.get("evaluator_simulation")
    edge_summary = all_results.get("edge_case_suite")

    if eval_summary and "error" not in eval_summary:
        eval_pass = eval_summary.get("passed", 0)
        eval_total = eval_summary.get("total_scenarios", 0)
        eval_rate = (eval_pass / eval_total * 100) if eval_total > 0 else 0
        print(f"Evaluator Simulation: {eval_pass}/{eval_total} ({eval_rate:.1f}%)")
    else:
        print("Evaluator Simulation: SKIPPED or ERROR")

    if edge_summary and "error" not in edge_summary:
        edge_pass = edge_summary.get("passed", 0)
        edge_total = edge_summary.get("total", 0)
        edge_rate = (edge_pass / edge_total * 100) if edge_total > 0 else 0
        print(f"Edge Case Suite:      {edge_pass}/{edge_total} ({edge_rate:.1f}%)")
    else:
        print("Edge Case Suite:      SKIPPED or ERROR")

    # Determine overall status
    all_passed = True
    if eval_summary and "error" not in eval_summary:
        all_passed = all_passed and (eval_summary.get("passed", 0) == eval_summary.get("total_scenarios", 0))
    if edge_summary and "error" not in edge_summary:
        all_passed = all_passed and (edge_summary.get("passed", 0) == edge_summary.get("total", 0))

    print()
    if all_passed:
        print("✓ ALL TESTS PASSED - System is production-ready")
    else:
        print("✗ SOME TESTS FAILED - Address issues before production")

    print("=" * 70)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    # Show verbose details if requested
    if args.verbose and eval_summary and "error" not in eval_summary:
        print("\n" + "=" * 70)
        print("EVALUATOR SIMULATION - DETAILED RESULTS")
        print("=" * 70)
        for scenario in eval_summary.get("scenarios", []):
            print(f"\n{scenario['scenario_name']}:")
            print(f"  Passed: {scenario['passed']}")
            if scenario.get("metrics"):
                for key, value in scenario["metrics"].items():
                    print(f"  {key}: {value}")
            if scenario.get("issues"):
                for issue in scenario["issues"]:
                    print(f"  Issue: {issue}")

    if args.verbose and edge_summary and "error" not in edge_summary:
        print("\n" + "=" * 70)
        print("EDGE CASE SUITE - DETAILED RESULTS")
        print("=" * 70)
        for scenario in edge_summary.get("scenarios", []):
            print(f"\n{scenario['name']}:")
            print(f"  Passed: {scenario['passed']}")
            print(f"  Latency: {scenario['metrics']['latency_ms']:.0f}ms")
            if scenario.get("issues"):
                for issue in scenario["issues"]:
                    print(f"  Issue: {issue}")

    print()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
