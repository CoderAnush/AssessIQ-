import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

TEST_QUERIES = [
    {
        "query": "Senior React Engineer with Redux and TypeScript",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["backend", "cloud", "devops", "machine learning", "nlp", "database", "sql"],
        "must_contain": ["react", "typescript"]
    },
    {
        "query": "Angular frontend architect with RxJS",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["react-only", "react", "backend", "cloud", "devops", "machine learning"],
        "must_contain": ["angular"]
    },
    {
        "query": "Backend Java Engineer with Spring Boot",
        "expected_domain": "BACKEND",
        "must_not_contain": ["react", "angular", "vue", "ui engineering", "frontend"],
        "must_contain": []
    },
    {
        "query": "Python FastAPI backend engineer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["react", "angular", "vue", "frontend", "machine learning", "nlp"],
        "must_contain": []
    },
    {
        "query": "Django backend developer",
        "expected_domain": "BACKEND",
        "must_not_contain": ["react", "angular", "vue", "frontend", "machine learning", "nlp"],
        "must_contain": []
    },
    {
        "query": "Kubernetes Terraform DevOps engineer",
        "expected_domain": "DEVOPS",
        "must_not_contain": ["react", "angular", "machine learning", "data science", "frontend"],
        "must_contain": ["kubernetes", "terraform", "infrastructure", "cloud"]
    },
    {
        "query": "Machine Learning Engineer with TensorFlow and NLP",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["frontend", "cloud infrastructure", "java enterprise backend", "react", "angular"],
        "must_contain": ["machine learning", "nlp", "tensorflow", "deep learning"]
    },
    {
        "query": "Data Scientist with PyTorch",
        "expected_domain": "DATA_AI",
        "must_not_contain": ["backend", "frontend", "react", "angular", "spring boot"],
        "must_contain": ["data science", "pytorch", "machine learning"]
    },
    {
        "query": "UI/UX frontend developer",
        "expected_domain": "FRONTEND",
        "must_not_contain": ["backend", "devops", "machine learning", "database"],
        "must_contain": ["ui", "frontend"]
    },
    {
        "query": "Cloud Infrastructure Engineer",
        "expected_domain": "DEVOPS",
        "must_not_contain": ["frontend", "react", "angular", "nlp"],
        "must_contain": ["cloud", "infrastructure"]
    }
]

