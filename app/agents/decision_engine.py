"""
Decision engine - core agentic reasoning.
Decides whether to clarify, recommend, refine, compare, or refuse.
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from app.services.conversation_analyzer import (
    HiringContext,
    UserIntent,
    ConversationAnalyzer,
)
from app.logging.logger import get_logger

logger = get_logger("decision_engine")


class AgentAction(str, Enum):
    """Possible agent actions."""

    REFUSE = "refuse"
    CLARIFY = "clarify"
    COMPARE = "compare"
    RECOMMEND = "recommend"
    REFINE = "refine"


@dataclass
class Decision:
    """Result of agent decision."""

    action: AgentAction
    reasoning: str
    confidence: float  # 0-1
    next_question: Optional[str] = None
    comparison_items: Optional[List[str]] = None  # For COMPARE action


class DecisionEngine:
    """
    Makes intelligent decisions about what the agent should do.
    Deterministic + explainable logic (not pure LLM magic).
    """

    def __init__(self):
        """Initialize decision engine."""
        self.analyzer = ConversationAnalyzer()

    def decide(self, messages: List[dict]) -> Decision:
        """
        Decide what to do based on conversation.

        Args:
            messages: Full conversation history

        Returns:
            Decision with action and reasoning
        """

        # Analyze conversation
        context, intent = self.analyzer.analyze_conversation(messages)

        logger.debug(f"Context: {context}")
        logger.debug(f"Intent: {intent}")

        # Decision tree (in order of priority)

        # 1. REFUSE if unsafe
        refuse_reason = self._check_refuse(intent, messages[-1]["content"])
        if refuse_reason:
            return Decision(
                action=AgentAction.REFUSE,
                reasoning=refuse_reason,
                confidence=0.95,
            )

        # 2. COMPARE if requested
        if intent == UserIntent.COMPARISON:
            comparison_items = self._extract_comparison_items(messages[-1]["content"])
            return Decision(
                action=AgentAction.COMPARE,
                reasoning="User asked to compare assessments",
                confidence=0.9,
                comparison_items=comparison_items,
            )

        # 3. REFINE if context changed
        if intent == UserIntent.REFINEMENT:
            return Decision(
                action=AgentAction.REFINE,
                reasoning="User modified constraints mid-conversation",
                confidence=0.85,
            )

        # 4. CLARIFY if insufficient context
        if not context.is_sufficient():
            next_q = self.analyzer.get_clarification_question(context)
            if next_q:
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning=f"Need more context: {context.get_missing_info()}",
                    confidence=0.9,
                    next_question=next_q,
                )

        # 5. RECOMMEND if we have context
        return Decision(
            action=AgentAction.RECOMMEND,
            reasoning="Sufficient context to generate recommendations",
            confidence=0.85,
        )

    def _check_refuse(self, intent: UserIntent, message: str) -> Optional[str]:
        """Check if we should refuse the request."""

        if intent == UserIntent.PROMPT_INJECTION:
            return "I can only help with SHL assessment recommendations"

        if intent == UserIntent.OFF_TOPIC:
            return "I focus specifically on SHL assessments. How can I help with assessment recommendations?"

        return None

    def _extract_comparison_items(self, message: str) -> List[str]:
        """Extract what user wants to compare."""

        msg_lower = message.lower()

        # Look for assessment names or patterns like "X vs Y"
        items = []

        # Pattern: "between X and Y"
        import re

        between_match = re.search(r"between\s+([^,]+?)\s+and\s+([^?\.!]+)", msg_lower)
        if between_match:
            items.append(between_match.group(1).strip())
            items.append(between_match.group(2).strip())
            return items

        # Pattern: "X vs Y"
        vs_match = re.search(r"(\w+)\s+vs\s+(\w+)", msg_lower)
        if vs_match:
            items.append(vs_match.group(1).strip())
            items.append(vs_match.group(2).strip())
            return items

        # Try to extract known assessment names
        known_assessments = ["opq", "gsa", "16pf", "java", "python", "leadership", "verbal"]
        for assessment in known_assessments:
            if assessment in msg_lower:
                items.append(assessment)

        return items[:2] if items else []  # Return first 2 items

    def get_context_from_messages(
        self, messages: List[dict]
    ) -> HiringContext:
        """Extract current context from messages."""
        context, _ = self.analyzer.analyze_conversation(messages)
        return context

    def get_turn_count(self, messages: List[dict]) -> int:
        """Get number of turns (pairs of user-assistant messages)."""
        # Count assistant messages (they're the full turns)
        return sum(1 for m in messages if m["role"] == "assistant")

    def is_conversation_complete(self, messages: List[dict]) -> bool:
        """Check if conversation should end."""
        # Conversation ends when:
        # 1. We just gave recommendations
        # 2. User confirms they're satisfied

        if len(messages) < 2:
            return False

        # Check if last assistant message included recommendations
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant":
                # Parse if recommendations included
                # This is a simple heuristic
                content = messages[i]["content"].lower()
                if (
                    "recommendation" in content
                    or "here are" in content
                    or "assessment" in content
                ):
                    return True
                break

        # Check if user is satisfied
        if len(messages) >= 2:
            last_user = messages[-1]["content"].lower()
            if any(
                phrase in last_user
                for phrase in [
                    "that's great",
                    "perfect",
                    "thanks",
                    "thank you",
                    "looks good",
                    "that works",
                    "excellent",
                    "exactly",
                    "that's it",
                ]
            ):
                return True

        return False

    def should_refetch_recommendations(self, messages: List[dict]) -> bool:
        """Check if we should fetch new recommendations (for REFINE action)."""
        # Simple heuristic: if last user message says "also" or "add"
        if not messages:
            return False

        last_user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            return False

        return any(
            word in last_user_msg.lower()
            for word in ["also", "add", "additionally", "plus", "change", "update"]
        )
