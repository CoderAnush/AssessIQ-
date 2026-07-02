"""Streamlit hosted app validation: default 12 queries or browser_20_scenarios.json."""
from __future__ import annotations

import argparse
import json
import re
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


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def _is_clarify_reply(reply: str) -> bool:
    text = _normalize_text(reply)
    if "?" not in (reply or ""):
        return False
    return any(pattern in text for pattern in CLARIFY_PATTERNS)


def wait_for_thinking(page, timeout=120000) -> None:
    frame = app_frame(page)
    # Wait up to 5s for the "Thinking..." element to appear in the DOM
    try:
        frame.locator('text="Thinking..."').wait_for(state="visible", timeout=5000)
    except Exception:
        pass
    # Now wait for it to disappear
    frame.locator('text="Thinking..."').wait_for(state="hidden", timeout=timeout)
    # Give a short extra wait for Streamlit state to settle
    page.wait_for_timeout(2000)


def evaluate_scenario(page, scenario: dict) -> dict:
    frame = app_frame(page)
    
    # 1. Locate the last assistant message
    last_assistant_msg = frame.locator('[data-testid="stChatMessage"]').last
    
    # 2. Get card names from the last assistant message
    recommendation_names = []
    if last_assistant_msg.locator("div.rec-card").count() > 0:
        recommendation_names = last_assistant_msg.locator("div.rec-card h4").all_inner_texts()
    
    recommendation_names = [name.strip() for name in recommendation_names if name.strip()]
    cards_count = len(recommendation_names)
    cards_text = _normalize_text(" | ".join(recommendation_names))
    
    # 3. Get assistant reply text (include comparison blocks rendered separately in Streamlit)
    reply_text = last_assistant_msg.inner_text()
    
    # 4. Check if clarify
    is_clarify = _is_clarify_reply(reply_text)
    has_banner = last_assistant_msg.locator("div.clarify-banner").count() > 0
    if has_banner:
        is_clarify = True
        
    errors = []
    ui_checks = scenario.get("ui_checks", {})
    
    expect_cards = bool(ui_checks.get("expect_cards", True))
    expect_clarify = bool(ui_checks.get("expect_clarify", False))
    min_cards = int(ui_checks.get("min_cards", 0))

    if expect_cards and cards_count == 0:
        errors.append("Expected recommendation cards but received none.")
    if not expect_cards and cards_count > 0:
        errors.append(f"Expected no recommendation cards but received {cards_count}.")
    if cards_count < min_cards:
        errors.append(f"Expected at least {min_cards} cards but received {cards_count}.")

    if expect_clarify and not is_clarify:
        errors.append("Expected clarification question in assistant reply.")
    if not expect_clarify and is_clarify and expect_cards:
        errors.append("Unexpected clarification question in assistant reply.")

    for item in ui_checks.get("must_text_in_cards", []):
        full_cards_text = ""
        if last_assistant_msg.locator("div.rec-card").count() > 0:
            full_cards_text = _normalize_text(" ".join(last_assistant_msg.locator("div.rec-card").all_inner_texts()))
        if item.lower() not in full_cards_text:
            errors.append(f"Expected card text containing '{item}'.")

    top_n_spec = ui_checks.get("must_text_in_top_n")
    if top_n_spec:
        n = int(top_n_spec.get("n", 3))
        top_names = _normalize_text(" | ".join(recommendation_names[:n]))
        terms = top_n_spec.get("terms", [])
        if terms and not any(term.lower() in top_names for term in terms):
            errors.append(f"Expected one of {terms} in top {n} cards; got {recommendation_names[:n]}.")

    forbidden_top = ui_checks.get("forbidden_in_top_n")
    if forbidden_top:
        n = int(forbidden_top.get("n", 3))
        top_names = _normalize_text(" | ".join(recommendation_names[:n]))
        for item in forbidden_top.get("terms", []):
            if item.lower() in top_names:
                errors.append(f"Forbidden text '{item}' in top {n} cards.")

    for item in ui_checks.get("forbidden_in_cards", []):
        full_cards_text = ""
        if last_assistant_msg.locator("div.rec-card").count() > 0:
            full_cards_text = _normalize_text(" ".join(last_assistant_msg.locator("div.rec-card").all_inner_texts()))
        if item.lower() in full_cards_text or item.lower() in cards_text:
            errors.append(f"Forbidden card text found: '{item}'.")

    for item in ui_checks.get("must_text_in_reply", []):
        if item.lower() not in _normalize_text(reply_text):
            errors.append(f"Expected reply text containing '{item}'.")

    for item in ui_checks.get("forbidden_in_reply", []):
        if item.lower() in _normalize_text(reply_text):
            errors.append(f"Forbidden reply text found: '{item}'.")

    # Check SHL URLs in the last assistant message
    shl_buttons = last_assistant_msg.locator('a:has-text("View on SHL")')
    urls = []
    for idx in range(shl_buttons.count()):
        href = shl_buttons.nth(idx).get_attribute("href")
        if href:
            urls.append(href)
            
    for url in urls:
        if url and not url.startswith("https://www.shl.com/"):
            errors.append(f"Invalid SHL URL: {url}")

    if len(recommendation_names) != len(set(recommendation_names)):
        errors.append("Duplicate assessment names in recommendations.")

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "cards": cards_count,
        "passed": len(errors) == 0,
        "reasons": errors,
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
                wait_for_thinking(page)
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
