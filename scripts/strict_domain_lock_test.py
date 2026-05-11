import requests
import sys

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "query": "Backend Java Engineer with Spring Boot",
        "expected_domain": "BACKEND",
        "must_not_contain": ["engineering_core", "electrical", "civil", "aerospace", "mechanical", "chemical", "aeronautical", "automotive", "ceramic", "electronics"]
    },
    {
        "query": "Kubernetes Terraform DevOps engineer",
        "expected_domain": "DEVOPS",
        "must_not_contain": ["engineering_core", "electrical", "civil", "aerospace", "mechanical", "chemical", "aeronautical", "automotive", "ceramic", "electronics"]
    },
    {
        "query": "Machine Learning Engineer with TensorFlow",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["engineering_core", "electrical", "civil", "aerospace", "mechanical", "chemical", "aeronautical", "automotive", "ceramic", "electronics"]
    },
    {
        "query": "Senior React Engineer",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["engineering_core", "electrical", "civil", "aerospace", "mechanical", "chemical", "aeronautical", "automotive", "ceramic", "electronics"]
    }
]

def run_test():
    print("="*80)
    print("STRICT DOMAIN LOCK VALIDATION")
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
            
            domains = []
            leakage_found = []
            
            for rec in recs:
                rec_name = rec.get("name", "")
                domain = rec.get("domain", "")
                insight = rec.get("recruiter_insight", "")
                domains.append(domain)
                
                rec_text = (rec_name + " " + domain + " " + insight).lower()
                
                # Check for strictly expected domains
                if domain.upper() != test["expected_domain"] and domain.upper() != "GENERAL":
                     leakage_found.append(f"Invalid Domain: {domain}")
                
                for forbidden in test["must_not_contain"]:
                    if forbidden.lower() in rec_text:
                        leakage_found.append(f"{forbidden} (in {rec_name})")
            
            print(f"  Domains: {domains}")
            
            if len(leakage_found) == 0:
                print("  [PASS] Zero Engineering Contamination")
                passed += 1
            else:
                print(f"  [FAIL] Leakage Detected: {list(set(leakage_found))}")
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    if passed == len(TEST_CASES):
        print(f"[OK] {passed}/{len(TEST_CASES)} PASSED. ZERO LEAKAGE VALIDATED.")
        sys.exit(0)
    else:
        print(f"[FAIL] {passed}/{len(TEST_CASES)} PASSED. LEAKAGE PERSISTS.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
