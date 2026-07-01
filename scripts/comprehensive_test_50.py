"""
Comprehensive Test Suite - 50+ Scenarios for AssessIQ
Tests role recognition, language filtering, and correct recommendations.
"""

import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

import requests

# Backend URL (defaults to local compliant build)
BASE_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
CHAT_URL = f"{BASE_URL}/chat"
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
REPORT_PATH = ARTIFACTS_DIR / "scenario_50_report.md"
JSON_PATH = Path(__file__).resolve().parents[1] / "test_results_50.json"


class TestCategory(Enum):
    JAVA = "Java Roles"
    PYTHON = "Python Roles"
    DEVOPS = "DevOps/Cloud"
    FRONTEND = "Frontend"
    DATASCIENCE = "Data Science/ML"
    QA = "QA/Testing"
    MANAGEMENT = "Management"
    GENERIC = "Generic/Clarification"
    EDGE = "Edge Cases"


@dataclass
class TestCase:
    query: str
    category: TestCategory
    expected_type: str
    should_clarify: bool = False


TEST_CASES = [
    TestCase("Senior Java Engineer", TestCategory.JAVA, "java"),
    TestCase("java backend developer", TestCategory.JAVA, "java"),
    TestCase("Junior Java Developer", TestCategory.JAVA, "java"),
    TestCase("Java Spring Boot Engineer", TestCategory.JAVA, "java"),
    TestCase("Lead Java Architect", TestCategory.JAVA, "java"),
    TestCase("Entry level Java programmer", TestCategory.JAVA, "java"),
    TestCase("Java microservices developer", TestCategory.JAVA, "java"),
    TestCase("Senior Java Backend Engineer", TestCategory.JAVA, "java"),
    TestCase("Java Enterprise Developer", TestCategory.JAVA, "java"),
    TestCase("Staff Java Engineer", TestCategory.JAVA, "java"),
    TestCase("Senior Python Engineer", TestCategory.PYTHON, "python"),
    TestCase("python backend developer", TestCategory.PYTHON, "python"),
    TestCase("Django Developer", TestCategory.PYTHON, "python"),
    TestCase("Flask Backend Engineer", TestCategory.PYTHON, "python"),
    TestCase("Python Data Engineer", TestCategory.PYTHON, "python"),
    TestCase("Junior Python Developer", TestCategory.PYTHON, "python"),
    TestCase("FastAPI Developer", TestCategory.PYTHON, "python"),
    TestCase("Python Backend Architect", TestCategory.PYTHON, "python"),
    TestCase("Senior Python Backend", TestCategory.PYTHON, "python"),
    TestCase("Python Microservices", TestCategory.PYTHON, "python"),
    TestCase("DevOps Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("SRE Site Reliability Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Cloud Infrastructure Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Kubernetes Administrator", TestCategory.DEVOPS, "devops"),
    TestCase("AWS Cloud Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Platform Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Infrastructure Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Docker Specialist", TestCategory.DEVOPS, "devops"),
    TestCase("Frontend Developer", TestCategory.FRONTEND, "frontend"),
    TestCase("React Developer", TestCategory.FRONTEND, "frontend"),
    TestCase("Angular Engineer", TestCategory.FRONTEND, "frontend"),
    TestCase("Senior Frontend Engineer", TestCategory.FRONTEND, "frontend"),
    TestCase("UI Developer", TestCategory.FRONTEND, "frontend"),
    TestCase("Data Scientist", TestCategory.DATASCIENCE, "data"),
    TestCase("Machine Learning Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("ML Ops Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("Data Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("AI Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("QA Engineer", TestCategory.QA, "qa"),
    TestCase("SDET Software Developer in Test", TestCategory.QA, "qa"),
    TestCase("Test Automation Engineer", TestCategory.QA, "qa"),
    TestCase("Senior QA Analyst", TestCategory.QA, "qa"),
    TestCase("Engineering Manager", TestCategory.MANAGEMENT, "management"),
    TestCase("Tech Lead", TestCategory.MANAGEMENT, "management"),
    TestCase("Product Manager", TestCategory.MANAGEMENT, "management"),
    TestCase("CTO Chief Technology Officer", TestCategory.MANAGEMENT, "management"),
    TestCase("developer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("software engineer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("programmer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("need assessments", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("Full Stack Developer", TestCategory.EDGE, "fullstack"),
    TestCase("Backend Developer", TestCategory.EDGE, "backend"),
    TestCase("Mobile Developer", TestCategory.EDGE, "mobile"),
    TestCase("Embedded Systems Engineer", TestCategory.EDGE, "embedded"),
]


def test_single_case(test_case: TestCase) -> Dict[str, Any]:
    """Test a single scenario and return results."""
    try:
        response = requests.post(
            CHAT_URL,
            json={"messages": [{"role": "user", "content": test_case.query}]},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        recommendations = data.get("recommendations", [])
        reply = data.get("reply", "")

        is_clarification = len(recommendations) == 0 and any(
            w in reply.lower() for w in ("what", "specific", "role", "seniority", "hiring")
        )

        recommendation_names = [r.get("name", "") for r in recommendations]
        recommendation_urls = [r.get("url", "") for r in recommendations]
        test_types = [r.get("test_type", "") for r in recommendations]

        first_rec = recommendation_names[0] if recommendation_names else None
        all_names = " ".join(n.lower() for n in recommendation_names[:5])
        has_java = "java" in all_names
        has_python = "python" in all_names
        has_devops = any(
            w in all_names
            for w in ("docker", "kubernetes", "aws", "cloud", "terraform", "infrastructure")
        )

        return {
            "query": test_case.query,
            "category": test_case.category.value,
            "expected": test_case.expected_type,
            "should_clarify": test_case.should_clarify,
            "is_clarification": is_clarification,
            "rec_count": len(recommendations),
            "first_rec": first_rec,
            "recommendation_names": recommendation_names,
            "recommendation_urls": recommendation_urls,
            "test_types": test_types,
            "reply_preview": reply[:200],
            "has_java": has_java,
            "has_python": has_python,
            "has_devops": has_devops,
            "success": False,
        }
    except Exception as e:
        return {
            "query": test_case.query,
            "category": test_case.category.value,
            "error": str(e),
            "success": False,
        }


def evaluate_result(result: Dict[str, Any], test_case: TestCase) -> bool:
    """Determine if test passed based on expectations."""
    if "error" in result:
        return False

    if test_case.should_clarify:
        return result.get("is_clarification", False)

    if result.get("rec_count", 0) == 0:
        return False

    expected = test_case.expected_type

    if expected == "java":
        return result.get("has_java") and not result.get("has_python")
    if expected == "python":
        return not result.get("has_java")
    if expected == "devops":
        return result.get("has_devops") or not result.get("has_java")
    if expected in ["frontend", "data", "qa", "management"]:
        return not result.get("has_java")
    return result.get("rec_count", 0) > 0


def write_markdown_report(results: List[Dict[str, Any]], passed: int, failed: int) -> None:
    """Write human-readable scenario report."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AssessIQ 50-Scenario Report",
        "",
        f"**Backend:** `{BASE_URL}`",
        f"**Total:** {len(results)} | **Passed:** {passed} | **Failed:** {failed}",
        f"**Success rate:** {passed / len(results) * 100:.1f}%",
        "",
    ]

    for i, r in enumerate(results, 1):
        status = "PASS" if r.get("success") else "FAIL"
        lines.append(f"## {i}. [{status}] {r.get('query', '')[:80]}")
        lines.append("")
        lines.append(f"- **Category:** {r.get('category', 'N/A')}")
        lines.append(f"- **Expected:** {r.get('expected', 'N/A')}")
        if r.get("error"):
            lines.append(f"- **Error:** {r['error']}")
        elif r.get("is_clarification"):
            lines.append("- **Result:** Clarification (no recommendations)")
            lines.append(f"- **Reply:** {r.get('reply_preview', '')[:150]}...")
        else:
            lines.append(f"- **Recommendations:** {r.get('rec_count', 0)}")
            names = r.get("recommendation_names", [])
            urls = r.get("recommendation_urls", [])
            types = r.get("test_types", [])
            if names:
                lines.append("")
                lines.append("| # | Name | Type | URL |")
                lines.append("|---|------|------|-----|")
                for j, (name, url, tt) in enumerate(zip(names, urls, types), 1):
                    lines.append(f"| {j} | {name} | {tt} | {url} |")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_all_tests() -> List[Dict[str, Any]]:
    """Run all test cases and generate report."""
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE - 50+ SCENARIOS")
    print("=" * 80)
    print(f"Backend: {BASE_URL}")
    print(f"Total tests: {len(TEST_CASES)}")
    print("=" * 80)

    results = []
    passed = 0
    failed = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] Testing: {test_case.query[:50]}...")

        result = test_single_case(test_case)
        is_success = evaluate_result(result, test_case)
        result["success"] = is_success
        results.append(result)

        if is_success:
            passed += 1
            status = "[PASS]"
        else:
            failed += 1
            status = "[FAIL]"

        if result.get("error"):
            print(f"  {status} | Error: {result['error']}")
        elif result.get("is_clarification"):
            print(f"  {status} | Clarification requested")
        elif result.get("rec_count", 0) > 0:
            first = (result.get("first_rec") or "N/A")[:40]
            print(f"  {status} | {result['rec_count']} recs | First: {first}")
        else:
            print(f"  {status} | No recommendations")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total: {len(TEST_CASES)} | Passed: {passed} | Failed: {failed}")
    print(f"Success Rate: {passed / len(TEST_CASES) * 100:.1f}%")

    write_markdown_report(results, passed, failed)
    print(f"\nReport saved to {REPORT_PATH}")

    return results


if __name__ == "__main__":
    results = run_all_tests()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {JSON_PATH}")
    sys.exit(0 if all(r.get("success") for r in results) else 1)
