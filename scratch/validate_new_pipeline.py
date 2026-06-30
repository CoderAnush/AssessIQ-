"""
End-to-end validation of the new semantic retrieval pipeline.

Tests five canonical queries and prints:
  - Extracted entities
  - Query domain
  - Top 10 retrieved (pre-reranking) with hybrid_score
  - Top 10 after cross-encoder reranking with rerank_score
  - Top 10 after business rules

Run from project root:
    python scratch/validate_new_pipeline.py
"""

import json
import os
import sys
import time

# Ensure project root is on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, root)

from app.services.catalog_loader import CatalogLoader
from app.services.retriever import HybridRetriever
from app.services.cross_encoder_reranker import CrossEncoderReranker
from app.services.business_rules_engine import BusinessRulesEngine
from app.agents.decision_engine import DecisionEngine

# ---------------------------------------------------------------------------
QUERIES = [
    "Senior Java Backend Engineer with Spring Boot and microservices",
    "Senior React Frontend Engineer with TypeScript and Redux",
    "Python Backend Developer with FastAPI and PostgreSQL",
    "Machine Learning Engineer with PyTorch and NLP experience",
    "DevOps Engineer with Kubernetes, Terraform and AWS",
]

CATALOG_PATH = os.path.join(root, "data", "processed", "catalog_processed.json")
# ---------------------------------------------------------------------------


def fmt_list(items, indent=4):
    pad = " " * indent
    return "\n".join(f"{pad}{i+1}. {x}" for i, x in enumerate(items))


def run():
    print("=" * 70)
    print("AssessIQ — New Semantic Pipeline Validation")
    print("=" * 70)

    # Initialise services
    t0 = time.time()
    print("\n[1/4] Loading catalog …")
    catalog_loader = CatalogLoader(CATALOG_PATH)
    print(f"      {len(catalog_loader.get_all())} assessments loaded")

    print("[2/4] Building BM25 + FAISS indices (this may take ~30s first run) …")
    retriever = HybridRetriever(catalog_loader)

    print("[3/4] Loading cross-encoder reranker …")
    reranker = CrossEncoderReranker()
    print(f"      Cross-encoder available: {reranker.is_available}")

    rules_engine = BusinessRulesEngine()
    decision_engine = DecisionEngine()

    print(f"[4/4] Services ready in {time.time()-t0:.1f}s\n")

    results_summary = {}

    for query in QUERIES:
        print("\n" + "=" * 70)
        print(f"QUERY: {query}")
        print("=" * 70)

        # Entity extraction
        messages = [{"role": "user", "content": query}]
        context, intent = decision_engine.analyzer.analyze(messages)

        print(f"\n  Role:       {context.role}")
        print(f"  Seniority:  {context.seniority}")
        print(f"  Tech stack: {sorted(context.tech_stack) if context.tech_stack else '(empty)'}")
        print(f"  Domain:     {context.domain}")
        print(f"  Normalized: {context.normalized_role}")

        # Retrieval
        t1 = time.time()
        candidates = retriever.retrieve(query, context, top_k=10)
        print(f"\n  Retrieved {len(candidates)} candidates in {time.time()-t1:.2f}s")

        print("\n  Top 10 (pre-reranking, by RRF score):")
        for i, c in enumerate(candidates[:10], 1):
            print(f"    {i:2}. [{c['hybrid_score']:.4f}] {c['name']}")

        # Cross-encoder reranking
        t2 = time.time()
        reranked = reranker.rerank(query, candidates, top_k=20)
        print(f"\n  Reranked {len(reranked)} candidates in {time.time()-t2:.2f}s")

        print("\n  Top 10 (after cross-encoder reranking):")
        for i, c in enumerate(reranked[:10], 1):
            print(f"    {i:2}. [{c['rerank_score']:+.4f}] {c['name']}")

        # Business rules
        final = rules_engine.apply(reranked, context, top_k=10)

        print("\n  *** FINAL RECOMMENDATIONS (top 10 after business rules) ***")
        for i, c in enumerate(final, 1):
            print(f"    {i:2}. [{c.get('rerank_score', 0):+.4f}] {c['name']} [{c['test_type']}]")

        results_summary[query] = {
            "role": context.role,
            "seniority": context.seniority,
            "tech_stack": sorted(context.tech_stack) if context.tech_stack else [],
            "domain": context.domain,
            "retrieved_count": len(candidates),
            "top_10_retrieved": [c["name"] for c in candidates[:10]],
            "top_10_reranked": [c["name"] for c in reranked[:10]],
            "final_recommendations": [
                {"name": c["name"], "score": round(c.get("rerank_score", 0.0), 4), "test_type": c["test_type"]}
                for c in final
            ],
        }

    # Save output
    out_path = os.path.join(root, "artifacts", "new_pipeline_validation.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results_summary, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Validation complete. Results saved to: {out_path}")
    print("=" * 70)

    # Quick diagnostic: check if Java/React appear in expected queries
    java_query = QUERIES[0]
    react_query = QUERIES[1]

    java_names = [c["name"].lower() for c in results_summary[java_query]["final_recommendations"]]
    react_names = [c["name"].lower() for c in results_summary[react_query]["final_recommendations"]]

    java_ok = any("java" in n or "spring" in n for n in java_names)
    react_ok = any("react" in n or "javascript" in n for n in react_names)
    db2_gone = not any("db2" in n for n in java_names)
    vb_gone = not any("visual basic" in n for n in react_names)

    print("\n  Regression checks:")
    print(f"  Java assessment in Java query:    {'PASS' if java_ok else 'FAIL'}")
    print(f"  React assessment in React query:  {'PASS' if react_ok else 'FAIL'}")
    print(f"  DB2 absent from Java results:     {'PASS' if db2_gone else 'FAIL'}")
    print(f"  Visual Basic absent from React:   {'PASS' if vb_gone else 'FAIL'}")


if __name__ == "__main__":
    run()
