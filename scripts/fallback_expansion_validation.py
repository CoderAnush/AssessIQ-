"""
Fallback Expansion Validation Script.
Verifies domain-constrained skill expansion and zero leakage.
"""

import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "name": "FastAPI Expansion (Backend Domain Only)",
        "query": "Hiring for a Python FastAPI backend engineer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["react", "angular", "ml", "machine learning", "aws", "kubernetes"],
        "min_recommendations": 3
    },
    {
        "name": "Django Expansion (Backend Domain Only)",
        "query": "Django backend developer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["ui ", "frontend", "aws", "tensorflow"],
        "min_recommendations": 3
    },
    {
        "name": "TensorFlow NLP Expansion (AI Domain Only)",
        "query": "TensorFlow NLP engineer",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["backend", "frontend", "react", "java"],
        "min_recommendations": 3
    },
    {
        "name": "React Expansion (Frontend Domain Only)",
        "query": "Senior React Engineer",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["backend", "cloud", "aws", "devops", "sql"],
        "min_recommendations": 3
    }
]

def run_validation():
    print("="*80)
    print("ASSESSIQ FALLBACK EXPANSION VALIDATION")
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
            
            print(f"  Reply: {reply[:150]}...")
            
            # 1. Domain Check
            domain_label = test["expected_domain"].lower().replace("_", " ")
            domain_ok = f"enterprise {domain_label} hiring" in reply
            
            # 2. Leakage Check
            leakage = []
            expanded_matches = 0
            for rec in recs:
                rec_name = rec.get("name", "")
                insight = rec.get("recruiter_insight", "")
                rec_text = (rec_name + " " + insight).lower()
                
                if "related competency" in insight.lower():
                    expanded_matches += 1
                
                for forbidden in test["must_not_contain"]:
                    if forbidden.lower() in rec_text:
                        leakage.append(f"{forbidden} (in {rec_name})")
            
            leakage_ok = len(leakage) == 0
            count_ok = len(recs) >= test["min_recommendations"]
            
            if domain_ok and leakage_ok and count_ok:
                print(f"  [PASS] Domain Correct | Count: {len(recs)} | Expanded: {expanded_matches} | Zero Leakage")
                passed += 1
            else:
                if not domain_ok:
                    print(f"  [FAIL] Domain mismatch in reply: '{reply[:50]}...'")
                if not leakage_ok:
                    print(f"  [FAIL] Leakage Detected: {list(set(leakage))}")
                if not count_ok:
                    print(f"  [FAIL] Recommendation count too low: {len(recs)} < {test['min_recommendations']}")
                    
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    print(f"VALIDATION SUMMARY: {passed}/{len(TEST_CASES)} PASSED")
    print("="*80)
    
    if passed == len(TEST_CASES):
        print("\n[OK] SYSTEM CERTIFIED: Intelligent Fallback Expansion Verified.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_validation()
