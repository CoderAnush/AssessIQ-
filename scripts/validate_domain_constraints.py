"""
Validation tests for AssessIQ Domain Gating and Ranking.
Ensures zero cross-domain leakage and correct technical alignment.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

# Mocking the minimal classes needed for the test to avoid file dependency issues
class Domain:
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DEVOPS = "DEVOPS"
    DATA_AI = "DATA_AI"
    MANAGEMENT = "MANAGEMENT"
    QA = "QA"
    ENGINEERING_CORE = "ENGINEERING_CORE"
    MEDICAL = "MEDICAL"
    GENERAL = "GENERAL"

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

# Import actual logic to test
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.services.domain_classifier import DomainClassifier
from app.services.ranker_v2 import EnterpriseRanker

def run_tests():
    print("="*60)
    print("ASSESSIQ PRODUCTION VALIDATION SUITE")
    print("="*60)
    
    # Setup mock catalog
    mock_catalog = {
        "angular-6": MockAssessment("angular-6", "Angular 6", "Frontend testing", "FRONTEND", ["angular"]),
        "react-dev": MockAssessment("react-dev", "React Development", "Frontend library", "FRONTEND", ["react"]),
        "civil-eng": MockAssessment("civil-eng", "Civil Engineering", "Bridge building", "ENGINEERING_CORE"),
        "cardiology": MockAssessment("cardiology", "Cardiology", "Heart health", "MEDICAL"),
        "kubernetes": MockAssessment("kubernetes", "Kubernetes", "Container orchestration", "DEVOPS", ["kubernetes"]),
        "aws-dev": MockAssessment("aws-dev", "AWS Development", "Cloud services", "DEVOPS", ["aws"]),
        "leadership": MockAssessment("leadership", "Leadership Report", "People management", "MANAGEMENT"),
        "chemical-eng": MockAssessment("chemical-eng", "Chemical Engineering", "Chemical plants", "ENGINEERING_CORE"),
    }
    
    ranker = EnterpriseRanker()
    
    mock_retrieved = [
        {"id": "angular-6", "hybrid_score": 0.8},
        {"id": "react-dev", "hybrid_score": 0.85},
        {"id": "civil-eng", "hybrid_score": 0.75},
        {"id": "cardiology", "hybrid_score": 0.7},
        {"id": "kubernetes", "hybrid_score": 0.8},
        {"id": "aws-dev", "hybrid_score": 0.82},
        {"id": "leadership", "hybrid_score": 0.9},
        {"id": "chemical-eng", "hybrid_score": 0.7},
    ]

    # TEST 1: React Frontend Developer
    print("\n[TEST 1] Query: 'React frontend developer'")
    ctx1 = Context("React frontend developer", {"react", "javascript"})
    results1 = ranker.rank(mock_retrieved, ctx1, mock_catalog)
    names1 = [r.assessment.name for r in results1]
    
    passed1 = any("React" in n or "Angular" in n for n in names1) and \
              not any(n in names1 for n in ["Civil Engineering", "Cardiology"])
    print(f"Results: {names1}")
    print(f"Status: {'PASSED' if passed1 else 'FAILED'}")

    # TEST 2: DevOps engineer with Kubernetes
    print("\n[TEST 2] Query: 'DevOps engineer with Kubernetes'")
    ctx2 = Context("DevOps engineer with Kubernetes", {"kubernetes", "docker", "aws"})
    results2 = ranker.rank(mock_retrieved, ctx2, mock_catalog)
    names2 = [r.assessment.name for r in results2]
    
    passed2 = any("Kubernetes" in n or "AWS" in n for n in names2) and \
              not any(n in names2 for n in ["Angular 6", "Civil Engineering"])
    print(f"Results: {names2}")
    print(f"Status: {'PASSED' if passed2 else 'FAILED'}")

    # TEST 3: Engineering manager
    print("\n[TEST 3] Query: 'Engineering manager'")
    ctx3 = Context("Engineering manager", {"leadership", "stakeholder management"})
    results3 = ranker.rank(mock_retrieved, ctx3, mock_catalog)
    names3 = [r.assessment.name for r in results3]
    
    passed3 = any("Leadership" in n for n in names3) and \
              not any(n in names3 for n in ["Chemical Engineering", "Civil Engineering"])
    print(f"Results: {names3}")
    print(f"Status: {'PASSED' if passed3 else 'FAILED'}")

    print("\n" + "="*60)
    print(f"FINAL SCORE: {sum([passed1, passed2, passed3])}/3")
    print("="*60)

if __name__ == "__main__":
    run_tests()
