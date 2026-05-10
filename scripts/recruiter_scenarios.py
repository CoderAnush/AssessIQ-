"""
Recruiter scenario runner for AssessIQ.

This is a lightweight manual validation script for representative hiring flows.
It uses the same stateless /chat contract as the evaluator suite.
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


SCENARIOS = [
    Scenario(
        name="Sales executive",
        messages=[{"role": "user", "content": "Need a sales executive assessment for a quota-carrying role. Prioritize persuasion, communication, and personality fit."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Retail store manager",
        messages=[{"role": "user", "content": "Need a retail store manager assessment for people leadership, operations, and communication."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="HR business partner",
        messages=[{"role": "user", "content": "Need an HR business partner assessment focused on communication, judgment, and stakeholder management."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Marketing manager",
        messages=[{"role": "user", "content": "Need a marketing manager assessment for communication, analytical thinking, and leadership."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Call center hiring",
        messages=[{"role": "user", "content": "Need a call center hiring assessment for customer support, communication, and empathy."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Cybersecurity analyst",
        messages=[{"role": "user", "content": "Need a cybersecurity analyst assessment with technical depth, problem solving, and risk awareness."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", "Business Communication (adaptive)"],
    ),
    Scenario(
        name="Cloud engineer",
        messages=[{"role": "user", "content": "Need a cloud engineer assessment for infrastructure, AWS, and technical screening."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", "Business Communication (adaptive)"],
    ),
    Scenario(
        name="Executive assistant",
        messages=[{"role": "user", "content": "Need an executive assistant assessment for organization, communication, judgment, and executive support."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Product manager",
        messages=[{"role": "user", "content": "Need a product manager assessment for communication, analytical thinking, prioritization, and cross-functional leadership."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Graduate trainee",
        messages=[{"role": "user", "content": "Need a graduate trainee assessment for learning agility, cognitive ability, and analytical potential."}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Global Skills Development Report", ".NET Framework 4.5"],
    ),
    Scenario(
        name="Data Science",
        messages=[{"role": "user", "content": "Need a data scientist with machine learning and SQL skills"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java", "Spring", "J2EE"],
    ),
    Scenario(
        name="Python Backend",
        messages=[{"role": "user", "content": "Need a senior Python backend engineer"}],
        expect_min_recommendations=1,
        expect_reply_not_contains=["Java", "Spring", "J2EE"],
    ),
    Scenario(
        name="Sales Personality",
        messages=[{"role": "user", "content": "Need personality tests for sales hiring"}],
        expect_min_recommendations=0, # Expect clarification
        expect_reply_not_contains=["Coding", "Programming", "Java", "Python"],
    ),
    Scenario(
        name="Engineering Leadership",
        messages=[{"role": "user", "content": "Need assessments for engineering managers"}],
        expect_min_recommendations=0, # Expect clarification
        expect_reply_not_contains=["Coding", "Multiple Choice", "Java"],
    ),
]

GENERIC_FALLBACK_NAMES = {
    "global skills development report",
    "global skills assessment",
    "entry level technical support solution",
    ".net framework 4.5",
    "adobe experience manager (new)",
    "adobe photoshop cc",
    "bank operations supervisor - short form",
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

    if not (scenario.expect_min_recommendations <= len(recs) <= scenario.expect_max_recommendations):
        errors.append(
            f"recommendation count {len(recs)} not in [{scenario.expect_min_recommendations}, {scenario.expect_max_recommendations}]"
        )

    for fragment in scenario.expect_reply_contains or []:
        if fragment.lower() not in reply.lower():
            errors.append(f"reply missing expected fragment: {fragment}")

    for fragment in scenario.expect_reply_not_contains or []:
        if fragment.lower() in reply.lower():
            errors.append(f"reply contained forbidden fragment: {fragment}")

    rec_names = {str(item.get("name", "")).lower() for item in recs}
    if rec_names.intersection(GENERIC_FALLBACK_NAMES):
        errors.append(f"generic fallback item returned: {sorted(rec_names.intersection(GENERIC_FALLBACK_NAMES))}")

    if any(name.startswith("adobe") or name.startswith(".net") for name in rec_names):
        errors.append("irrelevant technical fallback item returned")

    return errors


def main() -> int:
    print("=" * 80)
    print("AssessIQ Recruiter Scenario Runner")
    print(f"Backend: {BACKEND_URL}")
    print(f"Scenarios: {len(SCENARIOS)}")
    print("=" * 80)

    passed = 0
    failed = 0

    for scenario in SCENARIOS:
        print(f"\nSCENARIO: {scenario.name}")
        start = time.time()
        try:
            payload = send_chat(scenario.messages)
            latency = time.time() - start
            errors = validate_scenario(scenario, payload)
            if latency > 30:
                errors.append(f"latency exceeded 30 seconds: {latency:.2f}s")
            if errors:
                failed += 1
                print("FAIL")
                for error in errors:
                    print(f" - {error}")
                print(f" reply: {payload.get('reply', '')}")
            else:
                passed += 1
                print(f"PASS ({latency:.2f}s)")
                print(f" reply: {payload.get('reply', '')[:180]}")
                print(f" recommendations: {[item.get('name') for item in payload.get('recommendations', [])[:3]]}")
        except Exception as exc:
            failed += 1
            print(f"FAIL - request error: {exc}")

    print("\n" + "=" * 80)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 80)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
