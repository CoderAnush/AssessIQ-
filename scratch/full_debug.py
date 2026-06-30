import json, os, sys, re

# Add project root to PYTHONPATH
root = os.path.abspath('c:/Users/anush/Desktop/SHL/AssessIQ-')
sys.path.append(root)

from app.services.catalog_loader import CatalogLoader
from app.services.retriever import HybridRetriever
from app.services.ranker_v2 import EnterpriseRanker
from app.services.domain_classifier import DomainClassifier
from app.agents.decision_engine import DecisionEngine
from app.config import settings

# Initialise services (no FastAPI lifecycle needed)
catalog_path = getattr(settings, 'catalog_path', 'data/processed/catalog_enriched_v2.json')
catalog_loader = CatalogLoader(catalog_path)
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
    # Create minimal message list for context extraction
    messages = [{"role": "user", "content": q}]
    context, _ = decision_engine.analyzer.analyze(messages)
    # Domain detection
    domain_info = domain_classifier.detect_query_domain(q)
    domain = str(domain_info.get('primaryDomain'))
    # Extract entities (same regex used in chat route)
    extracted_entities = list(set(re.findall(r"\\b[a-z0-9.]+\\b", q.lower())))
    # Normalized role and tech stack
    normalized_role = getattr(context, 'role', '')
    normalized_skills = list(getattr(context, 'tech_stack', []))
    normalized_technologies = normalized_skills  # same list for this pipeline
    # Retrieval
    retrieved = retriever.retrieve(q, context, top_k=30)
    top_retrieved = []
    for item in retrieved[:10]:
        top_retrieved.append({
            "id": item.get('id'),
            "name": item.get('name'),
            "hybrid_score": item.get('hybrid_score'),
            "url": item.get('url')
        })
    # Ranking
    catalog = {a.id: a for a in catalog_loader.get_all()}
    ranked = ranker.rank(retrieved, context, catalog, top_k=12)
    top_ranked = []
    # Map fallback flag by checking original retrieved dict
    fallback_lookup = {item.get('id'): item.get('is_fallback', False) for item in retrieved}
    for res in ranked[:10]:
        assess = res.assessment
        fid = assess.id
        top_ranked.append({
            "id": fid,
            "name": assess.name,
            "reranked_score": res.final_score,
            "confidence": int((res.final_score or 0) * 100),
            "fallback": fallback_lookup.get(fid, False),
            "url": assess.url
        })
    results.append({
        "query": q,
        "extracted_entities": extracted_entities,
        "normalized_role": normalized_role,
        "normalized_skills": normalized_skills,
        "normalized_technologies": normalized_technologies,
        "classified_domain": domain,
        "top_10_retrieved": top_retrieved,
        "top_10_ranked": top_ranked
    })

print(json.dumps(results, indent=2))

# ---------- Catalog statistics ----------
catalog_file = os.path.join(root, catalog_path)
with open(catalog_file, 'r', encoding='utf-8') as f:
    catalog_data = json.load(f)

total = len(catalog_data)
java = [a['name'] for a in catalog_data if re.search(r'java', a['name'], re.I) or re.search(r'java', a.get('description',''), re.I)]
python = [a['name'] for a in catalog_data if re.search(r'python', a['name'], re.I) or re.search(r'python', a.get('description',''), re.I)]
react = [a['name'] for a in catalog_data if re.search(r'react', a['name'], re.I) or re.search(r'react', a.get('description',''), re.I) or re.search(r'frontend', a['name'], re.I) or re.search(r'frontend', a.get('description',''), re.I)]
devops = [a['name'] for a in catalog_data if re.search(r'devops', a['name'], re.I) or re.search(r'devops', a.get('description',''), re.I) or re.search(r'kubernetes', a['name'], re.I) or re.search(r'kubernetes', a.get('description',''), re.I) or re.search(r'terraform', a['name'], re.I) or re.search(r'terraform', a.get('description',''), re.I)]
ml = [a['name'] for a in catalog_data if re.search(r'(ml|machine learning|nlp|data science)', a['name'], re.I) or re.search(r'(ml|machine learning|nlp|data science)', a.get('description',''), re.I)]

stats = {
    "total_assessments": total,
    "java_assessments": java,
    "python_assessments": python,
    "react_frontend_assessments": react,
    "devops_assessments": devops,
    "ml_data_science_assessments": ml
}
print("---CATALOG STATISTICS---")
print(json.dumps(stats, indent=2))
