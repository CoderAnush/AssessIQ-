"""
Enterprise-grade Ranking Engine for AssessIQ.
Implements strict domain gating, diversity boosting, and absolute domain locking.
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from app.logger_config.logger import get_logger
from app.services.skill_graph import SkillGraph
from app.services.domain_classifier import DomainClassifier, Domain

logger = get_logger("enterprise_ranker")

@dataclass
class RankingFactors:
    semantic_similarity: float = 0.0
    domain_match_score: float = 0.0
    skill_overlap_score: float = 0.0
    diversity_bonus: float = 0.0

@dataclass
class RankedAssessment:
    assessment: Any
    factors: RankingFactors
    final_score: float
    explanation: str
    matched_skills: List[str] = field(default_factory=list)

class EnterpriseRanker:
    """
    UPGRADED Enterprise Ranking Engine (Absolute Domain Locking).
    """
    
    def __init__(self, embedding_service=None, skill_graph: Optional[SkillGraph] = None):
        self.embedding_service = embedding_service
        self.skill_graph = skill_graph or SkillGraph()
        self.domain_classifier = DomainClassifier()

    def rank(self, retrieved: List[Dict], context: Any, catalog: Dict[str, Any], top_k: int = 10) -> List[RankedAssessment]:
        """
        STRICT DOMAIN GATING PASS (Part 1, 3, 5 Fix).
        """
        query = getattr(context, "query", "")
        if not query and hasattr(context, "history") and context.history:
            query = context.history[-1].get("content", "")
            
        query_classification = self.domain_classifier.detect_query_domain(query)
        query_domain = query_classification["primaryDomain"]
        
        logger.info(f"RANKER: Detected Query Domain: {query_domain}")

        # 1. INITIAL STRICT FILTERING (Part 1 & 5 Fix)
        # We filter BEFORE any ranking or diversity logic.
        candidates = []
        # Optimization: Limit candidate pool to top 40 for performance
        for res in retrieved[:40]:
            assess = catalog.get(res["id"])
            if not assess: continue

            assess_domain = getattr(assess, "primary_domain", Domain.GENERAL)
            
            # ABSOLUTE GATE (Part 1 & 2 Fix)
            if not self.domain_classifier.is_allowed_domain(query_domain, assess_domain):
                continue
            
            # Base Factors
            semantic_sim = res.get("hybrid_score", 0.0)
            
            # Pre-calculate domain match (faster in hot loop)
            domain_match = 1.0 if assess_domain == query_domain else 0.6 if assess_domain in self.domain_classifier.ADJACENCY_MAP.get(query_domain, []) else 0.0
                
            tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
            assess_skills = {s.lower() for s in getattr(assess, "skills", [])}
            matched = tech_stack.intersection(assess_skills)
            skill_overlap = len(matched) / max(1, len(tech_stack)) if tech_stack else 0.5
            
            candidates.append({
                "assess": assess,
                "semantic": semantic_sim,
                "domain": domain_match,
                "overlap": skill_overlap,
                "matched": matched
            })

        # 2. DIVERSITY BOOST WITHIN SAME DOMAIN (Part 3 Fix)
        # We only work with the filtered candidates.
        # Optimization: Use pre-calculated weights
        candidates.sort(key=lambda x: (x["semantic"] * 0.5 + x["domain"] * 0.3 + x["overlap"] * 0.2), reverse=True)
        
        final_ranked = []
        global_skill_frequencies = {}
        
        # Optimization: Early exit if we have enough high-quality candidates
        for cand in candidates:
            assess = cand["assess"]
            
            diversity_bonus = 0.0
            assess_skills = getattr(assess, "skills", [])
            for skill in assess_skills:
                freq = global_skill_frequencies.get(skill, 0)
                diversity_bonus -= (freq * 0.1) # Increased penalty to force diversity
            
            final_score = (0.50 * cand["semantic"]) + (0.30 * cand["domain"]) + (0.20 * cand["overlap"]) + diversity_bonus
            
            for skill in assess_skills:
                global_skill_frequencies[skill] = global_skill_frequencies.get(skill, 0) + 1
            
            factors = RankingFactors(
                semantic_similarity=cand["semantic"],
                domain_match_score=cand["domain"],
                skill_overlap_score=cand["overlap"],
                diversity_bonus=diversity_bonus
            )

            explanation = self._generate_grounded_insight(assess, query_classification, cand["matched"])

            final_ranked.append(RankedAssessment(
                assessment=assess,
                factors=factors,
                final_score=final_score,
                explanation=explanation,
                matched_skills=list(cand["matched"])
            ))
            
            # Optimization: Stop once we have 15 good candidates to process for orchestration
            if len(final_ranked) >= 15: break
            
        # 3. PRECISION OVER QUANTITY (Part 5 Fix)
        # Sort and return only the top K.
        return sorted(final_ranked, key=lambda x: x.final_score, reverse=True)[:top_k]

    def _generate_grounded_insight(self, assess: Any, query_class: Dict, matched_skills: Set[str]) -> str:
        primary_domain = getattr(assess, "primary_domain", Domain.GENERAL)
        if matched_skills:
            skills_str = ", ".join(list(matched_skills)[:3])
            return f"Validates {skills_str} competencies with high domain precision."
        return f"Evaluates core {primary_domain.lower().replace('_', ' ')} principles essential for this role."
