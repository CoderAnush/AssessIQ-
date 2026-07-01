"""
Comprehensive Test Suite - 50+ Scenarios for AssessIQ
Tests role recognition, domain ranking, and correct recommendations.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

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
    must_contain_any: List[str] = field(default_factory=list)
    forbidden_terms: List[str] = field(default_factory=list)
    top_k_must_contain: Optional[str] = None


def _tc(
    query: str,
    category: TestCategory,
    expected_type: str,
    should_clarify: bool = False,
    must_contain_any: Optional[List[str]] = None,
    forbidden_terms: Optional[List[str]] = None,
    top_k_must_contain: Optional[str] = None,
) -> TestCase:
    return TestCase(
        query=query,
        category=category,
        expected_type=expected_type,
        should_clarify=should_clarify,
        must_contain_any=must_contain_any or [],
        forbidden_terms=forbidden_terms or [],
        top_k_must_contain=top_k_must_contain,
    )


_JAVA_FORBIDDEN = ["react", "angular", "javascript"]
_PYTHON_FORBIDDEN = ["spring", "java ee"]
_DEVOPS_MUST = ["linux", "cloud", "devops", "kubernetes", "docker", "terraform", "infrastructure", "programming", "automata"]
_DEVOPS_FORBIDDEN = ["front end", "react", "angular"]
_FRONTEND_MUST = ["react", "javascript", "angular", "front end", "html", "css", "automata front"]
_FRONTEND_FORBIDDEN = ["spring", "java ee", "core java"]
_DATA_MUST = ["data science", "automata data science", "ai skills", "python", "sql", "data warehousing", "statistics"]
_DATA_FORBIDDEN = ["front end", "selenium", "technical support", "xaml", "mechanical"]
_QA_MUST = ["test", "qa", "quality", "selenium", "automation"]
_MANAGEMENT_MUST = ["opq", "leadership", "competency", "manager", "development"]

TEST_CASES: List[TestCase] = []
_JAVA_QUERIES = [
    "Senior Java Engineer", "java backend developer", "Junior Java Developer",
    "Java Spring Boot Engineer", "Lead Java Architect", "Entry level Java programmer",
    "Java microservices developer", "Senior Java Backend Engineer",
    "Java Enterprise Developer", "Staff Java Engineer",
]
for _q in _JAVA_QUERIES:
    TEST_CASES.append(_tc(_q, TestCategory.JAVA, "java", must_contain_any=["java", "automata"], forbidden_terms=_JAVA_FORBIDDEN))

TEST_CASES.extend([
    _tc("Senior Python Engineer", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"], forbidden_terms=["java ee", "spring"]),
    _tc("python backend developer", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"], forbidden_terms=["java ee"]),
    _tc("Django Developer", TestCategory.PYTHON, "python", must_contain_any=["python", "django", "automata"], forbidden_terms=["java ee", "spring"]),
    _tc("Flask Backend Engineer", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
    _tc("Python Data Engineer", TestCategory.PYTHON, "python", must_contain_any=["python", "data", "sql", "automata"]),
    _tc("Junior Python Developer", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
    _tc("FastAPI Developer", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
    _tc("Python Backend Architect", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
    _tc("Senior Python Backend", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
    _tc("Python Microservices", TestCategory.PYTHON, "python", must_contain_any=["python", "automata"]),
])
for _q in [
    "DevOps Engineer", "SRE Site Reliability Engineer", "Cloud Infrastructure Engineer",
    "Kubernetes Administrator", "AWS Cloud Engineer", "Platform Engineer",
    "Infrastructure Engineer", "Docker Specialist",
]:
    TEST_CASES.append(_tc(_q, TestCategory.DEVOPS, "devops", must_contain_any=_DEVOPS_MUST, forbidden_terms=_DEVOPS_FORBIDDEN))
for _q in [
    "Frontend Developer", "React Developer", "Angular Engineer",
    "Senior Frontend Engineer", "UI Developer",
]:
    TEST_CASES.append(_tc(_q, TestCategory.FRONTEND, "frontend", must_contain_any=_FRONTEND_MUST, forbidden_terms=_FRONTEND_FORBIDDEN))
TEST_CASES.extend([
    _tc("Data Scientist", TestCategory.DATASCIENCE, "data",
        must_contain_any=["data science", "automata data science", "statistics"],
        forbidden_terms=["mechanical", "react", "front end"],
        top_k_must_contain="data science"),
    _tc("Machine Learning Engineer", TestCategory.DATASCIENCE, "data",
        must_contain_any=["data science", "automata data science", "ai skills", "machine learning"],
        forbidden_terms=["mechanical", "front end"],
        top_k_must_contain="data science"),
    _tc("ML Ops Engineer", TestCategory.DATASCIENCE, "data",
        must_contain_any=["ai skills", "sql", "data science", "automata"],
        forbidden_terms=["xaml", ".net", "front end"],
        top_k_must_contain="ai skills"),
    _tc("Data Engineer", TestCategory.DATASCIENCE, "data",
        must_contain_any=["data science", "sql", "data warehousing", "automata data science"],
        forbidden_terms=["data entry", "front end"],
        top_k_must_contain="data"),
    _tc("AI Engineer", TestCategory.DATASCIENCE, "data",
        must_contain_any=["ai skills", "data science", "automata data science"],
        forbidden_terms=["front end", "selenium", "technical support"]),
])
for _q in [
    "QA Engineer", "SDET Software Developer in Test",
    "Test Automation Engineer", "Senior QA Analyst",
]:
    TEST_CASES.append(_tc(_q, TestCategory.QA, "qa", must_contain_any=_QA_MUST, forbidden_terms=["manufacturing", "contact centre"]))
for _q in [
    "Engineering Manager", "Tech Lead", "Product Manager", "CTO Chief Technology Officer",
]:
    TEST_CASES.append(_tc(_q, TestCategory.MANAGEMENT, "management", must_contain_any=_MANAGEMENT_MUST))
TEST_CASES.extend([
    _tc("developer", TestCategory.GENERIC, "any", should_clarify=True),
    _tc("software engineer", TestCategory.GENERIC, "any", should_clarify=True),
    _tc("programmer", TestCategory.GENERIC, "any", should_clarify=True),
    _tc("need assessments", TestCategory.GENERIC, "any", should_clarify=True),
    _tc("Full Stack Developer", TestCategory.EDGE, "fullstack",
        must_contain_any=["full stack", "react", "java", "python", "javascript", "automata", "backend", "front"]),
    _tc("Backend Developer", TestCategory.EDGE, "backend",
        must_contain_any=["backend", "java", "python", "automata", "developer"]),
    _tc("Mobile Developer", TestCategory.EDGE, "mobile",
        must_contain_any=["mobile", "android", "ios", "developer", "automata", "javascript"]),
    _tc("Embedded Systems Engineer", TestCategory.EDGE, "embedded",
        must_contain_any=["embedded", "linux", "c ", "programming", "automata", "networking"]),
])


def _names_blob(names: List[str], k: int = 5) -> str:
    return " ".join(n.lower() for n in names[:k])


def _check_leakage(names: List[str], forbidden: List[str]) -> List[str]:
    violations = []
    blob = _names_blob(names, 7)
    for term in forbidden:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", blob):
            violations.append(term)
    return violations


def test_single_case(test_case: TestCase) -> Dict[str, Any]:
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
            w in reply.lower() for w in ("what", "specific", "role", "seniority", "hiring", "clarify", "which")
        )

        recommendation_names = [r.get("name", "") for r in recommendations]
        recommendation_urls = [r.get("url", "") for r in recommendations]
        test_types = [r.get("test_type", "") for r in recommendations]

        all_names = _names_blob(recommendation_names)
        has_java = bool(re.search(r"\bjava\b", all_names)) and "javascript" not in all_names.replace("java", "", 1)
        has_python = "python" in all_names
        has_devops = any(w in all_names for w in ("docker", "kubernetes", "aws", "cloud", "terraform", "infrastructure", "linux"))

        return {
            "query": test_case.query,
            "category": test_case.category.value,
            "expected": test_case.expected_type,
            "should_clarify": test_case.should_clarify,
            "is_clarification": is_clarification,
            "rec_count": len(recommendations),
            "first_rec": recommendation_names[0] if recommendation_names else None,
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
    if "error" in result:
        return False

    if test_case.should_clarify:
        return result.get("is_clarification", False) and result.get("rec_count", 0) == 0

    names = result.get("recommendation_names", [])
    if result.get("rec_count", 0) == 0:
        return False

    if test_case.forbidden_terms:
        if _check_leakage(names, test_case.forbidden_terms):
            return False

    if test_case.must_contain_any:
        blob = _names_blob(names)
        if not any(term.lower() in blob for term in test_case.must_contain_any):
            return False

    if test_case.top_k_must_contain:
        first = (result.get("first_rec") or "").lower()
        if test_case.top_k_must_contain.lower() not in first:
            return False

    expected = test_case.expected_type
    if expected == "java":
        return result.get("has_java") and not result.get("has_python")
    if expected == "python":
        return not result.get("has_java") or "python" in _names_blob(names)
    if expected == "devops":
        return result.get("has_devops") or not result.get("has_java")
    if expected in ["frontend", "data", "qa", "management"]:
        return True
    return result.get("rec_count", 0) > 0


def write_markdown_report(results: List[Dict[str, Any]], passed: int, failed: int) -> None:
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
            lines.append(f"- **First:** {r.get('first_rec', 'N/A')}")
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
