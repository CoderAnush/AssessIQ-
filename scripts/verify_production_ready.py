#!/usr/bin/env python3
"""
Full production readiness verification.
Builds pipeline, starts API, runs all tests, and verifies production readiness.
"""

import subprocess
import sys
import time
import requests
from pathlib import Path


class ProductionVerifier:
    """Verifies AssessIQ is production-ready."""

    def __init__(self):
        self.api_process = None
        self.steps = []
        self.failures = []

    def step(self, name: str, command: str, description: str = "") -> bool:
        """Execute a verification step."""
        print(f"\n{'=' * 70}")
        print(f"STEP: {name}")
        if description:
            print(f"DESC: {description}")
        print('=' * 70)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                print(f"✓ {name} passed")
                self.steps.append((name, True))
                return True
            else:
                print(f"✗ {name} failed")
                print("STDOUT:", result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                print("STDERR:", result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
                self.failures.append(name)
                self.steps.append((name, False))
                return False

        except subprocess.TimeoutExpired:
            print(f"✗ {name} timed out (>60s)")
            self.failures.append(name)
            self.steps.append((name, False))
            return False
        except Exception as e:
            print(f"✗ {name} error: {e}")
            self.failures.append(name)
            self.steps.append((name, False))
            return False

    def wait_for_api(self, url: str = "http://localhost:8000/health", timeout: int = 30) -> bool:
        """Wait for API to be ready."""
        print(f"\nWaiting for API at {url}...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print("✓ API is ready")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)

        print(f"✗ API did not respond within {timeout}s")
        return False

    def run_verification(self) -> bool:
        """Run complete production readiness verification."""
        print("\n╔════════════════════════════════════════════════════════════════════╗")
        print("║        ASSESSIQ PRODUCTION READINESS VERIFICATION                 ║")
        print("╚════════════════════════════════════════════════════════════════════╝\n")

        # Step 1: Validate pipeline exists
        if not self.step(
            "Pipeline Validation",
            "python scripts/validate_pipeline.py",
            "Verify embeddings, FAISS, and BM25 indices are ready"
        ):
            print("\n⚠ Pipeline may not be built. Run 'python scripts/build_pipeline.py' first.")
            return False

        # Step 2: Start API server
        print(f"\n{'=' * 70}")
        print("STEP: Starting API Server")
        print('=' * 70)

        try:
            self.api_process = subprocess.Popen(
                ["python", "app/main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("API server started (PID: {})".format(self.api_process.pid))
            time.sleep(2)  # Give server time to start

            if not self.wait_for_api():
                print("✗ API failed to start")
                if self.api_process.poll() is not None:
                    # Process ended, get output
                    stdout, stderr = self.api_process.communicate()
                    print("Server output:", stderr[-500:])
                self.failures.append("API Server")
                self.steps.append(("API Server", False))
                return False

            print("✓ API Server started")
            self.steps.append(("API Server", True))

        except Exception as e:
            print(f"✗ Failed to start API: {e}")
            self.failures.append("API Server")
            self.steps.append(("API Server", False))
            return False

        # Step 3: Run evaluator tests
        self.step(
            "Evaluator Simulation Tests",
            "python scripts/run_evaluator_tests.py --output evaluator_results.json",
            "Run 10 realistic recruiter scenarios"
        )

        # Step 4: Run edge case tests
        self.step(
            "Edge Case Test Suite",
            "python scripts/run_edge_case_tests.py --output edge_case_results.json",
            "Run 24 boundary condition tests"
        )

        # Step 5: Run complete test suite
        self.step(
            "Complete Test Suite",
            "python scripts/run_complete_tests.py --output complete_results.json --verbose",
            "Run all tests with detailed metrics"
        )

        # Step 6: Analyze metrics
        self.step(
            "Metrics Analysis",
            "python scripts/analyze_metrics.py --output metrics_report.txt",
            "Generate performance analytics report"
        )

        # Cleanup
        if self.api_process:
            print("\nShutting down API server...")
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.api_process.kill()
            print("✓ API server stopped")

        # Summary
        print(f"\n{'=' * 70}")
        print("VERIFICATION SUMMARY")
        print('=' * 70)

        passed = sum(1 for _, result in self.steps if result)
        total = len(self.steps)

        print(f"\nResults: {passed}/{total} steps passed\n")

        for name, result in self.steps:
            status = "✓" if result else "✗"
            print(f"  {status} {name}")

        if self.failures:
            print(f"\nFailed Steps: {', '.join(self.failures)}")
            print("\n✗ VERIFICATION FAILED - Fix issues before production deployment")
            return False
        else:
            print("\n✓ VERIFICATION PASSED - System is production-ready")
            print("\nNext steps:")
            print("  1. Review test results in evaluator_results.json")
            print("  2. Review metrics in metrics_report.txt")
            print("  3. Check DEPLOYMENT_CHECKLIST.md")
            print("  4. Deploy to production")
            return True

    def run(self) -> int:
        """Run verification and return exit code."""
        try:
            success = self.run_verification()
            return 0 if success else 1
        except KeyboardInterrupt:
            print("\n\n✗ Verification interrupted")
            if self.api_process:
                self.api_process.terminate()
            return 1
        except Exception as e:
            print(f"\n✗ Verification error: {e}")
            if self.api_process:
                self.api_process.terminate()
            return 1


def main():
    """Main entry point."""
    verifier = ProductionVerifier()
    exit_code = verifier.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
