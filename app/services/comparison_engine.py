"""
Real Comparison Engine for AssessIQ AI.

Provides structured, recruiter-grade comparison capabilities.

Supports:
- "compare top 2"
- "compare them" 
- "which is better"
- "which is better for leadership"
- etc.

Uses conversation memory and generates structured comparison matrices.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
from app.models.assessment import AssessmentWithMetadata
from app.services.conversation_analyzer import HiringContext
from app.core.assessment_taxonomy import (
    AssessmentTaxonomy, AssessmentDomain, RoleDomain, AssessmentClassification
)
from app.services.recruiter_reasoning import RecruiterExplanationEngine
from app.logger_config.logger import get_logger

logger = get_logger("comparison_engine")


class ComparisonDimension(str, Enum):
    """Dimensions for comparison matrix."""
    TECHNICAL_DEPTH = "technical_depth"
    COGNITIVE_REASONING = "cognitive_reasoning"
    PERSONALITY_MEASUREMENT = "personality_measurement"
    LEADERSHIP_ASSESSMENT = "leadership_assessment"
    COMMUNICATION_SKILLS = "communication_skills"
    BEHAVIORAL_INSIGHT = "behavioral_insight"
    ANALYTICAL_CAPABILITY = "analytical_capability"
    SALES_APTITUDE = "sales_aptitude"
    DURATION = "duration"
    SENIORITY_SUITABILITY = "seniority_suitability"


@dataclass
class ComparisonScore:
    """Score for a dimension in comparison."""
    dimension: ComparisonDimension
    assessment_1_score: float  # 0-1
    assessment_2_score: float  # 0-1
    winner: str  # "assessment_1", "assessment_2", or "tie"
    reasoning: str


@dataclass
class ComparisonResult:
    """Enterprise-grade comparison result."""
    assessment_1: AssessmentWithMetadata
    assessment_2: AssessmentWithMetadata
    
    # Structured Matrix Data
    best_for: Tuple[str, str]
    seniority: Tuple[str, str]
    measures: Tuple[str, str]
    strengths: Tuple[str, str]
    weaknesses: Tuple[str, str]
    recommended_use_case: Tuple[str, str]
    
    overall_winner: str
    recruiter_recommendation: str  # Strategic advice
    recruiter_summary: str
    comparison_matrix: List[ComparisonScore] = field(default_factory=list)


class ComparisonEngine:
    """
    Enterprise-grade comparison engine for assessment selection.
    
    Generates structured comparison matrices with recruiter-grade reasoning.
    """
    
    def __init__(self, taxonomy: Optional[AssessmentTaxonomy] = None):
        self.taxonomy = taxonomy or AssessmentTaxonomy()
        self.explanation_engine = RecruiterExplanationEngine(self.taxonomy)
    
    def compare(
        self,
        assessment_1: AssessmentWithMetadata,
        assessment_2: AssessmentWithMetadata,
        context: Optional[HiringContext] = None
    ) -> ComparisonResult:
        """
        Generate comprehensive comparison between two assessments.
        """
        logger.info(f"Comparing {assessment_1.name} vs {assessment_2.name}")
        
        class_1 = self.taxonomy.get_assessment_classification(assessment_1.id) or self.taxonomy._classify_assessment(assessment_1)
        class_2 = self.taxonomy.get_assessment_classification(assessment_2.id) or self.taxonomy._classify_assessment(assessment_2)
        
        # 1. Best For
        best_for = (
            class_1.ideal_use_cases[0] if class_1.ideal_use_cases else "General hiring",
            class_2.ideal_use_cases[0] if class_2.ideal_use_cases else "General hiring"
        )
        
        # 2. Seniority
        seniority = (
            ", ".join(assessment_1.seniority_levels) if assessment_1.seniority_levels else "Professional",
            ", ".join(assessment_2.seniority_levels) if assessment_2.seniority_levels else "Professional"
        )
        
        # 3. Measures
        measures = (
            ", ".join(class_1.key_capabilities[:2]),
            ", ".join(class_2.key_capabilities[:2])
        )
        
        # 4. Strengths
        strengths = (
            self._get_strength(assessment_1, class_1),
            self._get_strength(assessment_2, class_2)
        )
        
        # 5. Weaknesses
        weaknesses = (
            self._get_weakness(assessment_1, class_1),
            self._get_weakness(assessment_2, class_2)
        )
        
        # 6. Recommended Use Case
        use_case = (
            f"Screening for {class_1.primary_domain.value}",
            f"Screening for {class_2.primary_domain.value}"
        )
        
        # Build comparison matrix
        matrix = self._build_comparison_matrix(assessment_1, assessment_2, class_1, class_2, context)
        
        # Determine Winner & Strategic Recommendation
        winner, rec = self._determine_overall_winner(assessment_1, assessment_2, matrix, class_1, class_2, context)
        
        # Summary
        summary = self._generate_recruiter_summary(assessment_1, assessment_2, matrix, winner, context)
        
        return ComparisonResult(
            assessment_1=assessment_1,
            assessment_2=assessment_2,
            best_for=best_for,
            seniority=seniority,
            measures=measures,
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_use_case=use_case,
            overall_winner=winner,
            recruiter_recommendation=rec,
            recruiter_summary=summary,
            comparison_matrix=matrix
        )

    def _get_strength(self, assessment, classification) -> str:
        if classification.primary_domain == AssessmentDomain.TECHNICAL:
            return "Deep technical verification"
        if classification.primary_domain == AssessmentDomain.COGNITIVE:
            return "High learning agility predictor"
        if classification.primary_domain == AssessmentDomain.PERSONALITY:
            return "Strong behavioral fit insights"
        return "Comprehensive competency coverage"

    def _get_weakness(self, assessment, classification) -> str:
        if classification.primary_domain == AssessmentDomain.TECHNICAL:
            return "May overlook behavioral fit"
        if classification.primary_domain == AssessmentDomain.COGNITIVE:
            return "Doesn't measure specific skills"
        if getattr(assessment, "duration_minutes", 30) > 45:
            return "Higher candidate time commitment"
        return "Less specialized focus"

    def _calculate_strategic_recommendation(self, a1, a2, c1, c2, context) -> Tuple[str, str]:
        if not context:
            return "tie", f"Both assessments are catalog-listed SHL options. {a1.name} is classified as {c1.primary_domain.value}, and {a2.name} is classified as {c2.primary_domain.value}."
            
        role_domain = self.taxonomy.classify_role(context.role or "", list(context.tech_stack))
        p1 = self.taxonomy.get_domain_priorities(role_domain).get(c1.primary_domain, 0)
        p2 = self.taxonomy.get_domain_priorities(role_domain).get(c2.primary_domain, 0)
        
        if p1 > p2:
            return "assessment_1", f"{a1.name} is the closer catalog match for this role because it is classified as {c1.primary_domain.value} and the requested role maps more strongly to that domain."
        elif p2 > p1:
            return "assessment_2", f"{a2.name} is the closer catalog match for this role because it is classified as {c2.primary_domain.value} and the requested role maps more strongly to that domain."
        else:
            return "tie", f"Both assessments remain viable catalog options for {context.role or 'this role'} because the catalog priorities are tied for {c1.primary_domain.value} and {c2.primary_domain.value}."

    def _generate_recruiter_summary_v2(self, a1, a2, c1, c2, winner) -> str:
        if winner == "tie":
            return f"Both {a1.name} and {a2.name} are grounded SHL catalog assessments. {a1.name} is classified as {c1.primary_domain.value} and {a2.name} is classified as {c2.primary_domain.value}."
        
        w_name = a1.name if winner == "assessment_1" else a2.name
        l_name = a2.name if winner == "assessment_1" else a1.name
        return f"{w_name} is the catalog-backed recommendation. {l_name} remains the alternate catalog option for comparison."
    
    def compare_by_names(
        self,
        name_1: str,
        name_2: str,
        catalog: Dict[str, AssessmentWithMetadata],
        context: Optional[HiringContext] = None
    ) -> Optional[ComparisonResult]:
        """Compare assessments by their names."""
        # Find assessments by name
        a1 = None
        a2 = None
        
        for assessment in catalog.values():
            if assessment.name.lower() == name_1.lower() or name_1.lower() in assessment.name.lower():
                a1 = assessment
            if assessment.name.lower() == name_2.lower() or name_2.lower() in assessment.name.lower():
                a2 = assessment
        
        if not a1 or not a2:
            logger.error(f"Could not find assessments: {name_1} or {name_2}")
            return None
        
        return self.compare(a1, a2, context)
    
    def _build_comparison_matrix(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        c1: AssessmentClassification,
        c2: AssessmentClassification,
        context: Optional[HiringContext]
    ) -> List[ComparisonScore]:
        """Build comprehensive comparison matrix."""
        matrix = []
        
        # Technical Depth
        matrix.append(self._compare_technical_depth(a1, a2, c1, c2))
        
        # Cognitive Reasoning
        matrix.append(self._compare_cognitive_reasoning(a1, a2, c1, c2))
        
        # Personality Measurement
        matrix.append(self._compare_personality_measurement(a1, a2, c1, c2))
        
        # Leadership Assessment
        matrix.append(self._compare_leadership_assessment(a1, a2, c1, c2))
        
        # Communication Skills
        matrix.append(self._compare_communication_skills(a1, a2, c1, c2))
        
        # Behavioral Insight
        matrix.append(self._compare_behavioral_insight(a1, a2, c1, c2))
        
        # Analytical Capability
        matrix.append(self._compare_analytical_capability(a1, a2, c1, c2))
        
        # Duration
        matrix.append(self._compare_duration(a1, a2))
        
        # Seniority Suitability
        matrix.append(self._compare_seniority_suitability(a1, a2, c1, c2))
        
        return matrix
    
    def _compare_technical_depth(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare technical depth dimension."""
        s1 = c1.technical_depth / 10.0
        s2 = c2.technical_depth / 10.0
        
        if c1.primary_domain == AssessmentDomain.TECHNICAL:
            s1 = max(s1, 0.8)
        if c2.primary_domain == AssessmentDomain.TECHNICAL:
            s2 = max(s2, 0.8)
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "technical depth", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} measures {c1.key_capabilities[0] if c1.key_capabilities else 'technical skills'}" if s1 > s2 else
            f"{a2.name} measures {c2.key_capabilities[0] if c2.key_capabilities else 'technical skills'}" if s2 > s1 else
            "Both assess similar technical competencies"
        )
        
        return ComparisonScore(
            ComparisonDimension.TECHNICAL_DEPTH, s1, s2, winner, reasoning
        )
    
    def _compare_cognitive_reasoning(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare cognitive reasoning dimension."""
        s1 = 0.7 if c1.primary_domain == AssessmentDomain.COGNITIVE else 0.4
        s2 = 0.7 if c2.primary_domain == AssessmentDomain.COGNITIVE else 0.4
        
        # Boost if test type is Ability
        if a1.test_type.value == "A":
            s1 = max(s1, 0.8)
        if a2.test_type.value == "A":
            s2 = max(s2, 0.8)
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "cognitive reasoning", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} evaluates reasoning capabilities" if s1 > s2 else
            f"{a2.name} evaluates reasoning capabilities" if s2 > s1 else
            "Both assess cognitive abilities"
        )
        
        return ComparisonScore(
            ComparisonDimension.COGNITIVE_REASONING, s1, s2, winner, reasoning
        )
    
    def _compare_personality_measurement(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare personality measurement dimension."""
        s1 = 0.9 if c1.primary_domain == AssessmentDomain.PERSONALITY else 0.3
        s2 = 0.9 if c2.primary_domain == AssessmentDomain.PERSONALITY else 0.3
        
        # Check test type
        if a1.test_type.value == "P":
            s1 = 1.0
        if a2.test_type.value == "P":
            s2 = 1.0
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "personality assessment", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} provides comprehensive personality insights" if s1 > s2 else
            f"{a2.name} provides comprehensive personality insights" if s2 > s1 else
            "Both are personality assessments"
        )
        
        return ComparisonScore(
            ComparisonDimension.PERSONALITY_MEASUREMENT, s1, s2, winner, reasoning
        )
    
    def _compare_leadership_assessment(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare leadership assessment dimension."""
        s1 = 0.0
        s2 = 0.0
        
        # Check leadership focus flag
        if hasattr(a1, 'leadership_focus') and a1.leadership_focus:
            s1 = 0.9
        if hasattr(a2, 'leadership_focus') and a2.leadership_focus:
            s2 = 0.9
        
        # Check domain
        if c1.primary_domain == AssessmentDomain.LEADERSHIP:
            s1 = max(s1, 0.85)
        if c2.primary_domain == AssessmentDomain.LEADERSHIP:
            s2 = max(s2, 0.85)
        
        # Check name
        if "leadership" in a1.name.lower():
            s1 = 0.95
        if "leadership" in a2.name.lower():
            s2 = 0.95
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "leadership evaluation", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} specifically targets leadership competencies" if s1 > s2 else
            f"{a2.name} specifically targets leadership competencies" if s2 > s1 else
            "Neither focuses primarily on leadership" if s1 < 0.5 and s2 < 0.5 else
            "Both assess leadership dimensions"
        )
        
        return ComparisonScore(
            ComparisonDimension.LEADERSHIP_ASSESSMENT, s1, s2, winner, reasoning
        )
    
    def _compare_communication_skills(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare communication skills dimension."""
        s1 = 0.0
        s2 = 0.0
        
        # Check communication focus flag
        if hasattr(a1, 'communication_focus') and a1.communication_focus:
            s1 = 0.9
        if hasattr(a2, 'communication_focus') and a2.communication_focus:
            s2 = 0.9
        
        # Check skills
        if "communication" in [s.lower() for s in a1.skills]:
            s1 = max(s1, 0.8)
        if "communication" in [s.lower() for s in a2.skills]:
            s2 = max(s2, 0.8)
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "communication evaluation", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} measures communication effectiveness" if s1 > s2 else
            f"{a2.name} measures communication effectiveness" if s2 > s1 else
            "Communication assessment is secondary for both"
        )
        
        return ComparisonScore(
            ComparisonDimension.COMMUNICATION_SKILLS, s1, s2, winner, reasoning
        )
    
    def _compare_behavioral_insight(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare behavioral insight dimension."""
        s1 = c1.behavioral_relevance / 10.0
        s2 = c2.behavioral_relevance / 10.0
        
        # Boost for personality tests
        if a1.test_type.value == "P":
            s1 = max(s1, 0.8)
        if a2.test_type.value == "P":
            s2 = max(s2, 0.8)
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "behavioral insights", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} reveals workplace behavioral patterns" if s1 > s2 else
            f"{a2.name} reveals workplace behavioral patterns" if s2 > s1 else
            "Both provide behavioral insights"
        )
        
        return ComparisonScore(
            ComparisonDimension.BEHAVIORAL_INSIGHT, s1, s2, winner, reasoning
        )
    
    def _compare_analytical_capability(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare analytical capability dimension."""
        s1 = 0.8 if c1.primary_domain == AssessmentDomain.ANALYTICAL else 0.4
        s2 = 0.8 if c2.primary_domain == AssessmentDomain.ANALYTICAL else 0.4
        
        # Check for analytical terms
        if any(term in a1.description.lower() for term in ["analytical", "analysis", "data"]):
            s1 = max(s1, 0.7)
        if any(term in a2.description.lower() for term in ["analytical", "analysis", "data"]):
            s2 = max(s2, 0.7)
        
        winner = self._determine_winner(s1, s2)
        reasoning = self._generate_dimension_reasoning(
            "analytical evaluation", a1.name, a2.name, s1, s2, winner,
            f"{a1.name} tests analytical reasoning" if s1 > s2 else
            f"{a2.name} tests analytical reasoning" if s2 > s1 else
            "Analytical capability is not primary focus for either"
        )
        
        return ComparisonScore(
            ComparisonDimension.ANALYTICAL_CAPABILITY, s1, s2, winner, reasoning
        )
    
    def _compare_duration(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata
    ) -> ComparisonScore:
        """Compare duration - shorter is generally better for candidates."""
        d1 = getattr(a1, 'duration_minutes', 30)
        d2 = getattr(a2, 'duration_minutes', 30)
        
        # Score inversely - shorter is better (higher score)
        max_d = max(d1, d2, 60)
        s1 = 1.0 - (d1 / max_d) * 0.5  # 30min = 0.75, 60min = 0.5
        s2 = 1.0 - (d2 / max_d) * 0.5
        
        winner = self._determine_winner(s1, s2)
        reasoning = f"{a1.name} takes {d1}min, {a2.name} takes {d2}min - {a1.name if s1 > s2 else a2.name} requires less candidate time"
        
        return ComparisonScore(
            ComparisonDimension.DURATION, s1, s2, winner, reasoning
        )
    
    def _compare_seniority_suitability(
        self, a1: AssessmentWithMetadata, a2: AssessmentWithMetadata,
        c1: AssessmentClassification, c2: AssessmentClassification
    ) -> ComparisonScore:
        """Compare seniority suitability."""
        # Count seniority levels
        s1_levels = len(c1.seniority_suitability)
        s2_levels = len(c2.seniority_suitability)
        
        max_levels = max(s1_levels, s2_levels, 1)
        s1 = s1_levels / max_levels
        s2 = s2_levels / max_levels
        
        winner = self._determine_winner(s1, s2)
        reasoning = f"{a1.name} suitable for {', '.join(c1.seniority_suitability)}; {a2.name} suitable for {', '.join(c2.seniority_suitability)}"
        
        return ComparisonScore(
            ComparisonDimension.SENIORITY_SUITABILITY, s1, s2, winner, reasoning
        )
    
    def _determine_winner(self, s1: float, s2: float, threshold: float = 0.1) -> str:
        """Determine winner with threshold to avoid ties on small differences."""
        if abs(s1 - s2) < threshold:
            return "tie"
        return "assessment_1" if s1 > s2 else "assessment_2"
    
    def _generate_dimension_reasoning(
        self, dimension: str, name1: str, name2: str,
        s1: float, s2: float, winner: str, specific: str
    ) -> str:
        """Generate reasoning for a comparison dimension."""
        if winner == "tie":
            return f"Both assessments are comparable in {dimension}"
        
        winner_name = name1 if winner == "assessment_1" else name2
        winner_score = s1 if winner == "assessment_1" else s2
        
        if winner_score > 0.7:
            return f"{winner_name} strongly leads in {dimension}: {specific}"
        else:
            return f"{winner_name} has slight edge in {dimension}: {specific}"
    
    def _determine_overall_winner(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        matrix: List[ComparisonScore],
        c1: AssessmentClassification,
        c2: AssessmentClassification,
        context: Optional[HiringContext]
    ) -> Tuple[str, str]:
        """Determine overall winner based on context priorities."""
        # Score each assessment
        score1 = 0
        score2 = 0
        
        for comp in matrix:
            if comp.winner == "assessment_1":
                score1 += 1
            elif comp.winner == "assessment_2":
                score2 += 1
            else:
                score1 += 0.5
                score2 += 0.5
        
        # Apply context weighting
        if context:
            role_domain = self.taxonomy.classify_role(context.role or "", list(context.tech_stack or []))
            priorities = self.taxonomy.get_domain_priorities(role_domain)
            
            # Boost scores based on domain alignment
            p1 = priorities.get(c1.primary_domain, 0.5)
            p2 = priorities.get(c2.primary_domain, 0.5)
            
            if p1 > p2:
                score1 += 5  # Increased from 2 to 5 for decisive domain match
            elif p2 > p1:
                score2 += 5
        
        # Determine winner
        if abs(score1 - score2) < 1:
            return "tie", f"Both {a1.name} and {a2.name} are viable options with different strengths"
        
        winner = a1.name if score1 > score2 else a2.name
        return ("assessment_1" if score1 > score2 else "assessment_2"), \
               f"{winner} is better aligned with role requirements based on dimensional analysis"
    
    def _generate_use_case_recommendations(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        c1: AssessmentClassification,
        c2: AssessmentClassification,
        context: Optional[HiringContext]
    ) -> Dict[str, str]:
        """Generate use case specific recommendations."""
        recs = {}
        
        # Technical hiring
        if c1.primary_domain == AssessmentDomain.TECHNICAL:
            recs["technical_hiring"] = f"Use {a1.name} for hands-on skills verification"
        elif c2.primary_domain == AssessmentDomain.TECHNICAL:
            recs["technical_hiring"] = f"Use {a2.name} for hands-on skills verification"
        
        # Leadership hiring
        if c1.primary_domain == AssessmentDomain.LEADERSHIP:
            recs["leadership_hiring"] = f"Use {a1.name} for leadership readiness evaluation"
        elif c2.primary_domain == AssessmentDomain.LEADERSHIP:
            recs["leadership_hiring"] = f"Use {a2.name} for leadership readiness evaluation"
        
        # Cultural fit
        if c1.primary_domain == AssessmentDomain.PERSONALITY:
            recs["cultural_fit"] = f"Use {a1.name} for team dynamics and culture fit assessment"
        elif c2.primary_domain == AssessmentDomain.PERSONALITY:
            recs["cultural_fit"] = f"Use {a2.name} for team dynamics and culture fit assessment"
        
        # Quick screening
        d1 = getattr(a1, 'duration_minutes', 30)
        d2 = getattr(a2, 'duration_minutes', 30)
        if d1 < d2:
            recs["quick_screening"] = f"Use {a1.name} for shorter screening ({d1}min vs {d2}min)"
        else:
            recs["quick_screening"] = f"Use {a2.name} for shorter screening ({d2}min vs {d1}min)"
        
        return recs
    
    def _generate_recruiter_summary(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        matrix: List[ComparisonScore],
        overall_winner: str,
        context: Optional[HiringContext]
    ) -> str:
        """Generate recruiter-grade summary text with nuanced reasoning."""
        # Get key differences
        non_ties = [m for m in matrix if m.winner != "tie"]
        
        if not non_ties:
            return f"Both **{a1.name}** and **{a2.name}** offer highly comparable psychometric properties. Your selection should depend on minor preference for either {a1.test_type.value}-type or {a2.test_type.value}-type assessments within your specific workflow."
        
        # Determine the primary differentiator
        top_diff = non_ties[0]
        winner_name = a1.name if top_diff.winner == "assessment_1" else a2.name
        loser_name = a2.name if top_diff.winner == "assessment_1" else a1.name
        
        summary = f"While both assessments are grounded in SHL standards, **{winner_name}** provides a distinct advantage in **{top_diff.dimension.value.replace('_', ' ').title()}**. "
        
        if len(non_ties) > 1:
            second_diff = non_ties[1]
            s_winner = a1.name if second_diff.winner == "assessment_1" else a2.name
            if s_winner == winner_name:
                summary += f"It also demonstrates stronger alignment in {second_diff.dimension.value.replace('_', ' ')}. "
            else:
                summary += f"Conversely, **{s_winner}** performs better for {second_diff.dimension.value.replace('_', ' ')} requirements. "
        
        # Context-aware closing
        if context and context.role:
            if overall_winner == "tie":
                summary += f"For a {context.role} role, either option is strategically sound depending on whether you prioritize technical depth or behavioral fit."
            else:
                final_winner = a1.name if overall_winner == "assessment_1" else a2.name
                summary += f"Ultimately, for the {context.role} position, **{final_winner}** is the more robust choice due to its superior alignment with the core competencies identified."
        else:
            if overall_winner == "tie":
                summary += "Both options are viable; consider the specific seniority of your candidate pool when making the final selection."
            else:
                final_winner = a1.name if overall_winner == "assessment_1" else a2.name
                summary += f"Based on this dimensional analysis, **{final_winner}** is the recommended strategic choice."
        
        return summary
    
    def format_for_frontend(self, result: ComparisonResult) -> Dict:
        """Format comparison result for frontend display."""
        return {
            "assessment_1": {
                "id": result.assessment_1.id,
                "name": result.assessment_1.name,
                "test_type": result.assessment_1.test_type.value,
                "url": result.assessment_1.url,
            },
            "assessment_2": {
                "id": result.assessment_2.id,
                "name": result.assessment_2.name,
                "test_type": result.assessment_2.test_type.value,
                "url": result.assessment_2.url,
            },
            "matrix": {
                "Best For": result.best_for,
                "Seniority": result.seniority,
                "Measures": result.measures,
                "Strengths": result.strengths,
                "Weaknesses": result.weaknesses,
                "Recommended Use Case": result.recommended_use_case
            },
            "overall_winner": result.overall_winner,
            "recruiter_recommendation": result.recruiter_recommendation,
            "recruiter_summary": result.recruiter_summary,
        }


# Backward compatibility
class ComparisonService(ComparisonEngine):
    """Backward compatible wrapper."""
    pass
