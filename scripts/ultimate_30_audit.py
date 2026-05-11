"""
ULTIMATE 30-SCENARIO PRODUCTION AUDIT — AssessIQ
Validates all major engineering domains, stress cases, and physical engineering blocks.
"""

import re
import sys
import time
import requests

BACKEND_URL = "http://localhost:8000"

PHYSICAL_ENG = [
    "electrical", "civil", "aerospace", "mechanical", "chemical",
    "aeronautical", "automotive", "ceramic", "geoinformatics", "fire engineering",
    "geoscience", "instrumentation engineering", "industrial engineering",
    "petroleum", "mining", "naval", "metallurgy", "textile", "biomedical engineering",
    "cad", "bim", "structural", "surveying"
]

SCENARIOS = [
    # --- BACKEND / API ENGINEERING ---
    {"id": 1, "query": "Senior Java Backend Engineer with Spring Boot and Microservices", "domain": "BACKEND", "forbidden_terms": ["javascript", "react", "angular", "frontend"], "min_recs": 3},
    {"id": 2, "query": "Python FastAPI backend engineer", "domain": "BACKEND", "forbidden_terms": ["machine learning", "frontend"], "min_recs": 0},
    {"id": 3, "query": "Node.js backend developer with distributed systems", "domain": "BACKEND", "forbidden_terms": ["react", "ui", "frontend"], "min_recs": 0},
    {"id": 4, "query": "Django REST API developer", "domain": "BACKEND", "forbidden_terms": ["machine learning", "data science"], "min_recs": 0},
    {"id": 5, "query": "Java enterprise architect with distributed systems", "domain": "BACKEND", "forbidden_terms": ["javascript"], "min_recs": 2},

    # --- FRONTEND ENGINEERING ---
    {"id": 6, "query": "Senior React Engineer with Redux and TypeScript", "domain": "FRONTEND", "forbidden_terms": ["java", "spring", "backend api", "machine learning"], "min_recs": 0},
    {"id": 7, "query": "Angular frontend architect with RxJS", "domain": "FRONTEND", "forbidden_terms": ["react", "java"], "min_recs": 3},
    {"id": 8, "query": "Vue.js frontend engineer", "domain": "FRONTEND", "forbidden_terms": ["backend", "api", "machine learning"], "min_recs": 2},
    {"id": 9, "query": "Next.js frontend engineer", "domain": "FRONTEND", "forbidden_terms": ["backend", "java"], "min_recs": 0},
    {"id": 10, "query": "HTML CSS JavaScript UI engineer", "domain": "FRONTEND", "forbidden_terms": ["java", "backend", "machine learning"], "min_recs": 2},

    # --- DEVOPS / CLOUD / SRE ---
    {"id": 11, "query": "Kubernetes Terraform DevOps engineer", "domain": "DEVOPS", "forbidden_terms": ["frontend", "backend", "java", "react"], "min_recs": 3},
    {"id": 12, "query": "AWS cloud infrastructure engineer", "domain": "DEVOPS", "forbidden_terms": ["frontend", "backend", "react"], "min_recs": 3},
    {"id": 13, "query": "SRE engineer with Linux and monitoring", "domain": "DEVOPS", "forbidden_terms": ["frontend", "react"], "min_recs": 3},
    {"id": 14, "query": "Docker CI/CD platform engineer", "domain": "DEVOPS", "forbidden_terms": ["frontend", "react"], "min_recs": 3},
    {"id": 15, "query": "Helm ArgoCD Kubernetes platform engineer", "domain": "DEVOPS", "forbidden_terms": ["machine learning", "frontend"], "min_recs": 3},

    # --- AI / ML / DATA SCIENCE ---
    {"id": 16, "query": "Machine Learning Engineer with TensorFlow and NLP", "domain": "DATA_AI", "forbidden_terms": ["backend", "frontend", "civil"], "min_recs": 2},
    {"id": 17, "query": "Data Scientist with Python Pandas and Scikit-learn", "domain": "DATA_AI", "forbidden_terms": ["backend", "react"], "min_recs": 3},
    {"id": 18, "query": "LLM engineer with RAG and vector databases", "domain": "DATA_AI", "forbidden_terms": ["frontend", "backend"], "min_recs": 0},
    {"id": 19, "query": "Deep Learning engineer with PyTorch", "domain": "DATA_AI", "forbidden_terms": ["civil", "frontend"], "min_recs": 2},
    {"id": 20, "query": "ML deployment engineer", "domain": "DATA_AI", "forbidden_terms": ["frontend"], "min_recs": 0},

    # --- STRESS / EDGE CASES ---
    {"id": 21, "query": "React architect building scalable frontend systems", "domain": "FRONTEND", "forbidden_terms": ["java", "backend"], "min_recs": 0},
    {"id": 22, "query": "JavaScript frontend developer", "domain": "FRONTEND", "forbidden_terms": ["java "], "min_recs": 3}, # Space after java to avoid javascript
    {"id": 23, "query": "Senior Java developer", "domain": "BACKEND", "forbidden_terms": ["javascript"], "min_recs": 3},
    {"id": 24, "query": "Cloud DevOps SRE architect", "domain": "DEVOPS", "forbidden_terms": ["frontend", "backend"], "min_recs": 3},
    {"id": 25, "query": "AI researcher with generative AI and transformers", "domain": "DATA_AI", "forbidden_terms": ["frontend", "backend"], "min_recs": 0},
    {"id": 26, "query": "Backend engineer with Kafka Redis PostgreSQL", "domain": "BACKEND", "forbidden_terms": ["frontend", "react"], "min_recs": 0},
    {"id": 27, "query": "Frontend UI engineer with accessibility and design systems", "domain": "FRONTEND", "forbidden_terms": ["backend", "api"], "min_recs": 0},

    # --- PHYSICAL ENGINEERING (BLOCK) ---
    {"id": 28, "query": "Civil engineering project manager", "domain": "ENGINEERING_CORE", "forbidden_terms": ["software", "backend", "frontend", "devops", "data science"], "min_recs": 0, "max_recs": 0},
    {"id": 29, "query": "Electrical instrumentation engineer", "domain": "ENGINEERING_CORE", "forbidden_terms": ["software", "backend", "frontend"], "min_recs": 0, "max_recs": 0},
    {"id": 30, "query": "Mechanical CAD engineer", "domain": "ENGINEERING_CORE", "forbidden_terms": ["software", "backend", "frontend"], "min_recs": 0, "max_recs": 0},
]

