import json, re, os, sys

# Ensure project root on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root)

from app.services.catalog_loader import CatalogLoader
from app.services.retriever import HybridRetriever
from app.services.ranker_v2 import EnterpriseRanker
from app.services.domain_classifier import DomainClassifier
from app.agents.decision_engine import DecisionEngine
from app.config import settings

# Initialize services (no FastAPI lifecycle)
catalog_loader = CatalogLoader(getattr(settings, "catalog_path", "data/processed/catalog_enriched_v2.json"))
retriever = HybridRetriever(catalog_loader)
ranker = EnterpriseRanker(embedding_service=None, skill_graph=None)
domain_classifier = DomainClassifier()
decision_engine = DecisionEngine()

queries = [
    "Senior Java Backend Engineer",
    "Senior React Frontend Engineer",
    "Python Backend Developer",
    "ML Engineer",
    "DevOps Engineer",
]

results = []
for q in queries:
    # Build minimal message list for context extraction
    messages = [{"role": "user", "content": q}]
    # Extract context (skills, tech_stack, role, seniority) via conversation analyzer
    context, _ = decision_engine.analyzer.analyze(messages)
    # Domain detection
    domain_info = domain_classifier.detect_query_domain(q)
    domain = domain_info.get("primaryDomain")
    # Tokenization for entity extraction (simple regex used in chat route)
    user_query_tokens = set(re.findall(r"\\b[a-z0-9.]+\\b", q.lower()))
    normalized_skills = list(context.tech_stack)
    # Retrieval (hybrid) – top 30 candidates
    retrieved = retriever.retrieve(q, context, top_k=30)
    top10_retrieved = []
    for item in retrieved[:10]:
        top10_retrieved.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "score_before": item.get("hybrid_score"),
        })
    # Ranking – produce final scores and confidence values
    catalog = {a.id: a for a in catalog_loader.get_all()}
    ranked = ranker.rank(retrieved, context, catalog, top_k=12)
    top10_ranked = []
    for res in ranked[:10]:
        top10_ranked.append({
            "assessment_id": res.assessment.id,
            "name": res.assessment.name,
            "score_before": res.final_score,  # hybrid_score already folded into final_score by ranker
            "score_after": res.final_score,
            "confidence": int((res.final_score or 0) * 100),
        })
    results.append({
        "query": q,
        "extracted_entities": list(user_query_tokens),
        "normalized_skills": normalized_skills,
        "classified_domain": str(domain),
        "top_10_retrieved": top10_retrieved,
        "top_10_ranked": top10_ranked,
    })

print(json.dumps(results, indent=2))
