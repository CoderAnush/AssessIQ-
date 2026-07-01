"""One-shot validation pipeline runner with timing and exit codes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

SUITES = [
    ("pytest", [sys.executable, "-m", "pytest", "tests/", "-q"], {}),
    ("eval_suite", [sys.executable, "scripts/run_eval_suite.py"], {"BACKEND_URL": BACKEND}),
    ("acceptance", [sys.executable, "scratch/run_acceptance_tests.py"], {"BACKEND_URL": BACKEND}),
    ("comprehensive_54", [sys.executable, "scripts/comprehensive_test_50.py"], {"BACKEND_URL": BACKEND}),
    ("ui_30", [sys.executable, "scripts/run_curated_browser_validation.py"], {"BACKEND_URL": BACKEND}),
    ("c1_c10_recall", [sys.executable, "scripts/run_c1_c10_recall.py"], {"BACKEND_URL": BACKEND}),
    ("submission_readiness", [sys.executable, "scripts/run_submission_readiness.py"], {"BACKEND_URL": BACKEND}),
    ("production_readiness", [sys.executable, "scripts/run_submission_readiness.py"], {
        "BACKEND_URL": "https://assessiq-nkp2.onrender.com",
        "PRODUCTION_URL": "https://assessiq-nkp2.onrender.com",
    }),
    ("browser_smoke", [sys.executable, "scripts/smoke_frontend_checks.py"], {"BACKEND_URL": BACKEND}),
]


def main() -> None:
    results = []
    for name, cmd, extra_env in SUITES:
        env = {**os.environ, **extra_env}
        print(f"\n{'='*60}\nRUNNING: {name}\n{'='*60}", flush=True)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
        elapsed = time.time() - t0
        out = (proc.stdout or "") + (proc.stderr or "")
        passed = proc.returncode == 0
        extra = {}
        if name == "acceptance":
            tr = ROOT / "scratch" / "test_results.json"
            if tr.exists():
                data = json.loads(tr.read_text(encoding="utf-8"))
                extra["passed"] = sum(1 for x in data if x.get("passed"))
                extra["failed"] = sum(1 for x in data if not x.get("passed"))
                s41 = next((x for x in data if x.get("id") == 41), None)
                extra["scenario_41"] = s41
        results.append({
            "name": name,
            "exit_code": proc.returncode,
            "passed_gate": passed,
            "elapsed_s": round(elapsed, 1),
            "tail": out[-1500:],
            **extra,
        })
        print(json.dumps({k: v for k, v in results[-1].items() if k != "tail"}, indent=2))
        if not passed:
            print(f"FAILED {name} exit={proc.returncode}")
            print(out[-2000:])
            (ROOT / "artifacts" / "validation_pipeline_partial.json").write_text(
                json.dumps(results, indent=2, default=str), encoding="utf-8"
            )
            sys.exit(1)
    (ROOT / "artifacts" / "validation_pipeline_results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    print("\nALL SUITES PASSED")


if __name__ == "__main__":
    main()
