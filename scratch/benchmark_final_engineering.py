"""
Benchmark script for the final engineering pass.

Runs the full retrieval pipeline on a set of queries and prints per‑stage
results (BM25 top‑10, Vector top‑10, RRF merged top‑10) plus the final
recommendations after business‑rules.
"""

import json
import os
import sys
import time

# Ensure repo root is on PYTHONPATH
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from app.services.catalog_loader import CatalogLoader
from app.services.retriever import HybridRetriever
from app.services.business_rules_engine import BusinessRulesEngine
from app.agents.decision_engine import DecisionEngine

# ---------------------------------------------------------------------------
QUERIES = [
    "Senior Java Backend Engineer",
    "Senior React Frontend Engineer",
    "Python Backend Developer",
    "ML Engineer",
    "DevOps Engineer",
    "Sales Manager",
    "HR Executive",
    "Finance Analyst",
]

CATALOG_PATH = os.path.join(ROOT, "data", "processed", "catalog_processed.json")

def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def run():
    print_section("Loading catalog")
    catalog = CatalogLoader(CATALOG_PATH)
    print(f"Loaded {len(catalog.get_all())} assessments")

    # Initialise services
    retriever = HybridRetriever(catalog)
    rules_engine = BusinessRulesEngine()
    decision_engine = DecisionEngine()

    for query in QUERIES:
        print_section(f"QUERY: {query}")
        # Analyze to get context (needed for domain inference)
        messages = [{"role": "user", "content": query}]
        context, intent = decision_engine.analyzer.analyze(messages)

        # ----- BM25 -----
        bm25_results = retriever._bm25_retrieve(query.lower(), set(a.id for a in catalog.get_all()), k=10)
        # bm25_retrieve returns list of IDs – we need full objects
        bm25_assess = [retriever._to_dict(a) for a in catalog.get_all() if a.id in bm25_results]
        print("\nBM25 Top 10:")
        for i, aid in enumerate(bm25_results, 1):
            a = next((x for x in catalog.get_all() if x.id == aid), None)
            if a:
                print(f"  {i:2}. {a.name}")

        # ----- Vector -----
        vector_ids = retriever._vector_retrieve(query, context, set(a.id for a in catalog.get_all()), k=10)
        print("\nVector Top 10:")
        for i, aid in enumerate(vector_ids, 1):
            a = next((x for x in catalog.get_all() if x.id == aid), None)
            if a:
                print(f"  {i:2}. {a.name}")

        # ----- RRF merge -----
        merged = retriever.retrieve(query, context, top_k=10)
        print("\nRRF Merged Top 10 (pre-business-rules):")
        for i, cand in enumerate(merged[:10], 1):
            print(f"  {i:2}. [{cand['hybrid_score']:.4f}] {cand['name']}")

        # ----- Business rules -----
        final = rules_engine.apply(merged, context, top_k=10)
        print("\nFinal Recommendations (Top 10 after business rules):")
        for i, cand in enumerate(final, 1):
            print(f"  {i:2}. [{cand.get('rerank_score', cand.get('hybrid_score',0)):.4f}] {cand['name']} [{cand.get('test_type','')}]")

    # Save raw results for the engineering report
    out_path = os.path.join(ROOT, "artifacts", "final_engineering_benchmark.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"queries": QUERIES}, f, indent=2)
    print(f"\nBenchmark raw data saved to {out_path}")

if __name__ == "__main__":
    run()