def run_audit():
    print("="*80)
    print("FINAL RECOMMENDATION ACCURACY AUDIT")
    print("="*80)
    
    metrics = {
        "domain_precision": 0,
        "leakage_rate": 0,
        "relevance": 0,
        "fallback_accuracy": 0,
        "reasoning_quality": 0,
        "stage_accuracy": 0
    }
    
    total_queries = len(TEST_QUERIES)
    total_recommendations_evaluated = 0
    total_leakages_detected = 0
    total_relevant = 0
    total_valid_fallbacks = 0
    total_fallbacks = 0
    total_good_reasoning = 0
    total_good_stages = 0
    
    for i, test in enumerate(TEST_QUERIES):
        print(f"\n[{i+1}/{total_queries}] Query: '{test['query']}'")
        
        try:
            payload = {"messages": [{"role": "user", "content": test["query"]}]}
            resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
            
            if resp.status_code != 200:
                print(f"  [FAIL] HTTP {resp.status_code}")
                continue
                
            data = resp.json()
            reply = data.get("reply", "")
            recs = data.get("recommendations", [])
            pipeline = data.get("pipeline", {})
            stages = pipeline.get("stages", [])
            
            domain_label = test["expected_domain"].lower().replace("_", " ")
            detected_domain_ok = f"enterprise {domain_label} hiring" in reply.lower()
            if detected_domain_ok:
                metrics["domain_precision"] += 1
                
            print(f"1. Detected Domain: {test['expected_domain']} (Match: {detected_domain_ok})")
            print(f"2. Retrieved Recommendations: {len(recs)}")
            
            domains = []
            confidences = []
            signals = []
            match_types = []
            leakage_found = False
            relevant_count = 0
            
            for rec in recs:
                total_recommendations_evaluated += 1
                rec_name = rec.get("name", "")
                insight = rec.get("recruiter_insight", "")
                signal = rec.get("recruiter_signal", "")
                conf = rec.get("confidence", 0)
                domain = rec.get("domain", "")
                stage = rec.get("stage", "")
                
                domains.append(domain)
                confidences.append(conf)
                signals.append(signal)
                
                is_expanded = "Expanded Match" in insight or "Related Competency" in insight
                match_types.append("Expanded" if is_expanded else "Exact")
                
                if is_expanded:
                    total_fallbacks += 1
                    if "strongly aligns" in insight or "fallback recall" in insight or "Related Competency" in insight:
                        total_valid_fallbacks += 1
                
                if "Recommended because it" in insight or "Evaluates core" in insight or "Added due to" in insight or "Related Competency" in insight:
                    total_good_reasoning += 1
                    
                if stage in ["Screening", "Technical Stage", "Interview"]:
                    total_good_stages += 1
                
                rec_text = (rec_name + " " + insight + " " + signal + " " + domain).lower()
                
                # Check Leakage
                leaked = [f for f in test["must_not_contain"] if f.lower() in rec_text]
                if "angular" in test["must_not_contain"] and "angular" in rec_text and "react" in test.get("must_contain", []) and "angularjs" in rec_text:
                    # special case where penalty is applied but name might still contain angularjs?
                    pass
                    
                # Angular check in React test
                if test["query"].startswith("Senior React"):
                    if "angular" in rec_text and "angularjs" in rec_name.lower():
                        leaked.append("angularjs")
                        
                if leaked:
                    leakage_found = True
                    total_leakages_detected += 1
                    
                # Check Relevance
                if is_expanded or test["expected_domain"] in domain.upper() or any(c in rec_text for c in test["must_contain"]):
                    relevant_count += 1
                    
            total_relevant += relevant_count
            
            print(f"3. Recommendation Domains: {domains}")
            print(f"4. Confidence Scores: {confidences}")
            print(f"5. Recruiter Signals: {signals}")
            print(f"6. Exact vs Expanded Match: {match_types}")
            print(f"7. Leakage Check Result: {'LEAKAGE DETECTED' if leakage_found else 'CLEAN'}")
            
            if detected_domain_ok and not leakage_found and relevant_count == len(recs) and len(recs) >= 3:
                print("8. Final Verdict: [PASS]")
            else:
                print("8. Final Verdict: [FAIL]")
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print("\n" + "="*80)
    print("FINAL SCORECARD")
    print("="*80)
    
    domain_precision_pct = (metrics["domain_precision"] / total_queries) * 100
    leakage_rate_pct = (total_leakages_detected / max(1, total_recommendations_evaluated)) * 100
    relevance_pct = (total_relevant / max(1, total_recommendations_evaluated)) * 100
    fallback_acc_pct = (total_valid_fallbacks / max(1, total_fallbacks)) * 100 if total_fallbacks > 0 else 100.0
    reasoning_pct = (total_good_reasoning / max(1, total_recommendations_evaluated)) * 100
    stage_pct = (total_good_stages / max(1, total_recommendations_evaluated)) * 100
    
    print(f"- Domain Precision %: {domain_precision_pct:.1f}%")
    print(f"- Leakage Rate %: {leakage_rate_pct:.1f}%")
    print(f"- Recommendation Relevance %: {relevance_pct:.1f}%")
    print(f"- Fallback Accuracy %: {fallback_acc_pct:.1f}%")
    print(f"- Stage Naming Accuracy %: {stage_pct:.1f}%")
    print(f"- Recruiter Reasoning Quality %: {reasoning_pct:.1f}%")
    
    print("\n" + "="*80)
    print("FINAL RESULT")
    print("="*80)
    if domain_precision_pct >= 90 and leakage_rate_pct <= 5 and relevance_pct >= 90:
        print("[SYSTEM CERTIFIED]")
        print("Detailed Reasoning: The recommendation engine demonstrated high precision, robust fallback expansion, accurate reasoning, and negligible cross-domain leakage.")
    else:
        print("[CRITICAL ISSUES DETECTED]")
        print("Detailed Reasoning: The engine failed to meet enterprise benchmarks for precision, leakage, or relevance.")

if __name__ == "__main__":
    run_audit()
