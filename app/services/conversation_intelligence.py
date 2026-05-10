"""
Conversation intelligence layer - reconstructs structured hiring context.
Powers the entire recommendation pipeline with clean, structured state.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContextSufficiency(Enum):
    """How much context we have."""
    MINIMAL = 0.2  # Almost nothing
    PARTIAL = 0.5  # Some info
    GOOD = 0.75  # Most things
    EXCELLENT = 0.95  # Everything needed


@dataclass
class StructuredHiringContext:
    """Clean structured hiring context reconstructed from conversation."""

    # Core hiring needs
    role: Optional[str] = None
    seniority: Optional[str] = None  # junior, mid, senior, executive

    # Technical requirements
    tech_stack: Set[str] = field(default_factory=set)
    technical_depth: Optional[str] = None  # basic, intermediate, advanced

    # Soft skills
    communication_required: bool = False
    communication_level: Optional[str] = None  # basic, intermediate, advanced
    leadership_required: bool = False
    leadership_level: Optional[str] = None
    teamwork_required: bool = False

    # Personality/cognitive
    personality_focus: bool = False
    cognitive_focus: bool = False
    reasoning_required: bool = False

    # Hiring context
    team_size: Optional[int] = None
    reporting_to_executive: bool = False
    cross_functional_collaboration: bool = False

    # Refinement history
    previous_recommendations: List[str] = field(default_factory=list)
    refinements: List[str] = field(default_factory=list)

    # Retrieval state
    retrieval_confidence: float = 0.0

    def calculate_sufficiency(self) -> ContextSufficiency:
        """Calculate how sufficient our context is for good recommendations."""

        score = 0.0
        max_score = 0.0

        # Role is critical (30%)
        max_score += 0.3
        if self.role:
            score += 0.3

        # Seniority is important (25%)
        max_score += 0.25
        if self.seniority:
            score += 0.25

        # Soft skills (20%)
        max_score += 0.2
        if self.communication_required or self.leadership_required or self.teamwork_required:
            score += 0.2

        # Technical requirements (15%)
        max_score += 0.15
        if self.tech_stack or self.cognitive_focus:
            score += 0.15

        # Other context (10%)
        max_score += 0.1
        if self.team_size or self.reporting_to_executive:
            score += 0.1

        normalized_score = score / max_score if max_score > 0 else 0

        if normalized_score < 0.3:
            return ContextSufficiency.MINIMAL
        elif normalized_score < 0.6:
            return ContextSufficiency.PARTIAL
        elif normalized_score < 0.85:
            return ContextSufficiency.GOOD
        else:
            return ContextSufficiency.EXCELLENT

    def get_missing_context(self) -> List[str]:
        """Identify what information is still missing."""

        missing = []

        # Critical missing
        if not self.role:
            missing.append("job_role")

        if not self.seniority:
            missing.append("seniority_level")

        # Important missing
        if not (self.communication_required or self.leadership_required or self.teamwork_required):
            missing.append("soft_skills")

        if not (self.tech_stack or self.cognitive_focus or self.reasoning_required):
            missing.append("technical_or_cognitive_requirements")

        # Nice to have
        if not self.team_size and not self.reporting_to_executive:
            missing.append("team_context")

        return missing

    def get_highest_value_missing(self) -> Optional[str]:
        """Get the single highest-value missing piece of information."""

        missing = self.get_missing_context()

        if not missing:
            return None

        # Prioritize by impact
        priority = {
            "job_role": 1,  # Most critical
            "seniority_level": 2,
            "soft_skills": 3,
            "technical_or_cognitive_requirements": 4,
            "team_context": 5,  # Nice to have
        }

        return min(missing, key=lambda x: priority.get(x, 999))

    def __str__(self) -> str:
        """String representation for LLM context."""
        parts = []

        if self.role:
            parts.append(f"Role: {self.role}")

        if self.seniority:
            parts.append(f"Seniority: {self.seniority}")

        if self.tech_stack:
            parts.append(f"Tech: {', '.join(self.tech_stack)}")

        soft_skills = []
        if self.communication_required:
            soft_skills.append(f"communication ({self.communication_level or 'any'})")
        if self.leadership_required:
            soft_skills.append(f"leadership ({self.leadership_level or 'any'})")
        if self.teamwork_required:
            soft_skills.append("teamwork")

        if soft_skills:
            parts.append(f"Soft Skills: {', '.join(soft_skills)}")

        if self.personality_focus:
            parts.append("Personality assessment focus")

        if self.cognitive_focus:
            parts.append("Cognitive assessment focus")

        if self.team_size:
            parts.append(f"Team size: {self.team_size}")

        if self.reporting_to_executive:
            parts.append("Reports to executive")

        if self.cross_functional_collaboration:
            parts.append("Cross-functional collaboration required")

        return "\n".join(parts) if parts else "No context extracted yet"


class ConversationIntelligence:
    """Reconstructs structured context from stateless conversation history."""

    def __init__(self):
        """Initialize conversation intelligence."""
        pass

    def reconstruct_context(self, messages: List[Dict]) -> StructuredHiringContext:
        """
        Reconstruct structured hiring context from full message history.

        Args:
            messages: Full conversation message history

        Returns:
            StructuredHiringContext with all extracted information
        """

        context = StructuredHiringContext()

        # Extract from all user messages
        for msg in messages:
            if msg.get("role") == "user":
                self._extract_from_message(msg.get("content", ""), context)

        # Calculate confidence
        sufficiency = context.calculate_sufficiency()
        context.retrieval_confidence = sufficiency.value

        return context

    def _extract_from_message(self, text: str, context: StructuredHiringContext) -> None:
        """Extract context from a single message."""

        text_lower = text.lower()

        # Extract role
        role_keywords = {
            "developer": "Software Developer",
            "engineer": "Software Engineer",
            "manager": "Engineering Manager",
            "product": "Product Manager",
            "data scientist": "Data Scientist",
            "analyst": "Business Analyst",
            "designer": "UX Designer",
            "qa": "QA Engineer",
            "devops": "DevOps Engineer",
        }

        for keyword, role in role_keywords.items():
            if keyword in text_lower:
                context.role = role
                break

        # Extract seniority
        seniority_keywords = {
            "junior": "junior",
            "mid-level": "mid",
            "mid level": "mid",
            "intermediate": "mid",
            "senior": "senior",
            "lead": "senior",
            "principal": "executive",
            "executive": "executive",
            "c-level": "executive",
        }

        for keyword, seniority in seniority_keywords.items():
            if keyword in text_lower:
                context.seniority = seniority

        # Extract tech stack
        tech_keywords = {
            "python", "java", "go", "rust", "typescript", "javascript",
            "react", "vue", "angular", "node", "django", "flask",
            "sql", "postgres", "mysql", "mongodb", "redis",
            "aws", "gcp", "azure", "kubernetes", "docker",
            "backend", "frontend", "fullstack", "devops",
        }

        for tech in tech_keywords:
            if tech in text_lower:
                context.tech_stack.add(tech)

        # Extract soft skills
        if any(word in text_lower for word in ["communication", "communicat", "present", "speak"]):
            context.communication_required = True
            if "strong" in text_lower or "excellent" in text_lower:
                context.communication_level = "advanced"

        if any(word in text_lower for word in ["leadership", "lead", "manage", "direct"]):
            context.leadership_required = True
            if "strong" in text_lower or "excellent" in text_lower:
                context.leadership_level = "advanced"

        if any(word in text_lower for word in ["teamwork", "collaboration", "collaborate", "team"]):
            context.teamwork_required = True

        # Extract personality/cognitive focus
        if any(word in text_lower for word in ["personality", "traits", "behavior", "style"]):
            context.personality_focus = True

        if any(word in text_lower for word in ["reasoning", "cognitive", "analytical", "problem-solving"]):
            context.cognitive_focus = True

        # Extract team context
        if "team" in text_lower:
            # Try to extract team size
            import re
            team_match = re.search(r"(\d+)\s*(?:person|people|member)", text)
            if team_match:
                context.team_size = int(team_match.group(1))

        # Extract reporting context
        if any(word in text_lower for word in ["executive", "c-level", "director", "vp"]):
            context.reporting_to_executive = True

        # Extract collaboration context
        if any(word in text_lower for word in ["cross-functional", "cross functional", "stakeholder"]):
            context.cross_functional_collaboration = True

    def get_highest_value_question(self, context: StructuredHiringContext) -> Optional[str]:
        """
        Get the single highest-value clarification question.

        Returns:
            Question to ask, or None if context is sufficient
        """

        missing = context.get_highest_value_missing()

        if not missing:
            return None

        # Generate intelligent question
        questions = {
            "job_role": "What role are you hiring for?",
            "seniority_level": "What seniority level? (junior, mid-level, senior, or executive)",
            "soft_skills": "What soft skills are most important? (e.g., communication, leadership, teamwork)",
            "technical_or_cognitive_requirements": "Are there specific technical skills or cognitive abilities needed?",
            "team_context": "What's the team context? (size, reporting structure, cross-functional needs)",
        }

        return questions.get(missing, f"Can you provide more detail about {missing}?")
