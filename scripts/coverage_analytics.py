"""
AssessIQ Domain Coverage Analytics.
Measures catalog saturation across modern engineering roles.
"""

import sys
import os
import numpy as np
from typing import List, Dict, Set

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.catalog_loader import CatalogLoader
from app.services.ranker_v2 import EnterpriseRanker
from app.services.embedding_service import EmbeddingService
from app.services.conversation_analyzer import HiringContext

DOMAINS = {
    "Python Backend": {"FastAPI", "Django", "Flask"},
    "Cloud/DevOps": {"Kubernetes", "Terraform", "Docker", "SRE"},
    "AI/ML Engineering": {"PyTorch", "TensorFlow", "ML Architect"},
    "Data Engineering": {"Spark", "Data Pipeline", "ETL"},
    "Modern QA": {"Playwright", "Cypress", "SDET"},
    "Emerging Tech": {"Rust", "Go"}
}

def analyze_coverage():
    print("="*80)
    print("AssessIQ DOMAIN COVERAGE ANALYTICS")
    print("="*80)
    
    loader = CatalogLoader("data/processed/catalog_enriched_v2.json")
    catalog = {a.id: a for a in loader.get_all()}
    ranker = EnterpriseRanker(embedding_service=EmbeddingService())
    
    results = []
    
    for domain_name, sub_skills in DOMAINS.items():
        # Create a combined context
        context = HiringContext(
            role=domain_name,
            tech_stack=sub_skills,
            domain=domain_name.lower()
        )
        
        # Rank top 100 to see what we find
        retrieved = [{"id": a.id, "score": 0.5} for a in loader.get_all()]
        ranked = ranker.rank(retrieved, context, catalog, top_k=10)
        
        # Calculate metrics
        direct_matches = sum(1 for r in ranked if r.factors.keyword_similarity > 0)
        adjacency_reliance = sum(1 for r in ranked if r.factors.graph_relevance > 0.5 and r.factors.keyword_similarity == 0)
        confidence = float(np.mean([r.final_score for r in ranked])) if ranked else 0.0
        
        results.append({
            "domain": domain_name,
            "coverage": direct_matches / 10 if ranked else 0,
            "adjacency": adjacency_reliance / 10 if ranked else 0,
            "confidence": confidence
        })

    print(f"{'Domain':<25} | {'Direct':<10} | {'Adjacency':<10} | {'Confidence':<10}")
    print("-" * 80)
    for r in results:
        print(f"{r['domain']:<25} | {r['coverage']:<10.2%} | {r['adjacency']:<10.2%} | {r['confidence']:<10.2f}")
    
    print("="*80)

if __name__ == "__main__":
    analyze_coverage()
