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
from app.logger_config.logger import get_logger
import logging

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
        """
        # Analyze conversation (Phase 4)
        context, intent = self.analyzer.analyze(messages)

        logger.debug(f"Decision Context: {context}")
        logger.debug(f"Detected Intent: {intent}")

        # 1. REFUSE if unsafe or off-topic
        if intent == UserIntent.OFF_TOPIC:
            return Decision(
                action=AgentAction.REFUSE,
                reasoning="I specialize in recommending SHL assessments and cannot assist with unrelated topics.",
                confidence=1.0,
            )

        # 2. COMPARE if requested
        if intent == UserIntent.COMPARISON:
            return Decision(
                action=AgentAction.COMPARE,
                reasoning="User asked for assessment comparison.",
                confidence=0.9
            )

        # 3. CLARIFY if insufficient context (Phase 4)
        # Convergence logic: Max 8 turns (pair of user/assistant is 1 turn each)
        turn_count = sum(1 for m in messages if m["role"] == "assistant")
        
        if not context.is_sufficient and turn_count < 4: # 4 assistant turns = 8 turns total roughly
            next_q = self.analyzer.get_clarification_question(context)
            if next_q:
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning=f"Context incomplete. Turn {turn_count+1}/8.",
                    confidence=0.9,
                    next_question=next_q,
                )

        # 4. RECOMMEND if sufficient or turn limit reached
        return Decision(
            action=AgentAction.RECOMMEND,
            reasoning="Sufficient context reached.",
            confidence=0.85,
        )

    def _check_refuse(self, intent: UserIntent, message: str) -> Optional[str]:
        """Check if we should refuse the request with the strict evaluator phrase."""

        if intent == UserIntent.PROMPT_INJECTION:
            return "I specialize in recommending SHL assessments and cannot assist with unrelated topics."

        if intent == UserIntent.OFF_TOPIC:
            return "I specialize in recommending SHL assessments and cannot assist with unrelated topics."

        return None

    def _extract_comparison_items(self, messages: List[dict]) -> List[str]:
        """
        Extract what user wants to compare.
        Supports relative references like 'top 2', 'first two', 'them', 'which is better'.
        Returns empty list if relative reference detected (caller should use memory).
        """
        message = messages[-1]["content"]
        msg_lower = message.lower()
        items = []

        # 1. Check for relative references - these will be resolved by chat.py using memory
        relative_refs = [
            "top 2", "top two", "first 2", "first two", "compare them", "both of them", 
            "top recommendations", "which is better", "difference between them", "compare these",
            "which one is better", "what's the difference", "difference?", "compare the first two"
        ]
        if any(ref in msg_lower for ref in relative_refs):
            # Return empty - chat.py will resolve from conversation memory
            logger.info("Relative reference detected for comparison - will resolve from memory")
            return []

        # 2. Pattern matching: "between X and Y"
        import re
        between_match = re.search(r"between\s+([^,]+?)\s+and\s+([^?\.!]+)", msg_lower)
        if between_match:
            items.append(between_match.group(1).strip())
            items.append(between_match.group(2).strip())
            return items

        # 3. Pattern matching: "X vs Y" or "X versus Y"
        vs_match = re.search(r"([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)\s+(?:vs|versus)\s+([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)", message)
        if not vs_match:
            vs_match = re.search(r"(\w+)\s+(?:vs|versus)\s+(\w+)", msg_lower)
        if vs_match:
            items.append(vs_match.group(1).strip())
            items.append(vs_match.group(2).strip())
            return items

        # 4. Capitalized assessment names (filter out common words)
        temp_message = re.sub(r"^[Cc]ompare\s+", "", message)
        cap_words = re.findall(r"([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)", temp_message)
        skip_words = {"and", "vs", "versus", "between", "the", "top", "for", "with", "shl", "assessment", "test"}
        for word in cap_words:
            if word.lower() not in skip_words and len(word) > 2:
                items.append(word)

        # 5. Known assessment names (expanded list)
        known_assessments = [
            "opq32r", "opq", "gsa", "16pf", "java 8", "java", "python", "leadership 7", 
            "leadership", "verbal reasoning", "ceb verbal", "verify interactive", "react",
            "data science", "ml assessment", "personality", "cognitive"
        ]
        for assessment in known_assessments:
            if assessment in msg_lower:
                # Avoid duplicates
                if not any(assessment in item.lower() for item in items):
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
