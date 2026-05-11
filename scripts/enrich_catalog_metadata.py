"""
Catalog Enrichment Pipeline V2.
Uses Technical Knowledge Graph to expand assessment metadata.
"""

import json
import os
import sys

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.skill_graph import SkillGraph
from app.core.assessment_taxonomy import AssessmentTaxonomy

def enrich_catalog():
    print("Starting Enterprise Catalog Enrichment V2...")
    
    base_path = "data/processed/catalog_processed.json"
    if not os.path.exists(base_path):
        print(f"Base catalog not found at {base_path}")
        return

    with open(base_path, "r") as f:
        data = json.load(f)

    assessments = data.get("assessments", [])
    skill_graph = SkillGraph()
    taxonomy = AssessmentTaxonomy()

    enriched = []
    for assess in assessments:
        name = assess.get("name", "")
        desc = assess.get("description", "")
        combined = (name + " " + desc).lower()

        # 1. Infer Skills from Graph
        current_skills = set(s.lower() for s in assess.get("skills", []))
        # Add keywords from name/desc that are in the graph
        for node_name in skill_graph.nodes:
            if node_name in combined:
                current_skills.add(node_name)
        
        expanded_skills = skill_graph.expand_skills(current_skills, depth=1)
        assess["inferred_skills"] = list(expanded_skills)

        # 2. Infer Engineering Domains
        domains = set()
        if any(kw in combined for kw in ["python", "django", "flask", "fastapi", "backend"]):
            domains.add("backend")
        if any(kw in combined for kw in ["react", "angular", "vue", "frontend", "javascript", "css"]):
            domains.add("frontend")
        if any(kw in combined for kw in ["aws", "cloud", "kubernetes", "docker", "devops"]):
            domains.add("cloud")
        if any(kw in combined for kw in ["selenium", "testing", "qa", "automation"]):
            domains.add("qa")
        if any(kw in combined for kw in ["data science", "machine learning", "ml", "ai"]):
            domains.add("data")
            
        assess["engineering_domains"] = list(domains)

        # 3. Infer Hiring Stage Suitability
        stages = []
        if any(kw in combined for kw in ["aptitude", "reasoning", "cognitive", "screening", "basic"]):
            stages.append("early screening")
        if any(kw in combined for kw in ["advanced", "knowledge", "expert", "deep dive", "coding"]):
            stages.append("technical interview")
        if any(kw in combined for kw in ["leadership", "management", "strategic", "executive"]):
            stages.append("leadership evaluation")
        
        if not stages:
            stages.append("general evaluation")
            
        assess["suitable_stages"] = stages

        # 4. Infer Seniority Fit
        seniority = []
        if any(kw in combined for kw in ["senior", "lead", "architect", "expert", "strategic"]):
            seniority.append("senior")
            seniority.append("lead")
        if any(kw in combined for kw in ["junior", "entry", "graduate", "basic", "fundamental"]):
            seniority.append("entry")
            seniority.append("junior")
        if not seniority:
            seniority.append("mid")
            
        assess["seniority_levels"] = seniority
        
        # 5. Infer Category
        if "backend" in domains: assess["category"] = "Technical"
        elif "frontend" in domains: assess["category"] = "Technical"
        elif "cloud" in domains: assess["category"] = "DevOps"
        elif "qa" in domains: assess["category"] = "QA"
        elif "data" in domains: assess["category"] = "Data Science"
        elif any(s in ["leadership evaluation"] for s in stages): assess["category"] = "Leadership"
        elif assess.get("test_type") == "P": assess["category"] = "Personality"
        elif assess.get("test_type") == "A": assess["category"] = "Cognitive"
        else: assess["category"] = "General"

        enriched.append(assess)

    output_path = "data/processed/catalog_enriched_v2.json"
    with open(output_path, "w") as f:
        json.dump({"assessments": enriched}, f, indent=2)

    print(f"Enrichment complete! Saved to {output_path}")
    print(f"Enriched {len(enriched)} assessments.")

if __name__ == "__main__":
    enrich_catalog()
