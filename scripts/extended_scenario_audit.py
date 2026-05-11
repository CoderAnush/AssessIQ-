"""
Extended 20+ Scenario Audit — AssessIQ Recruiter Intelligence Copilot
Tests domain isolation, specialization precision, cross-domain leakage,
sparse catalog handling, and recommendation quality across 22 distinct scenarios.
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
    "petroleum", "mining", "naval", "metallurgy", "textile", "biomedical engineering"
]

SCENARIOS = [
    # ── BACKEND ──────────────────────────────────────────────────────────────
    {
        "id": 1, "label": "Backend Java + Spring Boot",
        "query": "Backend Java Engineer with Spring Boot",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["javascript", "react", "angular", "css", "html"],
        "forbidden_domains": ["FRONTEND", "DEVOPS", "DATA_AI"],
        "min_recs": 3,
    },
    {
        "id": 2, "label": "Python FastAPI Backend",
        "query": "Python FastAPI backend engineer",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["machine learning", "data science", "tensorflow", "react", "angular"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 3, "label": "Node.js Microservices Backend",
        "query": "Node.js microservices backend developer",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["react", "angular", "frontend", "civil", "electrical"],
        "forbidden_domains": ["FRONTEND", "DATA_AI", "DEVOPS"],
        "min_recs": 0,
    },
    {
        "id": 4, "label": "Django REST API Engineer",
        "query": "Django REST API backend engineer",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["react", "javascript frontend", "tensorflow"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 5, "label": "Senior Java Developer",
        "query": "Senior Java developer with distributed systems",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["javascript", "react", "angular", "civil"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 3,
    },

    # ── FRONTEND ─────────────────────────────────────────────────────────────
    {
        "id": 6, "label": "React + Redux + TypeScript",
        "query": "Senior React Engineer with Redux and TypeScript",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java", "spring", "backend api", "machine learning"],
        "forbidden_domains": ["BACKEND", "DEVOPS", "DATA_AI"],
        "min_recs": 0,   # sparse catalog — acceptable
    },
    {
        "id": 7, "label": "Angular Frontend Architect + RxJS",
        "query": "Angular frontend architect with RxJS",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java", "python backend", "machine learning"],
        "forbidden_domains": ["BACKEND", "DEVOPS", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 8, "label": "Vue.js Frontend Developer",
        "query": "Vue.js frontend developer",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java", "spring", "machine learning"],
        "forbidden_domains": ["BACKEND", "DEVOPS", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 9, "label": "Next.js Full Stack Frontend",
        "query": "Next.js full stack frontend engineer",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java", "backend api", "machine learning"],
        "forbidden_domains": ["BACKEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 10, "label": "CSS / HTML UI Engineer",
        "query": "Senior UI engineer with HTML CSS JavaScript",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java backend", "spring", "tensorflow"],
        "forbidden_domains": ["BACKEND", "DATA_AI"],
        "min_recs": 0,
    },

    # ── DATA / AI ─────────────────────────────────────────────────────────────
    {
        "id": 11, "label": "ML Engineer TensorFlow + NLP",
        "query": "Machine Learning Engineer with TensorFlow and NLP",
        "expected_domain": "DATA_AI",
        "forbidden_terms": ["civil engineering", "electrical engineering", "frontend", "react"],
        "forbidden_domains": ["FRONTEND", "DEVOPS", "ENGINEERING_CORE"],
        "min_recs": 2,
    },
    {
        "id": 12, "label": "Data Scientist Python + Pandas",
        "query": "Data Scientist with Python and Pandas",
        "expected_domain": "DATA_AI",
        "forbidden_terms": ["react", "angular", "frontend", "civil"],
        "forbidden_domains": ["FRONTEND", "DEVOPS"],
        "min_recs": 0,
    },
    {
        "id": 13, "label": "LLM / GenAI Engineer",
        "query": "LLM engineer with prompt engineering and RAG",
        "expected_domain": "DATA_AI",
        "forbidden_terms": ["react", "frontend", "devops", "civil", "electrical"],
        "forbidden_domains": ["FRONTEND", "DEVOPS"],
        "min_recs": 0,
    },
    {
        "id": 14, "label": "Deep Learning PyTorch",
        "query": "Deep learning engineer with PyTorch",
        "expected_domain": "DATA_AI",
        "forbidden_terms": ["civil", "react", "angular", "frontend"],
        "forbidden_domains": ["FRONTEND", "DEVOPS"],
        "min_recs": 0,
    },

    # ── DEVOPS ────────────────────────────────────────────────────────────────
    {
        "id": 15, "label": "Kubernetes + Terraform DevOps",
        "query": "Kubernetes Terraform DevOps engineer",
        "expected_domain": "DEVOPS",
        "forbidden_terms": ["react", "java", "machine learning", "civil", "electrical"],
        "forbidden_domains": ["FRONTEND", "BACKEND", "DATA_AI", "ENGINEERING_CORE"],
        "min_recs": 2,
    },
    {
        "id": 16, "label": "AWS Cloud Engineer",
        "query": "AWS Cloud infrastructure engineer",
        "expected_domain": "DEVOPS",
        "forbidden_terms": ["react", "java backend", "machine learning", "civil"],
        "forbidden_domains": ["FRONTEND", "BACKEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 17, "label": "SRE Site Reliability Engineer",
        "query": "Site Reliability Engineer with Linux and monitoring",
        "expected_domain": "DEVOPS",
        "forbidden_terms": ["react", "java backend", "machine learning"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 18, "label": "Docker CI/CD Engineer",
        "query": "Docker CI/CD pipeline DevOps engineer",
        "expected_domain": "DEVOPS",
        "forbidden_terms": ["react", "java", "machine learning", "civil", "electrical"],
        "forbidden_domains": ["FRONTEND", "BACKEND", "DATA_AI"],
        "min_recs": 0,
    },

    # ── CROSS-DOMAIN STRESS TESTS ─────────────────────────────────────────────
    {
        "id": 19, "label": "[STRESS] Java query must not get React",
        "query": "Java EE enterprise backend developer",
        "expected_domain": "BACKEND",
        "forbidden_terms": ["react", "angular", "vue", "css", "html", "frontend"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 3,
    },
    {
        "id": 20, "label": "[STRESS] React query must not get Java",
        "query": "React component architect",
        "expected_domain": "FRONTEND",
        "forbidden_terms": ["java", "spring boot", "hibernate", "enterprise java"],
        "forbidden_domains": ["BACKEND", "DATA_AI"],
        "min_recs": 0,
    },
    {
        "id": 21, "label": "[STRESS] ML query must not get frontend",
        "query": "Machine learning model deployment engineer",
        "expected_domain": "DATA_AI",
        "forbidden_terms": ["react", "angular", "frontend", "css", "html"],
        "forbidden_domains": ["FRONTEND"],
        "min_recs": 0,
    },
    {
        "id": 22, "label": "[STRESS] DevOps must not get ML/AI",
        "query": "Platform engineer with Helm and ArgoCD",
        "expected_domain": "DEVOPS",
        "forbidden_terms": ["machine learning", "tensorflow", "pytorch", "react"],
        "forbidden_domains": ["FRONTEND", "DATA_AI"],
        "min_recs": 0,
    },
]


def run_query(query: str, timeout: int = 30):
    payload = {"messages": [{"role": "user", "content": query}]}
    start = time.time()
    resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=timeout)
    elapsed = time.time() - start
    resp.raise_for_status()
    return resp.json(), elapsed


def check_leakage(recs, forbidden_terms, forbidden_domains):
    violations = []
    for rec in recs:
        name = str(rec.get("name", "")).lower()
        insight = str(rec.get("recruiter_insight", "")).lower()
        domain = str(rec.get("domain", "")).upper()
        text = name + " " + insight

        for term in forbidden_terms:
            if re.search(r'\b' + re.escape(term.lower()) + r'\b', text):
                violations.append(f'Forbidden term "{term}" in "{rec.get("name")}"')

        for dom in forbidden_domains:
            if domain == dom.upper():
                violations.append(f'Forbidden domain "{dom}" on "{rec.get("name")}"')

        for eng in PHYSICAL_ENG:
            if re.search(r'\b' + re.escape(eng) + r'\b', text):
                violations.append(f'Physical engineering "{eng}" in "{rec.get("name")}"')

    return violations


def run_audit():
    print()
    print("=" * 66)
    print("  ASSESSIQ EXTENDED 22-SCENARIO AUDIT")
    print("=" * 66)

    results = []
    latencies = []

    for sc in SCENARIOS:
        print(f"\n[{sc['id']:02d}/22] {sc['label']}")
        print(f"  Query: \"{sc['query']}\"")

        try:
            data, elapsed = run_query(sc["query"])
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append({"id": sc["id"], "passed": False, "note": str(e)})
            continue

        latencies.append(elapsed)
        recs = data.get("recommendations", [])
        reply = data.get("reply", "")
        domains = list({str(r.get("domain", "")).upper() for r in recs})

        violations = check_leakage(recs, sc["forbidden_terms"], sc["forbidden_domains"])

        # Min-recs check (only fail if non-zero requirement not met AND no sparse msg)
        sparse_keywords = ["limited in the current catalog", "no exact", "closest validated", "specialized assessments"]
        is_sparse = any(k in reply.lower() for k in sparse_keywords)
        min_ok = len(recs) >= sc["min_recs"] or is_sparse or sc["min_recs"] == 0

        # Domain check
        wrong_domain = []
        for r in recs:
            d = str(r.get("domain", "")).upper()
            if d not in [sc["expected_domain"], "GENERAL", ""]:
                wrong_domain.append(f'{r.get("name")} ({d})')

        passed = len(violations) == 0 and min_ok and len(wrong_domain) == 0

        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} | Recs: {len(recs)} | Domains: {domains} | {elapsed:.2f}s")

        if violations:
            for v in violations[:3]:
                print(f"    VIOLATION: {v}")
        if wrong_domain:
            for w in wrong_domain[:3]:
                print(f"    WRONG DOMAIN: {w}")
        if not min_ok:
            print(f"    MIN RECS not met: got {len(recs)}, needed {sc['min_recs']}")

        results.append({"id": sc["id"], "label": sc["label"], "passed": passed,
                        "recs": len(recs), "domains": domains, "latency": elapsed})

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    passed_count = sum(1 for r in results if r["passed"])
    total = len(SCENARIOS)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0

    print()
    print("=" * 66)
    print("  EXTENDED AUDIT RESULTS")
    print("=" * 66)
    print(f"  Passed:      {passed_count}/{total}")
    print(f"  Avg Latency: {avg_lat:.2f}s")
    print(f"  Max Latency: {max_lat:.2f}s")
    print()

    # Per-domain summary
    domains_tested = {"BACKEND": [], "FRONTEND": [], "DATA_AI": [], "DEVOPS": []}
    for r in results:
        for dom in domains_tested:
            sc_match = next((s for s in SCENARIOS if s["id"] == r["id"] and s["expected_domain"] == dom), None)
            if sc_match:
                domains_tested[dom].append(r["passed"])

    print("  Domain Breakdown:")
    for dom, outcomes in domains_tested.items():
        if outcomes:
            ok = sum(outcomes)
            print(f"    {dom:10s}: {ok}/{len(outcomes)} PASS")

    print()
    if passed_count == total:
        print("=" * 66)
        print("  ALL 22 SCENARIOS PASSED")
        print("  ZERO CROSS-DOMAIN LEAKAGE | ZERO PHYSICAL ENGINEERING LEAK")
        print("  ASSESSIQ ENTERPRISE VALIDATION: CERTIFIED")
        print("=" * 66)
        sys.exit(0)
    else:
        failed = [r for r in results if not r["passed"]]
        print(f"  {total - passed_count} SCENARIO(S) FAILED:")
        for f in failed:
            print(f"    [{f['id']:02d}] {f.get('label', '')}")
        print("=" * 66)
        sys.exit(1)


if __name__ == "__main__":
    run_audit()
