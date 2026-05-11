"""
Advanced Hiring Intelligence Benchmark.
Evaluates orchestration optimization, fatigue, and signal quality.
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
from app.services.adaptive_orchestrator import AdaptiveOrchestrator

logging.basicConfig(level=logging.INFO)

SCENARIOS = [
    {"name": "Backend Architect", "context": HiringContext(role="Senior Backend Architect", tech_stack={"Python", "AWS", "Distributed Systems"}, seniority="senior")},
    {"name": "Junior DevOps", "context": HiringContext(role="Junior DevOps Engineer", tech_stack={"Docker", "CI/CD"}, seniority="entry")},
    {"name": "Graduate Engineering", "context": HiringContext(role="Graduate Engineer", seniority="entry", workflow_mode="quick_screening")},
    {"name": "Leadership Candidate", "context": HiringContext(role="Engineering Director", seniority="senior", leadership_needs=True)}
]

def run_benchmark():
    print("Starting Adaptive Hiring Intelligence Benchmark...")
    
    catalog_loader = CatalogLoader("data/processed/catalog_enriched_v2.json")
    catalog = {a.id: a for a in catalog_loader.get_all()}
    
    ranker = EnterpriseRanker(embedding_service=EmbeddingService())
    orchestrator = AdaptiveOrchestrator()
    
    results = []
    
    for scenario in SCENARIOS:
        print(f"\nProcessing Scenario: {scenario['name']}")
        
        # 1. Rank
        retrieved = [{"id": a.id, "score": 0.5} for a in catalog_loader.get_all()[:50]]
        ranked = ranker.rank(retrieved, scenario["context"], catalog)
        
        # 2. Orchestrate
        pipeline = orchestrator.orchestrate(ranked, scenario["context"], catalog)
        
        # 3. Analyze
        results.append({
            "scenario": scenario["name"],
            "fatigue": pipeline.fatigue_report["fatigue_score"],
            "signal": pipeline.signal_report["signal_score"],
            "stages": len(pipeline.stages)
        })
        
    print_summary(results)

def print_summary(results: List[Dict]):
    print("\n" + "="*80)
    print(f"{'Scenario':<25} | {'Fatigue':<10} | {'Signal':<10} | {'Stages':<6}")
    print("-" * 80)
    for r in results:
        print(f"{r['scenario']:<25} | {r['fatigue']:<10.2f} | {r['signal']:<10.2f} | {r['stages']:<6}")
    print("="*80)

if __name__ == "__main__":
    run_benchmark()
