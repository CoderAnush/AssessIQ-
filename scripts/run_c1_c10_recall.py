"""
Replay C1-C10 multi-turn traces and compute Recall@10.
Writes artifacts/c1_c10_recall_report.md.
"""

import os
from pathlib import Path
from typing import Dict, List

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
REPORT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "c1_c10_recall_report.md"

TRACES: Dict[str, Dict] = {
    "C1_leadership": {
        "turns": [
            "We need a solution for senior leadership.",
            "The pool consists of CXOs, director-level positions; people with more than 15 years of experience.",
            "Selection — comparing candidates against a leadership benchmark.",
        ],
        "expected": ["opq", "leadership"],
    },
    "C2_rust": {
        "turns": [
            "I'm hiring a senior Rust engineer for high-performance networking infrastructure. What assessments should I use?",
            "Yes, go ahead. Should I also add a cognitive test for this level?",
        ],
        "expected": ["smart interview", "linux", "networking", "verify"],
    },
    "C3_contact_centre": {
        "turns": [
            "We're screening 500 entry-level contact centre agents. Inbound calls, customer service focus. What should we use?",
            "English.",
            "US.",
        ],
        "expected": ["svar", "contact center", "customer service"],
    },
    "C4_finance_grad": {
        "turns": [
            "Hiring graduate financial analysts — final-year students, no work experience. We need numerical reasoning and a finance knowledge test.",
            "Good. Can you also add a situational judgement element — work-context decision making for graduates?",
        ],
        "expected": ["numerical", "financial", "graduate scenarios"],
    },
    "C5_sales_reskill": {
        "turns": [
            "As part of our restructuring and annual talent audit, we need to re-skill our Sales organization. What solutions do you recommend?"
        ],
        "expected": ["global skills", "opq", "sales"],
    },
    "C6_safety": {
        "turns": [
            "We're hiring plant operators for a chemical facility. Safety is absolute top priority — reliability, procedure compliance, never cutting corners. What do you recommend?"
        ],
        "expected": ["safety", "dependability"],
    },
    "C7_healthcare_hybrid": {
        "turns": [
            "We're hiring bilingual healthcare admin staff in South Texas — they handle patient records and need to be assessed in Spanish. HIPAA compliance is critical. What assessments work?",
            "They're functionally bilingual — English fluent for written work. Go with the hybrid.",
        ],
        "expected": ["hipaa", "medical terminology", "opq"],
    },
    "C8_admin_assistant": {
        "turns": [
            "I need to quickly screen admin assistants for Excel and Word daily.",
            "In that case, I am OK with adding a simulation - we want to capture the capabilities.",
        ],
        "expected": ["excel", "word"],
    },
    "C9_fullstack_refinement": {
        "turns": [
            "Here's the JD for an engineer we need to fill. Can you recommend an assessment battery? Senior Full-Stack Engineer with Core Java, Spring, REST APIs, Angular, SQL, AWS, Docker.",
            "Backend-leaning. Day-one priorities are Core Java and Spring; SQL is constant. Angular is occasional — they'd review frontend PRs but not own features.",
            "Senior IC. They lead design on their own services but don't manage other engineers directly.",
            "Add AWS and Docker. Drop REST — the API design signal will already come through in Spring and the live interview.",
        ],
        "expected": ["java", "spring", "sql", "aws", "docker"],
    },
    "C10_grad_mgmt": {
        "turns": [
            "We run a graduate management trainee scheme. We need a full battery — cognitive, personality, and situational judgement. All recent graduates.",
            "Drop the OPQ. Final list: Verify G+ and Graduate Scenarios.",
        ],
        "expected": ["verify", "graduate scenarios"],
    },
}


def chat(messages: List[Dict[str, str]]) -> Dict:
    response = requests.post(f"{BACKEND_URL}/chat", json={"messages": messages}, timeout=45)
    response.raise_for_status()
    return response.json()


def recall_at_10(expected_substrings: List[str], recommendation_names: List[str]) -> float:
    if not expected_substrings:
        return 1.0
    top_names = [name.lower() for name in recommendation_names[:10]]
    hits = sum(
        1
        for expected in expected_substrings
        if any(expected.lower() in recommendation for recommendation in top_names)
    )
    return hits / len(expected_substrings)


def run_trace(trace: Dict) -> Dict:
    messages: List[Dict[str, str]] = []
    last = {}
    for turn in trace["turns"]:
        messages.append({"role": "user", "content": turn})
        last = chat(messages)
        messages.append({"role": "assistant", "content": last.get("reply", "")})

    names = [r.get("name", "") for r in (last.get("recommendations", []) or [])]
    recall = recall_at_10(trace["expected"], names)
    return {
        "recommendations": names,
        "recall_at_10": recall,
        "expected": trace["expected"],
    }


def write_report(results: Dict[str, Dict]) -> None:
    aggregate = sum(item["recall_at_10"] for item in results.values()) / len(results)
    lines = [
        "# C1-C10 Recall@10 Report",
        "",
        f"**Backend:** `{BACKEND_URL}`",
        f"**Average Recall@10:** {aggregate:.2f}",
        "",
    ]
    for trace_id, result in results.items():
        lines.append(f"## {trace_id}")
        lines.append("")
        lines.append(f"- **Recall@10:** {result['recall_at_10']:.2f}")
        lines.append(f"- **Expected:** {', '.join(result['expected'])}")
        lines.append(f"- **Top Recommendations:** {', '.join(result['recommendations'][:10])}")
        lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    results = {trace_id: run_trace(trace) for trace_id, trace in TRACES.items()}
    write_report(results)
    print(f"Wrote {REPORT_PATH}")
    for trace_id, result in results.items():
        print(f"{trace_id}: Recall@10={result['recall_at_10']:.2f}")


if __name__ == "__main__":
    main()
