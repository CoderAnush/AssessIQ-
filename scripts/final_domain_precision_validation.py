"""
Final Domain Precision Validation Script.
Verifies contextual Python disambiguation and strict negative filtering.
"""

import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "name": "Python Backend Disambiguation",
        "query": "python backend engineer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["machine learning", "data science"]
    },
    {
        "name": "FastAPI Backend Precision",
        "query": "FastAPI backend developer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["frontend", "ml"]
    },
    {
        "name": "Django API Intelligence",
        "query": "Django API engineer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["ui", "css"]
    },
    {
        "name": "Python AI/ML Context",
        "query": "machine learning engineer with python",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["web app", "django"]
    },
    {
        "name": "TensorFlow NLP Precision",
        "query": "TensorFlow NLP Engineer",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["backend", "frontend"]
    },
    {
        "name": "React Frontend Strictness (No AWS/DevOps)",
        "query": "Senior React Engineer",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["aws", "cloud", "devops", "kubernetes", "infrastructure"]
    },
    {
        "name": "Backend Java Strictness (No Frontend)",
        "query": "Backend Java Engineer with Spring Boot",
        "expected_domain": "BACKEND",
        "must_not_contain": ["react", "angular", "vue", "frontend", "ui "]
    }
]

def run_validation():
    print("="*80)
    print("ASSESSIQ FINAL DOMAIN PRECISION VALIDATION")
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
            
            print(f"  Reply Snippet: {reply[:100]}...")
            
            # Check Domain via Reply (Reply contains "I've optimized an enterprise [domain] hiring pipeline")
            reply_low = reply.lower()
            detected_domain = "UNKNOWN"
            
            domain_map = {
                "frontend": "FRONTEND",
                "backend": "BACKEND",
                "devops": "DEVOPS",
                "data ai": "DATA_AI",
                "data_ai": "DATA_AI",
                "qa": "QA",
                "management": "MANAGEMENT"
            }
            
            for label, domain_enum in domain_map.items():
                if f"enterprise {label} hiring" in reply_low:
                    detected_domain = domain_enum
                    break
            
            # 1. Domain Check
            domain_ok = detected_domain == test["expected_domain"]
            
            # 2. Leakage Check
            leakage = []
            for rec in recs:
                rec_name = rec.get("name", "")
                rec_text = (rec_name + " " + rec.get("recruiter_insight", "")).lower()
                for forbidden in test["must_not_contain"]:
                    if forbidden.lower() in rec_text:
                        leakage.append(f"{forbidden} (in {rec_name})")
            
            leakage_ok = len(leakage) == 0
            
            if domain_ok and leakage_ok:
                print(f"  [PASS] Domain: {detected_domain} | Zero Leakage")
                passed += 1
            else:
                if not domain_ok:
                    print(f"  [FAIL] Expected Domain {test['expected_domain']}, got {detected_domain}")
                if not leakage_ok:
                    print(f"  [FAIL] Leakage Detected: {list(set(leakage))}")
                    
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    print(f"VALIDATION SUMMARY: {passed}/{len(TEST_CASES)} PASSED")
    print("="*80)
    
    if passed == len(TEST_CASES):
        print("\n[OK] SYSTEM CERTIFIED: 100% Domain Intelligence Precision Achieved.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_validation()
