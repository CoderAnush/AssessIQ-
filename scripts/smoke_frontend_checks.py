"""
Smoke-check script to validate frontend compare/export logic programmatically.
Creates a markdown export file from a sample /chat response and catalog enrichment.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "catalog_processed.json"
OUTPUT = Path(__file__).resolve().parents[0] / "smoke_export.md"

SAMPLE_MESSAGE = [{"role": "user", "content": "Need a senior Java engineer: compare technical verification and leadership assessment"}]


def load_catalog() -> Dict[str, Dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return {}
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assessments = payload.get("assessments", []) if isinstance(payload, dict) else payload
    return {str(item.get("name", "")).strip().lower(): item for item in assessments}


def send_chat(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    resp = requests.post(f"{BACKEND_URL}/chat", json={"messages": messages}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def format_markdown(reply: str, recommendations: List[Dict[str, Any]], comparison: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# AssessIQ Smoke Export - {datetime.now(timezone.utc).isoformat()}\n")
    lines.append("## Query\n")
    lines.append(reply)
    lines.append("\n## Recommendations\n")
    for r in recommendations:
        lines.append(f"- **{r.get('name')}** — {r.get('confidence','N/A')}% — {r.get('url','')}")
    if comparison:
        lines.append("\n## Comparison\n")
        lines.append(comparison.get("summary", ""))
        lines.append("\n")
    return "\n".join(lines)


def main():
    print("Running smoke frontend checks...")
    catalog = load_catalog()
    print(f"Catalog entries: {len(catalog)}")
    payload = send_chat(SAMPLE_MESSAGE)
    reply = payload.get("reply", "")
    recs = payload.get("recommendations", [])
    # Enrich top2 from catalog if possible
    enriched = []
    for idx, r in enumerate(recs[:5], 1):
        key = str(r.get("name","") ).strip().lower()
        meta = catalog.get(key, {})
        enriched.append({
            "name": r.get("name"),
            "url": r.get("url"),
            "confidence": meta.get("relevance_scores", {}).get("communication_focus", 85) if meta else 85,
        })
    # Build a simple comparison if two items
    comparison = None
    if len(enriched) >= 2:
        comparison = {"summary": "Automated comparison (smoke).", "items": enriched[:2]}

    md = format_markdown(reply, enriched, comparison)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(md)

    print(f"Smoke export written to: {OUTPUT}")
    print("Done.")


if __name__ == '__main__':
    main()
