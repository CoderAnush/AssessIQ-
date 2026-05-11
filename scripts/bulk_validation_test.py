"""
Bulk Validation Stress Test for AssessIQ (Safe Encoding).
Tests 20+ recruitment scenarios for domain alignment and safety.
"""

import requests
import json
import time
import sys

# Ensure UTF-8 output if possible, or fallback to plain text
BACKEND_URL = "http://localhost:8000"

SCENARIOS = [
    "Senior React Frontend Engineer with TypeScript and Redux",
    "Backend Java Developer with Spring Boot and Microservices",
    "DevOps Engineer specialized in AWS, Docker, and Kubernetes",
    "Machine Learning Engineer with NLP and Deep Learning experience",
    "Data Scientist with Python, Pandas, and Statistical Modeling",
    "QA Automation Engineer using Selenium and Java",
    "Engineering Manager with experience in Leadership and Agile",
    "Site Reliability Engineer (SRE) for Cloud Infrastructure",
    "Fullstack Developer (Node.js and React)",
    "Android Developer with Kotlin experience",
    "iOS Developer with Swift and SwiftUI",
    "Database Administrator (PostgreSQL and NoSQL)",
    "Security Engineer for Penetration Testing and Network Security",
    "Cloud Architect for Azure and GCP migrations",
    "Technical Product Manager for AI products",
    "Frontend Architect specialized in Design Systems",
    "Backend Systems Engineer using Go and Distributed Systems",
    "Data Engineer with Spark and Hadoop ecosystem knowledge",
    "Embedded Systems Engineer with C/C++ experience",
    "UI/UX Engineer with CSS, Figma, and Tailwind expertise"
]

def run_stress_test():
    print("="*80)
    print("ASSESSIQ BULK VALIDATION: 20 SCENARIOS")
    print("="*80)
    
    results = []
    
    for i, query in enumerate(SCENARIOS):
        print(f"[{i+1}/20] Testing: {query}...")
        
        try:
            payload = {"messages": [{"role": "user", "content": query}]}
            start_time = time.time()
            resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
            latency = time.time() - start_time
            
            if resp.status_code != 200:
                print(f"  [FAIL] HTTP {resp.status_code}")
                results.append((query, "FAIL", "HTTP Error", latency))
                continue
                
            data = resp.json()
            recs = data.get("recommendations", [])
            reply = data.get("reply", "")
            
            # Validation Logic
            leakage = [r for r in recs if r.get("domain") in ["ENGINEERING_CORE", "MEDICAL"]]
            has_recs = len(recs) > 0
            
            if leakage:
                print(f"  [FAIL] Domain Leakage: {leakage[0].get('domain')}")
                results.append((query, "FAIL", "Leakage", latency))
            elif not has_recs and "I couldn't find" not in reply:
                print("  [WARN] No recommendations")
                results.append((query, "WARN", "No Recs", latency))
            else:
                print(f"  [PASS] {len(recs)} recs in {latency:.2f}s")
                results.append((query, "PASS", f"{len(recs)} recs", latency))
                
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            results.append((query, "ERROR", str(e), 0))
            
    print("\n" + "="*80)
    print("STRESS TEST SUMMARY")
    print("="*80)
    
    passed = len([r for r in results if r[1] == "PASS"])
    warned = len([r for r in results if r[1] == "WARN"])
    failed = len([r for r in results if r[1] in ["FAIL", "ERROR"]])
    
    print(f"TOTAL: {len(SCENARIOS)}")
    print(f"PASS:  {passed}")
    print(f"WARN:  {warned}")
    print(f"FAIL:  {failed}")
    
    if failed == 0:
        print("\n[OK] SYSTEM STABLE: No domain leakage or crashes detected across 20 diverse technical roles.")
    else:
        print(f"\n[FAIL] SYSTEM UNSTABLE: {failed} critical failures detected.")
    print("="*80)

if __name__ == "__main__":
    run_stress_test()
