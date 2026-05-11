"""
Evaluation Suite - Tests recommendation quality against recruiter scenarios.
Phase 7: Comprehensive assessment quality metrics.
"""

import json
import logging
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass

# Add current directory to path
sys.path.append(os.getcwd())

from app.services.conversation_analyzer import HiringContext
from app.services.catalog_loader import CatalogLoader
from app.services.ranker_v2 import RecruiterRanker
from app.services.embedding_service import EmbeddingService
from app.core.assessment_taxonomy import AssessmentTaxonomy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluation_suite")

@dataclass
class TestScenario:
    name: str
    role: str
    tech_stack: List[str]
    seniority: str
    expected_keywords: List[str]
    forbidden_keywords: List[str]

SCENARIOS = [
    TestScenario(
        "Senior Python Backend Engineer",
        "Senior Python Backend Engineer",
        ["Python", "Django", "FastAPI", "PostgreSQL"],
        "senior",
        ["Python", "Backend", "API", "System Design"],
        ["Frontend", "React", "Sales", "Customer Support"]
    ),
    TestScenario(
        "QA Automation Engineer",
        "QA Automation Engineer",
        ["Selenium", "Pytest", "Automation"],
        "mid",
        ["Testing", "QA", "Automation", "Selenium"],
        ["Sales", "Data Science", "Management"]
    ),
    TestScenario(
        "Data Scientist with SQL + ML",
        "Data Scientist",
        ["SQL", "Python", "Machine Learning", "Scikit-Learn"],
        "mid",
        ["Data Science", "Machine Learning", "SQL", "Statistics"],
        ["Frontend", "Java", "Sales"]
    ),
    TestScenario(
        "Engineering Manager",
        "Engineering Manager",
        ["Leadership", "Management"],
        "senior",
        ["Leadership", "Management", "Team", "Strategy"],
        ["Pure Coding", "React"]
    ),
    TestScenario(
        "Sales Executive",
        "Sales Executive",
        ["Sales", "CRM"],
        "mid",
        ["Sales", "Commercial", "Revenue", "Communication"],
        ["Java", "Python", "Coding", "Programming"]
    )
]

def evaluate():
    """Run evaluation suite."""
    logger.info("Starting Recruiter Quality Evaluation...")
    
    catalog_loader = CatalogLoader("data/processed/catalog_enriched.json")
    catalog_assessments = {a.id: a for a in catalog_loader.get_all()}
    
    embedding_service = EmbeddingService()
    taxonomy = AssessmentTaxonomy()
    ranker = RecruiterRanker(taxonomy, embedding_service)
    
    results = []
    
    for scenario in SCENARIOS:
        logger.info(f"Testing Scenario: {scenario.name}")
        
        context = HiringContext(
            role=scenario.role,
            tech_stack=set(scenario.tech_stack),
            seniority=scenario.seniority
        )
        
        # Simple retrieval for evaluation (top 20 candidates)
        all_candidates = []
        for a in catalog_loader.get_all():
            all_candidates.append({
                "id": a.id,
                "name": a.name,
                "hybrid_score": 0.5 # Dummy retrieval score
            })
            
        ranked = ranker.rank(all_candidates, context, catalog_assessments, top_k=5)
        
        # Metrics
        top_3 = ranked[:3]
        relevance_score = 0
        domain_correctness = 0
        diversity_score = 0
        
        # 1. Relevance & Domain Correctness
        for res in top_3:
            name_low = res.assessment.name.lower()
            desc_low = res.assessment.description.lower()
            combined = name_low + " " + desc_low
            
            if any(kw.lower() in combined for kw in scenario.expected_keywords):
                relevance_score += 1
            
            if not any(kw.lower() in combined for kw in scenario.forbidden_keywords):
                domain_correctness += 1
        
        # 2. Diversity (categories should be different if possible)
        categories = set(res.category for res in top_3)
        diversity_score = len(categories)
        
        pass_fail = "PASS" if (relevance_score >= 2 and domain_correctness >= 2) else "FAIL"
        
        results.append({
            "scenario": scenario.name,
            "status": pass_fail,
            "relevance": f"{relevance_score}/3",
            "domain": f"{domain_correctness}/3",
            "diversity": f"{diversity_score}/3",
            "top_results": [r.assessment.name for r in top_3]
        })
        
    # Print Summary
    print("\n" + "="*50)
    print("RECRUITER QUALITY EVALUATION SUMMARY")
    print("="*50)
    print(f"{'Scenario':<30} | {'Status':<6} | {'Rel':<4} | {'Dom':<4} | {'Div':<4}")
    print("-" * 55)
    
    total_pass = 0
    for r in results:
        print(f"{r['scenario']:<30} | {r['status']:<6} | {r['relevance']:<4} | {r['domain']:<4} | {r['diversity']:<4}")
        if r['status'] == "PASS":
            total_pass += 1
            
    print("-" * 55)
    print(f"TOTAL: {total_pass}/{len(SCENARIOS)} PASSED")
    print("="*50)

if __name__ == "__main__":
    evaluate()
