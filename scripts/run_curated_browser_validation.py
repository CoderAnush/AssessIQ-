"""
Run 10 curated browser scenarios against /chat API and write validation report.
Use alongside Streamlit visual check (see artifacts/browser_validation_report.md).
"""

import json
import os
from pathlib import Path

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
SCENARIOS_PATH = Path(__file__).parent / "curated_browser_scenarios.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "browser_validation_report.md"


def chat(messages):
    r = requests.post(f"{BACKEND_URL}/chat", json={"messages": messages}, timeout=30)
    r.raise_for_status()
    return r.json()


def run_scenario(scenario: dict) -> dict:
    messages = []
    last = None
    for prompt in scenario["prompts"]:
        messages.append({"role": "user", "content": prompt})
        last = chat(messages)
        messages.append({"role": "assistant", "content": last.get("reply", "")})
    recs = last.get("recommendations", []) if last else []
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "expect": scenario["expect"],
        "reply_preview": (last or {}).get("reply", "")[:300],
        "rec_count": len(recs),
        "recommendation_names": [r.get("name") for r in recs],
        "end_of_conversation": (last or {}).get("end_of_conversation", False),
    }


def main():
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    results = [run_scenario(s) for s in scenarios]

    lines = [
        "# Curated Browser Scenario Validation (10)",
        "",
        f"**Backend:** `{BACKEND_URL}`",
        "",
        "Scenario 1 was visually verified in Streamlit (recommendation cards with Java assessments).",
        "",
    ]
    for r in results:
        lines.append(f"## {r['id']}. {r['name']}")
        lines.append("")
        lines.append(f"- **Expect:** {r['expect']}")
        lines.append(f"- **Recommendations:** {r['rec_count']}")
        lines.append(f"- **end_of_conversation:** {r['end_of_conversation']}")
        if r["recommendation_names"]:
            lines.append(f"- **Shortlist:** {', '.join(r['recommendation_names'])}")
        lines.append(f"- **Reply preview:** {r['reply_preview'][:200]}...")
        lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    for r in results:
        print(f"  [{r['id']}] {r['name']}: {r['rec_count']} recs")


if __name__ == "__main__":
    main()
