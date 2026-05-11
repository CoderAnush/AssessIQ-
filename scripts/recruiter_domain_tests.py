"""
Comprehensive Recruiter Domain Testing Suite.

Tests role normalization, skill extraction, clarification loops, and domain filtering.
Run with: python scripts/recruiter_domain_tests.py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = float(os.environ.get("SCENARIO_TIMEOUT_SECONDS", "10"))


@dataclass
class Scenario:
    name: str
    messages: List[Dict[str, str]]
    expect_min_recommendations: int = 0
    expect_max_recommendations: int = 10
    expect_reply_contains: Optional[List[str]] = None
    expect_reply_not_contains: Optional[List[str]] = None
    allow_clarification: bool = False


SCENARIOS = [
    # ============ ENGINEERING SCENARIOS ============
    Scenario(
        name="Senior Python Backend Engineer",
        messages=[{"role": "user", "content": "Need a senior Python backend engineer with Django and AWS experience"}],
        expect_min_recommendations=2,
        expect_reply_not_contains=["Java", "Spring", "React", "C#"],
    ),
    Scenario(
        name="Java Developer - Mid Level",
        messages=[{"role": "user", "content": "Junior to mid-level Java developer for Spring Boot microservices"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Python", "Django", "C#", ".NET"],
    ),
    Scenario(
        name="React Frontend Engineer",
        messages=[{"role": "user", "content": "Senior React frontend engineer with TypeScript"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java", "Python Backend", "DevOps"],
    ),
    Scenario(
        name="Data Scientist with SQL and ML",
        messages=[{"role": "user", "content": "Data scientist with SQL and machine learning expertise"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java 8", "Spring", "C#"],
    ),
    Scenario(
        name="DevOps/Cloud Engineer",
        messages=[{"role": "user", "content": "DevOps engineer with Kubernetes and AWS"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Python Coding", "React Development"],
    ),
    Scenario(
        name="QA Automation Engineer",
        messages=[{"role": "user", "content": "QA automation engineer for technical testing"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Customer Service", "Personality Test"],
    ),

    # ============ MANAGEMENT SCENARIOS ============
    Scenario(
        name="Engineering Manager",
        messages=[{"role": "user", "content": "Engineering manager for a backend team"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java 8 Assessment", "Pure Coding"],
    ),
    Scenario(
        name="Product Manager",
        messages=[{"role": "user", "content": "Product manager with analytical and communication focus"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Programming", "Java", "Coding"],
    ),
    Scenario(
        name="Sales Manager Leadership",
        messages=[{"role": "user", "content": "Sales manager role, need leadership and personality assessment"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Programming", "Technical", "Java"],
    ),

    # ============ SALES SCENARIOS ============
    Scenario(
        name="Sales Representative",
        messages=[{"role": "user", "content": "Sales representative with communication and persuasion"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java", "Python", "Programming"],
    ),
    Scenario(
        name="Account Executive",
        messages=[{"role": "user", "content": "Account executive for B2B sales"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Coding", "Programming", "Technical"],
    ),

    # ============ SUPPORT SCENARIOS ============
    Scenario(
        name="Customer Support - Entry Level",
        messages=[{"role": "user", "content": "Entry-level customer support representative"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Advanced Programming", "Java Development"],
    ),
    Scenario(
        name="Technical Support Specialist",
        messages=[{"role": "user", "content": "Technical support specialist for troubleshooting"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Pure Coding Test", "Java Developer"],
    ),

    # ============ VAGUE QUERY SCENARIOS ============
    Scenario(
        name="Generic Developer Prompt",
        messages=[{"role": "user", "content": "Need a developer"}],
        expect_min_recommendations=0,
        allow_clarification=True,
    ),
    Scenario(
        name="Vague Manager Query",
        messages=[{"role": "user", "content": "Manager role needed"}],
        expect_min_recommendations=0,
        allow_clarification=True,
    ),

    # ============ CLARIFICATION LOOP FIX SCENARIOS ============
    Scenario(
        name="Clarification Follow-up - Senior",
        messages=[
            {"role": "user", "content": "Need a Python backend engineer"},
            {"role": "assistant", "content": "What seniority level?"},
            {"role": "user", "content": "Senior"},
        ],
        expect_min_recommendations=2,
        expect_reply_not_contains=["What seniority"],  # Should NOT ask again
    ),
    Scenario(
        name="Clarification Follow-up - Seniority",
        messages=[
            {"role": "user", "content": "Manager role"},
            {"role": "assistant", "content": "What kind of manager?"},
            {"role": "user", "content": "Sales manager"},
        ],
        expect_min_recommendations=1,
        expect_reply_not_contains=["What kind", "What type"],  # Should NOT ask again
    ),

    # ============ DOMAIN ISOLATION SCENARIOS ============
    Scenario(
        name="Python Should NOT Return Java",
        messages=[{"role": "user", "content": "Python backend engineer"}],
        expect_reply_not_contains=["Java 8", "Spring Framework", "J2EE"],
    ),
    Scenario(
        name="Sales Should NOT Return Coding",
        messages=[{"role": "user", "content": "Sales director assessment"}],
        expect_reply_not_contains=["Java", "Python", "Coding", "Programming"],
    ),
    Scenario(
        name="Frontend Should NOT Return Backend",
        messages=[{"role": "user", "content": "React frontend engineer"}],
        expect_reply_not_contains=["Backend", "Java", "Spring"],
    ),
    Scenario(
        name="Data Science NOT Java Backend",
        messages=[{"role": "user", "content": "Data scientist with ML"}],
        expect_reply_not_contains=["Java 8", "Spring", "Backend Development"],
    ),

    # ============ MULTI-TURN SCENARIOS ============
    Scenario(
        name="Multi-turn Refinement",
        messages=[
            {"role": "user", "content": "Need a backend engineer"},
            {"role": "assistant", "content": "Python or Java?"},
            {"role": "user", "content": "Python with senior level"},
        ],
        expect_min_recommendations=2,
    ),

    # ============ EDGE CASES ============
    Scenario(
        name="Graduate Trainee",
        messages=[{"role": "user", "content": "Graduate trainee assessment"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Senior", "Expert"],
    ),
    Scenario(
        name="Executive Assessment",
        messages=[{"role": "user", "content": "Executive leadership assessment for C-level"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Entry-level", "Programming"],
    ),
]

FORBIDDEN_FALLBACKS = {
    "global skills development report",
    "global skills assessment",
    "entry level technical support solution",
    ".net framework 4.5",
    "adobe experience manager (new)",
    "adobe photoshop cc",
}


def send_chat(messages: List[Dict[str, str]]) -> Dict:
    response = requests.post(
        f"{BACKEND_URL}/chat",
        json={"messages": messages},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def validate_scenario(scenario: Scenario, payload: Dict) -> List[str]:
    errors: List[str] = []
    recs = payload.get("recommendations", [])
    reply = str(payload.get("reply", ""))

    # Check recommendation count
    if not (scenario.expect_min_recommendations <= len(recs) <= scenario.expect_max_recommendations):
        errors.append(
            f"recommendation count {len(recs)} not in [{scenario.expect_min_recommendations}, {scenario.expect_max_recommendations}]"
        )

    # Check clarification expectation
    if not scenario.allow_clarification and len(recs) == 0:
        errors.append("expected recommendations but got clarification")

    # Check reply fragments
    for fragment in scenario.expect_reply_contains or []:
        if fragment.lower() not in reply.lower():
            errors.append(f"reply missing expected fragment: {fragment}")

    for fragment in scenario.expect_reply_not_contains or []:
        if fragment.lower() in reply.lower():
            errors.append(f"reply contained forbidden fragment: {fragment}")

    # Check for fallback assessments
    rec_names = {str(item.get("name", "")).lower() for item in recs}
    if rec_names.intersection(FORBIDDEN_FALLBACKS):
        errors.append(f"generic fallback item returned: {sorted(rec_names.intersection(FORBIDDEN_FALLBACKS))}")

    return errors


def main() -> int:
    print("=" * 100)
    print("AssessIQ Recruiter Domain Testing Suite")
    print(f"Backend: {BACKEND_URL}")
    print(f"Total Scenarios: {len(SCENARIOS)}")
    print("=" * 100)

    passed = 0
    failed = 0
    failed_scenarios = []

    for scenario in SCENARIOS:
        print(f"\n[TEST] {scenario.name}")
        start = time.time()
        try:
            payload = send_chat(scenario.messages)
            latency = time.time() - start
            errors = validate_scenario(scenario, payload)

            if latency > 30:
                errors.append(f"latency exceeded 30 seconds: {latency:.2f}s")

            recs = payload.get("recommendations", [])
            if errors:
                failed += 1
                failed_scenarios.append(scenario.name)
                print(f"[FAIL]")
                for error in errors:
                    print(f"   - {error}")
                print(f"   Reply: {payload.get('reply', '')[:100]}")
                if recs:
                    print(f"   Recommendations: {[item.get('name')[:40] for item in recs[:2]]}")
            else:
                passed += 1
                print(f"[PASS] ({latency:.2f}s)")
                if recs:
                    print(f"   Recommendations: {[item.get('name')[:40] for item in recs[:2]]}")
                else:
                    print(f"   (Clarification expected)")
        except Exception as exc:
            failed += 1
            failed_scenarios.append(scenario.name)
            print(f"[FAIL] - request error: {exc}")

    print("\n" + "=" * 100)
    print(f"RESULT: {passed} passed, {failed} failed out of {len(SCENARIOS)} scenarios")
    if failed > 0:
        print(f"\nFailed scenarios:")
        for name in failed_scenarios:
            print(f"  - {name}")
    print("=" * 100)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
