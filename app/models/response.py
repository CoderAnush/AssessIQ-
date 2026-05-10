"""
Pydantic models for API requests and responses.
Defines schema for validation and serialization.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from enum import Enum


class Message(BaseModel):
    """A single message in conversation."""

    role: Literal["user", "assistant"] = Field(
        ..., description="Speaker: user or assistant"
    )
    content: str = Field(
        ..., description="Message text", min_length=1, max_length=5000
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "I'm hiring a Java developer"
            }
        }


class ChatRequest(BaseModel):
    """POST /chat request schema."""

    messages: List[Message] = Field(
        ..., description="Full conversation history", min_items=1, max_items=16
    )

    @validator("messages")
    def validate_alternating_roles(cls, v):
        """Ensure messages alternate between user and assistant."""
        for i in range(len(v) - 1):
            if v[i].role == v[i + 1].role:
                raise ValueError(f"Messages must alternate roles, got {v[i].role} twice")
        if v[0].role != "user":
            raise ValueError("First message must be from user")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Hiring a Java developer"},
                    {"role": "assistant", "content": "What seniority level?"},
                    {"role": "user", "content": "Mid-level"}
                ]
            }
        }


class TestType(str, Enum):
    """Assessment test type."""

    KNOWLEDGE = "K"
    ABILITY = "A"
    PERSONALITY = "P"


class Recommendation(BaseModel):
    """A single assessment recommendation with high-fidelity metadata."""

    id: Optional[str] = Field(None, description="Assessment unique ID")
    name: str = Field(
        ..., description="Assessment name from catalog", min_length=1
    )
    url: str = Field(
        ..., description="Assessment URL (must be shl.com)", min_length=1
    )
    test_type: TestType = Field(
        ..., description="Assessment type: K (Knowledge), A (Ability), P (Personality)"
    )
    score: float = Field(
        0.85, description="Matching confidence score (0-1)", ge=0, le=1
    )
    match_label: str = Field(
        "Strong Match", description="Human-readable confidence label"
    )
    category: str = Field(
        "Assessment", description="Assessment category (e.g. Personality, Technical)"
    )
    explanation: str = Field(
        "", description="Grounded recruiter-grade reasoning"
    )

    @validator("url")
    def validate_url(cls, v):
        """Ensure URL is from SHL domain."""
        if not v.startswith("https://www.shl.com"):
            raise ValueError("URL must be from shl.com domain")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "opq32r",
                "name": "OPQ32r",
                "url": "https://www.shl.com/solutions/products/opq32r/",
                "test_type": "P",
                "score": 0.94,
                "match_label": "Exceptional Match",
                "category": "Personality",
                "explanation": "Recommended for evaluating behavior and leadership potential..."
            }
        }


class ChatResponse(BaseModel):
    """POST /chat response schema (NON-NEGOTIABLE)."""

    reply: str = Field(
        ..., description="Agent response text", min_length=1, max_length=2000
    )
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="Empty when gathering info, 1-10 items when recommending"
    )
    end_of_conversation: bool = Field(
        default=False,
        description="True only when task is complete"
    )

    @validator("recommendations")
    def validate_recommendations_count(cls, v):
        """Ensure 0 or 1-10 recommendations."""
        if 0 < len(v) <= 10:
            return v
        elif len(v) == 0:
            return v
        else:
            raise ValueError(f"Recommendations must be 0 or 1-10, got {len(v)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "reply": "Here are 5 assessments that fit...",
                "recommendations": [
                    {
                        "name": "OPQ32r",
                        "url": "https://www.shl.com/solutions/products/opq32r/",
                        "test_type": "P"
                    }
                ],
                "end_of_conversation": False
            }
        }


class HealthResponse(BaseModel):
    """GET /health response schema."""

    status: str = Field(..., description="Service status")

    class Config:
        json_schema_extra = {
            "example": {"status": "ok"}
        }
