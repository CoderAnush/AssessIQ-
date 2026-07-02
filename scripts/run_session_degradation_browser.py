"""Browser test: many role prompts in one session without clearing."""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "https://assessiq-ai.streamlit.app"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "streamlit_validation"
OUT.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    "Hiring a Senior Java Backend Engineer with Spring Boot, Microservices, Kafka, Redis, Docker, Kubernetes, AWS, MySQL and REST APIs.",
    "hiring frontend developer",
    "hiring java developer",
    "Hiring AI Developer",
    "hiring backend developer",
    "hiring python engineer",
    "hiring devops engineer",
    "hiring frontend developer",
    "python",
    "need frontend",
    "devops developer",
]

EXPECTED_TOP_TERMS = {
    8: ("react", "angular", "front"),
    9: ("python", "java", "spring"),
    10: ("react", "angular", "front"),
    11: ("docker", "kubernetes", "cloud", "devops"),
}


def app_frame(page):
    for frame in page.frames:
        if "~/+/" in (frame.url or ""):
            return frame
    return page


def send_chat(page, text: str) -> None:
    frame = app_frame(page)
    box = frame.get_by_placeholder("Describe the role or hiring need...")
    if box.count() == 0:
        box = frame.locator('[data-testid="stChatInput"] textarea')
    box.first.wait_for(state="visible", timeout=60000)
    box.first.fill(text)
    box.first.press("Enter")


def wait_for_thinking(page, timeout=120000) -> None:
    frame = app_frame(page)
    try:
        frame.locator('text="Thinking..."').wait_for(state="visible", timeout=5000)
    except Exception:
        pass
    try:
        frame.locator('text="Thinking..."').wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(2000)


def card_titles(page) -> list[str]:
    frame = app_frame(page)
    last_msg = frame.locator('[data-testid="stChatMessage"]').last
    if last_msg.locator("div.rec-card h4").count() == 0:
        return []
    return [t.strip() for t in last_msg.locator("div.rec-card h4").all_inner_texts() if t.strip()]


def main() -> None:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(APP, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(8000)

        for i, prompt in enumerate(PROMPTS, 1):
            t0 = time.time()
            send_chat(page, prompt)
            wait_for_thinking(page)
            titles = card_titles(page)
            top_blob = " | ".join(titles[:4]).lower()
            expected = EXPECTED_TOP_TERMS.get(i, ())
            passed = True
            reason = "ok"
            if expected and not any(term in top_blob for term in expected):
                passed = False
                reason = f"expected one of {expected}; got {titles[:4]}"
            if "finalized assessment shortlist" in app_frame(page).locator("body").inner_text().lower():
                if i >= 8 and not expected:
                    pass
                elif i >= 8:
                    passed = False
                    reason = "stale finalized shortlist returned"
            shot = OUT / f"session_{i:02d}.png"
            page.screenshot(path=str(shot), full_page=True)
            row = {
                "step": i,
                "prompt": prompt,
                "top4": titles[:4],
                "passed": passed,
                "reason": reason,
                "screenshot": str(shot),
                "elapsed_s": round(time.time() - t0, 1),
            }
            results.append(row)
            print(json.dumps(row))

        browser.close()

    passed = sum(1 for r in results if r["passed"])
    report = OUT / "session_degradation_report.md"
    lines = [
        "# Streamlit Session Degradation Test",
        "",
        f"**Summary:** {passed}/{len(results)} passed",
        "",
        "| Step | Prompt | Pass | Top 4 | Notes |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['step']} | {r['prompt'][:40]}... | {'PASS' if r['passed'] else 'FAIL'} | "
            f"{', '.join(r['top4'][:2])}... | {r['reason']} |"
        )
    report.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "session_degradation_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"SUMMARY {passed}/{len(results)}")
    if passed < len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
