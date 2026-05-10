"""
Catalog Validation Tool for AssessIQ.
Checks for duplicate IDs, missing fields, and schema compliance.
"""

import json
import sys
from pathlib import Path
import re

def validate_catalog(catalog_path: str):
    print(f"Validating catalog: {catalog_path}")
    path = Path(catalog_path)
    
    if not path.exists():
        print(f"ERROR: Catalog not found at {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"ERROR: Invalid JSON: {e}")
            return False

    assessments = data.get("assessments", [])
    print(f"Found {len(assessments)} assessments")

    errors = []
    warnings = []
    seen_ids = set()
    seen_urls = set()

    for i, ass in enumerate(assessments):
        name = ass.get("name", f"Unnamed-{i}")
        
        # 1. ID Check
        ass_id = ass.get("id")
        if not ass_id:
            errors.append(f"[{name}] Missing ID")
        elif ass_id in seen_ids:
            errors.append(f"[{name}] Duplicate ID: {ass_id}")
        else:
            seen_ids.add(ass_id)

        # 2. Required Fields
        if not ass.get("name"):
            errors.append(f"Assessment {i} missing Name")
        if not ass.get("url"):
            errors.append(f"[{name}] Missing URL")
        elif ass.get("url") in seen_urls:
            warnings.append(f"[{name}] Duplicate URL: {ass.get('url')}")
        else:
            seen_urls.add(ass.get("url"))

        # 3. Duration Check
        duration = ass.get("duration_minutes")
        if duration is None:
            errors.append(f"[{name}] Duration is None")
        elif not isinstance(duration, int):
            errors.append(f"[{name}] Duration must be int, got {type(duration)}")

        # 4. Description Check
        if not ass.get("description"):
            warnings.append(f"[{name}] Missing description")

    print("\nVALIDATION SUMMARY:")
    print(f"- Errors: {len(errors)}")
    print(f"- Warnings: {len(warnings)}")

    if warnings:
        print("\nWARNINGS:")
        for w in warnings[:10]:
            print(f"  ! {w}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings)-10} more")

    if errors:
        print("\nERRORS:")
        for e in errors[:10]:
            print(f"  X {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")
        return False

    print("\n[OK] Catalog is valid and production-ready!")
    return True

if __name__ == "__main__":
    path = "data/processed/catalog_processed.json"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    
    success = validate_catalog(path)
    if not success:
        sys.exit(1)
