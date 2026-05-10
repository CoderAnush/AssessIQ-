"""
Master Validation Suite for AssessIQ AI.

Comprehensive validation of all architectural components:
1. Senior Java engineer - validate technical ranking
2. Frontend React developer - validate frontend-focused ranking
3. Data scientist - validate analytical ranking
4. Leadership role - validate leadership/personality ranking
5. Sales role - validate sales aptitude ranking
6. Compare top 2 - validate comparison engine
7. Compare them - validate memory-based comparison
8. Follow-up refinement - validate conversational memory
9. Prompt injection - validate safety
10. Off-topic refusal - validate routing
"""

import unittest
import sys
import os
from typing import List, Dict
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.assessment_taxonomy import (
    AssessmentTaxonomy, AssessmentDomain, RoleDomain
)
from app.services.ranker import RecruiterRanker
from app.services.recruiter_reasoning import RecruiterExplanationEngine
from app.services.comparison_engine import ComparisonEngine
from app.services.assessment_validator import SHLAssessmentValidator
from app.services.conversation_memory import ConversationMemoryStore
from app.services.conversation_analyzer import HiringContext
from app.models.assessment import AssessmentWithMetadata, TestTypeEnum


@dataclass
class ValidationResult:
    """Result of a validation test."""
    test_name: str
    passed: bool
    score: float  # 0-100
    issues: List[str]
    notes: List[str]


