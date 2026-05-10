"""
Intelligence Quality Validation - Specific Test Cases for Sales, Personality, and Coding.
"""

import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "name": "Sales Personality Query",
        "query": "What's the best personality test for a sales role?",
        "expected_domain": "personality", 
        "disallowed_terms": ["java", "python", "coding"]
    },
    {
        "name": "Backend Coding Query",
        "query": "Best coding test for backend engineers",
        "expected_domain": "technical",
        "allowed_terms": ["java", "python", "c#", "coding"]
    },
    {
        "name": "Leadership Query",
        "query": "Leadership assessment for managers",
        "expected_domain": "leadership",
        "allowed_terms": ["leadership", "management"]
    },
    {
        "name": "Cognitive Graduate Query",
        "query": "Best cognitive test for graduates",
        "expected_domain": "cognitive",
        "allowed_terms": ["cognitive", "reasoning", "aptitude"]
    },
    {
        "name": "Off-Topic Rejection",
        "query": "Tell me a joke about recruiters",
        "expect_rejection": True
    }
]

def run_tests():
    print("=" * 60)
    print("INTELLIGENCE QUALITY VALIDATION")
    print("=" * 60)
    
    passed = 0
    total = len(TEST_CASES)

    for test in TEST_CASES:
        print(f"\nRUNNING: {test['name']}")
        print(f"QUERY: {test['query']}")
        
        try:
            payload = {
                "messages": [{"role": "user", "content": test['query']}]
            }
            response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=20)
            data = response.json()
            
            if response.status_code != 200:
                print(f"  [X] FAILED: Status code {response.status_code}")
                continue

            # Check for rejection
            if test.get("expect_rejection"):
                if "specialize in SHL" in data.get("reply", ""):
                    print("  [OK] SUCCESS: Correctly rejected off-topic query")
                    passed += 1
                else:
                    print(f"  [X] FAILED: Should have rejected but got: {data.get('reply')[:100]}...")
                continue

            # Check for technical issue
            if "technical issue" in data.get("reply", "").lower():
                print(f"  [X] FAILED: Encountered technical issue: {data.get('error')}")
                continue

            # Check recommendations
            recs = data.get("recommendations", [])
            if not recs:
                print(f"  [X] FAILED: No recommendations returned. Reply: {data.get('reply')[:100]}...")
                continue

            print(f"  [OK] SUCCESS: Returned {len(recs)} recommendations")
            
            # Validation logic
            valid = True
            for rec in recs:
                name = rec.get("name", "").lower()
                desc = rec.get("description", "").lower()
                
                # Check disallowed terms
                for term in test.get("disallowed_terms", []):
                    if term in name or term in desc:
                        print(f"    [!] WARNING: Found disallowed term '{term}' in '{rec.get('name')}'")
                        valid = False

            if valid:
                print("  [OK] PASSED Intelligence constraints")
                passed += 1
            else:
                print("  [X] FAILED Intelligence constraints")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {passed}/{total} Passed")
    print("=" * 60)

if __name__ == "__main__":
    # Ensure backend is running
    try:
        requests.get(f"{BACKEND_URL}/health")
        run_tests()
    except Exception as e:
        print(f"ERROR: Backend not running or inaccessible at {BACKEND_URL}: {e}")
