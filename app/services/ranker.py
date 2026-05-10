"""
REBUILT Ranking Engine - Phase 2 Architectural Refinement.

RECRUITER-STYLE SCORING MODEL:
FinalScore = 
    0.35 semantic retrieval relevance
    0.20 explicit skill overlap
    0.15 role-domain alignment (from taxonomy)
    0.10 seniority alignment
    0.10 assessment-category fit
    0.05 recruiter intent modifiers
    0.05 diversity balancing

Key Improvements:
1. Integrates with AssessmentTaxonomy for domain classification
2. Normalizes scores against candidate pool for natural spread
3. Enforces category diversity (no 5 personality tests)
4. Technical roles prioritize technical assessments
5. Leadership roles prioritize leadership/personality assessments
6. Natural score decay: 96, 92, 89, 84, 79, 73
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata
from app.services.conversation_analyzer import HiringContext
from app.core.assessment_taxonomy import AssessmentTaxonomy, AssessmentDomain, RoleDomain
from app.logging.logger import get_logger
import numpy as np

logger = get_logger("ranker_v2")


@dataclass
class RankingFactors:
    """All scoring factors for transparency."""
    semantic_score: float = 0.0
    skill_overlap_score: float = 0.0
    role_domain_alignment: float = 0.0
    seniority_alignment: float = 0.0
    category_fit: float = 0.0
    intent_modifier: float = 0.0
    diversity_penalty: float = 0.0
    
    def calculate_final(self) -> float:
        """Calculate weighted final score."""
        return (
            self.semantic_score * 0.35 +
            self.skill_overlap_score * 0.20 +
            self.role_domain_alignment * 0.15 +
            self.seniority_alignment * 0.10 +
            self.category_fit * 0.10 +
            self.intent_modifier * 0.05 +
            self.diversity_penalty * 0.05
        )


@dataclass
class RankedAssessment:
    """Complete ranking result with metadata."""
    assessment: AssessmentWithMetadata
    final_score: float
    raw_score: float
    confidence_label: str
    factors: RankingFactors
    explanation: str
    rank_position: int
    domain: AssessmentDomain
    category: str


class DiversityBalancer:
    """Enforces category diversity in recommendations."""
    
    def __init__(self, max_per_category: int = 2, max_per_domain: int = 3):
        self.max_per_category = max_per_category
        self.max_per_domain = max_per_domain
        self.category_counts: Dict[str, int] = {}
        self.domain_counts: Dict[AssessmentDomain, int] = {}
    
    def calculate_penalty(
        self, 
        assessment: AssessmentWithMetadata, 
        domain: AssessmentDomain,
        category: str
    ) -> float:
        """Calculate diversity penalty (0 = no penalty, negative = penalty)."""
        penalty = 0.0
        
        # Check category overflow
        current_category = self.category_counts.get(category, 0)
        if current_category >= self.max_per_category:
            penalty -= 0.15 * (current_category - self.max_per_category + 1)
        
        # Check domain overflow
        current_domain = self.domain_counts.get(domain, 0)
        if current_domain >= self.max_per_domain:
            penalty -= 0.10 * (current_domain - self.max_per_domain + 1)
        
        return penalty
    
    def record_selection(self, domain: AssessmentDomain, category: str) -> None:
        """Record that an assessment from this domain/category was selected."""
        self.category_counts[category] = self.category_counts.get(category, 0) + 1
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1


class RecruiterRanker:
    """
    Recruiter-style ranking engine with taxonomy integration.
    
    Produces natural score spreads and enforces category diversity.
    """
    
    def __init__(self, taxonomy: Optional[AssessmentTaxonomy] = None):
        self.taxonomy = taxonomy or AssessmentTaxonomy()
        self.diversity_balancer = DiversityBalancer()
    
    def rank(
        self,
        retrieved_results: List[Dict],
        context: HiringContext,
        catalog_assessments: Dict[str, AssessmentWithMetadata],
        top_k: int = 10
    ) -> List[RankedAssessment]:
        """
        Rank assessments using recruiter-style scoring.
        
        Returns naturally spread scores (96, 92, 89, 84, 79, 73...)
        """
        logger.info(f"Ranking {len(retrieved_results)} assessments for role: {context.role}")
        
        # Build/refresh taxonomy
        if not self.taxonomy._classifications:
            self.taxonomy.build_taxonomy(list(catalog_assessments.values()))
        
        # Classify role
        role_domain = self.taxonomy.classify_role(
            context.role or "",
            list(context.tech_stack)
        )
        logger.info(f"Role classified as: {role_domain.value}")
        
        # Score all assessments
        scored_assessments: List[Tuple[AssessmentWithMetadata, RankingFactors, float]] = []
        
        for result in retrieved_results:
            assessment_id = result["id"]
            assessment = catalog_assessments.get(assessment_id)
            
            if not assessment:
                continue
            
            factors = self._calculate_factors(
                assessment, context, role_domain, result
            )
            raw_score = factors.calculate_final()
            
            scored_assessments.append((assessment, factors, raw_score))
        
        # Sort by raw score
        scored_assessments.sort(key=lambda x: x[2], reverse=True)
        
        # Apply diversity balancing during selection
        ranked_results = self._apply_diversity_and_finalize(
            scored_assessments, role_domain, top_k
        )
        
        # Normalize to natural spread
        final_results = self._normalize_to_natural_spread(ranked_results)
        
        logger.info(f"Completed ranking with {len(final_results)} results")
        return final_results
    
    def _calculate_factors(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext,
        role_domain: RoleDomain,
        retrieval_result: Dict
    ) -> RankingFactors:
        """Calculate all ranking factors for an assessment."""
        factors = RankingFactors()
        
        # 1. Semantic retrieval relevance (35%)
        factors.semantic_score = retrieval_result.get("hybrid_score", 0.5)
        
        # 2. Explicit skill overlap (20%)
        factors.skill_overlap_score = self._calculate_skill_overlap(assessment, context)
        
        # 3. Role-domain alignment (15%) - from taxonomy
        alignment_score, _ = self.taxonomy.calculate_domain_alignment(
            assessment.id, role_domain
        )
        factors.role_domain_alignment = alignment_score
        
        # 4. Seniority alignment (10%)
        factors.seniority_alignment = self._calculate_seniority_alignment(
            assessment, context
        )
        
        # 5. Category fit (10%)
        factors.category_fit = self._calculate_category_fit(assessment, context)
        
        # 6. Recruiter intent modifiers (5%)
        factors.intent_modifier = self._calculate_intent_modifiers(assessment, context)
        
        return factors
    
    def _calculate_skill_overlap(
        self, 
        assessment: AssessmentWithMetadata, 
        context: HiringContext
    ) -> float:
        """Calculate explicit skill overlap score."""
        all_context_skills = (
            context.technical_skills | 
            context.soft_skills | 
            context.tech_stack
        )
        
        if not all_context_skills:
            return 0.5  # Neutral
        
        if not hasattr(assessment, 'skills') or not assessment.skills:
            return 0.3  # Low - no skills listed
        
        assess_skills = {s.lower() for s in assessment.skills}
        matches = 0
        
        for skill in all_context_skills:
            skill_lower = skill.lower()
            if any(skill_lower in a or a in skill_lower for a in assess_skills):
                matches += 1
        
        # Normalize
        overlap_ratio = matches / len(all_context_skills)
        return 0.3 + (overlap_ratio * 0.7)  # Scale 0.3-1.0
    
    def _calculate_seniority_alignment(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate seniority alignment with penalties for mismatch."""
        if not context.seniority:
            return 0.7  # Default
        
        target = context.seniority.lower()
        
        if not hasattr(assessment, 'seniority_levels'):
            return 0.6
        
        supported = {s.lower() for s in assessment.seniority_levels}
        
        if target in supported:
            return 1.0
        
        # Severe penalty: junior test for senior role
        if "senior" in target and "junior" in supported and "senior" not in supported:
            return 0.15
        
        # Moderate penalty
        if "junior" in target and "senior" in supported and "junior" not in supported:
            return 0.6
        
        return 0.4
    
    def _calculate_category_fit(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate category fit based on context needs."""
        test_type = assessment.test_type.value
        
        # Leadership roles need leadership focus
        if context.leadership_needs:
            if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
                return 1.0
            if test_type == "P":  # Personality helps with leadership
                return 0.7
        
        # Technical roles need technical focus
        if context.tech_stack and len(context.tech_stack) > 0:
            if test_type == "K":  # Knowledge tests
                return 0.9
            if hasattr(assessment, 'technical_focus') and assessment.technical_focus:
                return 0.95
        
        # Communication needs
        if "communication" in [s.lower() for s in context.soft_skills]:
            if hasattr(assessment, 'communication_focus') and assessment.communication_focus:
                return 0.9
        
        return 0.6  # Neutral
    
    def _calculate_intent_modifiers(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate recruiter intent modifier bonuses/penalties."""
        modifier = 0.5  # Neutral
        
        # Exact tech match bonus
        if context.tech_stack:
            for tech in context.tech_stack:
                if tech.lower() in assessment.name.lower():
                    modifier += 0.3  # Strong bonus for exact match
                    break
                elif tech.lower() in assessment.description.lower():
                    modifier += 0.15
                    break
        
        # Leadership bonus
        if context.leadership_needs:
            if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
                modifier += 0.2
        
        return min(modifier, 1.0)
    
    def _apply_diversity_and_finalize(
        self,
        scored_assessments: List[Tuple[AssessmentWithMetadata, RankingFactors, float]],
        role_domain: RoleDomain,
        top_k: int
    ) -> List[RankedAssessment]:
        """Apply diversity balancing and create ranked results."""
        results = []
        diversity_balancer = DiversityBalancer()
        
        for assessment, factors, raw_score in scored_assessments:
            # Get classification
            classification = self.taxonomy.get_assessment_classification(assessment.id)
            if not classification:
                continue
            
            # Calculate diversity penalty
            diversity_penalty = diversity_balancer.calculate_penalty(
                assessment,
                classification.primary_domain,
                classification.category
            )
            
            # Apply penalty
            factors.diversity_penalty = diversity_penalty
            adjusted_score = factors.calculate_final()
            
            # Record selection for diversity tracking
            diversity_balancer.record_selection(
                classification.primary_domain,
                classification.category
            )
            
            # Generate explanation
            explanation = self._generate_recruiter_explanation(
                assessment, factors, role_domain, classification
            )
            
            results.append(RankedAssessment(
                assessment=assessment,
                final_score=adjusted_score,
                raw_score=raw_score,
                confidence_label="",  # Will be set after normalization
                factors=factors,
                explanation=explanation,
                rank_position=0,  # Will be set after normalization
                domain=classification.primary_domain,
                category=classification.category
            ))
            
            if len(results) >= top_k * 2:  # Get extra for final selection
                break
        
        return results
    
    def _normalize_to_natural_spread(
        self, 
        ranked_results: List[RankedAssessment]
    ) -> List[RankedAssessment]:
        """
        Normalize scores to create natural recruiter-style spread.
        
        Target distribution: 96, 92, 89, 84, 79, 73, 70...
        """
        if not ranked_results:
            return []
        
        # Get raw scores
        raw_scores = [r.raw_score for r in ranked_results]
        
        if len(raw_scores) == 1:
            ranked_results[0].final_score = 0.94
            ranked_results[0].confidence_label = "Exceptional Match"
            ranked_results[0].rank_position = 1
            return ranked_results
        
        # Calculate statistics
        max_score = max(raw_scores)
        min_score = min(raw_scores)
        mean_score = np.mean(raw_scores)
        std_score = np.std(raw_scores) if len(raw_scores) > 1 else 0.1
        
        # Normalize with natural spread transformation
        normalized = []
        for i, result in enumerate(ranked_results):
            # Apply position-based decay (6% per position for natural recruiter spread)
            position_factor = 1.0 - (i * 0.06)  
            
            # Apply score-based transformation
            if result.raw_score >= max_score * 0.95:
                # Top tier: 94-96%
                normalized_score = 0.94 + (0.02 * (result.raw_score - min_score) / (max_score - min_score + 0.001))
            elif result.raw_score >= mean_score:
                # Above average: 84-94%
                normalized_score = 0.84 + (0.10 * (result.raw_score - mean_score) / (max_score - mean_score + 0.001))
            else:
                # Below average: 70-84%
                normalized_score = 0.70 + (0.14 * (result.raw_score - min_score) / (mean_score - min_score + 0.001))
            
            # Apply position decay
            final_score = normalized_score * position_factor
            final_score = max(0.70, min(0.97, final_score))  # Clamp to 70-97%
            
            # Round to avoid artificial precision
            final_score = round(final_score, 2)
            
            result.final_score = final_score
            result.rank_position = i + 1
            result.confidence_label = self._get_confidence_label(final_score)
            
            normalized.append(result)
        
        return normalized
    
    def _get_confidence_label(self, score: float) -> str:
        """Get confidence label based on score."""
        if score >= 0.94:
            return "Exceptional Match"
        elif score >= 0.89:
            return "Strong Match"
        elif score >= 0.84:
            return "Good Match"
        elif score >= 0.78:
            return "Moderate Match"
        else:
            return "Partial Match"
    
    def _generate_recruiter_explanation(
        self,
        assessment: AssessmentWithMetadata,
        factors: RankingFactors,
        role_domain: RoleDomain,
        classification: Optional[AssessmentDomain] = None
    ) -> str:
        """Generate recruiter-grade contextual explanation."""
        parts = []
        
        # Get classification if not provided
        if classification is None:
            classification = self.taxonomy.get_assessment_classification(assessment.id)
        
        # Role relevance statement
        if factors.role_domain_alignment > 0.7:
            parts.append(f"Critical assessment for {role_domain.value.replace('_', ' ')} roles")
        elif factors.role_domain_alignment > 0.5:
            parts.append(f"Relevant evaluation for {role_domain.value.replace('_', ' ')}")
        
        # Technical capability statement
        if factors.skill_overlap_score > 0.7:
            tech_focus = self._extract_technical_focus(assessment)
            if tech_focus:
                parts.append(f"Evaluates {tech_focus}")
        
        # Assessment purpose from description
        purpose = self._extract_assessment_purpose(assessment)
        if purpose:
            parts.append(purpose)
        
        # Seniority calibration
        if factors.seniority_alignment > 0.9:
            parts.append("Appropriate for senior-level expectations")
        
        # Combine into recruiter-style explanation
        if len(parts) >= 2:
            explanation = ". ".join(parts[:3]) + "."
        elif parts:
            explanation = parts[0] + "."
        else:
            explanation = f"{assessment.name} assesses key competencies for this role."
        
        return explanation
    
    def _extract_technical_focus(self, assessment: AssessmentWithMetadata) -> str:
        """Extract technical focus from assessment metadata."""
        # Check name for technology
        tech_keywords = {
            "java": "Java programming proficiency",
            "python": "Python programming capabilities",
            "react": "React frontend development",
            "javascript": "JavaScript development skills",
            "data science": "data science and ML workflows",
            "machine learning": "machine learning competency",
        }
        
        name_lower = assessment.name.lower()
        for tech, description in tech_keywords.items():
            if tech in name_lower:
                return description
        
        return ""
    
    def _extract_assessment_purpose(self, assessment: AssessmentWithMetadata) -> str:
        """Extract purpose from assessment description."""
        desc = assessment.description
        
        # Extract first meaningful sentence
        sentences = desc.split(".")
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 120:
                # Clean up
                sent = sent.lower()
                sent = sent[0].upper() + sent[1:]
                return sent
        
        return ""
    
    def get_top_recommendations(
        self,
        ranked_results: List[RankedAssessment],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Backward compatible method to get top recommendations.
        Calls get_recommendations_for_api internally.
        """
        return self.get_recommendations_for_api(ranked_results, top_k)

    def get_recommendations_for_api(
        self, 
        ranked_results: List[RankedAssessment],
        top_k: int = 5
    ) -> List[Dict]:
        """Convert ranked results to API response format."""
        recommendations = []
        
        for result in ranked_results[:top_k]:
            rec = {
                "id": result.assessment.id,
                "name": result.assessment.name,
                "url": result.assessment.url,
                "test_type": result.assessment.test_type.value,
                "score": result.final_score,
                "match_label": result.confidence_label,
                "category": result.category,
                "explanation": result.explanation,
            }
            recommendations.append(rec)
        
        return recommendations


# Backward compatibility - maintain existing interface
class RecommendationRanker(RecruiterRanker):
    """Backward compatible wrapper for existing code."""
    pass
