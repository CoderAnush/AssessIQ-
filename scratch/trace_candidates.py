import json, os, sys, re

# Add project root to PYTHONPATH
root = os.path.abspath('c:/Users/anush/Desktop/SHL/AssessIQ-')
sys.path.append(root)

from app.services.catalog_loader import CatalogLoader
from app.services.retriever import HybridRetriever
from app.services.domain_classifier import DomainClassifier
from app.agents.decision_engine import DecisionEngine

# Initialise services
catalog_path = getattr(__import__('app.config').config.settings, 'catalog_path', 'data/processed/catalog_enriched_v2.json')
catalog_loader = CatalogLoader(catalog_path)
retriever = HybridRetriever(catalog_loader)
decision_engine = DecisionEngine()

def trace_query(query):
    messages = [{"role": "user", "content": query}]
    context, _ = decision_engine.analyzer.analyze(messages)
    domain_info = DomainClassifier().detect_query_domain(query)
    domain = str(domain_info.get('primaryDomain'))
    # Retrieve (to get normal behavior) – not used here
    # Build detailed trace for first 50 assessments
    candidate_trace = []
    # Pre-compute flags used in scoring
    query_low = query.lower()
    query_tokens = set(re.findall(r"\\b[a-z0-9.]+\\b", query_low))
    explicit_python = "python" in query_low
    explicit_java = "java" in query_low and "javascript" not in query_low
    explicit_fastapi = "fastapi" in query_low
    explicit_devops = any(w in query_low for w in ["devops", "kubernetes", "terraform", "sre"]) 
    explicit_frontend = any(w in query_low for w in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web"]) 
    # Backend tech family detection (same as in retriever)
    BACKEND_TECH_FAMILIES = {
        "node": ["node", "node.js", "nodejs", "express", "nestjs", "javascript backend"],
        "python": ["python", "fastapi", "django", "flask", "sqlalchemy"],
        "java": ["java", "spring", "springboot", "spring boot", "java ee", "hibernate", "j2ee"],
        "go": ["golang", "go ", "gorilla", "grpc"],
        "distributed": ["distributed", "kafka", "microservices", "microservice", "event-driven", "message queue"],
        "api": ["graphql", "api gateway", "rest api", "grpc", "openapi"],
        "database": ["postgresql", "mysql", "redis", "mongodb", "cassandra", "nosql", "sql"],
        "devops_adj": ["docker", "kubernetes", "terraform", "ci/cd", "helm"]
    }
    query_family = set()
    for family, signals in BACKEND_TECH_FAMILIES.items():
        if any(s in query_low for s in signals):
            query_family.add(family)
    JAVA_ASSESSMENT_TOKENS = {"java", "spring", "j2ee", "hibernate", "java ee", "servlet", "ejb", "java beans"}
    suppress_java = bool(query_family) and "java" not in query_family
    # Retrieve all assessments (but we'll only process first 50)
    all_assessments = catalog_loader.get_all()
    for idx, assessment in enumerate(all_assessments):
        if idx >= 50:
            break
        name_low = assessment.name.lower()
        desc_low = assessment.description.lower()
        metadata_str = f"{name_low} {desc_low}"
        # Domain mismatch filter (same as retriever)
        if retriever._is_domain_mismatch(context.normalized_role, name_low, desc_low, None):
            continue
        # Component scores
        comp = {
            "assessment_name": assessment.name,
            "base_keyword_score": 0.0,
            "legacy_penalty": 0.0,
            "explicit_java_bonus": 0.0,
            "explicit_python_bonus": 0.0,
            "react_bonus": 0.0,
            "react_penalty": 0.0,
            "java_penalty": 0.0,
            "cross_stack_penalty": 0.0,
            "devops_bonus": 0.0,
            "skill_graph_bonus": 0.0,
            "fastapi_bonus": 0.0,
            "domain_bonus": 0.0
        }
        # Base keyword matching
        if any(term in metadata_str for term in query_low.split()):
            comp["base_keyword_score"] += 0.1
        # Legacy technology penalty
        LEGACY_TECH_TOKENS = {"db2", "sas", "embedded", "mainframe", "z/os", "os390", "cobol", "fortran"}
        query_tokens_set = set(re.findall(r"\\b[a-z0-9.]+\\b", query_low))
        metadata_tokens = set(re.findall(r"\\b[a-z0-9.]+\\b", metadata_str))
        if any(tok in metadata_tokens for tok in LEGACY_TECH_TOKENS):
            if not any(tok in query_low for tok in LEGACY_TECH_TOKENS):
                comp["legacy_penalty"] -= 4.0
        # Explicit tech boosts
        if explicit_python and "python" in metadata_tokens:
            comp["explicit_python_bonus"] += 0.5
        if explicit_java and "java" in metadata_tokens:
            comp["explicit_java_bonus"] += 0.5
        # React framework boost/penalty
        if "react" in query_tokens:
            if "react" in metadata_tokens:
                comp["react_bonus"] += 3.0
            if "java" in metadata_tokens:
                comp["react_penalty"] -= 3.0
        # Java penalty for non‑java queries
        if explicit_java and "javascript" in metadata_tokens and "javascript" not in query_low:
            comp["java_penalty"] -= 3.0
        # Cross‑stack Java suppression
        if suppress_java:
            java_hit = any(t in metadata_tokens for t in JAVA_ASSESSMENT_TOKENS)
            if java_hit:
                arch_signals = {"distributed", "microservices", "architecture", "systems", "backend"}
                arch_overlap = arch_signals.intersection(metadata_tokens)
                if not arch_overlap:
                    comp["cross_stack_penalty"] -= 4.0
                else:
                    comp["cross_stack_penalty"] -= 2.0
        # DevOps boost
        if explicit_devops and any(w in metadata_tokens for w in ["devops", "kubernetes", "terraform", "cloud", "infrastructure"]):
            comp["devops_bonus"] += 0.5
        # Skill graph expansion (use tech_stack from context)
        tech_stack = getattr(context, "tech_stack", set())
        for skill in tech_stack:
            if skill.lower() in metadata_str:
                comp["skill_graph_bonus"] += 0.3
            else:
                related = retriever.skill_graph.get_related_skills(skill)
                if any(r.lower() in metadata_str for r in related):
                    comp["skill_graph_bonus"] += 0.15
        # FastAPI role mapping bonus
        if explicit_fastapi:
            if any(term in metadata_str for term in ["fastapi", "python", "backend", "microservice", "django", "flask"]):
                comp["fastapi_bonus"] += 0.7
        # Domain bonus – not explicitly coded in retriever, placeholder 0
        # Sum total score
        total_score = sum(v for v in comp.values() if isinstance(v, (int, float)))
        comp["final_pre_threshold_score"] = total_score
        # Apply threshold used in retriever (>= 0.0 after our change)
        if total_score >= 0.0:
            comp["filtered_out"] = False
            comp["filter_reason"] = None
        else:
            comp["filtered_out"] = True
            comp["filter_reason"] = "score below threshold"
        candidate_trace.append(comp)
    return candidate_trace

if __name__ == "__main__":
    queries = [
        "Senior Java Backend Engineer",
        "Senior React Frontend Engineer",
        "Python Backend Developer"
    ]
    all_results = {}
    for q in queries:
        trace = trace_query(q)
        # Sort by pre‑threshold score descending
        trace_sorted = sorted(trace, key=lambda x: x["final_pre_threshold_score"], reverse=True)
        all_results[q] = trace_sorted
    print(json.dumps(all_results, indent=2))
