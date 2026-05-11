"""
Recovery Verification for Domain Filtering.
Ensures valid technical matches are restored while keeping safety guards active.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

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
    print("DOMAIN RECOVERY VALIDATION")
    print("="*60)
    
    classifier = DomainClassifier()
    
    # Verify Normalization (Part 2)
    print("\n[TEST 1] Smart Normalization Check")
    names = ["React Development", "AngularJS Basics", "JavaScript Fundamentals", "Civil Engineering"]
    for name in names:
        domain = classifier.normalize_assessment_domain(name, "")
        print(f"'{name}' -> {domain}")
    
    mock_catalog = {
        "react": MockAssessment("react", "React Development", "UI", "FRONTEND"),
        "angular": MockAssessment("angular", "AngularJS Basics", "Web", "FRONTEND"),
        "js": MockAssessment("js", "JavaScript Fundamentals", "Frontend", "FRONTEND"),
        "civil": MockAssessment("civil", "Civil Engineering", "Bridges", "ENGINEERING_CORE"),
        "ceramic": MockAssessment("ceramic", "Ceramic Engineering", "Materials", "ENGINEERING_CORE"),
    }
    
    ranker = EnterpriseRanker()
    
    mock_retrieved = [
        {"id": "react", "hybrid_score": 0.95},
        {"id": "angular", "hybrid_score": 0.9},
        {"id": "js", "hybrid_score": 0.85},
        {"id": "civil", "hybrid_score": 0.8},
        {"id": "ceramic", "hybrid_score": 0.75},
    ]

    # TEST 2: Frontend Query (Restoration Check)
    print("\n[TEST 2] Restoration Check: 'Senior React Engineer'")
    ctx1 = Context("Senior React Engineer")
    results1 = ranker.rank(mock_retrieved, ctx1, mock_catalog)
    names1 = [r.assessment.name for r in results1]
    
    print(f"Results: {names1}")
    restored = all(n in names1 for n in ["React Development", "AngularJS Basics", "JavaScript Fundamentals"])
    safe = not any(n in names1 for n in ["Civil Engineering", "Ceramic Engineering"])
    
    if restored and safe:
        print("Status: PASSED (Restored valid matches + Kept safety guards)")
    else:
        print(f"Status: FAILED (Restored: {restored}, Safe: {safe})")

    # TEST 3: Hard Safety Guard Check
    print("\n[TEST 3] Safety Guard Check: 'Mechanical Design'")
    ctx2 = Context("Mechanical Design")
    results2 = ranker.rank(mock_retrieved, ctx2, mock_catalog)
    names2 = [r.assessment.name for r in results2]
    print(f"Results: {names2}")
    
    if "Civil Engineering" in names2 or "Ceramic Engineering" in names2:
        print("Status: PASSED (Allowed within same engineering group)")
    else:
        print("Status: FAILED (Over-corrected even for its own domain)")

    print("\n" + "="*60)
    print("RECOVERY VALIDATION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_tests()
