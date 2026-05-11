"""
Final Elite Polish Validation Script.
Verifies React specialization, DevOps expansion, explainable reasoning, and recruiter signal.
"""

import requests
import sys

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "name": "React Specialization (Frontend)",
        "query": "Senior React Engineer with Redux and TypeScript",
        "expected_domain": "FRONTEND",
        "must_contain_any": ["react", "typescript"],
        "must_not_contain": ["angularjs", "angular", "backend"],
        "min_recommendations": 3
    },
    {
        "name": "Angular Specialization (Frontend)",
        "query": "Angular frontend architect",
        "expected_domain": "FRONTEND",
        "must_contain_any": ["angular", "rxjs"],
        "must_not_contain": ["react", "backend"],
        "min_recommendations": 3
    },
    {
        "name": "DevOps Cloud Expansion (DevOps)",
        "query": "Kubernetes Terraform Engineer",
        "expected_domain": "DEVOPS",
        "must_contain_any": ["kubernetes", "terraform", "cloud", "devops", "infrastructure"],
        "must_not_contain": ["frontend", "react"],
        "min_recommendations": 3
    },
    {
        "name": "FastAPI Validation (Backend)",
        "query": "FastAPI backend engineer",
        "expected_domain": "BACKEND",
        "must_contain_any": ["api", "backend systems", "distributed service", "fastapi"],
        "must_not_contain": ["frontend", "ui engineering"],
        "min_recommendations": 3
    },
    {
        "name": "TensorFlow NLP Validation (Data/AI)",
        "query": "TensorFlow NLP Engineer",
        "expected_domain": "DATA_AI",
        "must_contain_any": ["machine learning foundations", "nlp reasoning", "data science"],
        "must_not_contain": ["frontend", "ui engineering"],
        "min_recommendations": 3
    }
]

def run_validation():
    print("="*80)
    print("ASSESSIQ FINAL ELITE VALIDATION")
    print("="*80)
    
    passed = 0
    
    for i, test in enumerate(TEST_CASES):
        print(f"[{i+1}/{len(TEST_CASES)}] Testing: {test['name']}")
        print(f"  Prompt: '{test['query']}'")
        
        try:
            payload = {"messages": [{"role": "user", "content": test["query"]}]}
            resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
            
            if resp.status_code != 200:
                print(f"  [FAIL] HTTP {resp.status_code}")
                continue
                
            data = resp.json()
            reply = data.get("reply", "")
            recs = data.get("recommendations", [])
            
            # 1. Domain Check
            domain_label = test["expected_domain"].lower().replace("_", " ")
            domain_ok = f"enterprise {domain_label} hiring" in reply
            
            # 2. Constraints Check
            leakage = []
            matched_positives = 0
            reasoning_present = True
            
            for rec in recs:
                rec_name = rec.get("name", "")
                insight = rec.get("recruiter_insight", "")
                signal = rec.get("recruiter_signal", "")
                rec_text = (rec_name + " " + insight + " " + signal).lower()
                
                # Check for explainable AI phrases
                if not any(phr in insight.lower() for phr in ["recommended because", "related competency", "expanded match", "added due to"]):
                    reasoning_present = False
                    print(f"  [WARN] Reasoning missing or generic for {rec_name}: {insight}")

                for required in test.get("must_contain_any", []):
                    if required.lower() in rec_text:
                        matched_positives += 1
                        break
                
                for forbidden in test.get("must_not_contain", []):
                    if forbidden.lower() in rec_text:
                        leakage.append(f"{forbidden} (in {rec_name})")
            
            leakage_ok = len(leakage) == 0
            count_ok = len(recs) >= test["min_recommendations"]
            
            if domain_ok and leakage_ok and count_ok and reasoning_present:
                print(f"  [PASS] Domain: {test['expected_domain']} | Count: {len(recs)} | Zero Leakage | Explainable reasoning OK")
                passed += 1
            else:
                if not domain_ok:
                    print(f"  [FAIL] Domain mismatch in reply: '{reply[:50]}...'")
                if not leakage_ok:
                    print(f"  [FAIL] Leakage Detected: {list(set(leakage))}")
                if not count_ok:
                    print(f"  [FAIL] Recommendation count too low: {len(recs)} < {test['min_recommendations']}")
                if not reasoning_present:
                    print(f"  [FAIL] Did not detect explainable AI reasoning string.")
                    
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    print(f"VALIDATION SUMMARY: {passed}/{len(TEST_CASES)} PASSED")
    print("="*80)
    
    if passed == len(TEST_CASES):
        print("\n[OK] SYSTEM CERTIFIED: Elite Recruiter Polish Verified.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_validation()
