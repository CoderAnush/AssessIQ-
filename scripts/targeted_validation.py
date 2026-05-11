"""
Targeted validation for frontend, generic clarification, and backend/FastAPI stability.
"""

from __future__ import annotations

import json
import os
import requests

BASE = os.environ.get("TARGET_CHAT_URL", "http://localhost:8000/chat")

TESTS = [
    {"group": "FRONTEND", "query": "frontend developer", "expect_clarify": False},
    {"group": "FRONTEND", "query": "react engineer", "expect_clarify": False},
    {"group": "FRONTEND", "query": "angular developer", "expect_clarify": False},
    {"group": "FRONTEND", "query": "javascript engineer", "expect_clarify": False},
    {"group": "GENERIC", "query": "software engineer", "expect_clarify": True},
    {"group": "GENERIC", "query": "developer", "expect_clarify": True},
    {"group": "GENERIC", "query": "engineer", "expect_clarify": True},
    {"group": "BACKEND", "query": "backend developer", "expect_clarify": False},
    {"group": "BACKEND", "query": "python backend engineer", "expect_clarify": False},
    {"group": "BACKEND", "query": "fastapi developer", "expect_clarify": False},
]

FRONTEND_TERMS = ("frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web")
BACKEND_TERMS = ("backend", "python", "java", "api", "microservice", "fastapi", "django", "flask")
SUPPRESSED_TERMS = ("sales", "account manager", "customer service")


def is_clarification(reply: str, recommendations: list[dict]) -> bool:
    return len(recommendations) == 0 and "?" in (reply or "")


def run() -> int:
    results = []

    for test in TESTS:
        payload = {"messages": [{"role": "user", "content": test["query"]}]}
        response = requests.post(BASE, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        recs = data.get("recommendations", []) or []
        reply = str(data.get("reply", ""))
        names = " | ".join(str(r.get("name", "")) for r in recs)
        names_low = names.lower()
        reply_low = reply.lower()

        clarify = is_clarification(reply, recs)
        has_frontend = any(term in names_low for term in FRONTEND_TERMS)
        has_backend = any(term in names_low for term in BACKEND_TERMS)
        has_sales_leak = any(term in names_low for term in SUPPRESSED_TERMS)
        has_emergency_fallback = any(term in reply_low for term in ("technical issue", "unable to find", "fallback", "error"))

        passed = True
        if test["expect_clarify"] and not clarify:
            passed = False
        if not test["expect_clarify"] and clarify:
            passed = False
        if test["group"] == "FRONTEND" and not has_frontend:
            passed = False
        if test["group"] == "BACKEND" and not has_backend:
            passed = False
        if test["group"] != "GENERIC" and has_sales_leak:
            passed = False
        if has_emergency_fallback:
            passed = False

        results.append(
            {
                "group": test["group"],
                "query": test["query"],
                "pass": passed,
                "clarify": clarify,
                "rec_count": len(recs),
                "sales_leak": has_sales_leak,
                "emergency_fallback": has_emergency_fallback,
                "top_recs": [r.get("name", "") for r in recs[:3]],
                "reply": reply,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    rate = round(100.0 * passed / max(total, 1), 1)

    print(json.dumps(results, indent=2))
    print(f"TARGETED_PASS_RATE={passed}/{total} ({rate}%)")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
