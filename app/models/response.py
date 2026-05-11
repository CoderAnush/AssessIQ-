"""
Pydantic models for API requests and responses.
STRICT COMPLIANCE VERSION FOR SHL EVALUATOR.
Hardened with safe defaults (Critical Sync Fix).
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
    name: str = "Technical Stage"
    description: str = "Standard validation."
    assessments: List[str] = Field(default_factory=list)
    estimated_duration: int = 30
    competencies_covered: List[str] = Field(default_factory=list)

class FatigueReportModel(BaseModel):
    fatigue_score: float = 0.0
    risk_level: str = "Low"
    total_duration: int = 0
    dropout_probability: float = 0.0

class SignalReportModel(BaseModel):
    signal_score: float = 0.0
    coverage: Dict[str, float] = Field(default_factory=dict)
    confidence_levels: Dict[str, str] = Field(default_factory=dict)

class HiringPipelineModel(BaseModel):
    stages: List[PipelineStageModel] = Field(default_factory=list)
    fatigue: FatigueReportModel = Field(default_factory=FatigueReportModel)
    signal: SignalReportModel = Field(default_factory=SignalReportModel)
    tradeoff_analysis: str = "Standard pipeline optimization applied."
    strategic_guidance: str = "Follow SHL best practices for interviewing."

class Recommendation(BaseModel):
    """
    CLEAN Recommendation model for production.
    """
    name: str = Field("Assessment", description="Assessment name")
    url: str = Field("#", description="SHL URL")
    test_type: str = Field("K", description="K, A, or P")
    subtitle: str = Field("", description="Sub-heading e.g. Knowledge assessment")
    confidence: int = Field(0, description="Match confidence score")
    category: str = Field("", description="E.g. Knowledge, Personality")
    stage: str = Field("", description="Best hiring stage")
    duration: str = Field("", description="Assessment duration")
    recruiter_insight: str = Field("", description="Grounded insight")
    ideal_use_case: str = Field("", description="Ideal scenario for use")
    domain: str = Field("", description="Detected engineering domain")
    matched_skills: List[str] = Field(default_factory=list, description="Directly matching skills")
    recruiter_signal: str = Field("", description="Dynamic hiring signal tag")

    class Config:
        extra = "ignore"


class ChatResponse(BaseModel):
    """
    STRICT POST /chat response schema.
    """
    reply: str = Field("I am analyzing your request...", description="Assistant response")
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
