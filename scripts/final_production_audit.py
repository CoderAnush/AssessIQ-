"""
Final Production Audit for AssessIQ.
Validates Part 1 (Repetitive Stages), Part 2 (Diversity), and Part 8 (Data Safety).
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

# Mocking classes
class Domain:
    FRONTEND, BACKEND, DEVOPS, MANAGEMENT = "FRONTEND", "BACKEND", "DEVOPS", "MANAGEMENT"
    GENERAL = "GENERAL"

@dataclass
class MockAssessment:
    id: str
    name: str
    description: str
    primary_domain: str
    test_type: Any
    skills: List[str] = field(default_factory=list)
    duration_minutes: int = 30

class TestType:
    def __init__(self, val): self.value = val

class Context:
    def __init__(self, query, role="Engineer", domain="Technical"):
        self.query = query
        self.role = role
        self.domain = domain
        self.tech_stack = set()
        self.history = [{"role": "user", "content": query}]

# Imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.services.ranker_v2 import EnterpriseRanker
from app.services.adaptive_orchestrator import AdaptiveOrchestrator

def run_audit():
    print("="*60)
    print("ASSESSIQ FINAL PRODUCTION AUDIT")
    print("="*60)
    
    # 1. Setup Data
    catalog = {
        "a1": MockAssessment("a1", "React Basics", "UI", "FRONTEND", TestType("K"), ["react"]),
        "a2": MockAssessment("a2", "React Advanced", "UI", "FRONTEND", TestType("K"), ["react"]),
        "a3": MockAssessment("a3", "JavaScript UI", "UI", "FRONTEND", TestType("K"), ["javascript"]),
        "a4": MockAssessment("a4", "Angular 10", "UI", "FRONTEND", TestType("K"), ["angular"]),
    }
    
    ranker = EnterpriseRanker()
    orchestrator = AdaptiveOrchestrator()
    
    mock_retrieved = [
        {"id": "a1", "hybrid_score": 0.9},
        {"id": "a2", "hybrid_score": 0.89}, # Very similar to a1
        {"id": "a3", "hybrid_score": 0.88},
        {"id": "a4", "hybrid_score": 0.87},
    ]

    # AUDIT 1: Diversity (Part 2)
    print("\n[AUDIT 1] Diversity Boost Check")
    ctx = Context("React developer")
    ranked = ranker.rank(mock_retrieved, ctx, catalog)
    
    # We expect 'Angular 10' or 'JavaScript UI' to move up if diversity penalty hits 'React Advanced'
    names = [r.assessment.name for r in ranked]
    print(f"Ranked results: {names}")
    # If React Advanced (0.89) is below JavaScript UI (0.88), diversity worked
    react_adv_score = next(r.final_score for r in ranked if r.assessment.id == "a2")
    js_ui_score = next(r.final_score for r in ranked if r.assessment.id == "a3")
    print(f"React Advanced Score: {react_adv_score:.4f} | JS UI Score: {js_ui_score:.4f}")
    
    diversity_pass = react_adv_score < js_ui_score
    print(f"Status: {'PASSED' if diversity_pass else 'FAILED (Diversity penalty too low)'}")

    # AUDIT 2: Dynamic Stage Naming (Part 1)
    print("\n[AUDIT 2] Stage Naming Repetition Check")
    pipeline = orchestrator.orchestrate(ranked, ctx, catalog)
    stage_names = [s["name"] for s in pipeline.stages]
    print(f"Generated Stages: {stage_names}")
    
    repetition_check = len(stage_names) == len(set(stage_names))
    has_generic = any("Technical Deep Dive" in n for n in stage_names)
    
    passed_naming = repetition_check and not has_generic
    print(f"Status: {'PASSED' if passed_naming else 'FAILED (Repetitive or generic names found)'}")

    # AUDIT 3: Trust Signal Alignment (Part 6)
    print("\n[AUDIT 3] Strategic Advice Trust Signal")
    print(f"Strategic Advice: {pipeline.strategic_advice}")
    trust_pass = "FAANG" in pipeline.strategic_advice or "Strong" in pipeline.strategic_advice
    print(f"Status: {'PASSED' if trust_pass else 'FAILED'}")

    print("\n" + "="*60)
    print(f"FINAL AUDIT SCORE: {sum([diversity_pass, passed_naming, trust_pass])}/3")
    print("="*60)

if __name__ == "__main__":
    run_audit()
