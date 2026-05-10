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
        """
        scored_results = []

        for result in retrieved_results:
            assessment_id = result["id"]
            assessment = catalog_assessments.get(assessment_id)

            if not assessment:
                logger.warning(f"Assessment {assessment_id} not found in catalog")
                continue

            # Calculate score components
            score_breakdown = {}

            # 1. Hybrid retrieval score (0-1) - This already includes semantic + keyword
            score_breakdown["hybrid"] = result.get("hybrid_score", 0.5)

            # 2. Role fit (Weighted by domain relevance)
            score_breakdown["role_fit"] = self._score_role_fit(assessment, context)

            # 3. Seniority fit (With mismatch penalties)
            score_breakdown["seniority_fit"] = self._score_seniority_fit(assessment, context)

            # 4. Skill overlap (Soft + Tech + Cognitive)
            score_breakdown["skill_overlap"] = self._score_skill_overlap(assessment, context)

            # 5. Domain specific boosts
            score_breakdown["communication_boost"] = self._score_communication_needs(assessment, context)
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

            # Apply a small natural jitter (0.98 - 1.02) to avoid identical scores
            import random
            jitter = 0.98 + (random.random() * 0.04)
            final_score = min(final_score * jitter, 1.0)

            # Map score to label
            label = self._get_confidence_label(final_score)

            scored_results.append(
                {
                    **result,
                    "score_breakdown": score_breakdown,
                    "score": final_score,
                    "match_label": label,
                    "category": assessment.category if hasattr(assessment, "category") else self._infer_category(assessment),
                }
            )

        # Sort by final score
        ranked = sorted(scored_results, key=lambda x: x["score"], reverse=True)

        logger.info(f"Ranked {len(ranked)} results with dynamic scoring")
        return ranked

    def _get_confidence_label(self, score: float) -> str:
        """Map numeric score to human-readable confidence label."""
        if score >= 0.90: return "Exceptional Match"
        if score >= 0.80: return "Strong Match"
        if score >= 0.70: return "Good Match"
        return "Moderate Match"

    def _infer_category(self, assessment: AssessmentWithMetadata) -> str:
        """Infer category if missing."""
        tt = assessment.test_type
        if tt == "P": return "Personality"
        if tt == "A": return "Ability / Cognitive"
        if tt == "K": return "Technical Knowledge"
        return "General Assessment"

    def _score_role_fit(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """
        Score how well assessment fits the stated role.
        """
        if not context.role and not context.domain:
            return 0.6  # Default

        role_lower = (context.role or "").lower()
        domain_lower = (context.domain or "").lower()

        max_fit = 0.3 # Base level

        # Check recommended roles
        for rec_role in assessment.recommended_roles:
            rec_lower = rec_role.lower()
            if role_lower == rec_lower:
                max_fit = max(max_fit, 1.0)
            elif any(part in rec_lower for part in role_lower.split() if len(part) > 3):
                max_fit = max(max_fit, 0.8)
            elif domain_lower and domain_lower in rec_lower:
                max_fit = max(max_fit, 0.7)

        return max_fit

    def _score_seniority_fit(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """
        Score seniority alignment with penalties for mismatch.
        """
        if not context.seniority:
            return 0.7  # Default

        target = context.seniority.lower()
        supported = [s.lower() for s in assessment.seniority_levels]

        if target in supported:
            return 1.0
        
        # Penalize if it's a junior test for a senior role
        if "senior" in target and "junior" in supported and "senior" not in supported:
            return 0.2
        
        # Partial overlap
        if any(target in s or s in target for s in supported):
            return 0.6

        return 0.4

    def _score_skill_overlap(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        """Score skill overlap with higher weight for specifically requested skills."""
        req_skills = context.technical_skills | context.soft_skills
        if not req_skills:
            return 0.6

        assess_skills = {s.lower() for s in assessment.skills}
        matches = 0
        for s in req_skills:
            s_lower = s.lower()
            if any(s_lower in a or a in s_lower for a in assess_skills):
                matches += 1
        
        ratio = matches / len(req_skills)
        return 0.3 + (ratio * 0.7) # Scale 0.3 to 1.0

    def _score_communication_needs(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        if "communication" not in [s.lower() for s in context.soft_skills]:
            return 0.5
        return 1.0 if assessment.communication_focus else 0.4

    def _score_leadership_needs(self, assessment: AssessmentWithMetadata, context: HiringContext) -> float:
        if not context.leadership_needs:
            return 0.5
        return 1.0 if assessment.leadership_focus else 0.4

    def get_top_recommendations(
        self, ranked_results: List[Dict], top_k: int = 10
    ) -> List[Dict]:
        """
        Extract top-k recommendations in format for API response.
        Now includes score and match_label.
        """
        recommendations = []
        for result in ranked_results[:top_k]:
            recommendations.append(
                {
                    "id": result["id"],
                    "name": result["name"],
                    "url": result["url"],
                    "test_type": result["test_type"],
                    "score": result.get("score", 0.85),
                    "match_label": result.get("match_label", "Strong Match"),
                    "category": result.get("category", "Assessment"),
                    "explanation": result.get("explanation", ""), # Placeholder for LLM to fill
                    "score_breakdown": result.get("score_breakdown", {})
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
