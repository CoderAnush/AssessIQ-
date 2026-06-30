import asyncio
import json
import re
from pathlib import Path
import aiohttp

def normalize_name(name):
    name = re.sub(r'<[^>]+>', '', name)  # strip html tags if any
    name = name.strip()
    return name

async def check_url_status(session, name, url, semaphore):
    if not url or not url.startswith("http"):
        return name, "Invalid URL"
    
    async with semaphore:
        try:
            # First try HEAD request
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=3), allow_redirects=True) as response:
                if response.status == 200:
                    return name, "OK"
                elif response.status == 404:
                    return name, "Broken (404)"
                else:
                    return name, f"HTTP {response.status}"
        except Exception:
            # Fall back to GET request
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3), allow_redirects=True) as response:
                    if response.status == 200:
                        return name, "OK"
                    elif response.status == 404:
                        return name, "Broken (404)"
                    else:
                        return name, f"HTTP {response.status}"
            except Exception as ex:
                return name, f"Error: {type(ex).__name__}"

async def audit_catalog():
    print("Starting catalog audit...")
    
    # 1. Load existing catalog
    local_path = Path("data/processed/catalog_processed.json")
    if not local_path.exists():
        print(f"Error: Existing catalog not found at {local_path}")
        return
        
    with open(local_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
        
    local_assessments = local_data.get("assessments", []) if isinstance(local_data, dict) else local_data
    print(f"Loaded {len(local_assessments)} local assessments.")
    
    # 2. Load live scraped catalog
    live_path = Path("data/raw/raw_scraped_catalog.json")
    live_assessments = []
    if live_path.exists():
        with open(live_path, "r", encoding="utf-8") as f:
            live_data = json.load(f)
        live_assessments = live_data.get("assessments", [])
        print(f"Loaded {len(live_assessments)} live assessments.")
    else:
        print("Warning: Live scraped catalog not found.")
        
    # Normalize names
    local_names = {normalize_name(a.get("name", "")): a for a in local_assessments}
    live_names = {normalize_name(row[1]): row for row in live_assessments}
    
    # 3. Detect missing assessments
    missing_names = set(live_names.keys()) - set(local_names.keys())
    print(f"Missing assessments (in live but not local): {len(missing_names)}")
    
    # 4. Check for duplicates in local catalog
    seen_names = set()
    duplicates = []
    for a in local_assessments:
        name = normalize_name(a.get("name", ""))
        if name in seen_names:
            duplicates.append(a.get("name"))
        seen_names.add(name)
    print(f"Duplicate assessments in local catalog: {len(duplicates)}")
    
    # 5. Validate URLs in local catalog concurrently
    print("Validating local assessment URLs concurrently...")
    semaphore = asyncio.Semaphore(20)
    
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        tasks = []
        for a in local_assessments:
            url = a.get("url", "")
            tasks.append(check_url_status(session, a.get("name"), url, semaphore))
            
        results = await asyncio.gather(*tasks)
        
    url_statuses = {name: status for name, status in results}
    
    broken_urls = {}
    for a in local_assessments:
        name = a.get("name")
        status = url_statuses.get(name, "Unknown")
        if status != "OK":
            broken_urls[name] = {"url": a.get("url"), "status": status}
            
    print(f"Broken/Failed URLs in local catalog: {len(broken_urls)}")
    
    # 6. Calculate Metadata Completeness % and missing fields for local catalog
    audit_report = []
    
    expected_fields = [
        "name", "url", "test_type", "category", "duration_minutes", 
        "remote_testing", "adaptive", "languages", "description", 
        "skills", "seniority_fit"
    ]
    
    for a in local_assessments:
        missing_fields = []
        filled_count = 0
        
        for field in expected_fields:
            val = a.get(field)
            # Check if field is empty/null/default placeholder
            is_empty = False
            if val is None:
                is_empty = True
            elif isinstance(val, (list, set, dict)) and len(val) == 0:
                is_empty = True
            elif isinstance(val, str) and (val.strip() == "" or "placeholder" in val.lower() or "standard shl assessment" in val.lower()):
                is_empty = True
            elif field == "duration_minutes" and val == 0:
                is_empty = True
                
            if is_empty:
                missing_fields.append(field)
            else:
                filled_count += 1
                
        completeness = (filled_count / len(expected_fields)) * 100
        
        audit_report.append({
            "name": a.get("name"),
            "url": a.get("url"),
            "test_type": a.get("test_type"),
            "category": a.get("category"),
            "duration": a.get("duration_minutes"),
            "remote_testing": a.get("remote_testing", True),
            "adaptive": a.get("adaptive", False),
            "languages": a.get("languages", []),
            "description": a.get("description"),
            "skills": a.get("skills", []),
            "job_levels": a.get("seniority_fit", []),
            "completeness_pct": completeness,
            "missing_fields": missing_fields,
            "url_status": url_statuses.get(a.get("name"), "Unknown")
        })
        
    # Write audit reports
    output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed JSON report
    with open(output_dir / "audit_detailed_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "local_count": len(local_assessments),
            "live_count": len(live_assessments),
            "missing_count": len(missing_names),
            "duplicates_count": len(duplicates),
            "broken_urls_count": len(broken_urls),
            "missing_assessments": list(missing_names),
            "duplicates": duplicates,
            "broken_urls": broken_urls,
            "assessments_audit": audit_report
        }, f, indent=2)
        
    # Build markdown report file
    markdown_path = Path("data/raw/audit_report.md")
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write("# SHL Catalog Audit Report\n\n")
        f.write("## Executive Summary\n")
        f.write(f"- **Local Catalog Size**: {len(local_assessments)} assessments\n")
        f.write(f"- **Live Catalog Size**: {len(live_assessments)} assessments\n")
        f.write(f"- **Missing Assessments**: {len(missing_names)} assessments\n")
        f.write(f"- **Duplicate Assessments**: {len(duplicates)} assessments\n")
        f.write(f"- **Broken/Invalid URLs**: {len(broken_urls)} assessments\n\n")
        
        f.write("## Broken/Failed URLs in Local Catalog\n")
        if broken_urls:
            f.write("| Assessment Name | URL | Status |\n")
            f.write("| --- | --- | --- |\n")
            for name, details in broken_urls.items():
                f.write(f"| {name} | {details['url']} | {details['status']} |\n")
        else:
            f.write("None found.\n")
            
        f.write("\n## Missing Assessments (Available Live but Missing Locally)\n")
        if missing_names:
            f.write("| # | Assessment Name | Live Description |\n")
            f.write("| --- | --- | --- |\n")
            for i, name in enumerate(sorted(missing_names), 1):
                row = live_names[name]
                desc = row[2].replace('\n', ' ').strip()[:100] + '...' if len(row[2]) > 100 else row[2]
                f.write(f"| {i} | {name} | {desc} |\n")
        else:
            f.write("None found.\n")
            
        f.write("\n## Detailed Metadata Completeness Table\n")
        f.write("| Assessment Name | Completeness % | Missing Fields | URL Status |\n")
        f.write("| --- | --- | --- | --- |\n")
        # Sort by completeness ascending to highlight incomplete ones
        for item in sorted(audit_report, key=lambda x: x["completeness_pct"]):
            missing = ", ".join(item["missing_fields"]) if item["missing_fields"] else "None"
            f.write(f"| {item['name']} | {item['completeness_pct']:.1f}% | {missing} | {item['url_status']} |\n")
            
    print(f"Audit completed! Markdown report saved to {markdown_path}")

if __name__ == "__main__":
    asyncio.run(audit_catalog())
