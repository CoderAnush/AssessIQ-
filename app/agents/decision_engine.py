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
        Decide what to do based on conversation (Phase 5: Clarify once).
        """
        # Analyze conversation
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

        # 3. CLARIFY if insufficient context (Phase 5: Exactly ONCE)
        turn_count = sum(1 for m in messages if m["role"] == "assistant")
        
        # Phase 5: Only clarify if we haven't hit the turn limit AND we haven't already asked the missing slot
        missing = context.get_missing_slots()
        if missing and turn_count < 1: # Strict Phase 5: Clarify ONCE
            next_q = self.analyzer.get_clarification_question(context)
            if next_q:
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning=f"Context incomplete. Phase 5: Clarifying ONCE.",
                    confidence=0.9,
                    next_question=next_q,
                )

        # 4. RECOMMEND if sufficient or turn limit reached
        return Decision(
            action=AgentAction.RECOMMEND,
            reasoning="Sufficient context reached or clarification budget spent.",
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
        """
        message = messages[-1]["content"]
        msg_lower = message.lower()
        items = []

        # 1. Check for relative references
        relative_refs = [
            "top 2", "top two", "first 2", "first two", "compare them", "both of them", 
            "top recommendations", "which is better", "difference between them", "compare these",
            "which one is better", "what's the difference", "difference?", "compare the first two"
        ]
        if any(ref in msg_lower for ref in relative_refs):
            return []

        # 2. Pattern matching
        import re
        between_match = re.search(r"between\s+([^,]+?)\s+and\s+([^?\.!]+)", msg_lower)
        if between_match:
            items.append(between_match.group(1).strip())
            items.append(between_match.group(2).strip())
            return items

        vs_match = re.search(r"([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)\s+(?:vs|versus)\s+([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)", message)
        if not vs_match:
            vs_match = re.search(r"(\w+)\s+(?:vs|versus)\s+(\w+)", msg_lower)
        if vs_match:
            items.append(vs_match.group(1).strip())
            items.append(vs_match.group(2).strip())
            return items

        return items[:2] if items else []

    def get_turn_count(self, messages: List[dict]) -> int:
        return sum(1 for m in messages if m["role"] == "assistant")

    def is_conversation_complete(self, messages: List[dict]) -> bool:
        if len(messages) < 2: return False
        
        # If recommendations given, we consider it a complete loop
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant":
                content = messages[i]["content"].lower()
                if "recommendation" in content or "assessment" in content:
                    return True
                break
        return False
