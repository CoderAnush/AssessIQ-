import json, re, sys, os
# Ensure project root on path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root)
from app.main import create_app
from app.models.response import ChatRequest, Message

app = create_app()
services = app.state

queries = [
    "Senior Java Backend Engineer",
    "Senior React Frontend Engineer",
    "Python Backend Developer",
    "ML Engineer",
    "DevOps Engineer",
]

results = []
for q in queries:
    # Build minimal message list
    messages = [{"role": "user", "content": q}]
    # Decision engine to get context and intent (ignore intent)
    context, _ = services.decision_engine.analyze(messages)
    # Domain detection
    domain_classifier = services.domain_classifier
    domain_class = domain_classifier.detect_query_domain(q)
    domain = domain_class["primaryDomain"]
    # Extract entities (simple tokenization as used in chat route)
    user_query_tokens = set(re.findall(r'\\b[a-z0-9.]+\\b', q.lower()))
    # For normalized skills we assume context.tech_stack after merging
    normalized_skills = list(context.tech_stack)
    # Retrieval
    retrieved = services.retriever.retrieve(q, context, top_k=30)
    # Score before ranking (hybrid_score)
    top10 = retrieved[:10]
    # Ranking
    catalog = {a.id: a for a in services.catalog_loader.get_all()}
    ranked = services.ranker.rank(retrieved, context, catalog, top_k=12)
    # Build output
    entry = {
        "query": q,
        "extracted_entities": list(user_query_tokens),
        "normalized_skills": normalized_skills,
        "classified_domain": str(domain),
        "top_10_retrieved": [{"id": r["id"], "name": r.get("name"), "score_before": r.get("hybrid_score")} for r in top10],
        "ranked": [{
            "name": res.assessment.name,
            "id": res.assessment.id,
            "score_before": res.final_score,
            "score_after": res.final_score,  # ranker may adjust final_score already
            "confidence": res.final_score,  # placeholder
            "primary": True,  # placeholder, will compute later
        } for res in ranked[:10]],
    }
    results.append(entry)

print(json.dumps(results, indent=2))
