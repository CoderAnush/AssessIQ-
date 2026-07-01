"""
Run all SHL submission gates and write artifacts/submission_readiness_report.md.
Exits 1 if any blocker fails.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "submission_readiness_report.md"
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
PRODUCTION_URL = os.environ.get("PRODUCTION_URL", "https://assessiq-nkp2.onrender.com").rstrip("/")
RECALL_MIN = float(os.environ.get("RECALL_MIN", "0.80"))
RECALL_AVG_MIN = float(os.environ.get("RECALL_AVG_MIN", "0.90"))


def run_cmd(cmd: list[str], env: dict | None = None) -> tuple[bool, str]:
    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=merged,
        timeout=600,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip()[-2000:]


def check_recall() -> tuple[bool, str]:
    env = {"BACKEND_URL": BACKEND_URL}
    ok, out = run_cmd([sys.executable, "scripts/run_c1_c10_recall.py"], env)
    if not ok:
        return False, out
    report = (ROOT / "artifacts" / "c1_c10_recall_report.md").read_text(encoding="utf-8")
    recalls = []
    for line in report.splitlines():
        if "Recall@10:" in line:
            try:
                value = line.split("Recall@10:")[-1].strip().lstrip("*").strip()
                recalls.append(float(value))
            except ValueError:
                pass
    if not recalls:
        return False, "No recall values parsed"
    avg = sum(recalls) / len(recalls)
    low = [r for r in recalls if r < RECALL_MIN]
    passed = not low and avg >= RECALL_AVG_MIN
    summary = f"avg={avg:.2f}, min={min(recalls):.2f}, traces_below_{RECALL_MIN}={len(low)}"
    return passed, summary + "\n" + out[-500:]


def main() -> None:
    gates = []
    blockers = []

    # Health
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=30)
        local_ok = r.status_code == 200 and r.json().get("status") == "ok"
    except Exception as e:
        local_ok = False
        gates.append(("Local /health", False, str(e)))
    else:
        gates.append(("Local /health", local_ok, r.text[:80]))

    env = {"BACKEND_URL": BACKEND_URL}
    for label, cmd in [
        ("pytest", [sys.executable, "-m", "pytest", "tests/", "-q"]),
        ("eval_suite", [sys.executable, "scripts/run_eval_suite.py"]),
        ("acceptance", [sys.executable, "scratch/run_acceptance_tests.py"]),
        ("comprehensive_54", [sys.executable, "scripts/comprehensive_test_50.py"]),
        ("ui_30", [sys.executable, "scripts/run_curated_browser_validation.py"]),
        ("smoke_frontend", [sys.executable, "scripts/smoke_frontend_checks.py"]),
    ]:
        ok, tail = run_cmd(cmd, env)
        gates.append((label, ok, tail[-300:] if tail else ""))
        if not ok:
            blockers.append(label)

    recall_ok, recall_detail = check_recall()
    gates.append(("c1_c10_recall", recall_ok, recall_detail))
    if not recall_ok:
        blockers.append("c1_c10_recall")

    try:
        pr = requests.get(f"{PRODUCTION_URL}/health", timeout=60)
        prod_ok = pr.status_code == 200 and pr.json().get("status") == "ok"
    except Exception as e:
        prod_ok = False
        gates.append(("Production /health", False, str(e)))
    else:
        gates.append(("Production /health", prod_ok, pr.text[:80]))
    if not prod_ok:
        blockers.append("production_health")

    verdict = "READY TO SUBMIT" if not blockers else "NOT READY"
    lines = [
        "# Submission Readiness Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Backend:** `{BACKEND_URL}`",
        f"**Production:** `{PRODUCTION_URL}`",
        f"**Verdict:** **{verdict}**",
        "",
    ]
    if blockers:
        lines.append("## Blockers")
        for b in blockers:
            lines.append(f"- {b}")
        lines.append("")

    lines.append("## Gate Results")
    lines.append("")
    lines.append("| Gate | Pass | Notes |")
    lines.append("|------|------|-------|")
    for name, ok, note in gates:
        note_cell = note.replace("\n", " ").replace("|", "/")[:120]
        lines.append(f"| {name} | {'YES' if ok else 'NO'} | {note_cell} |")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"Verdict: {verdict}")
    if blockers:
        sys.exit(1)


if __name__ == "__main__":
    main()
