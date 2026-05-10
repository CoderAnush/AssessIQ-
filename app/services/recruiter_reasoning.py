"""
Recruiter-Grade Explanation Generation Engine.

Generates contextual, grounded explanations that sound like recruiter intelligence.
NO generic filler language. Every explanation must:
- Mention role relevance
- Mention assessed capability
- Explain WHY it matters for hiring
- Use grounded metadata only
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from app.models.assessment import AssessmentWithMetadata
from app.models.ranking import RankingFactors
from app.services.conversation_analyzer import HiringContext
from app.core.assessment_taxonomy import (
    AssessmentTaxonomy, AssessmentDomain, RoleDomain, AssessmentClassification
)
from app.logger_config.logger import get_logger

logger = get_logger("recruiter_reasoning")


@dataclass
class ExplanationContext:
    """Context for explanation generation."""
    role: str
    seniority: str
    tech_stack: List[str]
    soft_skills: List[str]
    domain: RoleDomain
    key_requirements: List[str]
    leadership_needed: bool
    communication_needed: bool


class RecruiterExplanationEngine:
    """
    Generates recruiter-grade explanations for assessment recommendations.
    
    Uses grounded assessment metadata to create unique, contextual explanations.
    """
    
    # Capability templates by domain
    DOMAIN_CAPABILITY_TEMPLATES = {
        AssessmentDomain.TECHNICAL: [
            "Evaluates {tech} proficiency for {role} responsibilities",
            "Assesses hands-on {tech} coding and problem-solving capability",
            "Measures practical {tech} knowledge critical for {role} success",
            "Tests {tech} implementation skills required in {role} contexts",
            "Verifies core {tech} competencies for {seniority}-level {role} engineering",
            "Benchmarks {tech} expertise against industry standards for {role} candidates",
        ],
        AssessmentDomain.COGNITIVE: [
            "Measures reasoning ability essential for complex {role} problem-solving",
            "Assesses learning agility and mental flexibility for {role} challenges",
            "Evaluates critical thinking capacity needed in {seniority} {role} roles",
            "Tests problem-solving approach relevant to {role} work scenarios",
            "Quantifies cognitive potential for high-complexity {role} tasks",
            "Identifies analytical reasoning skills required for effective {role} performance",
        ],
        AssessmentDomain.PERSONALITY: [
            "Reveals work style preferences affecting {role} team dynamics",
            "Assesses behavioral tendencies in {role} workplace contexts",
            "Measures personality fit for {role} cultural requirements",
            "Evaluates interpersonal approach for {role} collaboration",
            "Profiles behavioral alignment with {role} competency requirements",
            "Maps personality traits to {role} performance success factors",
        ],
        AssessmentDomain.LEADERSHIP: [
            "Assesses leadership readiness for {seniority} {role} responsibilities",
            "Evaluates management capability required in {role} positions",
            "Measures strategic thinking essential for {role} leadership",
            "Tests decision-making approach in {role} contexts",
            "Identifies leadership potential for driving {role} team outcomes",
            "Benchmarks executive presence and strategic influence for {role} leaders",
        ],
        AssessmentDomain.BEHAVIORAL: [
            "Predicts workplace behavior in {role} team environments",
            "Assesses professional conduct expectations for {role}",
            "Evaluates adaptability to {role} workplace demands",
            "Measures resilience under {role} work pressures",
            "Assesses core behavioral competencies for {role} success",
            "Identifies work-style patterns relevant to {role} productivity",
        ],
        AssessmentDomain.COMMUNICATION: [
            "Evaluates communication effectiveness for {role} stakeholder interaction",
            "Assesses clarity in conveying complex {role} concepts",
            "Measures interpersonal communication essential for {role}",
            "Tests presentation capability for {seniority} {role} responsibilities",
            "Verifies communication proficiency for {role} collaboration needs",
            "Assesses influence and persuasion skills required for {role}",
        ],
        AssessmentDomain.ANALYTICAL: [
            "Assesses data analysis capability for {role} decision-making",
            "Evaluates quantitative reasoning required in {role} work",
            "Measures research methodology for {role} problem-solving",
            "Tests analytical thinking in {role} business contexts",
            "Verifies data-driven reasoning skills for {role} performance",
            "Assesses information synthesis capability for {role} roles",
        ],
        AssessmentDomain.SALES: [
            "Evaluates sales aptitude for {role} revenue targets",
            "Assesses customer relationship capability for {role}",
            "Measures deal-making potential in {role} contexts",
            "Tests negotiation skills essential for {role} success",
            "Identifies sales drive and commercial acumen for {role}",
            "Benchmarks revenue generation potential for {role} candidates",
        ],
    }
    
    # Why-it-matters templates
    IMPACT_TEMPLATES = {
        "technical": [
            "Directly impacts code quality and system reliability",
            "Predicts technical problem-solving effectiveness",
            "Indicates implementation capability",
            "Shows debugging and optimization potential",
            "Ensures technical excellence and architectural alignment",
            "Reduces technical debt risk through verified expertise",
        ],
        "cognitive": [
            "Predicts ability to handle complex technical challenges",
            "Indicates capacity for learning new technologies",
            "Shows analytical problem-solving potential",
            "Reveals strategic thinking capability",
            "Ensures high-quality decision making under pressure",
            "Mitigates risk of performance plateaus in evolving roles",
        ],
        "personality": [
            "Predicts cultural fit and team integration",
            "Indicates collaboration style effectiveness",
            "Shows alignment with company values",
            "Reveals potential for long-term retention",
            "Enhances team cohesion and psychological safety",
            "Reduces friction in cross-functional collaboration",
        ],
        "leadership": [
            "Predicts team motivation and development capability",
            "Indicates strategic decision-making quality",
            "Shows organizational influence potential",
            "Reveals executive readiness level",
            "Drives organizational growth through effective leadership",
            "Ensures sustainable team performance and talent development",
        ],
        "behavioral": [
            "Predicts workplace conduct and professionalism",
            "Indicates stress management capability",
            "Shows adaptability to organizational change",
            "Reveals conflict resolution approach",
            "Fosters a positive and productive work environment",
            "Aligns individual behaviors with organizational expectations",
        ],
        "communication": [
            "Predicts stakeholder management effectiveness",
            "Indicates cross-functional collaboration capability",
            "Shows presentation and influence potential",
            "Reveals customer-facing interaction quality",
            "Ensures clear information flow across the organization",
            "Facilitates effective knowledge transfer and alignment",
        ],
        "analytical": [
            "Predicts data-driven decision-making quality",
            "Indicates research and investigation capability",
            "Shows quantitative problem-solving potential",
            "Reveals insights generation effectiveness",
            "Drives evidence-based strategies and operational efficiency",
            "Enhances organizational capability for complex data interpretation",
        ],
        "sales": [
            "Predicts revenue generation capability",
            "Indicates customer acquisition potential",
            "Shows relationship building effectiveness",
            "Reveals competitive drive and resilience",
            "Accelerates sales cycles through verified aptitude",
            "Ensures consistent performance against revenue targets",
        ],
    }
    
    def __init__(self, taxonomy: Optional[AssessmentTaxonomy] = None):
        self.taxonomy = taxonomy or AssessmentTaxonomy()
        self._cache: Dict[str, Dict[str, str]] = {}

    async def generate_explanation(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext,
        factors: Optional[RankingFactors] = None,
    ) -> Dict[str, str]:
        """
        Generate enterprise-grade recruiter reasoning for an assessment (Async).
        """
        # Cache key based on assessment and high-level context
        cache_key = f"{assessment.id}_{context.role}_{context.seniority}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Simulate slight processing (or real LLM call if we were using it here)
            # In our current logic it's deterministic but structured
            exp_context = self._build_explanation_context(context)
            classification = self.taxonomy.get_assessment_classification(assessment.id)
            if not classification:
                classification = self.taxonomy._classify_assessment(assessment)
            
            best_stage = self._determine_best_stage(exp_context, classification, factors)

            # Use awaitable components if needed, or just execute
            matches = self._generate_match_reasoning(assessment, exp_context, classification, factors, best_stage)
            measures = self._generate_measurement_reasoning(assessment, classification, exp_context)
            ranking = self._generate_ranking_reasoning(assessment, factors, exp_context, classification, best_stage)
            use_case = self._generate_use_case_reasoning(assessment, exp_context, classification, best_stage)
            
            result = {
                "why_it_matches": matches,
                "what_it_measures": measures,
                "why_ranked_higher": ranking,
                "ideal_use_case": use_case,
                "best_hiring_stage": best_stage,
            }
            
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Explanation generation error: {e}", exc_info=True)
            return {
                "why_it_matches": f"Directly aligns with {context.role or 'specified'} requirements.",
                "what_it_measures": assessment.description[:100] + "...",
                "why_ranked_higher": "Strong alignment with role seniority and domain.",
                "ideal_use_case": f"Best used for screening {context.role} candidates.",
                "best_hiring_stage": "screening",
            }

    def _generate_match_reasoning(self, assessment, context, classification, factors, stage) -> str:
        """Section 1: Why it matches the recruiter's specific query."""
        role_label = context.role or "this role"
        if factors and factors.skill_overlap > 0.8 and context.tech_stack:
            focus = ", ".join(list(context.tech_stack)[:2])
            return f"Fits this {role_label} because it directly measures {focus} capability that the role profile prioritizes for screening."

        if classification.primary_domain == AssessmentDomain.SALES:
            return f"Fits this {role_label} because it measures sales performance signals such as persuasion and customer-facing effectiveness that matter early in screening."

        if classification.primary_domain == AssessmentDomain.COMMUNICATION:
            return f"Fits this {role_label} because it measures communication signals that influence coordination, stakeholder management, and candidate suitability."

        if classification.primary_domain == AssessmentDomain.PERSONALITY:
            return f"Fits this {role_label} because it measures behavioral style and work preferences that help shortlist candidates for team fit."

        if classification.primary_domain == AssessmentDomain.LEADERSHIP:
            return f"Fits this {role_label} because it measures leadership behaviors relevant to people management and senior responsibility screening."

        if classification.primary_domain == AssessmentDomain.ANALYTICAL:
            return f"Fits this {role_label} because it measures analytical problem solving and decision quality that are useful for recruiter screening."

        if classification.primary_domain == AssessmentDomain.COGNITIVE:
            return f"Fits this {role_label} because it measures learning agility and reasoning ability, which are important when the role needs fast ramp-up."

        if classification.primary_domain == AssessmentDomain.TECHNICAL:
            tech_focus = self._extract_primary_technology(assessment) or "technical"
            return f"Fits this {role_label} because it measures {tech_focus} capability aligned to the role requirements and the assessment catalog metadata."

        return f"Fits this {role_label} because it measures the role-aligned competencies identified in the catalog metadata."

    def _generate_measurement_reasoning(self, assessment, classification, context) -> str:
        """Section 2: What specific capabilities are being tested."""
        capabilities = classification.key_capabilities[:3]
        if capabilities:
            return f"Measures {', '.join(capabilities)} from the catalog metadata, which gives a concrete hiring signal for this role."
        return f"Measures the core capability described in the catalog entry and helps compare candidates at the screening stage for {context.role}."

    def _generate_ranking_reasoning(self, assessment, factors, context, classification, stage) -> str:
        """Section 3: Competitive ranking justification."""
        if not factors:
            return f"Ranked above alternatives because the catalog metadata better matches the {context.role or 'target'} role and is most suitable for {stage} screening."
            
        reasons = []
        if factors.domain_match > 0.8:
            reasons.append("strong domain alignment")
        if factors.skill_overlap > 0.7:
            reasons.append("specific skill coverage")
        if factors.seniority_fit > 0.8:
            reasons.append("seniority fit")
        if classification and classification.primary_domain in {AssessmentDomain.LEADERSHIP, AssessmentDomain.COMMUNICATION, AssessmentDomain.PERSONALITY}:
            reasons.append("better recruiter-stage fit")
            
        if not reasons:
            return f"Ranked higher than alternatives because its catalog signals are more relevant to {context.role or 'the role'} and it fits the {stage} stage better."
            
        return f"Ranked higher than alternatives due to its {' and '.join(reasons[:2])} for this specific hiring context and the {stage} stage."

    def _generate_use_case_reasoning(self, assessment, context, classification, stage) -> str:
        """Section 4: Strategic recruiter advice."""
        if classification.primary_domain == AssessmentDomain.TECHNICAL:
            return f"Best used for {stage} screening of {context.seniority} engineering candidates when hands-on execution matters."
            
        if classification.primary_domain == AssessmentDomain.COGNITIVE:
            return f"Ideal for early {stage} screening to identify candidates with the strongest learning agility and problem-solving potential."
            
        return f"Strategic choice for {stage} screening when you need to compare {context.role} candidates on the role signals described in the catalog metadata."
    
    def _build_explanation_context(self, context: HiringContext) -> ExplanationContext:
        """Build explanation context from hiring context."""
        # Identify key requirements
        key_requirements = []
        
        if context.tech_stack:
            key_requirements.extend(context.tech_stack)
        if context.soft_skills:
            key_requirements.extend(context.soft_skills)
        if context.leadership_needs:
            key_requirements.append("leadership")
        
        # Classify domain
        domain = self.taxonomy.classify_role(
            context.role or "",
            list(context.tech_stack)
        )
        
        return ExplanationContext(
            role=context.role or "this position",
            seniority=context.seniority or "professional",
            tech_stack=list(context.tech_stack),
            soft_skills=list(context.soft_skills),
            domain=domain,
            key_requirements=key_requirements,
            leadership_needed=context.leadership_needs,
            communication_needed="communication" in [s.lower() for s in context.soft_skills]
        )

    def _determine_best_stage(
        self,
        context: ExplanationContext,
        classification: AssessmentClassification,
        factors: Optional[RankingFactors],
    ) -> str:
        if classification.primary_domain in {AssessmentDomain.TECHNICAL, AssessmentDomain.ANALYTICAL, AssessmentDomain.COGNITIVE}:
            return "screening"
        if classification.primary_domain in {AssessmentDomain.LEADERSHIP, AssessmentDomain.PERSONALITY, AssessmentDomain.BEHAVIORAL, AssessmentDomain.COMMUNICATION, AssessmentDomain.SALES}:
            return "shortlist"
        if factors and factors.seniority_fit >= 0.9:
            return "final shortlist"
        return "screening"
    
    def _generate_opening(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext,
        classification: AssessmentClassification
    ) -> str:
        """Generate role-specific opening statement."""
        role_phrase = context.role
        
        # Check for exact tech match
        if context.tech_stack:
            for tech in context.tech_stack:
                if tech.lower() in assessment.name.lower():
                    return f"Directly evaluates {tech} proficiency required for {role_phrase}"
        
        # Domain-specific openings
        if classification.primary_domain == AssessmentDomain.TECHNICAL:
            tech_focus = self._extract_primary_technology(assessment)
            if tech_focus:
                return f"Assesses {tech_focus} capabilities essential for {role_phrase}"
            return f"Technical skills evaluation for {role_phrase} requirements"
        
        elif classification.primary_domain == AssessmentDomain.COGNITIVE:
            return f"Cognitive ability assessment for {context.seniority} {role_phrase} problem-solving"
        
        elif classification.primary_domain == AssessmentDomain.PERSONALITY:
            return f"Personality and work style evaluation for {role_phrase} cultural fit"
        
        elif classification.primary_domain == AssessmentDomain.LEADERSHIP:
            return f"Leadership capability assessment for {role_phrase} responsibilities"
        
        elif classification.primary_domain == AssessmentDomain.COMMUNICATION:
            return f"Communication skills evaluation for {role_phrase} stakeholder interaction"
        
        return f"Assessment for {role_phrase} competency verification"
    
    def _generate_capability_statement(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext,
        classification: AssessmentClassification
    ) -> str:
        """Generate capability-focused statement."""
        domain = classification.primary_domain
        templates = self.DOMAIN_CAPABILITY_TEMPLATES.get(domain, [])
        
        if not templates:
            return ""
        
        # Select the first grounded template for deterministic output.
        template = templates[0]
        
        # Fill placeholders
        tech = context.tech_stack[0] if context.tech_stack else "technical"
        filled = template.format(
            tech=tech,
            role=context.role,
            seniority=context.seniority
        )
        
        return filled
    
    def _generate_impact_statement(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext,
        classification: AssessmentClassification
    ) -> str:
        """Generate 'why it matters' statement."""
        domain_key = classification.primary_domain.value
        templates = self.IMPACT_TEMPLATES.get(domain_key, [])
        
        if not templates:
            return ""
        
        return templates[0]
    
    def _generate_seniority_note(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext
    ) -> str:
        """Generate seniority calibration note if relevant."""
        if not hasattr(assessment, 'seniority_levels'):
            return ""
        
        levels = [s.lower() for s in assessment.seniority_levels]
        target = context.seniority.lower()
        
        if target in levels:
            if target == "senior":
                return "Calibrated for senior-level complexity expectations"
            elif target == "junior":
                return "Appropriate for entry-level candidate assessment"
            else:
                return f"Suitable for {target}-level professional evaluation"
        
        # Mismatch warning
        if "senior" in target and "junior" in levels and "senior" not in levels:
            return "Note: May be below target level for senior role"
        
        return ""
    
    def _extract_primary_technology(self, assessment: AssessmentWithMetadata) -> str:
        """Extract primary technology from assessment name."""
        tech_map = {
            "java": "Java programming",
            "python": "Python development",
            "react": "React frontend",
            "javascript": "JavaScript",
            "data science": "data science",
            "machine learning": "machine learning",
            "sql": "SQL database",
            "aws": "AWS cloud",
            "docker": "containerization",
        }
        
        name_lower = assessment.name.lower()
        for tech, description in tech_map.items():
            if tech in name_lower:
                return description
        
        return ""
    
    def _generate_fallback_explanation(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext
    ) -> str:
        """Generate fallback explanation when specific generation fails."""
        # Use assessment description
        desc = assessment.description
        first_sentence = desc.split(".")[0] if "." in desc else desc
        
        if len(first_sentence) > 100:
            first_sentence = first_sentence[:97] + "..."
        
        return f"{first_sentence} for {context.role}"
    
    def _clean_explanation(self, explanation: str) -> str:
        """Clean up explanation text."""
        # Remove duplicate periods
        explanation = explanation.replace("..", ".")
        
        # Ensure proper spacing after periods
        explanation = explanation.replace(". ", ".")
        explanation = explanation.replace(".", ". ")
        
        # Clean up spaces
        explanation = " ".join(explanation.split())
        
        # Capitalize first letter
        if explanation:
            explanation = explanation[0].upper() + explanation[1:]
        
        return explanation.strip()
    
    def generate_comparison_reasoning(
        self,
        assessment_1: AssessmentWithMetadata,
        assessment_2: AssessmentWithMetadata,
        context: HiringContext
    ) -> Dict[str, str]:
        """
        Generate recruiter-grade comparison between two assessments.
        
        Returns structured comparison with recruiter reasoning.
        """
        exp_context = self._build_explanation_context(context)
        
        # Get classifications
        class_1 = self.taxonomy.get_assessment_classification(assessment_1.id)
        class_2 = self.taxonomy.get_assessment_classification(assessment_2.id)
        
        comparison = {
            "primary_difference": self._compare_primary_difference(
                assessment_1, assessment_2, class_1, class_2
            ),
            "when_to_use_1": self._generate_when_to_use(
                assessment_1, exp_context, class_1
            ),
            "when_to_use_2": self._generate_when_to_use(
                assessment_2, exp_context, class_2
            ),
            "recruiter_recommendation": self._generate_comparison_recommendation(
                assessment_1, assessment_2, exp_context, class_1, class_2
            )
        }
        
        return comparison
    
    def _compare_primary_difference(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        c1: Optional[AssessmentClassification],
        c2: Optional[AssessmentClassification]
    ) -> str:
        """Generate primary difference statement."""
        if not c1 or not c2:
            return f"{a1.name} and {a2.name} assess different competencies"
        
        if c1.primary_domain != c2.primary_domain:
            return (
                f"{a1.name} focuses on {c1.primary_domain.value} capabilities, "
                f"while {a2.name} measures {c2.primary_domain.value}"
            )
        
        return (
            f"Both assess {c1.primary_domain.value} but {a1.name} emphasizes "
            f"{', '.join(c1.key_capabilities[:2])} whereas "
            f"{a2.name} covers {', '.join(c2.key_capabilities[:2])}"
        )
    
    def _generate_when_to_use(
        self,
        assessment: AssessmentWithMetadata,
        context: ExplanationContext,
        classification: Optional[AssessmentClassification]
    ) -> str:
        """Generate 'when to use' recommendation."""
        if not classification:
            return f"Use {assessment.name} for general competency assessment"
        
        domain = classification.primary_domain
        
        if domain == AssessmentDomain.TECHNICAL:
            return f"Use when verifying hands-on {context.tech_stack[0] if context.tech_stack else 'technical'} skills is critical"
        
        elif domain == AssessmentDomain.COGNITIVE:
            return f"Use for {context.seniority}-level problem-solving capability screening"
        
        elif domain == AssessmentDomain.PERSONALITY:
            return f"Use when cultural fit and team dynamics are priority concerns"
        
        elif domain == AssessmentDomain.LEADERSHIP:
            return f"Use for leadership readiness evaluation in {context.role} contexts"
        
        return f"Use {assessment.name} when {classification.ideal_use_cases[0]} is needed"
    
    def _generate_comparison_recommendation(
        self,
        a1: AssessmentWithMetadata,
        a2: AssessmentWithMetadata,
        context: ExplanationContext,
        c1: Optional[AssessmentClassification],
        c2: Optional[AssessmentClassification]
    ) -> str:
        """Generate recruiter recommendation for which to use."""
        if not c1 or not c2:
            return f"Both {a1.name} and {a2.name} are valid options - select based on specific competency priorities"
        
        # Get priorities
        priorities = self.taxonomy.get_domain_priorities(context.domain)
        p1 = priorities.get(c1.primary_domain, 0)
        p2 = priorities.get(c2.primary_domain, 0)
        
        if p1 > p2 + 0.2:
            return f"Recommend {a1.name} - higher priority for {context.role} requirements"
        elif p2 > p1 + 0.2:
            return f"Recommend {a2.name} - better alignment with {context.role} needs"
        else:
            return f"Both are viable - consider administering together for comprehensive evaluation"


# Convenience function for backward compatibility
def generate_explanation(
    assessment: AssessmentWithMetadata,
    context: HiringContext,
    taxonomy: Optional[AssessmentTaxonomy] = None
) -> str:
    """Generate recruiter-grade explanation."""
    engine = RecruiterExplanationEngine(taxonomy)
    return engine.generate_explanation(assessment, context)
