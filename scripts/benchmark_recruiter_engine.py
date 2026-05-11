"""
Enterprise Recruiter Engine Benchmark Suite.
Evaluates the system across multiple recruiter scenarios.
"""

import sys
import os
import json
import logging
from typing import List, Dict, Any

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.conversation_analyzer import HiringContext
from app.services.catalog_loader import CatalogLoader
from app.services.ranker_v2 import EnterpriseRanker
from app.services.retriever import HybridRetriever
from app.services.embedding_service import EmbeddingService
from app.services.skill_graph import SkillGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

SCENARIOS = [
    {
        "name": "Backend Engineer",
        "query": "Senior Python Backend Engineer with FastAPI and AWS",
        "context": HiringContext(role="Senior Python Backend Engineer", tech_stack={"Python", "FastAPI", "AWS"}, seniority="senior"),
        "expected_domains": ["backend", "cloud"],
        "forbidden_keywords": ["frontend", "react", "sales"]
    },
    {
        "name": "Frontend Engineer",
        "query": "React developer for a high-performance web app",
        "context": HiringContext(role="React Developer", tech_stack={"React", "JavaScript"}, seniority="mid"),
        "expected_domains": ["frontend"],
        "forbidden_keywords": ["backend", "python", "java"]
    },
    {
        "name": "Engineering Manager",
        "query": "Hiring a lead for a team of 10 engineers",
        "context": HiringContext(role="Engineering Manager", seniority="senior", leadership_needs=True),
        "expected_domains": ["management"],
        "forbidden_keywords": ["junior", "coding basics"]
    },
    {
        "name": "QA Automation",
        "query": "SDET with Selenium and Pytest experience",
        "context": HiringContext(role="QA Automation Engineer", tech_stack={"Selenium", "Pytest"}, seniority="mid"),
        "expected_domains": ["qa"],
        "forbidden_keywords": ["sales", "marketing"]
    },
    {
        "name": "Graduate Hiring",
        "query": "Quick screening for graduate engineers",
        "context": HiringContext(role="Graduate Engineer", seniority="entry", workflow_mode="quick_screening"),
        "expected_domains": ["general"],
        "forbidden_keywords": ["strategic", "management", "executive"]
    }
]

def run_benchmark():
    print("Starting Enterprise Benchmark Suite...")
    
    catalog_loader = CatalogLoader("data/processed/catalog_enriched_v2.json")
    catalog = {a.id: a for a in catalog_loader.get_all()}
    
    skill_graph = SkillGraph()
    embedding_service = EmbeddingService()
    retriever = HybridRetriever(catalog_loader)
    ranker = EnterpriseRanker(embedding_service=embedding_service, skill_graph=skill_graph)
    
    results = []
    
    for scenario in SCENARIOS:
        print(f"Testing Scenario: {scenario['name']}")
        
        # 1. Retrieve
        retrieved = retriever.retrieve(scenario["query"], scenario["context"], top_k=20)
        
        # 2. Rank
        ranked = ranker.rank(retrieved, scenario["context"], catalog, top_k=5)
        print(f"  -> Top Results: {[r.assessment.name for r in ranked]}")
        
        # 3. Evaluate
        metrics = evaluate_results(ranked, scenario)
        results.append({
            "scenario": scenario["name"],
            "metrics": metrics
        })
        
    print_summary(results)

def evaluate_results(ranked: List[Any], scenario: Dict) -> Dict:
    top_5 = ranked[:5]
    if not top_5:
        return {"relevance": 0, "domain_accuracy": 0, "diversity": 0}
    
    # Relevance (Score based)
    avg_score = sum(r.final_score for r in top_5) / len(top_5)
    
    # Domain Accuracy
    domain_hits = 0
    for r in top_5:
        assess_domains = getattr(r.assessment, "engineering_domains", [])
        if any(d in assess_domains for d in scenario["expected_domains"]):
            domain_hits += 1
    domain_accuracy = domain_hits / len(top_5)
    
    # Diversity (Type diversity)
    types = {r.assessment.test_type.value for r in top_5}
    diversity_score = len(types) / min(len(top_5), 3) # Cap at 3 types
    
    # False Positive Suppression
    fp_count = 0
    for r in top_5:
        text = (r.assessment.name + " " + r.assessment.description).lower()
        if any(kw in text for kw in scenario["forbidden_keywords"]):
            fp_count += 1
    fp_suppression = 1.0 - (fp_count / len(top_5))
    
    return {
        "relevance": avg_score,
        "domain_accuracy": domain_accuracy,
        "diversity": min(1.0, diversity_score),
        "fp_suppression": fp_suppression
    }

def print_summary(results: List[Dict]):
    print("\n" + "="*80)
    print(f"{'Scenario':<25} | {'Rel':<6} | {'Dom':<6} | {'Div':<6} | {'FPS':<6}")
    print("-" * 80)
    
    for r in results:
        m = r["metrics"]
        print(f"{r['scenario']:<25} | {m['relevance']:.2f} | {m['domain_accuracy']:.2f} | {m['diversity']:.2f} | {m['fp_suppression']:.2f}")
    
    print("="*80)

if __name__ == "__main__":
    run_benchmark()
