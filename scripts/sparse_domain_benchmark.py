"""
Sparse Domain Benchmark for AssessIQ.
Tests difficult modern engineering scenarios with adjacency reasoning.
"""

import sys
import os

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.catalog_loader import CatalogLoader
from app.services.ranker_v2 import EnterpriseRanker
from app.services.embedding_service import EmbeddingService
from app.services.conversation_analyzer import HiringContext

SCENARIOS = [
    {"name": "Senior FastAPI Engineer", "role": "Senior FastAPI Engineer", "tech": {"FastAPI", "Python"}},
    {"name": "Kubernetes Platform Engineer", "role": "Kubernetes Platform Engineer", "tech": {"Kubernetes", "Docker"}},
    {"name": "ML Infrastructure Engineer", "role": "ML Infrastructure Engineer", "tech": {"PyTorch", "Kubernetes"}},
    {"name": "SDET with Selenium", "role": "SDET", "tech": {"Selenium", "QA Automation"}},
    {"name": "Terraform Cloud Architect", "role": "Cloud Architect", "tech": {"Terraform", "AWS"}},
    {"name": "Data Engineer with Spark", "role": "Data Engineer", "tech": {"Spark", "SQL"}}
]

def run_benchmark():
    print("="*80)
    print("AssessIQ SPARSE DOMAIN BENCHMARK")
    print("="*80)
    
    loader = CatalogLoader("data/processed/catalog_enriched_v2.json")
    catalog = {a.id: a for a in loader.get_all()}
    ranker = EnterpriseRanker(embedding_service=EmbeddingService())
    
    for s in SCENARIOS:
        print(f"\nScenario: {s['name']}")
        context = HiringContext(role=s['role'], tech_stack=s['tech'], domain="backend engineering")
        
        retrieved = [{"id": a.id, "score": 0.5} for a in loader.get_all()[:50]]
        ranked = ranker.rank(retrieved, context, catalog, top_k=3)
        
        for i, r in enumerate(ranked, 1):
            print(f"  {i}. {r.assessment.name}")
            print(f"     Reasoning: {r.explanation}")
            
    print("="*80)

if __name__ == "__main__":
    run_benchmark()
