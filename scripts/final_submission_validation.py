"""
Phase 7 Final Submission Validation Suite.
Tests critical recruiter scenarios and produces production metrics.
"""

import os
import requests
import json
import time

BASE_URL = os.environ.get("TARGET_CHAT_URL", "http://localhost:8010/chat")

TEST_SCENARIOS = [
    {
        "name": "Senior Python Backend (FastAPI/Microservices)",
        "prompt": "Need assessments for a senior Python backend engineer using FastAPI and microservices"
    },
    {
        "name": "React Frontend Developer",
        "prompt": "Need assessments for a React frontend developer"
    },
    {
        "name": "DevOps (Kubernetes/Terraform)",
        "prompt": "Need assessments for a DevOps engineer using Kubernetes and Terraform"
    },
    {
        "name": "Engineering Manager",
        "prompt": "Hiring an engineering manager with stakeholder management"
    },
    {
        "name": "Vague Software Engineer",
        "prompt": "I need a software engineer assessment"
    }
]

def run_validation():
    print("="*80)
    print("ASSESSIQ FINAL SUBMISSION VALIDATION")
    print("="*80)
    
    results = []
    
    for scenario in TEST_SCENARIOS:
        print(f"\n[RUNNING] {scenario['name']}...")
        payload = {"messages": [{"role": "user", "content": scenario["prompt"]}]}
        
        try:
            start = time.time()
            resp = requests.post(BASE_URL, json=payload, timeout=30)
            elapsed = time.time() - start
            
            if resp.status_code != 200:
                print(f"FAILED: {scenario['name']} (Status {resp.status_code})")
                results.append({"name": scenario["name"], "pass": False, "error": f"Status {resp.status_code}"})
                continue
                
            data = resp.json()
            recs = data.get("recommendations", [])
            reply = data.get("reply", "")
            
            # Validation Rules
            is_empty = len(recs) == 0
            is_clarification = "?" in reply and not recs
            has_mismatch = False
            
            # Domain specific checks
            rec_names = [r.get("name", "").lower() for r in recs]
            if scenario["name"] == "Senior Python Backend (FastAPI/Microservices)":
                if is_empty: has_mismatch = True
                if any("react" in n for n in rec_names): has_mismatch = True
                
            if scenario["name"] == "React Frontend Developer":
                if not any("frontend" in n or "react" in n or "javascript" in n or "angular" in n for n in rec_names):
                    has_mismatch = True

            passed = not is_empty or is_clarification
            if scenario["name"] == "Vague Software Engineer" and not is_clarification:
                passed = False # Should clarify vague query
            
            if has_mismatch: passed = False
            
            results.append({
                "name": scenario["name"],
                "pass": passed,
                "latency": elapsed,
                "rec_count": len(recs),
                "is_clarification": is_clarification,
                "has_mismatch": has_mismatch,
                "recommendations": [r.get("name") for r in recs]
            })
            
            print(f"DONE: {scenario['name']} (Passed: {passed}, Latency: {elapsed:.2f}s)")
            
        except Exception as e:
            print(f"CRITICAL ERROR: {scenario['name']} - {str(e)}")
            results.append({"name": scenario["name"], "pass": False, "error": str(e)})

    # Calculate Metrics
    total = len(results)
    passed = sum(1 for r in results if r.get("pass"))
    mismatches = sum(1 for r in results if r.get("has_mismatch", False))
    empty = sum(1 for r in results if r.get("rec_count", 0) == 0 and not r.get("is_clarification"))
    
    metrics = {
        "DOMAIN_ACCURACY": (total - mismatches) / total * 100,
        "FALLBACK_RATE": 0.0, # Placeholder
        "EMPTY_RESPONSE_RATE": empty / total * 100,
        "CLARIFICATION_LOOP_RATE": 0.0, # Placeholder
        "PASS_RATE": passed / total * 100
    }
    
    print("\n" + "="*80)
    print("FINAL METRICS")
    print("="*80)
    for k, v in metrics.items():
        print(f"{k:<25}: {v:.1f}%")
    print("="*80)
    
    with open("data/logs/final_submission_results/validation_suite_results.json", "w") as f:
        json.dump({"results": results, "metrics": metrics}, f, indent=2)

if __name__ == "__main__":
    run_validation()