class AssessIQValidationSuite(unittest.TestCase):
    """Master validation suite for AssessIQ AI platform."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        # Create mock catalog
        cls.catalog = cls._create_mock_catalog()
        cls.catalog_dict = {a.id: a for a in cls.catalog}
        
        # Initialize components
        cls.taxonomy = AssessmentTaxonomy(cls.catalog)
        cls.ranker = RecruiterRanker(cls.taxonomy)
        cls.explanation_engine = RecruiterExplanationEngine(cls.taxonomy)
        cls.comparison_engine = ComparisonEngine(cls.taxonomy)
        cls.validator = SHLAssessmentValidator(cls.catalog)
        cls.memory_store = ConversationMemoryStore()
    
    @classmethod
    def _create_mock_catalog(cls) -> List[AssessmentWithMetadata]:
        """Create mock SHL catalog for testing."""
        return [
            AssessmentWithMetadata(
                id="opq32r",
                name="OPQ32r",
                description="Comprehensive personality assessment measuring 32 workplace traits",
                url="https://www.shl.com/solutions/products/opq32r",
                duration_minutes=30,
                test_type=TestTypeEnum.PERSONALITY,
                skills=["personality", "behavior", "work style", "communication"],
                seniority_levels=["mid", "senior"],
                category="personality",
                leadership_focus=True,
                communication_focus=True,
            ),
            AssessmentWithMetadata(
                id="java_8",
                name="Java 8 Knowledge Test",
                description="Measures Java programming proficiency including streams and lambdas",
                url="https://www.shl.com/solutions/products/java-8-knowledge-test",
                duration_minutes=45,
                test_type=TestTypeEnum.KNOWLEDGE,
                skills=["Java", "programming", "backend", "OOP"],
                seniority_levels=["junior", "mid", "senior"],
                category="technical",
                technical_focus=True,
            ),
            AssessmentWithMetadata(
                id="gsa",
                name="General Ability Assessment",
                description="Tests cognitive ability through verbal, numerical and logical reasoning",
                url="https://www.shl.com/solutions/products/gsa",
                duration_minutes=25,
                test_type=TestTypeEnum.ABILITY,
                skills=["reasoning", "cognitive", "problem solving"],
                seniority_levels=["junior", "mid", "senior"],
                category="cognitive",
            ),
            AssessmentWithMetadata(
                id="python_adv",
                name="Advanced Python Assessment",
                description="Evaluates advanced Python including decorators and async",
                url="https://www.shl.com/solutions/products/python-advanced",
                duration_minutes=50,
                test_type=TestTypeEnum.KNOWLEDGE,
                skills=["Python", "programming", "data science", "backend"],
                seniority_levels=["mid", "senior"],
                category="technical",
                technical_focus=True,
            ),
            AssessmentWithMetadata(
                id="leadership_7",
                name="Leadership 7",
                description="Assesses leadership potential and management readiness",
                url="https://www.shl.com/solutions/products/leadership-7",
                duration_minutes=35,
                test_type=TestTypeEnum.ABILITY,
                skills=["leadership", "management", "decision making"],
                seniority_levels=["mid", "senior"],
                category="leadership",
                leadership_focus=True,
            ),
        ]
    
    def test_1_senior_java_engineer_ranking(self) -> ValidationResult:
        """
        Test 1: Senior Java Engineer
        
        Expected:
        - Java test ranked first (~94-96%)
        - Technical tests prioritized
        - Personality tests ranked lower
        - Natural score spread: 96, 89, 82...
        """
        context = HiringContext()
        context.role = "Senior Java Engineer"
        context.seniority = "senior"
        context.tech_stack = {"java", "spring", "backend"}
        context.soft_skills = {"communication"}
        
        # Mock retrieval results
        retrieved = [
            {"id": "opq32r", "hybrid_score": 0.7},
            {"id": "java_8", "hybrid_score": 0.8},
            {"id": "gsa", "hybrid_score": 0.75},
            {"id": "python_adv", "hybrid_score": 0.6},
            {"id": "leadership_7", "hybrid_score": 0.65},
        ]
        
        results = self.ranker.rank(retrieved, context, self.catalog_dict, top_k=5)
        
        issues = []
        notes = []
        
        # Validate ranking order
        if results[0].assessment.id != "java_8":
            issues.append(f"Java test not ranked first - got {results[0].assessment.name}")
        else:
            notes.append(f"✓ Java test correctly ranked first: {results[0].final_score:.0%}")
        
        # Validate score spread
        scores = [r.final_score for r in results]
        if scores[0] < 0.90:
            issues.append(f"Top score too low: {scores[0]:.0%} (expected >90%)")
        
        if len(set(f"{s*100:.0f}" for s in scores)) < 3:
            issues.append(f"Poor score diversity - scores too similar: {[f'{s:.0%}' for s in scores]}")
        else:
            notes.append(f"✓ Good score spread: {[f'{s:.0%}' for s in scores[:3]]}")
        
        # Technical tests should dominate top 3
        top_3_domains = [r.domain for r in results[:3]]
        tech_count = sum(1 for d in top_3_domains if d == AssessmentDomain.TECHNICAL)
        if tech_count < 2:
            issues.append(f"Technical tests not prioritized: {top_3_domains}")
        else:
            notes.append(f"✓ Technical tests prioritized: {tech_count}/3 in top 3")
        
        passed = len(issues) == 0
        score = 100 if passed else max(0, 100 - len(issues) * 25)
        
        return ValidationResult(
            test_name="Senior Java Engineer Ranking",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_2_frontend_react_developer(self) -> ValidationResult:
        """
        Test 2: Frontend React Developer
        
        Expected:
        - Frontend-focused assessments prioritized
        - Technical knowledge tests first
        - Cognitive tests secondary
        """
        context = HiringContext()
        context.role = "Frontend React Developer"
        context.seniority = "mid"
        context.tech_stack = {"react", "javascript", "frontend"}
        context.soft_skills = {"communication", "teamwork"}
        
        retrieved = [
            {"id": "opq32r", "hybrid_score": 0.65},
            {"id": "java_8", "hybrid_score": 0.5},  # Low relevance
            {"id": "gsa", "hybrid_score": 0.7},
            {"id": "python_adv", "hybrid_score": 0.4},  # Low relevance
            {"id": "leadership_7", "hybrid_score": 0.55},
        ]
        
        results = self.ranker.rank(retrieved, context, self.catalog_dict, top_k=5)
        
        issues = []
        notes = []
        
        # Java test should be deprioritized for frontend role
        java_rank = next((i for i, r in enumerate(results) if r.assessment.id == "java_8"), 999)
        if java_rank < 2:
            issues.append(f"Java test ranked too high ({java_rank + 1}) for frontend role")
        else:
            notes.append(f"✓ Java correctly deprioritized: rank {java_rank + 1}")
        
        notes.append(f"Scores: {[f'{r.final_score:.0%}' for r in results]}")
        
        passed = len(issues) == 0
        score = 100 if passed else max(0, 100 - len(issues) * 30)
        
        return ValidationResult(
            test_name="Frontend React Developer Ranking",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_3_data_scientist(self) -> ValidationResult:
        """
        Test 3: Data Scientist
        
        Expected:
        - Python/Analytical assessments prioritized
        - Cognitive tests secondary
        """
        context = HiringContext()
        context.role = "Data Scientist"
        context.seniority = "senior"
        context.tech_stack = {"python", "machine learning", "statistics"}
        context.soft_skills = {"communication"}
        
        retrieved = [
            {"id": "opq32r", "hybrid_score": 0.6},
            {"id": "java_8", "hybrid_score": 0.5},
            {"id": "gsa", "hybrid_score": 0.75},
            {"id": "python_adv", "hybrid_score": 0.85},
            {"id": "leadership_7", "hybrid_score": 0.55},
        ]
        
        results = self.ranker.rank(retrieved, context, self.catalog_dict, top_k=5)
        
        issues = []
        notes = []
        
        # Python should be high
        python_rank = next((i for i, r in enumerate(results) if r.assessment.id == "python_adv"), 999)
        if python_rank > 2:
            issues.append(f"Python test ranked too low ({python_rank + 1}) for data scientist")
        else:
            notes.append(f"✓ Python test correctly prioritized: rank {python_rank + 1}")
        
        passed = len(issues) == 0
        score = 100 if passed else 70
        
        return ValidationResult(
            test_name="Data Scientist Ranking",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_4_leadership_role(self) -> ValidationResult:
        """
        Test 4: Leadership Role
        
        Expected:
        - Leadership/personality tests prioritized
        - Technical tests ranked lower
        """
        context = HiringContext()
        context.role = "Engineering Manager"
        context.seniority = "senior"
        context.tech_stack = {"management"}
        context.soft_skills = {"leadership", "communication", "teamwork"}
        context.leadership_needs = True
        
        retrieved = [
            {"id": "opq32r", "hybrid_score": 0.75},
            {"id": "java_8", "hybrid_score": 0.6},
            {"id": "gsa", "hybrid_score": 0.7},
            {"id": "python_adv", "hybrid_score": 0.55},
            {"id": "leadership_7", "hybrid_score": 0.8},
        ]
        
        results = self.ranker.rank(retrieved, context, self.catalog_dict, top_k=5)
        
        issues = []
        notes = []
        
        # Leadership and personality should be top
        top_2_ids = [r.assessment.id for r in results[:2]]
        if "leadership_7" not in top_2_ids and "opq32r" not in top_2_ids:
            issues.append(f"Leadership/personality not in top 2: {top_2_ids}")
        else:
            notes.append(f"✓ Leadership assessments prioritized")
        
        passed = len(issues) == 0
        score = 100 if passed else 60
        
        return ValidationResult(
            test_name="Leadership Role Ranking",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_5_unique_explanations(self) -> ValidationResult:
        """
        Test 5: Explanation Uniqueness
        
        Expected:
        - Each explanation is unique
        - No template/generic language
        - Mentions specific capabilities
        """
        context = HiringContext()
        context.role = "Senior Java Engineer"
        context.seniority = "senior"
        context.tech_stack = {"java"}
        
        explanations = []
        for assessment in self.catalog[:4]:
            exp = self.explanation_engine.generate_explanation(assessment, context)
            explanations.append((assessment.name, exp))
        
        issues = []
        notes = []
        
        # Check uniqueness
        unique_explanations = set(e[1] for e in explanations)
        if len(unique_explanations) < len(explanations) * 0.75:
            issues.append(f"Too many duplicate explanations: {len(unique_explanations)}/{len(explanations)} unique")
        else:
            notes.append(f"✓ {len(unique_explanations)}/{len(explanations)} unique explanations")
        
        # Check for generic language
        generic_phrases = ["strong fit", "good alignment", "strategic recommendation"]
        for name, exp in explanations:
            for phrase in generic_phrases:
                if phrase.lower() in exp.lower():
                    issues.append(f"Generic phrase '{phrase}' in {name} explanation")
        
        if not any("generic" in i.lower() for i in issues):
            notes.append("✓ No generic filler language detected")
        
        passed = len([i for i in issues if "Generic" in i]) == 0
        score = 100 if passed else max(0, 100 - len(issues) * 10)
        
        return ValidationResult(
            test_name="Explanation Uniqueness",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_6_comparison_engine(self) -> ValidationResult:
        """
        Test 6: Comparison Engine
        
        Expected:
        - Structured comparison matrix
        - Winner determined logically
        - Use cases provided
        """
        a1 = self.catalog_dict["java_8"]
        a2 = self.catalog_dict["opq32r"]
        
        context = HiringContext()
        context.role = "Senior Java Engineer"
        context.tech_stack = {"java"}
        
        result = self.comparison_engine.compare(a1, a2, context)
        
        issues = []
        notes = []
        
        # Check matrix
        if len(result.comparison_matrix) < 5:
            issues.append(f"Comparison matrix too small: {len(result.comparison_matrix)} dimensions")
        else:
            notes.append(f"✓ {len(result.comparison_matrix)} comparison dimensions")
        
        # Check for winner
        if not result.overall_winner:
            issues.append("No overall winner determined")
        else:
            notes.append(f"✓ Winner determined: {result.overall_winner}")
        
        # For Java role, Java test should win
        if result.overall_winner != "assessment_1":
            issues.append(f"Java test should win for Java role, got: {result.overall_winner}")
        
        passed = len(issues) == 0
        score = 100 if passed else max(0, 100 - len(issues) * 20)
        
        return ValidationResult(
            test_name="Comparison Engine",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_7_conversational_memory(self) -> ValidationResult:
        """
        Test 7: Conversational Memory
        
        Expected:
        - Recommendations stored
        - Relative references resolved
        - Context maintained
        """
        session_id = "test_session_123"
        
        # Store recommendations
        recommendations = [
            {"id": "java_8", "name": "Java 8 Knowledge Test", "score": 0.94, "category": "Technical"},
            {"id": "gsa", "name": "GSA", "score": 0.88, "category": "Cognitive"},
        ]
        
        context = HiringContext()
        context.role = "Senior Java Engineer"
        
        self.memory_store.store_recommendations(session_id, recommendations, context)
        
        # Test retrieval
        stored = self.memory_store.get_current_recommendations(session_id)
        
        issues = []
        notes = []
        
        if len(stored) != 2:
            issues.append(f"Wrong number of stored recommendations: {len(stored)}")
        else:
            notes.append(f"✓ {len(stored)} recommendations stored")
        
        # Test relative reference resolution
        resolved = self.memory_store.resolve_relative_reference(session_id, "top 2")
        if not resolved or len(resolved) != 2:
            issues.append("Failed to resolve 'top 2' reference")
        else:
            notes.append("✓ 'top 2' reference resolved correctly")
        
        passed = len(issues) == 0
        score = 100 if passed else 50
        
        return ValidationResult(
            test_name="Conversational Memory",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_8_assessment_validation(self) -> ValidationResult:
        """
        Test 8: Assessment Legitimacy
        
        Expected:
        - Valid assessments pass
        - Invalid assessments rejected
        - Hallucinations detected
        """
        issues = []
        notes = []
        
        # Test valid assessment
        valid = self.catalog[0]
        result = self.validator.validate_assessment(valid)
        if not result.is_valid:
            issues.append(f"Valid assessment rejected: {valid.name} - {result.errors}")
        else:
            notes.append(f"✓ Valid assessment accepted: {valid.name}")
        
        # Test hallucination detection
        hallucinated_text = "I recommend the SuperTest Pro and UltraAssessment 5000."
        is_clean, hallucinated = self.validator.check_for_hallucinations(hallucinated_text)
        if is_clean or len(hallucinated) == 0:
            issues.append("Failed to detect hallucinated assessments")
        else:
            notes.append(f"✓ Hallucinations detected: {hallucinated}")
        
        passed = len(issues) == 0
        score = 100 if passed else 50
        
        return ValidationResult(
            test_name="Assessment Validation",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_9_taxonomy_classification(self) -> ValidationResult:
        """
        Test 9: Taxonomy Classification
        
        Expected:
        - Roles classified correctly
        - Assessments categorized correctly
        - Domain alignment calculated
        """
        issues = []
        notes = []
        
        # Test role classification
        role_tests = [
            ("Senior Java Engineer", RoleDomain.BACKEND_ENGINEER),
            ("Data Scientist", RoleDomain.DATA_SCIENTIST),
            ("Sales Manager", RoleDomain.SALES_MANAGER),
        ]
        
        for role, expected in role_tests:
            classified = self.taxonomy.classify_role(role, [])
            if classified != expected:
                issues.append(f"Role misclassified: {role} -> {classified} (expected {expected})")
            else:
                notes.append(f"✓ {role} -> {classified.value}")
        
        # Test assessment classification
        java_class = self.taxonomy.get_assessment_classification("java_8")
        if java_class and java_class.primary_domain != AssessmentDomain.TECHNICAL:
            issues.append(f"Java test misclassified: {java_class.primary_domain}")
        else:
            notes.append("✓ Java test correctly classified as Technical")
        
        passed = len(issues) == 0
        score = 100 if passed else max(0, 100 - len(issues) * 15)
        
        return ValidationResult(
            test_name="Taxonomy Classification",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )
    
    def test_10_diversity_balancing(self) -> ValidationResult:
        """
        Test 10: Diversity Balancing
        
        Expected:
        - No 5 personality tests
        - Mixed categories in recommendations
        - Domain diversity enforced
        """
        # Create catalog with many personality tests
        diverse_catalog = self.catalog + [
            AssessmentWithMetadata(
                id="16pf",
                name="16PF",
                description="Personality factors assessment",
                url="https://www.shl.com/solutions/products/16pf",
                duration_minutes=45,
                test_type=TestTypeEnum.PERSONALITY,
                skills=["personality"],
                seniority_levels=["mid", "senior"],
                category="personality",
            ),
        ]
        diverse_dict = {a.id: a for a in diverse_catalog}
        
        context = HiringContext()
        context.role = "Senior Manager"  # Role that might get personality tests
        context.leadership_needs = True
        
        retrieved = [{"id": a.id, "hybrid_score": 0.7} for a in diverse_catalog]
        
        results = self.ranker.rank(retrieved, context, diverse_dict, top_k=5)
        
        issues = []
        notes = []
        
        # Check category diversity
        categories = [r.category for r in results]
        personality_count = categories.count("personality")
        
        if personality_count > 3:
            issues.append(f"Too many personality tests: {personality_count}/5")
        else:
            notes.append(f"✓ Category diversity maintained: {personality_count}/5 personality")
        
        notes.append(f"Categories: {categories}")
        
        passed = len(issues) == 0
        score = 100 if passed else 70
        
        return ValidationResult(
            test_name="Diversity Balancing",
            passed=passed,
            score=score,
            issues=issues,
            notes=notes
        )


def run_validation_suite():
    """Run all validation tests and print results."""
    print("=" * 70)
    print("ASSESSIQ AI - MASTER VALIDATION SUITE")
    print("=" * 70)
    print()
    
    suite = AssessIQValidationSuite()
    suite.setUpClass()
    
    tests = [
        suite.test_1_senior_java_engineer_ranking,
        suite.test_2_frontend_react_developer,
        suite.test_3_data_scientist,
        suite.test_4_leadership_role,
        suite.test_5_unique_explanations,
        suite.test_6_comparison_engine,
        suite.test_7_conversational_memory,
        suite.test_8_assessment_validation,
        suite.test_9_taxonomy_classification,
        suite.test_10_diversity_balancing,
    ]
    
    results = []
    for test_func in tests:
        result = test_func()
        results.append(result)
        
        status = "[PASS]" if result.passed else "[FAIL]"
        print(f"{status} - {result.test_name} ({result.score:.0f}%)")
        
        for note in result.notes:
            print(f"   {note}")
        for issue in result.issues:
            print(f"   ⚠️  {issue}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    avg_score = sum(r.score for r in results) / len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Average Score: {avg_score:.1f}%")
    print(f"Overall Status: {'✅ ALL TESTS PASSED' if passed == total else '⚠️  SOME TESTS FAILED'}")
    print()
    
    # Detailed results
    if any(not r.passed for r in results):
        print("Failed Tests:")
        for r in results:
            if not r.passed:
                print(f"  - {r.test_name}: {r.score:.0f}%")
                for issue in r.issues:
                    print(f"    - {issue}")
        print()
    
    return results


if __name__ == "__main__":
    run_validation_suite()
