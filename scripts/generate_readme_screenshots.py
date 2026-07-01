"""
Generate README screenshot placeholders from live API responses.
Run with backend on localhost:8000.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

PROMPTS = {
    "01-landing.png": None,
    "02-java-recommendations.png": "Java Spring Boot backend developer",
    "03-clarify-flow.png": "programmer",
    "04-compare-export.png": "Java Spring Boot backend developer",
}


def _font(size: int = 18):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def render_card(title: str, lines: list[str], path: Path) -> None:
    if Image is None:
        path.write_text("\n".join([title, *lines]), encoding="utf-8")
        return
    img = Image.new("RGB", (1280, 720), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1280, 80], fill=(30, 58, 95))
    draw.text((40, 28), title, fill=(255, 255, 255), font=_font(28))
    y = 110
    for line in lines[:18]:
        draw.text((40, y), line[:110], fill=(30, 41, 59), font=_font(16))
        y += 32
    img.save(path)


def main() -> None:
    # Landing
    render_card(
        "AssessIQ — SHL Assessment Recommender",
        [
            "Sample starters: Leadership · Contact centre · Java backend · Vague query",
            f"Backend: {BACKEND}",
            "Professional recruiter chat UI",
        ],
        OUT / "01-landing.png",
    )

    for fname, prompt in PROMPTS.items():
        if not prompt:
            continue
        r = requests.post(f"{BACKEND}/chat", json={"messages": [{"role": "user", "content": prompt}]}, timeout=45)
        r.raise_for_status()
        data = r.json()
        lines = [data.get("reply", "")[:200]]
        for rec in (data.get("recommendations") or [])[:6]:
            lines.append(f"• {rec.get('name')} [{rec.get('test_type')}]")
        render_card(f"AssessIQ — {prompt[:40]}", lines, OUT / fname)

    # Compare follow-up
    msgs = [{"role": "user", "content": "Java Spring Boot backend developer"}]
    r1 = requests.post(f"{BACKEND}/chat", json={"messages": msgs}, timeout=45).json()
    msgs.append({"role": "assistant", "content": r1.get("reply", "")})
    msgs.append({"role": "user", "content": "Compare the top two assessments"})
    r2 = requests.post(f"{BACKEND}/chat", json={"messages": msgs}, timeout=45).json()
    lines = [r2.get("reply", "")[:300]]
    for rec in (r2.get("recommendations") or [])[:4]:
        lines.append(f"• {rec.get('name')}")
    render_card("AssessIQ — Compare + shortlist", lines, OUT / "04-compare-export.png")

    render_card(
        "Validation gates",
        [
            "pytest tests/",
            "run_eval_suite.py — 15/15",
            "comprehensive_test_50.py — 54 scenarios",
            "run_curated_browser_validation.py — 30 UI",
            "run_c1_c10_recall.py — C1–C10",
            "run_submission_readiness.py",
        ],
        OUT / "05-validation-gates.png",
    )
    print(f"Screenshots written to {OUT}")


if __name__ == "__main__":
    main()