def run_query(query: str):
    payload = {"messages": [{"role": "user", "content": query}]}
    resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

def check_leakage(recs, forbidden_terms):
    violations = []
    for rec in recs:
        text = (rec.get("name", "") + " " + rec.get("recruiter_insight", "")).lower()
        for term in forbidden_terms:
            if re.search(r'\b' + re.escape(term.lower()) + r'\b', text):
                violations.append(f'Forbidden term "{term}" found in "{rec.get("name")}"')
        
        # Physical engineering check for software domains
        for eng in PHYSICAL_ENG:
            if re.search(r'\b' + re.escape(eng) + r'\b', text):
                violations.append(f'Physical engineering term "{eng}" leaked into software recommendation')
    return violations

def run_audit():
    print("=" * 70)
    print("  ULTIMATE 30-SCENARIO PRODUCTION AUDIT")
    print("=" * 70)
    
    passed_count = 0
    results = []

    for sc in SCENARIOS:
        print(f"[{sc['id']:02d}/30] Testing: \"{sc['query']}\"")
        try:
            data = run_query(sc["query"])
            recs = data.get("recommendations", [])
            reply = data.get("reply", "")
            
            violations = check_leakage(recs, sc["forbidden_terms"])
            
            # Domain check
            wrong_domain = []
            for r in recs:
                dom = str(r.get("domain", "")).upper()
                if sc["domain"] != "ENGINEERING_CORE" and dom == "ENGINEERING_CORE":
                    wrong_domain.append(f"{r.get('name')} (ENGINEERING_CORE)")
                elif sc["domain"] == "ENGINEERING_CORE" and len(recs) > 0:
                     # For physical engineering, any recs might be considered a leak if they are software
                     pass

            # Sparse check
            is_sparse = any(k in reply.lower() for k in ["no exact", "limited", "closest", "sparse", "broadening", "analyzed this"])
            min_ok = len(recs) >= sc["min_recs"] or is_sparse or sc["min_recs"] == 0
            max_ok = len(recs) <= sc.get("max_recs", 999)

            if not violations and not wrong_domain and min_ok and max_ok:
                passed_count += 1
                print(f"  [PASS] Recs: {len(recs)}")
            else:
                print(f"  [FAIL]")
                if violations: print(f"    Violations: {violations[:2]}")
                if wrong_domain: print(f"    Wrong Domain: {wrong_domain[:2]}")
                if not min_ok: print(f"    Min Recs not met (got {len(recs)})")
                if not max_ok: print(f"    Max Recs exceeded (got {len(recs)})")
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 70)
    print(f"  AUDIT COMPLETE: {passed_count}/30 PASSED")
    print("=" * 70)
    
    if passed_count == 30:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_audit()
