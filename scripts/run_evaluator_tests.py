#!/usr/bin/env python3
"""
Evaluator test runner - executes the full simulation suite.
Generates comprehensive pass/fail report and identifies issues.
"""

import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.evaluator_simulation import EvaluatorSimulation


def main():
    """Run evaluator simulation suite."""
    parser = argparse.ArgumentParser(description="Run AssessIQ evaluator simulation tests")
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
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output for each scenario"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("ASSESSIQ EVALUATOR SIMULATION SUITE")
    print("=" * 70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"API endpoint: {args.api_url}")
    print(f"Total scenarios: {len(EvaluatorSimulation.SCENARIOS)}")
    print("=" * 70)
    print()

    # Run all scenarios
    print("Running scenarios...")
    results = EvaluatorSimulation.run_all_scenarios()

    # Generate report
    report = EvaluatorSimulation.generate_report(results)
    print(report)

    # Show verbose output if requested
    if args.verbose:
        print("\nVERBOSE OUTPUT")
        print("=" * 70)
        for scenario in results["scenarios"]:
            print(f"\n{scenario['scenario_name']}:")
            print(f"  Status: {'PASS' if scenario['passed'] else 'FAIL'}")
            print(f"  Metrics: {json.dumps(scenario['metrics'], indent=4)}")
            if scenario["issues"]:
                print(f"  Issues: {scenario['issues']}")
            if scenario.get("warnings"):
                print(f"  Warnings: {scenario['warnings']}")

    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    # Summary
    print()
    print("=" * 70)
    total = results["total_scenarios"]
    passed = results["passed"]
    pass_rate = (passed / total * 100) if total > 0 else 0
    print(f"FINAL RESULT: {passed}/{total} passed ({pass_rate:.1f}%)")
    print("=" * 70)

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
