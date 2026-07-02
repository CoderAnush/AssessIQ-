"""Manual spot-check: 4 original user prompts on hosted Streamlit."""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "https://assessiq-ai.streamlit.app"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "streamlit_validation" / "spot_check"
OUT.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    ("01_ai_developer", "Hiring AI Developer", ["ai skills", "data science", "automata data science"], ["spring", "opq leadership"]),
    ("02_ai_engineer_llm", "Hiring an AI Engineer with Python, LLMs, LangChain, HuggingFace, Vector Databases and AWS.", ["ai skills", "data science", "automata data science"], ["spring", "opq leadership", "executive scenarios"]),
    ("03_qa_automation", "Hiring QA Automation Engineer with Selenium, Playwright, Cypress, API Testing and Postman.", ["selenium", "automata selenium", "agile testing"], ["spring", "opq leadership"]),
    ("04_b2b_sales", "Hiring B2B Sales Manager.", ["sales", "opq mq sales", "global skills"], ["core java", "spring"]),
]


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


def reply_text(page) -> str:
    frame = app_frame(page)
    last_msg = frame.locator('[data-testid="stChatMessage"]').last
    if last_msg.locator('[data-testid="stMarkdownContainer"]').count() == 0:
        return ""
    return last_msg.locator('[data-testid="stMarkdownContainer"]').first.inner_text().lower()


def main() -> None:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(APP, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(8000)

        for slug, prompt, must, forbid in PROMPTS:
            app_frame(page).get_by_role("button", name="Clear conversation").click(timeout=15000)
            page.wait_for_timeout(1500)
            send_chat(page, prompt)
            wait_for_thinking(page)
            titles = card_titles(page)
            top3 = " | ".join(titles[:3]).lower()
            reply = reply_text(page)
            errors = []
            if not any(m in top3 for m in must):
                errors.append(f"top3 missing one of {must}; got {titles[:3]}")
            for f in forbid:
                if f in top3:
                    errors.append(f"forbidden '{f}' in top3")
            if "management pipeline" in reply:
                errors.append("forbidden management pipeline in reply")
            shot = OUT / f"{slug}.png"
            page.screenshot(path=str(shot), full_page=True)
            row = {"slug": slug, "prompt": prompt, "top3": titles[:3], "passed": not errors, "errors": errors, "screenshot": str(shot)}
            results.append(row)
            print(json.dumps(row))

        browser.close()

    passed = sum(1 for r in results if r["passed"])
    (OUT / "spot_check_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"SUMMARY {passed}/{len(results)}")
    if passed < len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
