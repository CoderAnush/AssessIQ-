"""
Recommendation intelligence layer - generates explanations and confidence scores.
Makes recommendations more trustworthy and explainable for recruiters.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class RecommendationIntelligence:
    """Generates explanation and confidence for each recommendation."""

    assessment_name: str
    assessment_id: str
    url: str
    test_type: str
    hybrid_score: float  # 0-1 from retriever
    role_fit_score: float  # 0-1 from ranker
    seniority_fit_score: float  # 0-1 from ranker
    skill_overlap_score: float  # 0-1 from ranker
    communication_boost: float  # 0-1
    leadership_boost: float  # 0-1
    final_score: float  # 0-1 weighted sum
    rank_position: int  # 1st, 2nd, etc.

    def calculate_confidence(self) -> Tuple[float, str]:
        """
        Calculate confidence 0-100 with reasoning.

        Returns:
            (confidence_percentage, confidence_level)
        """

        # Weighted confidence factors
        confidence = (
            self.hybrid_score * 0.35 +  # Retrieval quality
            self.role_fit_score * 0.25 +  # Role alignment
            self.seniority_fit_score * 0.15 +  # Seniority match
            self.skill_overlap_score * 0.15 +  # Skill coverage
            (self.communication_boost + self.leadership_boost) * 0.1  # Special skills
        )

        confidence_pct = int(confidence * 100)

        # Confidence level
        if confidence_pct >= 90:
            level = "Excellent"
        elif confidence_pct >= 75:
            level = "Strong"
        elif confidence_pct >= 60:
            level = "Good"
        elif confidence_pct >= 45:
            level = "Fair"
        else:
            level = "Weak"

        return confidence_pct, level

    def generate_explanation(self, context_str: str) -> str:
        """
        Generate grounded explanation for this recommendation.

        Uses ranking signals and context to build human-readable reasoning.

        Args:
            context_str: String representation of extracted hiring context

        Returns:
            Explanation text
        """

        confidence_pct, confidence_level = self.calculate_confidence()

        # Build explanation from signals
        reasons = []

        # Role fit
        if self.role_fit_score > 0.7:
            reasons.append("Strong role fit based on assessment purpose")
        elif self.role_fit_score > 0.5:
            reasons.append("Relevant to the hiring role")

        # Seniority fit
        if self.seniority_fit_score > 0.7:
            reasons.append("Well-matched to seniority level")

        # Skill overlap
        if self.skill_overlap_score > 0.7:
            reasons.append("Comprehensive skill coverage")
        elif self.skill_overlap_score > 0.5:
            reasons.append("Covers key required skills")

        # Special skills
        if self.communication_boost > 0.5:
            reasons.append("Measures communication effectiveness")

        if self.leadership_boost > 0.5:
            reasons.append("Assesses leadership capability")

        # Retrieval quality
        if self.hybrid_score > 0.8:
            reasons.append("Strong semantic match to requirements")

        # Test type context
        if self.test_type == "P":
            reasons.append("Personality assessment for culture fit")
        elif self.test_type == "A":
            reasons.append("Ability assessment for capability screening")
        elif self.test_type == "K":
            reasons.append("Knowledge assessment for technical proficiency")

        # Build final explanation
        if reasons:
            explanation = ". ".join(reasons) + "."
        else:
            explanation = "Matched to your hiring requirements."

        return explanation

    def get_key_signals(self) -> Dict[str, float]:
        """Get the key signals that drove this recommendation."""

        return {
            "semantic_match": round(self.hybrid_score, 2),
            "role_alignment": round(self.role_fit_score, 2),
            "seniority_match": round(self.seniority_fit_score, 2),
            "skill_overlap": round(self.skill_overlap_score, 2),
            "communication_fit": round(self.communication_boost, 2),
            "leadership_fit": round(self.leadership_boost, 2),
        }

    def to_recommendation_dict(self) -> Dict:
        """Convert to recommendation dict for API response."""

        confidence_pct, confidence_level = self.calculate_confidence()

        return {
            "name": self.assessment_name,
            "url": self.url,
            "test_type": self.test_type,
            "confidence": {
                "percentage": confidence_pct,
                "level": confidence_level,
            },
            "explanation": self.generate_explanation(""),
            "rank": self.rank_position,
            "key_signals": self.get_key_signals(),
        }


class ExplanationGenerator:
    """Generates human-readable explanations for recommendations."""

    # Assessment type descriptions
    ASSESSMENT_PURPOSES = {
        "opq32r": "Measures personality traits and work styles",
        "16pf": "Comprehensive personality and reasoning assessment",
        "gsa": "General ability assessment (numerical, verbal, logical)",
        "java8": "Technical proficiency in Java 8",
        "verbal": "Verbal reasoning and comprehension",
        "numerical": "Numerical reasoning capability",
        "leadership7": "Leadership and decision-making competencies",
    }

    ROLE_ASSESSMENT_MAPPING = {
        "developer": ["Java8", "GSA", "Verbal", "Numerical"],
        "manager": ["OPQ32r", "16PF", "Leadership7"],
        "analyst": ["GSA", "Numerical", "Verbal"],
        "executive": ["OPQ32r", "Leadership7", "16PF"],
    }

    @staticmethod
    def generate_comparison_explanation(
        assessment1: Dict, assessment2: Dict
    ) -> str:
        """
        Generate comparison explanation between two assessments.

        Args:
            assessment1: First assessment data
            assessment2: Second assessment data

        Returns:
            Comparison explanation
        """

        name1 = assessment1.get("name", "Assessment 1")
        name2 = assessment2.get("name", "Assessment 2")

        type1 = assessment1.get("test_type", "")
        type2 = assessment2.get("test_type", "")

        # Build comparison based on types
        explanation = f"**{name1}** vs **{name2}**\n\n"

        if type1 == type2:
            explanation += "These are both personality assessments measuring different aspects.\n"
        elif type1 == "P":
            explanation += f"{name1} focuses on personality traits, while {name2} measures "
            if type2 == "A":
                explanation += "cognitive abilities.\n"
            else:
                explanation += "technical knowledge.\n"
        elif type2 == "P":
            explanation += f"{name2} focuses on personality traits, while {name1} measures "
            if type1 == "A":
                explanation += "cognitive abilities.\n"
            else:
                explanation += "technical knowledge.\n"

        explanation += f"\n**Use {name1} when**: You need to assess "
        if type1 == "P":
            explanation += "personality fit and work style preferences.\n"
        elif type1 == "A":
            explanation += "cognitive abilities and reasoning.\n"
        else:
            explanation += "technical proficiency.\n"

        explanation += f"\n**Use {name2} when**: You need to assess "
        if type2 == "P":
            explanation += "personality fit and work style preferences.\n"
        elif type2 == "A":
            explanation += "cognitive abilities and reasoning.\n"
        else:
            explanation += "technical proficiency.\n"

        return explanation

    @staticmethod
    def generate_refinement_explanation(
        original_count: int, new_count: int, added_assessments: List[str]
    ) -> str:
        """
        Explain how recommendations changed after refinement.

        Args:
            original_count: Original recommendation count
            new_count: New recommendation count
            added_assessments: Newly added assessment names

        Returns:
            Explanation of changes
        """

        if new_count > original_count:
            change = new_count - original_count
            return f"Added {change} assessment{'s' if change > 1 else ''} to the recommendation: {', '.join(added_assessments)}."
        elif new_count < original_count:
            change = original_count - new_count
            return f"Refined recommendations to focus on {new_count} most relevant assessments."
        else:
            return "Updated recommendations based on your input."

    @staticmethod
    def generate_retrieval_summary(
        retrieved_count: int, recommended_count: int, context_sufficiency: float
    ) -> str:
        """
        Generate summary of retrieval process for transparency.

        Args:
            retrieved_count: Total assessed
            recommended_count: Recommended
            context_sufficiency: Confidence in recommendations (0-1)

        Returns:
            Summary for user
        """

        sufficiency_pct = int(context_sufficiency * 100)

        if sufficiency_pct >= 90:
            confidence = "very confident"
        elif sufficiency_pct >= 75:
            confidence = "confident"
        elif sufficiency_pct >= 60:
            confidence = "moderately confident"
        else:
            confidence = "not entirely confident"

        return (
            f"Searched {retrieved_count} assessments from the SHL catalog. "
            f"Recommending top {recommended_count} match{'es' if recommended_count > 1 else ''}. "
            f"We're {confidence} in these recommendations based on the information provided."
        )
