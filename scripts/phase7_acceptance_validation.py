"""
Phase 7 acceptance validation for targeted frontend/generic/backend checks.
"""

from __future__ import annotations

import json
import os
import requests

BASE = os.environ.get("TARGET_CHAT_URL", "http://localhost:8010/chat")

TESTS = [
    ("FRONTEND", "frontend developer"),
    ("FRONTEND", "react engineer"),
    ("FRONTEND", "angular developer"),
    ("FRONTEND", "javascript engineer"),
    ("GENERIC", "software engineer"),
    ("GENERIC", "developer"),
    ("GENERIC", "engineer"),
    ("BACKEND", "backend developer"),
    ("BACKEND", "python backend engineer"),
    ("BACKEND", "fastapi developer"),
]

FRONTEND_TERMS = ("frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web")
HARD_SUPPRESS = ("sales", "account manager", "customer service", "reservation agent", "cashier", "clerk")


def classify(test_group: str, query: str, data: dict) -> tuple[bool, dict]:
    recs = data.get("recommendations", []) or []
    reply = str(data.get("reply", ""))
    names = " | ".join(str(r.get("name", "")) for r in recs)
    names_low = names.lower()
    reply_low = reply.lower()

    is_clarify = len(recs) == 0 and "?" in reply
    has_frontend_signal = any(t in names_low for t in FRONTEND_TERMS)
    has_suppressed_leak = any(t in names_low for t in HARD_SUPPRESS)
    has_emergency = any(t in reply_low for t in ("technical issue", "pipeline error", "unable to find", "fallback", "traceback"))

    passed = True
    if test_group == "GENERIC":
        if not is_clarify:
            passed = False
    else:
        if is_clarify:
            passed = False
        if has_suppressed_leak:
            passed = False

    if test_group == "FRONTEND" and not has_frontend_signal:
        passed = False

    if has_emergency:
        passed = False

    return passed, {
        "group": test_group,
        "query": query,
        "pass": passed,
        "clarify": is_clarify,
        "rec_count": len(recs),
        "suppressed_leak": has_suppressed_leak,
        "emergency_fallback": has_emergency,
        "top_recs": [r.get("name", "") for r in recs[:3]],
        "reply": reply,
    }


def run() -> int:
    rows = []
    for group, query in TESTS:
        payload = {"messages": [{"role": "user", "content": query}]}
        resp = requests.post(BASE, json=payload, timeout=30)
        resp.raise_for_status()
        passed, row = classify(group, query, resp.json())
        rows.append(row)

    passed_count = sum(1 for r in rows if r["pass"])
    total = len(rows)
    rate = round(100.0 * passed_count / total, 1)

    print(json.dumps(rows, indent=2))
    print(f"PHASE7_PASS_RATE={passed_count}/{total} ({rate}%)")

    return 0 if passed_count == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
