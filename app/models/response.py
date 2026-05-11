"""
Pydantic models for API requests and responses.
STRICT COMPLIANCE VERSION FOR SHL EVALUATOR.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Optional, Any


class Message(BaseModel):
    """A single message in conversation."""
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """POST /chat request schema."""
    messages: List[Message]


class PipelineStageModel(BaseModel):
    name: str
    description: str
    assessments: List[str]
    estimated_duration: int
    competencies_covered: List[str]

class FatigueReportModel(BaseModel):
    fatigue_score: float
    risk_level: str
    total_duration: int
    dropout_probability: float

class SignalReportModel(BaseModel):
    signal_score: float
    coverage: Dict[str, float]
    confidence_levels: Dict[str, str]

class HiringPipelineModel(BaseModel):
    stages: List[PipelineStageModel]
    fatigue: FatigueReportModel
    signal: SignalReportModel
    tradeoff_analysis: str
    strategic_guidance: str

class Recommendation(BaseModel):
    """
    CLEAN Recommendation model for production (Step 8 Fix).
    Removed internal debug fields.
    """
    name: str = Field(..., description="Assessment name")
    url: str = Field(..., description="SHL URL")
    test_type: str = Field(..., description="K, A, or P")
    subtitle: str = Field("", description="Sub-heading e.g. Knowledge assessment")
    confidence: int = Field(0, description="Match confidence score")
    category: str = Field("", description="E.g. Knowledge, Personality")
    stage: str = Field("", description="Best hiring stage")
    duration: str = Field("", description="Assessment duration")
    recruiter_insight: str = Field("", description="Grounded insight")
    ideal_use_case: str = Field("", description="Ideal scenario for use")
    domain: str = Field("", description="Detected engineering domain")
    matched_skills: List[str] = Field(default_factory=list, description="Directly matching skills")

    class Config:
        extra = "ignore"


class ChatResponse(BaseModel):
    """
    STRICT POST /chat response schema.
    """
    reply: str = Field(..., description="Assistant response")
    recommendations: List[Recommendation] = Field(default_factory=list)
    pipeline: Optional[HiringPipelineModel] = None
    detail: Optional[str] = Field(None, description="Detailed error information")
    end_of_conversation: bool = Field(default=False)

    class Config:
        extra = "forbid"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    memory_usage_mb: float
