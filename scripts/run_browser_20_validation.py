"""
Run 20 browser scenarios against /chat (same prompts/checks as Streamlit UI suite).
Writes artifacts/browser_20_validation_report.md and exits non-zero on failure.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "https://assessiq-nkp2.onrender.com").rstrip("/")
SCENARIOS_PATH = Path(__file__).parent / "browser_20_scenarios.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "browser_20_validation_report.md"
RESULTS_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "browser_20" / "browser_20_results.json"

CLARIFY_PATTERNS = [
    "can you clarify",
    "could you clarify",
    "which role",
    "what role",
    "what type of role",
    "type of role",
    "seniority",
    "which language",
    "before i shape",
    "before i commit",
]


def chat(messages: List[Dict[str, str]]) -> Dict:
    response = requests.post(f"{BACKEND_URL}/chat", json={"messages": messages}, timeout=120)
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

    expect_cards = bool(ui_checks.get("expect_cards", True))
    expect_clarify = bool(ui_checks.get("expect_clarify", False))
    min_cards = int(ui_checks.get("min_cards", 0))

    if expect_cards and len(recommendations) == 0:
        errors.append("Expected recommendation cards but received none.")
    if not expect_cards and len(recommendations) > 0:
        errors.append(f"Expected no recommendation cards but received {len(recommendations)}.")
    if len(recommendations) < min_cards:
        errors.append(f"Expected at least {min_cards} cards but received {len(recommendations)}.")

    if expect_clarify and not is_clarify:
        errors.append("Expected clarification question in assistant reply.")
    if not expect_clarify and is_clarify and expect_cards:
        errors.append("Unexpected clarification question in assistant reply.")

    for item in ui_checks.get("must_text_in_cards", []):
        if item.lower() not in cards_text:
            errors.append(f"Expected card text containing '{item}'.")

    for item in ui_checks.get("forbidden_in_cards", []):
        if item.lower() in cards_text:
            errors.append(f"Forbidden card text found: '{item}'.")

    for item in ui_checks.get("must_text_in_reply", []):
        if item.lower() not in _normalize_text(reply_text):
            errors.append(f"Expected reply text containing '{item}'.")

    for rec in recommendations:
        url = rec.get("url", "")
        if url and not url.startswith("https://www.shl.com/"):
            errors.append(f"Invalid SHL URL: {url}")

    if len(recommendation_names) != len(set(recommendation_names)):
        errors.append("Duplicate assessment names in recommendations.")

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "pass": len(errors) == 0,
        "errors": errors,
        "rec_count": len(recommendations),
        "recommendation_names": recommendation_names,
        "reply_preview": reply_text[:200],
        "is_clarify": is_clarify,
    }


def main() -> None:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    results = [evaluate_scenario(s) for s in scenarios]
    passed = sum(1 for r in results if r["pass"])

    lines = [
        "# Browser 20 Validation Report",
        "",
        f"**Backend:** `{BACKEND_URL}`",
        f"**Summary:** {passed}/{len(results)} passed",
        "",
        "| # | Scenario | Cards | Pass | Notes |",
        "|---|----------|-------|------|-------|",
    ]
    for r in results:
        notes = "; ".join(r["errors"]) if r["errors"] else "ok"
        lines.append(
            f"| {r['id']} | {r['name']} | {r['rec_count']} | {'PASS' if r['pass'] else 'FAIL'} | {notes} |"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for r in results:
        print(f"[{'PASS' if r['pass'] else 'FAIL'}] {r['id']:02d} {r['name']} ({r['rec_count']} cards)")

    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
