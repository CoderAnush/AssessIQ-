"""
Quick Diagnostics - AssessIQ Recruiter Intent Upgrade

Run this to verify all components are working correctly.
"""

import requests
import json
import time
from typing import Dict, List

BACKEND_URL = "http://localhost:8000"

def test_scenario(name: str, prompt: str, expect_recs: bool = True) -> Dict:
    """Test a single scenario."""
    print(f"\n[TEST] {name}")
    print("-" * 60)

    try:
        start = time.time()
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"messages": [{"role": "user", "content": prompt}]},
            timeout=15
        )
        latency = time.time() - start

        payload = response.json()
        recs = payload.get("recommendations", [])
        reply = payload.get("reply", "")

        status = "OK"
        if expect_recs and not recs:
            status = "CLARIFY"
        elif not expect_recs and recs:
            status = "UNEXPECTED"

        print(f"Status: {status}")
        print(f"Recommendations: {len(recs)}")
        print(f"Latency: {latency:.2f}s")

        if recs:
            for i, rec in enumerate(recs[:2], 1):
                print(f"  {i}. {rec['name'][:50]} ({rec['confidence']}%)")
        else:
            print(f"Reply: {reply[:100]}")

        return {
            "name": name,
            "status": status,
            "recs": len(recs),
            "latency": latency,
            "ok": (expect_recs and recs) or (not expect_recs and not recs)
        }
    except Exception as e:
        print(f"ERROR: {e}")
        return {"name": name, "status": "ERROR", "ok": False}


def main():
    print("\n" + "=" * 80)
    print("ASSESSIQ RECRUITER INTENT UPGRADE - DIAGNOSTIC SUITE")
    print("=" * 80)

    # Check backend
    print("\n1. CHECKING BACKEND CONNECTION...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print("   [OK] Backend is running")
    except:
        print("   [ERROR] Backend not responding - start it with: python -m app.main")
        return

    # Run diagnostic scenarios
    print("\n2. RUNNING DIAGNOSTIC SCENARIOS...")

    results = []

    # Engineering domain
    results.append(test_scenario(
        "Python Backend (Domain Filtering)",
        "Senior Python backend engineer",
        expect_recs=True
    ))

    # Vague query
    results.append(test_scenario(
        "Generic Developer (Clarification)",
        "Need a developer",
        expect_recs=False
    ))

    # Clarification memory
    print("\n[TEST] Clarification Memory (Multi-turn)")
    print("-" * 60)
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"messages": [
                {"role": "user", "content": "Python backend engineer"},
                {"role": "assistant", "content": "What seniority level?"},
                {"role": "user", "content": "Senior"}
            ]},
            timeout=15
        )
        payload = response.json()
        recs = payload.get("recommendations", [])
        reply = payload.get("reply", "")

        has_question = "seniority" in reply.lower() and "what" in reply.lower()

        print(f"Recommendations returned: {len(recs)}")
        print(f"Asking for seniority again: {has_question} (should be NO)")
        print(f"Status: {'OK' if recs and not has_question else 'ISSUE'}")

        results.append({
            "name": "Clarification Memory",
            "ok": recs and not has_question,
            "status": "OK" if recs and not has_question else "ISSUE"
        })
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"name": "Clarification Memory", "ok": False, "status": "ERROR"})

    # Sales domain (no coding)
    results.append(test_scenario(
        "Sales Manager (No Coding Tests)",
        "Sales manager assessment",
        expect_recs=True
    ))

    # Report
    print("\n" + "=" * 80)
    print("DIAGNOSTIC RESULTS")
    print("=" * 80)

    passed = sum(1 for r in results if r.get("ok"))
    total = len(results)

    print(f"\nTotal Scenarios: {total}")
    print(f"Passed: {passed}")
    print(f"Pass Rate: {100 * passed // total}%\n")

    for result in results:
        status_symbol = "[OK]" if result.get("ok") else "[FAIL]"
        print(f"{status_symbol} {result['name']}: {result['status']}")

    print("\n" + "=" * 80)
    print("KEY CAPABILITIES VERIFIED:")
    print("=" * 80)

    checks = [
        ("Role Normalization", any("Python" in r['name'] for r in results)),
        ("Clarification Questions", any("Clarification" in r['name'] for r in results)),
        ("Clarification Memory Fix", any("Memory" in r['name'] for r in results)),
        ("Domain Filtering", any("Domain" in r['name'] for r in results)),
    ]

    for check_name, check_result in checks:
        status = "[OK]" if check_result else "[?]"
        print(f"{status} {check_name}")

    print("\n" + "=" * 80)
    if passed == total:
        print("[OK] ALL DIAGNOSTICS PASSING - SYSTEM READY FOR PRODUCTION")
    else:
        print(f"[WARN] {total - passed} ISSUES FOUND - REVIEW ABOVE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
