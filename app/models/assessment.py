"""
Pydantic models for assessment data.
Used throughout the system for type safety.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from enum import Enum


class TestTypeEnum(str, Enum):
    """Assessment test type."""
    KNOWLEDGE = "K"
    ABILITY = "A"
    PERSONALITY = "P"


class Assessment(BaseModel):
    """Core assessment data from catalog."""

    id: str = Field(..., description="Unique assessment ID")
    name: str = Field(..., description="Assessment name")
    description: str = Field(..., description="Full description")
    url: str = Field(..., description="SHL catalog URL")
    duration_minutes: int = Field(..., description="Duration in minutes", ge=5, le=180)
    test_type: TestTypeEnum = Field(..., description="Type: K, A, or P")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "opq32r",
                "name": "OPQ32r",
                "description": "Measures personality and behavioral style",
                "url": "https://www.shl.com/solutions/products/opq32r/",
                "duration_minutes": 30,
                "test_type": "P"
            }
        }


class AssessmentWithMetadata(Assessment):
    """Assessment with additional metadata for matching."""

    skills: List[str] = Field(
        default_factory=list,
        description="Skills this assessment measures"
    )
    recommended_roles: List[str] = Field(
        default_factory=list,
        description="Recommended for these roles"
    )
    ideal_roles: List[str] = Field(
        default_factory=list,
        description="Ideal roles from catalog"
    )
    inferred_roles: List[str] = Field(
        default_factory=list,
        description="Roles inferred during processing"
    )
    skill_tags: List[str] = Field(
        default_factory=list,
        description="Tags from catalog"
    )
    seniority_levels: List[str] = Field(
        default_factory=list,
        description="Recommended seniority levels: junior, mid, senior"
    )
    seniority_fit: List[str] = Field(
        default_factory=list,
        description="Seniority fit from catalog"
    )
    difficulty_level: Optional[str] = Field(
        default=None,
        description="Difficulty level: entry, intermediate, advanced"
    )
    relevance_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Relevance scores for various focuses"
    )
    communication_focus: bool = Field(
        default=False,
        description="Explicitly measures communication"
    )
    leadership_focus: bool = Field(
        default=False,
        description="Explicitly measures leadership"
    )
    technical_focus: bool = Field(
        default=False,
        description="Explicitly measures technical skills"
    )
    
    # Enterprise Metadata (Phase 6)
    inferred_skills: List[str] = Field(default_factory=list)
    
    @validator("inferred_skills", pre=True)
    def flatten_inferred_skills(cls, v):
        if isinstance(v, dict):
            skills = []
            for category, items in v.items():
                if isinstance(items, list):
                    skills.extend(items)
            return list(set(skills))
        return v

    engineering_domains: List[str] = Field(default_factory=list)
    suitable_stages: List[str] = Field(default_factory=list)
    category: str = Field(default="general")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "opq32r",
                "name": "OPQ32r",
                "description": "Measures personality and behavioral style",
                "url": "https://www.shl.com/solutions/products/opq32r/",
                "duration_minutes": 30,
                "test_type": "P",
                "skills": ["communication", "leadership", "teamwork"],
                "recommended_roles": ["manager", "team_lead"],
                "seniority_levels": ["mid", "senior"],
                "communication_focus": True,
                "leadership_focus": True,
                "technical_focus": False
            }
        }


class RetrievalResult(BaseModel):
    """Result from retrieval pipeline."""

    assessment: AssessmentWithMetadata = Field(..., description="Retrieved assessment")
    semantic_score: float = Field(..., description="Semantic similarity (0-1)", ge=0, le=1)
    bm25_score: float = Field(..., description="BM25 keyword score (0-1)", ge=0, le=1)
    hybrid_score: float = Field(..., description="Combined hybrid score (0-1)", ge=0, le=1)

    class Config:
        json_schema_extra = {
            "example": {
                "assessment": {
                    "id": "opq32r",
                    "name": "OPQ32r",
                    "description": "...",
                    "url": "...",
                    "duration_minutes": 30,
                    "test_type": "P",
                    "skills": ["communication"],
                    "recommended_roles": ["manager"],
                    "seniority_levels": ["mid", "senior"],
                    "communication_focus": True,
                    "leadership_focus": True,
                    "technical_focus": False
                },
                "semantic_score": 0.92,
                "bm25_score": 0.75,
                "hybrid_score": 0.869
            }
        }
