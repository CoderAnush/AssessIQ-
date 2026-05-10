"""
Conversation analyzer - extracts hiring context from messages.
Reconstructs conversation state to understand user needs.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple
from enum import Enum
import re
from app.logging.logger import get_logger

logger = get_logger("conversation_analyzer")


class UserIntent(str, Enum):
    """Detected user intent."""
    VAGUE_QUERY = "vague"
    CLARIFICATION_PROVIDED = "clarification"
    REFINEMENT = "refinement"
    COMPARISON = "comparison"
    OFF_TOPIC = "off_topic"
    PROMPT_INJECTION = "prompt_injection"
    CLEAR_REQUIREMENT = "clear_requirement"


@dataclass
class HiringContext:
    """
    Extracted hiring context from conversation.
    Represents what we know about the hiring requirement.
    """

    # Role/Title Information
    role: Optional[str] = None
    tech_stack: Set[str] = field(default_factory=set)  # Java, Python, etc.
    domain: Optional[str] = None  # e.g., backend, frontend, data

    # Seniority
    seniority: Optional[str] = None  # junior, mid, senior, lead
    years_experience: Optional[int] = None

    # Skills Required
    soft_skills: Set[str] = field(default_factory=set)  # communication, leadership
    technical_skills: Set[str] = field(default_factory=set)
    cognitive_skills: Set[str] = field(default_factory=set)  # reasoning, problem-solving

    # Personality/Traits
    personality_traits: Set[str] = field(default_factory=set)  # extrovert, detail-oriented
    communication_needs: Set[str] = field(default_factory=set)  # presentation, negotiation
    leadership_needs: bool = False

    # Test Preferences
    preferred_test_types: Set[str] = field(default_factory=set)  # K, A, P
    max_duration_minutes: Optional[int] = None
    avoid_test_types: Set[str] = field(default_factory=set)

    # User Preferences
    budget_constraints: Optional[str] = None
    team_size: Optional[int] = None
    company_culture: Optional[str] = None

    def is_sufficient(self, min_role: bool = True) -> bool:
        """
        Check if we have enough context to recommend.

        Requires:
        - At least role or domain
        - At least one of: skill, seniority, or personality need
        """
        has_role = bool(self.role or self.domain or self.tech_stack)
        has_specificity = (
            bool(self.soft_skills)
            or bool(self.technical_skills)
            or bool(self.seniority)
            or self.leadership_needs
        )

        return has_role and has_specificity

    def get_missing_info(self) -> List[str]:
        """Identify missing high-value information."""
        missing = []

        if not (self.role or self.domain):
            missing.append("role")

        if not self.seniority:
            missing.append("seniority")

        if not (self.soft_skills or self.technical_skills):
            missing.append("skills")

        # Only ask about personality if we're assessing soft requirements
        if self.soft_skills and "communication" in self.soft_skills and not self.personality_traits:
            missing.append("personality_traits")

        return missing

    def __str__(self) -> str:
        """Human-readable context."""
        parts = []

        if self.role:
            parts.append(f"Role: {self.role}")
        if self.tech_stack:
            parts.append(f"Tech: {', '.join(self.tech_stack)}")
        if self.seniority:
            parts.append(f"Level: {self.seniority}")
        if self.soft_skills:
            parts.append(f"Soft skills: {', '.join(self.soft_skills)}")
        if self.technical_skills:
            parts.append(f"Tech skills: {', '.join(self.technical_skills)}")
        if self.leadership_needs:
            parts.append("Needs: Leadership")

        return " | ".join(parts) if parts else "No context extracted"


class ConversationAnalyzer:
    """Analyzes conversations to extract hiring context."""

    # Patterns for common terms
    SENIORITY_KEYWORDS = {
        "junior": ["junior", "entry-level", "fresh", "graduate", "entry level"],
        "mid": ["mid-level", "intermediate", "mid level", "mid-level", "3-5 years", "4 years"],
        "senior": ["senior", "staff", "principal", "lead", "experienced", "10+ years"],
    }

    SOFT_SKILLS = {
        "communication",
        "negotiation",
        "presentation",
        "leadership",
        "teamwork",
        "collaboration",
        "stakeholder",
        "people",
        "mentoring",
    }

    TECH_KEYWORDS = {
        "java",
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "c++",
        "c#",
        ".net",
        "nodejs",
        "react",
        "angular",
        "vue",
        "sql",
        "nosql",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "docker",
        "backend",
        "frontend",
        "fullstack",
        "devops",
    }

    SENIORITY_KEYWORDS_REVERSE = {}  # Will be built in __init__

    def __init__(self):
        """Initialize analyzer with keyword mappings."""
        # Build reverse mapping
        for level, keywords in self.SENIORITY_KEYWORDS.items():
            for keyword in keywords:
                self.SENIORITY_KEYWORDS_REVERSE[keyword] = level

    def analyze_conversation(
        self, messages: List[dict]
    ) -> Tuple[HiringContext, UserIntent]:
        """
        Analyze full conversation to extract context.

        Args:
            messages: List of {"role": "user"/"assistant", "content": "..."}

        Returns:
            (HiringContext, UserIntent)
        """
        context = HiringContext()
        intent = UserIntent.VAGUE_QUERY

        # Analyze all user messages in order
        user_messages = [m["content"] for m in messages if m["role"] == "user"]

        if not user_messages:
            return context, intent

        # Get latest user message for intent detection
        latest_user_msg = user_messages[-1]

        # Detect intent first
        intent = self._detect_intent(latest_user_msg, len(user_messages))

        # Extract context from all user messages
        for user_msg in user_messages:
            self._extract_context(user_msg, context)

        logger.debug(f"Analyzed context: {context}")
        logger.debug(f"Detected intent: {intent}")

        return context, intent

    def _detect_intent(self, latest_message: str, message_count: int) -> UserIntent:
        """Detect user's intent from latest message."""

        msg_lower = latest_message.lower()

        # Check for prompt injection patterns
        if self._is_prompt_injection(msg_lower):
            return UserIntent.PROMPT_INJECTION

        # Check for comparison questions
        if any(
            phrase in msg_lower
            for phrase in [
                "difference between",
                "compare",
                "vs",
                "versus",
                "which is better",
                "how does",
                "differ from",
            ]
        ):
            return UserIntent.COMPARISON

        # Check for refinement (adding to previous request)
        if any(
            phrase in msg_lower
            for phrase in [
                "also add",
                "additionally",
                "plus",
                "also need",
                "don't forget",
                "in addition",
                "actually",
            ]
        ) and message_count > 1:
            return UserIntent.REFINEMENT

        # Check for off-topic
        if self._is_off_topic(msg_lower):
            return UserIntent.OFF_TOPIC

        # Check if this provides clear information
        if any(
            keyword in msg_lower
            for keyword in ["years", "level", "need", "require", "must", "should"]
        ):
            return UserIntent.CLARIFICATION_PROVIDED

        # Check if still vague
        if len(latest_message.split()) < 5:
            return UserIntent.VAGUE_QUERY

        return UserIntent.CLEAR_REQUIREMENT

    def _is_prompt_injection(self, text: str) -> bool:
        """Detect prompt injection attempts."""
        injection_patterns = [
            "forget everything",
            "ignore",
            "disregard",
            "system prompt",
            "instructions",
            "jailbreak",
            "bypass",
            "override",
            "new instructions",
            "tell me the prompt",
            "what's your system",
        ]

        return any(pattern in text for pattern in injection_patterns)

    def _is_off_topic(self, text: str) -> bool:
        """Detect off-topic queries."""
        off_topic_patterns = [
            "python tutorial",
            "how to code",
            "legal",
            "law",
            "contract",
            "hire",
            "fire",
            "salary",
            "compensation",
            "market rate",
            "explain python",
            "teach me",
            "recommend restaurants",
            "weather",
        ]

        # Check for explicitly off-topic keywords
        if any(pattern in text for pattern in off_topic_patterns):
            # Exception: allow "hire" or "legal" if "assessment" or "test" is present
            if "assessment" in text or "test" in text:
                return False
            return True

        # Check for generic "how to" or "tell me about" without relevant context
        if any(text.startswith(pattern) for pattern in ["how to", "teach me", "tell me about", "explain"]):
            if "role" not in text and "job" not in text and "assessment" not in text and "test" not in text:
                return True

        return False

    def _extract_context(self, message: str, context: HiringContext) -> None:
        """Extract context fields from a single message."""

        msg_lower = message.lower()

        # Extract seniority
        for keyword, level in self.SENIORITY_KEYWORDS_REVERSE.items():
            if keyword in msg_lower:
                context.seniority = level
                # Try to extract years
                years_match = re.search(r"(\d+)\s*(?:years?|yrs?)", msg_lower)
                if years_match:
                    context.years_experience = int(years_match.group(1))
                break

        # Extract role
        role_patterns = [
            r"(?:hiring|looking for|need)s?\s+(?:a\s+)?(?:assessments?\s+for\s+)?(?:a\s+)?([^,\.!?]+?)(?:\s+(?:who|with|that|engineer|developer|manager))",
            r"(?:hiring|looking for|need)s?\s+(?:a\s+)?([^,\.!?]+?)$",
            r"([^,\.!?]+?)\s+(?:role|position|job|opening)",
        ]
        
        for pattern in role_patterns:
            role_match = re.search(pattern, msg_lower)
            if role_match:
                role = role_match.group(1).strip()
                # Clean up role
                role = re.sub(r"^(?:a|an|the|hiring)\s+", "", role)
                role = re.sub(r"\s+role$", "", role)
                if role and len(role.split()) < 5:  # Avoid capturing full sentences
                    context.role = role
                    break

        # Extract tech stack
        for tech in self.TECH_KEYWORDS:
            # Match whole word to avoid "go" in "good"
            if re.search(rf"\b{re.escape(tech)}\b", msg_lower):
                context.tech_stack.add(tech)

        # Extract soft skills
        for skill in self.SOFT_SKILLS:
            if skill in msg_lower:
                context.soft_skills.add(skill)

        # Extract specific patterns
        if "leadership" in msg_lower or "lead" in msg_lower:
            context.leadership_needs = True

        if "communication" in msg_lower:
            context.soft_skills.add("communication")

        if "problem solving" in msg_lower or "problem-solving" in msg_lower:
            context.cognitive_skills.add("problem_solving")

        if "creativity" in msg_lower or "creative" in msg_lower:
            context.personality_traits.add("creative")

        if "detail" in msg_lower:
            context.personality_traits.add("detail_oriented")

        if "analytical" in msg_lower:
            context.cognitive_skills.add("analytical")

    def get_clarification_question(self, context: HiringContext) -> Optional[str]:
        """
        Generate the MOST important clarification question.
        Ask only ONE question. Choose high-value question.
        """

        if not context.role and not context.domain:
            return "What role are you looking to fill?"

        if not context.seniority:
            return "What seniority level? (junior, mid-level, senior)"

        if not context.soft_skills and not context.technical_skills:
            return "What skills are most important for this role?"

        if context.soft_skills and not context.leadership_needs and "leadership" not in " ".join(context.soft_skills).lower():
            # Check if management/lead role
            if context.role and any(
                word in context.role.lower() for word in ["manager", "lead", "director", "head"]
            ):
                return "Does this person need to lead or mentor others?"

        # No more questions - we have enough
        return None

    def compare_contexts(self, ctx1: HiringContext, ctx2: HiringContext) -> bool:
        """Check if context has meaningfully changed."""
        return (
            ctx1.role != ctx2.role
            or ctx1.seniority != ctx2.seniority
            or ctx1.soft_skills != ctx2.soft_skills
            or ctx1.technical_skills != ctx2.technical_skills
            or ctx1.leadership_needs != ctx2.leadership_needs
        )
