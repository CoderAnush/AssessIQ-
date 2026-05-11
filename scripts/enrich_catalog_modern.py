"""
Modern Catalog Enrichment Pipeline.
Enriches catalog metadata for sparse technical domains.
"""

import json
import os

CATALOG_PATH = "data/processed/catalog_enriched_v2.json"
OUTPUT_PATH = "data/processed/catalog_enriched_v2.json" # Overwrite for simplicity

MAPPINGS = {
    "backend engineering": ["python", "java", "django", "flask", "fastapi", "node", "ruby", "api", "microservice", "distributed"],
    "devops": ["kubernetes", "terraform", "docker", "aws", "cloud", "infra", "automation", "sre", "ci/cd"],
    "data science": ["pytorch", "tensorflow", "ml", "ai", "machine learning", "spark", "hadoop", "sql", "data"],
    "qa automation": ["selenium", "cypress", "playwright", "test", "automation", "sdet"],
    "frontend engineering": ["react", "angular", "vue", "javascript", "typescript", "css", "html"]
}

def enrich_catalog():
    if not os.path.exists(CATALOG_PATH):
        print(f"Error: Catalog not found at {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r") as f:
        data = json.load(f)

    enriched_count = 0
    for assess in data["assessments"]:
        name = assess["name"].lower()
        desc = assess["description"].lower()
        text = name + " " + desc
        
        inferred_skills = set(assess.get("inferred_skills", []))
        engineering_domains = set(assess.get("engineering_domains", []))
        
        for domain, keywords in MAPPINGS.items():
            for kw in keywords:
                if kw in text:
                    inferred_skills.add(kw)
                    engineering_domains.add(domain)
                    enriched_count += 1
        
        assess["inferred_skills"] = list(inferred_skills)
        assess["engineering_domains"] = list(engineering_domains)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Enriched {enriched_count} data points across {len(data['assessments'])} assessments.")
    print(f"Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    enrich_catalog()
