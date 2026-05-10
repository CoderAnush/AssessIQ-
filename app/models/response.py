"""
Pydantic models for API requests and responses.
STRICT COMPLIANCE VERSION FOR SHL EVALUATOR.
"""

from pydantic import BaseModel, Field
from typing import List, Literal


class Message(BaseModel):
    """A single message in conversation."""
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """POST /chat request schema."""
    messages: List[Message]


class Recommendation(BaseModel):
    """
    STRICT Recommendation model for recruiter.
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

    class Config:
        extra = "forbid"


class ChatResponse(BaseModel):
    """
    STRICT POST /chat response schema.
    NO EXTRA TOP-LEVEL FIELDS ALLOWED.
    """
    reply: str = Field(..., description="Assistant response")
    recommendations: List[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = Field(default=False)

    class Config:
        # Prevent any extra fields from being serialized
        extra = "forbid"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    memory_usage_mb: float
