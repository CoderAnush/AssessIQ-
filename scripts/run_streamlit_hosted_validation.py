"""Streamlit hosted app validation: default 12 queries or browser_20_scenarios.json."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "https://assessiq-ai.streamlit.app"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "streamlit_validation"
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


def app_frame(page):
    for frame in page.frames:
        if "~/+/" in (frame.url or ""):
            return frame
    return page


def chat_input(page):
    frame = app_frame(page)
    loc = frame.get_by_placeholder("Describe the role or hiring need...")
    if loc.count() == 0:
        loc = frame.locator('[data-testid="stChatInput"] textarea')
    return loc.first


def count_cards(page) -> int:
    return app_frame(page).locator("div.rec-card").count()


def send_chat(page, text: str) -> None:
    box = chat_input(page)
    box.wait_for(state="visible", timeout=60000)
    box.fill(text)
    box.press("Enter")


def card_text(page) -> str:
    frame = app_frame(page)
    texts = frame.locator("div.rec-card").all_inner_texts()
    return " ".join(texts).lower()


def evaluate_scenario(page, scenario: dict) -> dict:
    checks = scenario.get("ui_checks", {})
    cards = count_cards(page)
    body = card_text(page)
    reply = app_frame(page).locator("body").inner_text().lower()
    passed = True
    reasons = []

    if checks.get("expect_cards") and cards == 0:
        passed = False
        reasons.append("expected cards")
    if checks.get("expect_clarify") and cards > 0:
        passed = False
        reasons.append("expected clarify without cards")
    min_cards = checks.get("min_cards", 0)
    if cards < min_cards:
        passed = False
        reasons.append(f"cards {cards} < {min_cards}")

    for token in checks.get("must_text_in_cards", []):
        if token.lower() not in body:
            passed = False
            reasons.append(f"missing card text: {token}")

    for token in checks.get("forbidden_in_cards", []):
        if token.lower() in body:
            passed = False
            reasons.append(f"forbidden card text: {token}")

    for token in checks.get("must_text_in_reply", []):
        if token.lower() not in reply:
            passed = False
            reasons.append(f"missing reply text: {token}")

    return {
        "id": scenario.get("id"),
        "name": scenario.get("name"),
        "cards": cards,
        "passed": passed,
        "reasons": reasons,
    }


def run_browser_20(page, out_dir: Path) -> list:
    scenarios_path = ROOT / "scripts" / "browser_20_scenarios.json"
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, scenario in enumerate(scenarios):
        t0 = time.time()
        err = ""
        try:
            if i > 0:
                app_frame(page).get_by_role("button", name="Clear conversation").click(timeout=15000)
                page.wait_for_timeout(1500)
            for prompt in scenario["prompts"]:
                send_chat(page, prompt)
                page.wait_for_timeout(45000)
            result = evaluate_scenario(page, scenario)
        except Exception as e:
            result = {
                "id": scenario.get("id"),
                "name": scenario.get("name"),
                "cards": 0,
                "passed": False,
                "reasons": [str(e)],
            }
            err = str(e)
        result["elapsed_s"] = round(time.time() - t0, 1)
        result["error"] = err
        shot = out_dir / f"{scenario['id']:02d}_{scenario['name'].replace(' ', '_').lower()}.png"
        page.screenshot(path=str(shot), full_page=True)
        result["screenshot"] = str(shot)
        results.append(result)
        print(json.dumps(result))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-20", action="store_true", help="Run 20-scenario browser validation suite")
    args = parser.parse_args()

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(APP, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(8000)

        if args.browser_20:
            browser_out = ROOT / "artifacts" / "browser_20"
            results = run_browser_20(page, browser_out)
            report_path = ROOT / "artifacts" / "browser_20_validation_report.md"
            lines = ["# Browser 20 Validation Report", "", "| # | Scenario | Cards | Pass | Notes |", "|---|----------|-------|------|-------|"]
            for r in results:
                notes = "; ".join(r.get("reasons", [])) or "ok"
                lines.append(f"| {r.get('id')} | {r.get('name')} | {r.get('cards')} | {'PASS' if r.get('passed') else 'FAIL'} | {notes} |")
            passed = sum(1 for r in results if r.get("passed"))
            lines.extend(["", f"**Summary:** {passed}/{len(results)} passed"])
            report_path.write_text("\n".join(lines), encoding="utf-8")
            (browser_out / "browser_20_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(f"SUMMARY {passed}/{len(results)} passed")
            browser.close()
            return

        for slug, query in QUERIES:
            t0 = time.time()
            ok = False
            cards = 0
            err = ""
            try:
                if slug != "01_java_backend":
                    app_frame(page).get_by_role("button", name="Clear conversation").click(timeout=15000)
                    page.wait_for_timeout(1500)
                send_chat(page, query)
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
