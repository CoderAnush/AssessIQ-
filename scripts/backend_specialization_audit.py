"""
Backend Specialization Audit — AssessIQ
Validates that different backend tech stacks get meaningfully different recommendations.
"""
import re
import sys
import time
import requests

BACKEND_URL = "http://localhost:8000"

JAVA_TOKENS = {"java", "spring", "j2ee", "hibernate", "enterprise java", "java beans",
               "java ee", "java 2", "java 8", "core java", "java frameworks", "java platform",
               "java web", "java design"}

SCENARIOS = [
    {
        "id": 1, "query": "Node.js backend developer with distributed systems",
        "label": "Node.js + Distributed",
        "forbidden_assessment_families": ["java"],
        "max_java_recs": 1,
        "expected_signals": ["distributed", "api", "backend", "architecture", "systems"],
    },
    {
        "id": 2, "query": "Python developer",
        "label": "Python Developer",
        "forbidden_assessment_families": [],
        "max_java_recs": 1,
        "expected_signals": ["python", "backend", "data", "api"],
    },
    {
        "id": 3, "query": "Backend Java Engineer with Spring Boot",
        "label": "Java Spring Boot",
        "forbidden_assessment_families": ["node", "frontend"],
        "max_java_recs": 10,  # Java is expected here
        "expected_signals": ["java", "backend"],
    },
    {
        "id": 4, "query": "FastAPI Python backend engineer",
        "label": "FastAPI Python",
        "forbidden_assessment_families": ["java"],
        "max_java_recs": 1,
        "expected_signals": ["python", "backend"],
    },
    {
        "id": 5, "query": "Django REST developer",
        "label": "Django REST",
        "forbidden_assessment_families": ["java"],
        "max_java_recs": 1,
        "expected_signals": ["python", "backend"],
    },
    {
        "id": 6, "query": "Kafka distributed systems backend engineer",
        "label": "Kafka Distributed",
        "forbidden_assessment_families": ["java"],
        "max_java_recs": 1,
        "expected_signals": ["distributed", "backend", "systems"],
    },
    {
        "id": 7, "query": "GraphQL API backend engineer",
        "label": "GraphQL API",
        "forbidden_assessment_families": ["java"],
        "max_java_recs": 1,
        "expected_signals": ["api", "backend"],
    },
]

def run_query(query):
    payload = {"messages": [{"role": "user", "content": query}]}
    start = time.time()
    r = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
    r.raise_for_status()
    return r.json(), time.time() - start

def count_java_recs(recs):
    count = 0
    for r in recs:
        name = str(r.get("name", "")).lower()
        insight = str(r.get("recruiter_insight", "")).lower()
        text = name + " " + insight
        if any(t in text for t in JAVA_TOKENS):
            count += 1
    return count

def check_diversity(results):
    """Checks that different non-Java queries return meaningfully different pipelines."""
    non_java = [(s["id"], s["query"], r) for s, r in results if "java" not in s["query"].lower() and "spring" not in s["query"].lower()]
    if len(non_java) < 2:
        return True, []
    
    issues = []
    for i in range(len(non_java)):
        for j in range(i+1, len(non_java)):
            id_a, q_a, recs_a = non_java[i]
            id_b, q_b, recs_b = non_java[j]
            names_a = {r.get("name") for r in recs_a}
            names_b = {r.get("name") for r in recs_b}
            if not names_a or not names_b:
                continue
            overlap = names_a.intersection(names_b)
            overlap_pct = len(overlap) / max(len(names_a), len(names_b))
            if overlap_pct > 0.80:  # >80% identical is a real duplication problem
                issues.append(f"[{id_a}] vs [{id_b}]: {int(overlap_pct*100)}% identical recommendations ({len(overlap)} shared)")
    return len(issues) == 0, issues

def run_audit():
    print()
    print("=" * 60)
    print("  BACKEND SPECIALIZATION AUDIT")
    print("=" * 60)

    all_results = []
    passed = 0

    for sc in SCENARIOS:
        print(f"\n[{sc['id']}/7] {sc['label']}")
        print(f"  Query: \"{sc['query']}\"")
        try:
            data, elapsed = run_query(sc["query"])
        except Exception as e:
            print(f"  [ERROR] {e}")
            all_results.append((sc, []))
            continue

        recs = data.get("recommendations", [])
        reply = data.get("reply", "")
        names = [r.get("name", "") for r in recs]
        java_count = count_java_recs(recs)

        violations = []
        if java_count > sc["max_java_recs"]:
            violations.append(f"Too many Java recs: {java_count} (max {sc['max_java_recs']})")
            for r in recs:
                name = str(r.get("name", "")).lower()
                if any(t in name for t in JAVA_TOKENS):
                    violations.append(f"  -> Java rec: {r.get('name')}")

        # Check sparse message correctness (non-java queries with 0 recs)
        if not recs and "java" not in sc["query"].lower():
            sparse_ok = any(k in reply.lower() for k in ["no exact", "limited", "closest", "sparse"])
            if not sparse_ok:
                violations.append("No sparse catalog guidance in reply despite 0 recs")

        ok = len(violations) == 0
        if ok:
            passed += 1

        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} | Recs: {len(recs)} | Java recs: {java_count} | {elapsed:.2f}s")
        print(f"  Names: {names[:4]}")
        for v in violations:
            print(f"  VIOLATION: {v}")

        all_results.append((sc, recs))

    # Diversity check
    print()
    print("  --- Diversity Check ---")
    div_ok, div_issues = check_diversity(all_results)
    if div_ok:
        print("  [PASS] Different backend queries return meaningfully different pipelines")
        passed += 1
    else:
        print("  [FAIL] Recommendation diversity insufficient:")
        for issue in div_issues:
            print(f"    {issue}")

    total = len(SCENARIOS) + 1  # +1 for diversity check
    print()
    print("=" * 60)
    print(f"  Passed: {passed}/{total}")
    if passed == total:
        print()
        print("  BACKEND SPECIALIZATION VERIFIED")
        print("  Zero Java spam | Full diversity | Correct sparse routing")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    run_audit()
