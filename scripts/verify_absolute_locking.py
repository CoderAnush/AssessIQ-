"""
Automated Verification for Absolute Domain Locking.
Ensures zero leakage of unrelated domains into technical pipelines.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

# Mocking the minimal classes needed for the test
class Domain:
    FRONTEND, BACKEND, DEVOPS, DATA_AI = "FRONTEND", "BACKEND", "DEVOPS", "DATA_AI"
    MANAGEMENT, QA, ENGINEERING_CORE, MEDICAL, GENERAL = "MANAGEMENT", "QA", "ENGINEERING_CORE", "MEDICAL", "GENERAL"

@dataclass
class MockAssessment:
    id: str
    name: str
    description: str
    primary_domain: str
    skills: List[str] = field(default_factory=list)

class Context:
    def __init__(self, query, tech_stack=None):
        self.query = query
        self.tech_stack = tech_stack or set()
        self.history = [{"role": "user", "content": query}]

# Import actual logic
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.services.domain_classifier import DomainClassifier
from app.services.ranker_v2 import EnterpriseRanker

def run_tests():
    print("="*60)
    print("ABSOLUTE DOMAIN LOCKING VALIDATION")
    print("="*60)
    
    mock_catalog = {
        "react-1": MockAssessment("react-1", "React Basics", "UI", "FRONTEND"),
        "java-1": MockAssessment("java-1", "Java Backend", "API", "BACKEND"),
        "civil-1": MockAssessment("civil-1", "Civil Engineering", "Bridges", "ENGINEERING_CORE"),
        "ceramic-1": MockAssessment("ceramic-1", "Ceramic Engineering", "Materials", "ENGINEERING_CORE"),
        "fire-1": MockAssessment("fire-1", "Fire Engineering", "Safety", "ENGINEERING_CORE"),
        "medical-1": MockAssessment("medical-1", "Cardiology", "Heart", "MEDICAL"),
        "general-1": MockAssessment("general-1", "General Reasoning", "Logic", "GENERAL"),
        "kubernetes-1": MockAssessment("kubernetes-1", "Kubernetes Ops", "Cloud", "DEVOPS"),
    }
    
    ranker = EnterpriseRanker()
    
    mock_retrieved = [
        {"id": "react-1", "hybrid_score": 0.9},
        {"id": "java-1", "hybrid_score": 0.8},
        {"id": "civil-1", "hybrid_score": 0.7},
        {"id": "ceramic-1", "hybrid_score": 0.75},
        {"id": "fire-1", "hybrid_score": 0.72},
        {"id": "medical-1", "hybrid_score": 0.65},
        {"id": "general-1", "hybrid_score": 0.6},
        {"id": "kubernetes-1", "hybrid_score": 0.85},
    ]

    # TEST 1: Frontend Query (Absolute Lock)
    print("\n[TEST 1] Query: 'Senior React Frontend Engineer'")
    ctx1 = Context("Senior React Frontend Engineer", {"react", "typescript"})
    results1 = ranker.rank(mock_retrieved, ctx1, mock_catalog)
    names1 = [r.assessment.name for r in results1]
    
    # Assert zero leakage
    disallowed = ["Civil Engineering", "Ceramic Engineering", "Fire Engineering", "Cardiology", "General Reasoning", "Java Backend"]
    leakage = [n for n in names1 if n in disallowed]
    
    print(f"Results: {names1}")
    if not leakage and "React Basics" in names1:
        print("Status: PASSED (Zero Leakage)")
    else:
        print(f"Status: FAILED (Leakage detected: {leakage})")

    # TEST 2: DevOps Query (Absolute Lock)
    print("\n[TEST 2] Query: 'Cloud DevOps with Kubernetes'")
    ctx2 = Context("Cloud DevOps with Kubernetes", {"kubernetes", "aws"})
    results2 = ranker.rank(mock_retrieved, ctx2, mock_catalog)
    names2 = [r.assessment.name for r in results2]
    
    disallowed2 = ["React Basics", "Civil Engineering", "General Reasoning", "Cardiology"]
    leakage2 = [n for n in names2 if n in disallowed2]
    
    print(f"Results: {names2}")
    if not leakage2 and "Kubernetes Ops" in names2:
        print("Status: PASSED (Zero Leakage)")
    else:
        print(f"Status: FAILED (Leakage detected: {leakage2})")

    # TEST 3: General Query (Allow General)
    print("\n[TEST 3] Query: 'Generic logical assessment'")
    ctx3 = Context("Generic logical assessment")
    results3 = ranker.rank(mock_retrieved, ctx3, mock_catalog)
    names3 = [r.assessment.name for r in results3]
    
    print(f"Results: {names3}")
    if "General Reasoning" in names3:
        print("Status: PASSED (General allowed for generic query)")
    else:
        print("Status: FAILED (General rejected for generic query)")

    print("\n" + "="*60)
    print("VALIDATION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_tests()
