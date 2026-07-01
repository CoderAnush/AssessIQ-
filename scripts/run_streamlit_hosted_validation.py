"""Streamlit hosted app validation: 12 recruiter queries + screenshots."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "https://assessiq-ai.streamlit.app"
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "streamlit_validation"
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    ("01_java_backend", "Hiring a Java Spring Boot backend developer with microservices experience."),
    ("02_react_frontend", "Senior React Frontend Engineer with TypeScript and Next.js."),
    ("03_ai_engineer", "AI Engineer with machine learning and NLP experience."),
    ("04_data_scientist", "Data Scientist with Python, statistics, and machine learning."),
    ("05_finance_analyst", "Finance Analyst with Excel, modeling, and reporting skills."),
    ("06_hr_executive", "HR Executive for talent acquisition and employee relations."),
    ("07_sales_manager", "Sales Manager for B2B enterprise software sales."),
    ("08_graduate_swe", "Graduate Software Engineer with aptitude and communication skills."),
    ("09_engineering_manager", "Engineering Manager leading backend and platform teams."),
    ("10_contact_centre", "Entry-level contact centre agents for US inbound calls."),
    ("11_scenario41_fullstack", "Hiring a Full Stack Engineer with Java, Spring Boot, React, Next.js, AWS, Docker, Kubernetes, Leadership, and Communication skills."),
    ("12_vague_programmer", "programmer"),
]


def count_cards(page) -> int:
    return page.locator("div.rec-card").count()


def main() -> None:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(APP, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(8000)
        for slug, query in QUERIES:
            t0 = time.time()
            ok = False
            cards = 0
            err = ""
            try:
                if slug != "01_java_backend":
                    page.get_by_role("button", name="Clear conversation").click(timeout=15000)
                    page.wait_for_timeout(1500)
                chat = page.locator('textarea[aria-label="Describe the role or hiring need..."]')
                chat.wait_for(state="visible", timeout=60000)
                chat.fill(query)
                chat.press("Enter")
                page.wait_for_timeout(45000)
                cards = count_cards(page)
                ok = True
            except Exception as e:
                err = str(e)
            elapsed = round(time.time() - t0, 1)
            shot = OUT / f"{slug}.png"
            page.screenshot(path=str(shot), full_page=True)
            results.append({
                "slug": slug,
                "query": query,
                "cards": cards,
                "passed": ok and (cards > 0 or slug in {"10_contact_centre", "12_vague_programmer"}),
                "elapsed_s": elapsed,
                "screenshot": str(shot),
                "error": err,
            })
            print(json.dumps(results[-1]))
        browser.close()
    (OUT / "streamlit_validation_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    passed = sum(1 for r in results if r["passed"])
    print(f"SUMMARY {passed}/{len(results)} passed")


if __name__ == "__main__":
    main()
