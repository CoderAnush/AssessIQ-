"""
Evaluation Suite for Hiring Pipeline Quality.
Measures competency coverage, diversity, and orchestration quality.
"""

import sys
import os
import logging
from typing import List, Dict, Any

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.conversation_analyzer import HiringContext
from app.services.catalog_loader import CatalogLoader
from app.services.ranker_v2 import EnterpriseRanker
from app.services.embedding_service import EmbeddingService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.competency_engine import CompetencyEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval_pipeline")

SCENARIOS = [
    {
        "name": "Backend Engineer",
        "query": "Senior Python Backend Engineer",
        "context": HiringContext(role="Senior Python Backend Engineer", tech_stack={"Python", "FastAPI"}, seniority="senior"),
        "expected_clusters": ["technical", "cognitive"]
    },
    {
        "name": "Engineering Manager",
        "query": "Engineering Manager for a team of 10",
        "context": HiringContext(role="Engineering Manager", seniority="senior", leadership_needs=True),
        "expected_clusters": ["leadership", "behavioral", "cognitive"]
    },
    {
        "name": "Graduate Hiring",
        "query": "Graduate software engineer screening",
        "context": HiringContext(role="Graduate Engineer", seniority="entry", workflow_mode="quick_screening"),
        "expected_clusters": ["cognitive"]
    },
    {
        "name": "DevOps Engineer",
        "query": "Cloud and DevOps expert",
        "context": HiringContext(role="DevOps Engineer", tech_stack={"AWS", "Kubernetes"}),
        "expected_clusters": ["technical", "cognitive"]
    }
]

def run_evaluation():
    print("Starting Advanced Hiring Pipeline Evaluation...")
    
    catalog_loader = CatalogLoader("data/processed/catalog_enriched_v2.json")
    catalog = {a.id: a for a in catalog_loader.get_all()}
    
    embedding_service = EmbeddingService()
    ranker = EnterpriseRanker(embedding_service=embedding_service)
    competency_engine = CompetencyEngine()
    orchestrator = PipelineOrchestrator(competency_engine)
    
    results = []
    
    for scenario in SCENARIOS:
        print(f"\nEvaluating Scenario: {scenario['name']}")
        
        # 1. Rank
        retrieved = [{"id": a.id, "score": 0.5} for a in catalog_loader.get_all()[:50]]
        ranked = ranker.rank(retrieved, scenario["context"], catalog, top_k=20)
        
        # 2. Orchestrate
        pipeline = orchestrator.generate_pipeline(ranked, scenario["context"])
        
        # 3. Measure
        metrics = measure_pipeline(pipeline, scenario)
        results.append({
            "scenario": scenario["name"],
            "metrics": metrics
        })
        
    print_summary(results)

def measure_pipeline(pipeline: Any, scenario: Dict) -> Dict:
    # 1. Coverage Score
    coverage = pipeline.competency_coverage
    covered_expected = sum(1 for c in scenario["expected_clusters"] if coverage.get(c, 0.0) >= 0.5)
    coverage_score = covered_expected / len(scenario["expected_clusters"])
    
    # 2. Efficiency (Stages count)
    stages_count = len(pipeline.stages)
    
    # 3. Redundancy (Duplicates in stage assessments)
    total_assessments = sum(len(s.assessments) for s in pipeline.stages)
    unique_ids = set()
    for s in pipeline.stages:
        for a in s.assessments:
            unique_ids.add(a["id"])
    redundancy_score = 1.0 - (1.0 - (len(unique_ids) / total_assessments if total_assessments > 0 else 1))
    
    # 4. Gaps
    gap_count = len(pipeline.gaps)
    
    return {
        "coverage": coverage_score,
        "stages": stages_count,
        "redundancy_suppression": redundancy_score,
        "gaps": gap_count,
        "total_assessments": total_assessments
    }

def print_summary(results: List[Dict]):
    print("\n" + "="*90)
    print(f"{'Scenario':<25} | {'Cov':<6} | {'Stages':<6} | {'Redun':<6} | {'Gaps':<6} | {'Total':<6}")
    print("-" * 90)
    
    for r in results:
        m = r["metrics"]
        print(f"{r['scenario']:<25} | {m['coverage']:.2f} | {m['stages']:<6} | {m['redundancy_suppression']:.2f} | {m['gaps']:<6} | {m['total_assessments']:<6}")
    
    print("="*90)

if __name__ == "__main__":
    run_evaluation()
