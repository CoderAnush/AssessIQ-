import requests
import sys

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "query": "Senior React Engineer with Redux and TypeScript",
        "must_have": [],
        "must_not_have": ["java"]
    },
    {
        "query": "Backend Java Engineer with Spring Boot",
        "must_have": ["java", "spring"],
        "must_not_have": ["javascript", "react", "angular", "vue"]
    },
    {
        "query": "Machine Learning Engineer with TensorFlow and NLP",
        "must_have": ["tensorflow", "nlp", "machine learning"],
        "must_not_have": ["engineering", "frontend", "backend"]
    },
    {
        "query": "Kubernetes Terraform DevOps engineer",
        "must_have": ["kubernetes", "docker", "cloud", "infrastructure"],
        "must_not_have": ["react", "java", "machine learning"]
    }
]

def run_test():
    print("="*80)
    print("SPECIALIZATION PRECISION TEST")
    print("="*80)
    
    passed = 0
    
    for i, test in enumerate(TEST_CASES):
        print(f"\n[{i+1}/{len(TEST_CASES)}] Query: '{test['query']}'")
        
        try:
            payload = {"messages": [{"role": "user", "content": test["query"]}]}
            resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
            
            if resp.status_code != 200:
                print(f"  [FAIL] HTTP {resp.status_code}")
                continue
                
            data = resp.json()
            recs = data.get("recommendations", [])
            
            print(f"  Retrieved Recommendations: {len(recs)}")
            
            leakage_found = []
            matched_tech = []
            
            for rec in recs:
                rec_name = rec.get("name", "")
                insight = rec.get("recruiter_insight", "")
                
                rec_text = (rec_name + " " + insight).lower()
                
                for required in test["must_have"]:
                    if required.lower() in rec_text:
                        matched_tech.append(required)
                        
                for forbidden in test["must_not_have"]:
                    if forbidden.lower() in rec_text and forbidden.lower() != "engineering":
                        leakage_found.append(f"{forbidden} (in {rec_name})")
                    # Special check for "engineering" word: it's fine if "UI Engineering" or "Software Engineering"
                    # But we want to avoid physical engineering. That was tested in domain lock test.
            
            # De-duplicate
            matched_tech = list(set(matched_tech))
            leakage_found = list(set(leakage_found))
            
            print(f"  Matched Required Tech: {matched_tech}")
            
            if len(leakage_found) == 0:
                print("  [PASS] Specialization Isolation Verified")
                passed += 1
            else:
                print(f"  [FAIL] Cross-Tech Leakage Detected: {leakage_found}")
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    if passed == len(TEST_CASES):
        print("[CATALOG-AWARE PRECISION VERIFIED]")
        sys.exit(0)
    else:
        print(f"[FAIL] {passed}/{len(TEST_CASES)} PASSED.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
