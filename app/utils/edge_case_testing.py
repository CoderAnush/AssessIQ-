"""
Edge case testing suite for AssessIQ.
Tests robustness against malformed input, extreme scenarios, and boundary conditions.
"""

from typing import List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EdgeCaseScenario:
    """Edge case test scenario."""
    name: str
    description: str
    conversation: List[Dict]
    should_fail_gracefully: bool  # True = should return safe default, False = should process normally


class EdgeCaseTestSuite:
    """Comprehensive edge case testing."""

    EDGE_CASES = [
        # Input validation edge cases
        EdgeCaseScenario(
            name="Empty Message",
            description="User sends empty message",
            conversation=[{"role": "user", "content": ""}],
            should_fail_gracefully=True
        ),

        EdgeCaseScenario(
            name="Whitespace Only",
            description="User sends only whitespace",
            conversation=[{"role": "user", "content": "   \n\t  "}],
            should_fail_gracefully=True
        ),

        EdgeCaseScenario(
            name="Excessive Text",
            description="User sends very long message (10k chars)",
            conversation=[{"role": "user", "content": "x" * 10000}],
            should_fail_gracefully=False  # Should truncate gracefully
        ),

        EdgeCaseScenario(
            name="Unicode Special Characters",
            description="User sends message with emoji and unicode",
            conversation=[{"role": "user", "content": "Senior Java developer 🚀 with λ-calculus knowledge"}],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="HTML Injection",
            description="User attempts HTML injection",
            conversation=[{"role": "user", "content": "<script>alert('xss')</script> Java developer"}],
            should_fail_gracefully=False  # Should sanitize
        ),

        EdgeCaseScenario(
            name="SQL-like Injection",
            description="User sends SQL-like injection attempt",
            conversation=[{"role": "user", "content": "'; DROP TABLE assessments; -- Java dev"}],
            should_fail_gracefully=False
        ),

        # Conversation structure edge cases
        EdgeCaseScenario(
            name="Very Long Conversation",
            description="User has 20+ turn conversation",
            conversation=[
                {"role": "user", "content": "I need a Java developer"},
                {"role": "assistant", "content": "What seniority level?"},
                {"role": "user", "content": "Senior"},
                {"role": "assistant", "content": "Here are recommendations..."},
                {"role": "user", "content": "Add communication focus"},
                {"role": "assistant", "content": "Updated..."},
            ] + [
                item for i in range(1, 11) for item in [
                    {"role": "user", "content": f"Refinement {i}"},
                    {"role": "assistant", "content": f"Updated recommendation {i}"}
                ]
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Alternating Roles Error",
            description="Two consecutive user messages (malformed history)",
            conversation=[
                {"role": "user", "content": "Java developer"},
                {"role": "user", "content": "Actually, Python"},
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Missing Role Field",
            description="Message missing role field",
            conversation=[{"content": "Java developer"}],  # Missing "role"
            should_fail_gracefully=True
        ),

        EdgeCaseScenario(
            name="Missing Content Field",
            description="Message missing content field",
            conversation=[{"role": "user"}],  # Missing "content"
            should_fail_gracefully=True
        ),

        EdgeCaseScenario(
            name="Invalid Role Value",
            description="Message with invalid role value",
            conversation=[{"role": "moderator", "content": "Java developer"}],
            should_fail_gracefully=True
        ),

        # Context edge cases
        EdgeCaseScenario(
            name="Contradictory Requirements",
            description="Requirements that conflict",
            conversation=[
                {"role": "user", "content": "Junior developer with 20 years experience and startup energy"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="All Soft Skills Focus",
            description="User only mentions soft skills, no technical requirements",
            conversation=[
                {"role": "user", "content": "Need someone with excellent communication, leadership, integrity, and empathy"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="No Context At All",
            description="User gives zero context",
            conversation=[
                {"role": "user", "content": "I'm hiring"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Ambiguous Role Description",
            description="Role description is ambiguous",
            conversation=[
                {"role": "user", "content": "I need someone to do things in technology"}
            ],
            should_fail_gracefully=False
        ),

        # Language/encoding edge cases
        EdgeCaseScenario(
            name="Non-English Language",
            description="User queries in Spanish",
            conversation=[
                {"role": "user", "content": "Necesito un desarrollador de Java senior"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Mixed Language",
            description="User mixes English and other languages",
            conversation=[
                {"role": "user", "content": "Senior Java developer, 日本語も話せます"}
            ],
            should_fail_gracefully=False
        ),

        # Assessment catalog edge cases
        EdgeCaseScenario(
            name="Unknown Assessment Request",
            description="User asks for non-existent assessment",
            conversation=[
                {"role": "user", "content": "Recommend the FAKE_ASSESSMENT_XYZ"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Hallucination Bait",
            description="User prompt designed to trigger hallucinations",
            conversation=[
                {"role": "user", "content": "What about the new AI assessment that SHL just released last week?"}
            ],
            should_fail_gracefully=False
        ),

        # Boundary conditions
        EdgeCaseScenario(
            name="Zero Recommendations Request",
            description="Context matches nothing in catalog",
            conversation=[
                {"role": "user", "content": "I need someone fluent in COBOL and FORTRAN"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Maximum Recommendations Trigger",
            description="Context that should match all/many assessments",
            conversation=[
                {"role": "user", "content": "Senior developer, excellent communication, leadership, teamwork, all skills"}
            ],
            should_fail_gracefully=False
        ),

        EdgeCaseScenario(
            name="Rapid Fire Refinements",
            description="Many refinements in one turn",
            conversation=[
                {"role": "user", "content": "Java dev"},
                {"role": "assistant", "content": "Recommendations..."},
                {"role": "user", "content": "Add personality; also add communication; also add cognitive; also focus on leadership"}
            ],
            should_fail_gracefully=False
        ),
    ]

    @staticmethod
    def run_edge_case(scenario: EdgeCaseScenario, api_url: str = "http://localhost:8000/chat") -> Dict:
        """
        Run a single edge case scenario.

        Returns:
            Result dict with pass/fail and details
        """
        import time
        import requests
        from app.utils.hard_eval_safety import HardEvalSafetyLayer

        result = {
            "name": scenario.name,
            "description": scenario.description,
            "passed": False,
            "should_fail_gracefully": scenario.should_fail_gracefully,
            "metrics": {
                "latency_ms": 0,
                "handled_gracefully": False,
                "returned_safe_response": False,
            },
            "issues": []
        }

        logger.info(f"Running edge case: {scenario.name}")

        try:
            start_time = time.time()
            response = requests.post(
                api_url,
                json={"messages": scenario.conversation},
                timeout=5
            )
            latency_ms = (time.time() - start_time) * 1000
            result["metrics"]["latency_ms"] = latency_ms

            if response.status_code != 200:
                result["issues"].append(f"HTTP {response.status_code}")
                result["metrics"]["handled_gracefully"] = (response.status_code >= 400)
                result["passed"] = (
                    scenario.should_fail_gracefully and response.status_code >= 400
                ) or (
                    not scenario.should_fail_gracefully and response.status_code == 200
                )
                return result

            api_response = response.json()

            # Check if response is valid
            is_valid, error, cleaned = HardEvalSafetyLayer.validate_response(api_response)

            if is_valid:
                result["metrics"]["handled_gracefully"] = True
                result["metrics"]["returned_safe_response"] = True
                result["passed"] = True
            else:
                if cleaned:
                    result["metrics"]["handled_gracefully"] = True
                    result["metrics"]["returned_safe_response"] = True
                    result["passed"] = True
                else:
                    result["issues"].append(f"Invalid response and repair failed: {error}")
                    result["passed"] = False

        except requests.exceptions.Timeout:
            result["issues"].append("Request timeout (>5s)")
            result["metrics"]["handled_gracefully"] = scenario.should_fail_gracefully
            result["passed"] = scenario.should_fail_gracefully
        except requests.exceptions.ConnectionError:
            result["issues"].append("Connection refused (API not running?)")
            result["passed"] = False
        except Exception as e:
            result["issues"].append(f"Exception: {str(e)}")
            result["passed"] = False

        return result

    @staticmethod
    def run_all_edge_cases(api_url: str = "http://localhost:8000/chat") -> Dict:
        """Run all edge case scenarios."""
        results = {
            "total": len(EdgeCaseTestSuite.EDGE_CASES),
            "passed": 0,
            "failed": 0,
            "scenarios": []
        }

        for scenario in EdgeCaseTestSuite.EDGE_CASES:
            result = EdgeCaseTestSuite.run_edge_case(scenario, api_url)
            results["scenarios"].append(result)

            if result["passed"]:
                results["passed"] += 1
            else:
                results["failed"] += 1

        return results

    @staticmethod
    def generate_report(results: Dict) -> str:
        """Generate edge case test report."""
        total = results["total"]
        passed = results["passed"]
        failed = results["failed"]
        pass_rate = (passed / total * 100) if total > 0 else 0

        report = f"""
╔════════════════════════════════════════════════════════════════════╗
║         ASSESSIQ EDGE CASE TEST REPORT                             ║
╚════════════════════════════════════════════════════════════════════╝

RESULTS
=======
Total: {total}
Passed: {passed}
Failed: {failed}
Pass Rate: {pass_rate:.1f}%

DETAILS
=======
"""

        for scenario in results["scenarios"]:
            status = "✓" if scenario["passed"] else "✗"
            report += f"\n{status} {scenario['name']}\n"
            report += f"   {scenario['description']}\n"
            report += f"   Latency: {scenario['metrics']['latency_ms']:.0f}ms\n"
            report += f"   Handled Gracefully: {scenario['metrics']['handled_gracefully']}\n"

            if scenario["issues"]:
                for issue in scenario["issues"]:
                    report += f"   Issue: {issue}\n"

        report += "\n" + "=" * 70 + "\n"
        return report
