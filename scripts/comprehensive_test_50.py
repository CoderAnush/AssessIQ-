"""
Comprehensive Test Suite - 50+ Scenarios for AssessIQ
Tests role recognition, language filtering, and correct recommendations.
"""

import requests
import json
import sys
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Backend URL
BASE_URL = "https://assessiq-nkp2.onrender.com"
CHAT_URL = f"{BASE_URL}/chat"

class TestCategory(Enum):
    JAVA = "Java Roles"
    PYTHON = "Python Roles"
    DEVOPS = "DevOps/Cloud"
    FRONTEND = "Frontend"
    DATASCIENCE = "Data Science/ML"
    QA = "QA/Testing"
    MANAGEMENT = "Management"
    GENERIC = "Generic/Clarification"
    EDGE = "Edge Cases"

@dataclass
class TestCase:
    query: str
    category: TestCategory
    expected_type: str  # "java", "python", "devops", "clarify", etc.
    should_clarify: bool = False

# 50+ Test Scenarios
TEST_CASES = [
    # === JAVA ROLES (10 tests) ===
    TestCase("Senior Java Engineer", TestCategory.JAVA, "java"),
    TestCase("java backend developer", TestCategory.JAVA, "java"),
    TestCase("Junior Java Developer", TestCategory.JAVA, "java"),
    TestCase("Java Spring Boot Engineer", TestCategory.JAVA, "java"),
    TestCase("Lead Java Architect", TestCategory.JAVA, "java"),
    TestCase("Entry level Java programmer", TestCategory.JAVA, "java"),
    TestCase("Java microservices developer", TestCategory.JAVA, "java"),
    TestCase("Senior Java Backend Engineer", TestCategory.JAVA, "java"),
    TestCase("Java Enterprise Developer", TestCategory.JAVA, "java"),
    TestCase("Staff Java Engineer", TestCategory.JAVA, "java"),
    
    # === PYTHON ROLES (10 tests) ===
    TestCase("Senior Python Engineer", TestCategory.PYTHON, "python"),
    TestCase("python backend developer", TestCategory.PYTHON, "python"),
    TestCase("Django Developer", TestCategory.PYTHON, "python"),
    TestCase("Flask Backend Engineer", TestCategory.PYTHON, "python"),
    TestCase("Python Data Engineer", TestCategory.PYTHON, "python"),
    TestCase("Junior Python Developer", TestCategory.PYTHON, "python"),
    TestCase("FastAPI Developer", TestCategory.PYTHON, "python"),
    TestCase("Python Backend Architect", TestCategory.PYTHON, "python"),
    TestCase("Senior Python Backend", TestCategory.PYTHON, "python"),
    TestCase("Python Microservices", TestCategory.PYTHON, "python"),
    
    # === DEVOPS/CLOUD (8 tests) ===
    TestCase("DevOps Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("SRE Site Reliability Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Cloud Infrastructure Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Kubernetes Administrator", TestCategory.DEVOPS, "devops"),
    TestCase("AWS Cloud Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Platform Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Infrastructure Engineer", TestCategory.DEVOPS, "devops"),
    TestCase("Docker Specialist", TestCategory.DEVOPS, "devops"),
    
    # === FRONTEND (5 tests) ===
    TestCase("Frontend Developer", TestCategory.FRONTEND, "frontend"),
    TestCase("React Developer", TestCategory.FRONTEND, "frontend"),
    TestCase("Angular Engineer", TestCategory.FRONTEND, "frontend"),
    TestCase("Senior Frontend Engineer", TestCategory.FRONTEND, "frontend"),
    TestCase("UI Developer", TestCategory.FRONTEND, "frontend"),
    
    # === DATA SCIENCE/ML (5 tests) ===
    TestCase("Data Scientist", TestCategory.DATASCIENCE, "data"),
    TestCase("Machine Learning Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("ML Ops Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("Data Engineer", TestCategory.DATASCIENCE, "data"),
    TestCase("AI Engineer", TestCategory.DATASCIENCE, "data"),
    
    # === QA/TESTING (4 tests) ===
    TestCase("QA Engineer", TestCategory.QA, "qa"),
    TestCase("SDET Software Developer in Test", TestCategory.QA, "qa"),
    TestCase("Test Automation Engineer", TestCategory.QA, "qa"),
    TestCase("Senior QA Analyst", TestCategory.QA, "qa"),
    
    # === MANAGEMENT (4 tests) ===
    TestCase("Engineering Manager", TestCategory.MANAGEMENT, "management"),
    TestCase("Tech Lead", TestCategory.MANAGEMENT, "management"),
    TestCase("Product Manager", TestCategory.MANAGEMENT, "management"),
    TestCase("CTO Chief Technology Officer", TestCategory.MANAGEMENT, "management"),
    
    # === GENERIC/SHOULD CLARIFY (4 tests) ===
    TestCase("developer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("software engineer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("programmer", TestCategory.GENERIC, "any", should_clarify=True),
    TestCase("need assessments", TestCategory.GENERIC, "any", should_clarify=True),
    
    # === EDGE CASES (4 tests) ===
    TestCase("Full Stack Developer", TestCategory.EDGE, "fullstack"),
    TestCase("Backend Developer", TestCategory.EDGE, "backend"),
    TestCase("Mobile Developer", TestCategory.EDGE, "mobile"),
    TestCase("Embedded Systems Engineer", TestCategory.EDGE, "embedded"),
]

def test_single_case(test_case: TestCase) -> Dict[str, Any]:
    """Test a single scenario and return results."""
    try:
        response = requests.post(
            CHAT_URL,
            json={"messages": [{"role": "user", "content": test_case.query}]},
            timeout=30
        )
        data = response.json()
        
        recommendations = data.get("recommendations", [])
        reply = data.get("reply", "")
        
        # Check if clarification was requested
        is_clarification = len(recommendations) == 0 and ("what" in reply.lower() or "specific" in reply.lower() or "role" in reply.lower())
        
        # Analyze first recommendation
        first_rec = None
        has_java = False
        has_python = False
        has_devops = False
        
        if recommendations:
            first_rec = recommendations[0]["name"]
            all_names = " ".join([r["name"].lower() for r in recommendations[:5]])
            has_java = "java" in all_names
            has_python = "python" in all_names
            has_devops = any(w in all_names for w in ["docker", "kubernetes", "aws", "cloud", "terraform", "infrastructure"])
        
        return {
            "query": test_case.query,
            "category": test_case.category.value,
            "expected": test_case.expected_type,
            "should_clarify": test_case.should_clarify,
            "is_clarification": is_clarification,
            "rec_count": len(recommendations),
            "first_rec": first_rec,
            "has_java": has_java,
            "has_python": has_python,
            "has_devops": has_devops,
            "success": False,  # Will be determined
        }
    except Exception as e:
        return {
            "query": test_case.query,
            "category": test_case.category.value,
            "error": str(e),
            "success": False,
        }

def evaluate_result(result: Dict[str, Any], test_case: TestCase) -> bool:
    """Determine if test passed based on expectations."""
    if "error" in result:
        return False
    
    # If should clarify, check for clarification
    if test_case.should_clarify:
        return result["is_clarification"]
    
    # If has recommendations, check content
    if result["rec_count"] == 0:
        return False  # Should have recommendations but doesn't
    
    # Check for correct type
    expected = test_case.expected_type
    
    if expected == "java":
        # Should have Java recommendations, NOT Python
        return result["has_java"] and not result["has_python"]
    elif expected == "python":
        # Should NOT have Java (can be generic or Python-specific)
        return not result["has_java"]
    elif expected == "devops":
        return result["has_devops"] or not result["has_java"]  # DevOps or at least not pure Java
    elif expected in ["frontend", "data", "qa", "management"]:
        # These should NOT return Java assessments
        return not result["has_java"]
    else:
        # Fullstack, backend, edge cases - just check we got something
        return result["rec_count"] > 0

def run_all_tests():
    """Run all test cases and generate report."""
    print("="*80)
    print("COMPREHENSIVE TEST SUITE - 50+ SCENARIOS")
    print("="*80)
    print(f"Total tests: {len(TEST_CASES)}")
    print("="*80)
    
    results = []
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] Testing: {test_case.query[:50]}...")
        
        result = test_single_case(test_case)
        is_success = evaluate_result(result, test_case)
        result["success"] = is_success
        results.append(result)
        
        if is_success:
            passed += 1
            status = "[PASS]"
        else:
            failed += 1
            status = "[FAIL]"
        
        if result["is_clarification"]:
            print(f"  {status} | Clarification requested")
        elif result["rec_count"] > 0:
            first = result["first_rec"][:40] if result["first_rec"] else "N/A"
            print(f"  {status} | {result['rec_count']} recs | First: {first}")
            if result["has_java"]:
                print(f"      ! Contains Java assessments")
            if result["has_python"]:
                print(f"      ! Contains Python assessments")
        else:
            print(f"  {status} | No recommendations")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total: {len(TEST_CASES)} | Passed: {passed} | Failed: {failed}")
    print(f"Success Rate: {passed/len(TEST_CASES)*100:.1f}%")
    
    # Category breakdown
    print("\n--- BY CATEGORY ---")
    category_stats = {}
    for r in results:
        cat = r.get("category", "Unknown")
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r["success"]:
            category_stats[cat]["passed"] += 1
    
    for cat, stats in sorted(category_stats.items()):
        rate = stats["passed"]/stats["total"]*100
        print(f"{cat:25} | {stats['passed']:2}/{stats['total']:2} | {rate:5.1f}%")
    
    # Failed cases
    if failed > 0:
        print("\n--- FAILED CASES ---")
        for r in results:
            if not r["success"] and "error" not in r:
                print(f"  - {r['query'][:50]}: {r['first_rec'][:50] if r['first_rec'] else 'No recs/clarification'}")
    
    return results

if __name__ == "__main__":
    results = run_all_tests()
    
    # Save results
    with open("test_results_50.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to test_results_50.json")
