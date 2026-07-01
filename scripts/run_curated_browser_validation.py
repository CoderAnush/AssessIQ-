"""
Run 30 curated UI scenarios against /chat and validate UI-oriented checks.
Writes a markdown report and exits non-zero when any scenario fails.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
SCENARIOS_PATH = Path(__file__).parent / "curated_browser_scenarios.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "ui_30_validation_report.md"

CLARIFY_PATTERNS = [
    "can you clarify",
    "could you clarify",
    "which role",
    "what role",
    "which language",
    "which fits",
    "before i shape",
    "before i commit",
    "need to know",
    "which one",
]


def chat(messages: List[Dict[str, str]]) -> Dict:
    response = requests.post(f"{BACKEND_URL}/chat", json={"messages": messages}, timeout=45)
    response.raise_for_status()
    return response.json()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def _is_clarify_reply(reply: str) -> bool:
    text = _normalize_text(reply)
    if "?" not in (reply or ""):
        return False
    return any(pattern in text for pattern in CLARIFY_PATTERNS)


def evaluate_scenario(scenario: Dict) -> Dict:
    messages: List[Dict[str, str]] = []
    last_response: Dict = {}

    for prompt in scenario["prompts"]:
        messages.append({"role": "user", "content": prompt})
        last_response = chat(messages)
        messages.append({"role": "assistant", "content": last_response.get("reply", "")})

    ui_checks = scenario.get("ui_checks", {})
    recommendations = last_response.get("recommendations", []) or []
    recommendation_names = [r.get("name", "") for r in recommendations]
    cards_text = _normalize_text(" | ".join(recommendation_names))
    reply_text = last_response.get("reply", "") or ""
    is_clarify = _is_clarify_reply(reply_text)
    errors: List[str] = []

    expect_cards = bool(ui_checks.get("expect_cards", False))
    expect_clarify = bool(ui_checks.get("expect_clarify", False))
    min_cards = int(ui_checks.get("min_cards", 0))
    must_text = [t.lower() for t in ui_checks.get("must_text_in_cards", [])]
    forbidden_text = [t.lower() for t in ui_checks.get("forbidden_in_cards", [])]

    if expect_cards and len(recommendations) == 0:
        errors.append("Expected recommendation cards but received none.")
    if not expect_cards and len(recommendations) > 0:
        errors.append(f"Expected no recommendation cards but received {len(recommendations)}.")
    if len(recommendations) < min_cards:
        errors.append(f"Expected at least {min_cards} cards but received {len(recommendations)}.")

    if expect_clarify and not is_clarify:
        errors.append("Expected clarification question in assistant reply.")
    if not expect_clarify and is_clarify:
        errors.append("Unexpected clarification question in assistant reply.")

    for item in must_text:
        if item and item not in cards_text:
            errors.append(f"Expected card text containing '{item}'.")
    for item in forbidden_text:
        if item and item in cards_text:
            errors.append(f"Forbidden card text found: '{item}'.")

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "expect": scenario["expect"],
        "pass": len(errors) == 0,
        "errors": errors,
        "reply_preview": reply_text[:260],
        "rec_count": len(recommendations),
        "recommendation_names": recommendation_names,
        "is_clarify": is_clarify,
        "end_of_conversation": bool(last_response.get("end_of_conversation", False)),
    }


def _render_report(results: List[Dict]) -> str:
    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed
    lines = [
        "# UI Curated Validation Report (30)",
        "",
        f"**Backend:** `{BACKEND_URL}`",
        f"**Passed:** {passed}/{len(results)}",
        f"**Failed:** {failed}/{len(results)}",
        "",
    ]

    for result in results:
        status = "PASS" if result["pass"] else "FAIL"
        lines.append(f"## [{status}] {result['id']}. {result['name']}")
        lines.append("")
        lines.append(f"- **Expectation:** {result['expect']}")
        lines.append(f"- **Cards:** {result['rec_count']}")
        lines.append(f"- **Clarify Detected:** {result['is_clarify']}")
        lines.append(f"- **end_of_conversation:** {result['end_of_conversation']}")
        if result["recommendation_names"]:
            lines.append(f"- **Top cards:** {', '.join(result['recommendation_names'][:8])}")
        lines.append(f"- **Reply preview:** {result['reply_preview']}")
        if result["errors"]:
            lines.append("- **Errors:**")
            for err in result["errors"]:
                lines.append(f"  - {err}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        scenarios = []
        for value in payload.values():
            if isinstance(value, list):
                scenarios.extend(value)
    else:
        scenarios = payload
    results = [evaluate_scenario(s) for s in scenarios]
    report_text = _render_report(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    failed = [r for r in results if not r["pass"]]
    print(f"Wrote {REPORT_PATH}")
    for r in results:
        print(f"[{'PASS' if r['pass'] else 'FAIL'}] {r['id']:02d} {r['name']} ({r['rec_count']} cards)")

    if failed:
        print(f"\nValidation failed: {len(failed)} scenario(s) did not pass.")
        sys.exit(1)


if __name__ == "__main__":
    main()
