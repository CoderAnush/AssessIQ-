"""
Models for ranking results and factors.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from app.models.assessment import AssessmentWithMetadata
from app.core.assessment_taxonomy import AssessmentDomain

@dataclass
class RankingFactors:
    """All scoring factors for transparency."""
    domain_match: float = 0.0        # 25%
    seniority_fit: float = 0.0      # 15%
    type_alignment: float = 0.0     # 15%
    skill_overlap: float = 0.0      # 15%
    soft_skill_match: float = 0.0   # 10%
    role_completeness: float = 0.0  # 10%
    semantic_relevance: float = 0.0 # 10%
    diversity_penalty: float = 0.0  # Penalty modifier
    
    def calculate_final(self) -> float:
        """Calculate weighted final score (0-1)."""
        weighted_sum = (
            self.domain_match * 0.25 +
            self.seniority_fit * 0.15 +
            self.type_alignment * 0.15 +
            self.skill_overlap * 0.15 +
            self.soft_skill_match * 0.10 +
            self.role_completeness * 0.10 +
            self.semantic_relevance * 0.10
        )
        return max(0.0, min(1.0, weighted_sum + self.diversity_penalty))

@dataclass
class RankedAssessment:
    """Complete ranking result with metadata."""
    assessment: AssessmentWithMetadata
    final_score: float
    raw_score: float
    confidence_label: str
    factors: RankingFactors
    explanation: Dict[str, str]  # Structured explanation
    rank_position: int
    domain: AssessmentDomain
    category: str
    exclusion_reason: Optional[str] = None  # Priority 6: Trust & Transparency
