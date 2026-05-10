"""
Ranking engine - scores and ranks assessments by relevance.
Ensures best recommendations are returned first.
"""

from typing import List, Dict
from app.models.assessment import AssessmentWithMetadata
from app.services.conversation_analyzer import HiringContext
from app.logging.logger import get_logger

logger = get_logger("ranker")


class RecommendationRanker:
    """
    Scores and ranks assessments based on hiring context.
    Uses multiple signals for robust ranking.
    """

    # Configurable weights
    WEIGHTS = {
        "hybrid_retrieval": 0.40,  # Base retrieval score
        "role_fit": 0.15,           # How well matches stated role
        "seniority_fit": 0.15,      # Seniority alignment
        "skill_overlap": 0.15,      # Required skills match
        "communication_boost": 0.10, # Communication needs boost
        "leadership_boost": 0.05,   # Leadership needs boost
    }

    def rank(
        self,
        retrieved_results: List[Dict],
        context: HiringContext,
        catalog_assessments: Dict[str, AssessmentWithMetadata],
    ) -> List[Dict]:
        """
        Rank retrieved results by relevance to context.

        Args:
            retrieved_results: Results from hybrid retrieval
            context: Hiring context
            catalog_assessments: Dict of ID → Assessment

        Returns:
            Ranked results with final scores
        """

        # Score each result
        scored_results = []

        for result in retrieved_results:
            assessment_id = result["id"]
            assessment = catalog_assessments.get(assessment_id)

            if not assessment:
                logger.warning(f"Assessment {assessment_id} not found in catalog")
                continue

            # Calculate score components
            score_breakdown = {}

            # 1. Hybrid retrieval score (0-1)
            score_breakdown["hybrid"] = result.get("hybrid_score", 0.5)

            # 2. Role fit
            score_breakdown["role_fit"] = self._score_role_fit(assessment, context)

            # 3. Seniority fit
            score_breakdown["seniority_fit"] = self._score_seniority_fit(assessment, context)

            # 4. Skill overlap
            score_breakdown["skill_overlap"] = self._score_skill_overlap(assessment, context)

            # 5. Communication needs
            score_breakdown["communication_boost"] = self._score_communication_needs(assessment, context)

            # 6. Leadership needs
            score_breakdown["leadership_boost"] = self._score_leadership_needs(assessment, context)

            # Weighted final score
            final_score = (
                self.WEIGHTS["hybrid_retrieval"] * score_breakdown["hybrid"]
                + self.WEIGHTS["role_fit"] * score_breakdown["role_fit"]
                + self.WEIGHTS["seniority_fit"] * score_breakdown["seniority_fit"]
                + self.WEIGHTS["skill_overlap"] * score_breakdown["skill_overlap"]
                + self.WEIGHTS["communication_boost"] * score_breakdown["communication_boost"]
                + self.WEIGHTS["leadership_boost"] * score_breakdown["leadership_boost"]
            )

            scored_results.append(
                {
                    **result,
                    "score_breakdown": score_breakdown,
                    "final_score": min(final_score, 1.0),  # Cap at 1.0
                }
            )

        # Sort by final score
        ranked = sorted(scored_results, key=lambda x: x["final_score"], reverse=True)

        logger.info(f"Ranked {len(ranked)} results")
        for i, r in enumerate(ranked[:5]):
            logger.debug(f"  {i+1}. {r['name']} (score: {r['final_score']:.3f})")

        return ranked

    def _score_role_fit(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """
        Score how well assessment fits the stated role.
        1.0 = perfect fit, 0.0 = no fit
        """

        if not context.role and not context.domain:
            return 0.5  # Neutral if no role specified

        role_lower = (context.role or "").lower()

        # Check if assessment is recommended for similar roles
        for recommended_role in assessment.recommended_roles:
            recommended_lower = recommended_role.lower()

            # Exact match
            if role_lower == recommended_lower:
                return 1.0

            # Partial match
            if any(part in recommended_lower for part in role_lower.split()):
                return 0.8

        # Check domain (if specified)
        if context.domain:
            domain_lower = context.domain.lower()
            if any(domain_lower in r.lower() for r in assessment.recommended_roles):
                return 0.7

        # No match
        return 0.3

    def _score_seniority_fit(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """
        Score seniority alignment.
        1.0 = exact match, 0.5 = partial, 0.0 = no match
        """

        if not context.seniority:
            return 0.5  # Neutral

        seniority_lower = context.seniority.lower()

        # Check if assessment supports this seniority
        for level in assessment.seniority_levels:
            if level.lower() == seniority_lower:
                return 1.0

        # Partial match (e.g., mid matches both mid and senior)
        if any(seniority_lower in l.lower() or l.lower() in seniority_lower
               for l in assessment.seniority_levels):
            return 0.7

        return 0.3

    def _score_skill_overlap(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """
        Score how many required skills this assessment covers.
        More skills = higher score
        """

        all_required_skills = context.soft_skills | context.technical_skills | context.cognitive_skills

        if not all_required_skills:
            return 0.5  # Neutral if no skills specified

        assessment_skills = {s.lower() for s in assessment.skills}
        required_lower = {s.lower() for s in all_required_skills}

        # Count exact matches
        matches = sum(
            1
            for req_skill in required_lower
            if any(req_skill in assess_skill or assess_skill in req_skill
                   for assess_skill in assessment_skills)
        )

        # Score based on ratio
        ratio = matches / len(all_required_skills)
        return min(ratio, 1.0)

    def _score_communication_needs(
        self, assessment: AssessmentWithMetadata, context: HiringContext
    ) -> float:
        """Boost score if communication is needed and assessment measures it."""

        if "communication" not in context.soft_skills:
            return 0.0

        if assessment.communication_focus:
            return 1.0  # Assessment explicitly focuses on communication
        elif "communication" in {s.lower() for s in assessment.skills}:
            return 0.7  # Assessment mentions communication
        else:
            return 0.3  # Assessment might touch on it

    def _score_leadership_needs(
        self, assessment: AssessmentWithMetadata, context: HiringContext
    ) -> float:
        """Boost score if leadership is needed and assessment measures it."""

        if not context.leadership_needs:
            return 0.0

        if assessment.leadership_focus:
            return 1.0  # Assessment explicitly focuses on leadership
        elif "leadership" in {s.lower() for s in assessment.skills}:
            return 0.7  # Assessment mentions leadership
        else:
            return 0.3  # Assessment might touch on it

    def get_top_recommendations(
        self, ranked_results: List[Dict], top_k: int = 10
    ) -> List[Dict]:
        """
        Extract top-k recommendations in format for API response.

        Returns:
            List of {name, url, test_type}
        """

        recommendations = []
        for result in ranked_results[:top_k]:
            recommendations.append(
                {
                    "name": result["name"],
                    "url": result["url"],
                    "test_type": result["test_type"],
                }
            )

        return recommendations

    def explain_ranking(self, ranked_results: List[Dict], top_n: int = 3) -> str:
        """
        Generate human-readable explanation of ranking.
        Useful for debugging and transparency.
        """

        lines = ["Ranking Explanation:\n"]

        for i, result in enumerate(ranked_results[:top_n]):
            score_breakdown = result.get("score_breakdown", {})
            lines.append(f"{i+1}. {result['name']} (score: {result['final_score']:.2f})")

            if score_breakdown:
                lines.append(f"   - Hybrid retrieval: {score_breakdown.get('hybrid', 0):.2f}")
                lines.append(f"   - Role fit: {score_breakdown.get('role_fit', 0):.2f}")
                lines.append(f"   - Seniority fit: {score_breakdown.get('seniority_fit', 0):.2f}")
                lines.append(f"   - Skill overlap: {score_breakdown.get('skill_overlap', 0):.2f}")

        return "\n".join(lines)
