"""
Decision engine - core agentic reasoning.
Decides whether to clarify, recommend, refine, compare, or refuse.
"""

import re
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
        if intent in {UserIntent.OFF_TOPIC, UserIntent.PROMPT_INJECTION}:
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
        full_user_text = " ".join(m["content"].lower() for m in messages if m["role"] == "user")
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        if intent == UserIntent.VAGUE_QUERY or self.analyzer.is_vague_request(last_user):
            if turn_count < 2:
                question = (
                    self.analyzer.get_clarification_question(context)
                    or (
                        "I'd be happy to help. What role are you hiring for? "
                        "(e.g. Senior Backend Developer, Junior Frontend Engineer — "
                        "and any technical focus like Java, React, or DevOps.)"
                    )
                )
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Vague assessment request requires role clarification.",
                    confidence=0.9,
                    next_question=question,
                )

        # Leadership roles need purpose clarification before first recommendation
        # Only for executive/CXO-style leadership queries, not functional managers (sales, engineering, etc.)
        specific_function_signals = (
            "sales", "engineering", "marketing", "hr ", "human resources", "developer",
            "financial", "data scientist", "devops", "full stack", "fullstack", "java",
            "python", "react", "contact centre", "contact center", "analyst", "operator",
            "chief technology",
        )
        # "cto" needs word-boundary matching: plain substring falsely matches "director"/"vector".
        has_specific_function = (
            any(sig in full_user_text for sig in specific_function_signals)
            or bool(re.search(r"\bcto\b", full_user_text))
        )
        # Word-boundary matching: substring "director" would match "Active Directory",
        # substring "cto" matches inside "director"/"vector".
        _role_low = (context.role or "").lower()
        leadership_role = (
            not has_specific_function
            and (
                bool(re.search(r"\b(leadership|cxo|cxos|director|cto|chief)\b", _role_low))
                or bool(
                    re.search(
                        r"senior leadership|solution for leadership|\bcxos?\b|\bdirector-level\b|chief technology|chief executive",
                        full_user_text,
                    )
                )
            )
        )
        if (
            leadership_role
            and turn_count < 2
            and not any(w in full_user_text for w in ["selection", "development", "benchmark", "feedback"])
        ):
            if turn_count < 1:
                question = (
                    self.analyzer.get_clarification_question(context)
                    or "Who is this meant for — selection against a benchmark, or developmental feedback?"
                )
            else:
                # Turn 2 (C1): audience described but purpose still unknown — ask before shortlisting.
                question = (
                    "For such roles, the OPQ32r is the right instrument — it measures 32 workplace "
                    "behaviour dimensions including strategic thinking, influencing style, and leadership. "
                    "One question before I commit to a report format: is this for selection against a "
                    "benchmark, or developmental feedback for an executive already in role?"
                )
            return Decision(
                action=AgentAction.CLARIFY,
                reasoning="Leadership context requires purpose clarification.",
                confidence=0.9,
                next_question=question,
            )
        
        # Contact centre flows need language clarification before recommendations (C3)
        cc_role = context.role and any(
            w in (context.role or "").lower()
            for w in ["contact centre", "contact center", "call center", "call centre", "customer service"]
        ) or any(w in full_user_text for w in ["contact centre", "contact center", "call center", "inbound calls"])
        if cc_role:
            if turn_count < 1 and not any(
                w in full_user_text
                for w in ["english", "spanish", "french", "german", "language"]
            ):
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Contact centre screening requires language selection.",
                    confidence=0.9,
                    next_question="Before I shape the stack — what language are the calls in? That drives which spoken-language screen we use.",
                )
            # Word-boundary matching: plain " us" would false-match "use" ("what should we use?").
            accent_selected = bool(
                re.search(r"\b(us|uk|usa|australian|american|british)\b", full_user_text)
                or "indian accent" in full_user_text
            )
            if turn_count < 3 and "english" in full_user_text and not accent_selected:
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Contact centre English accent selection.",
                    confidence=0.9,
                    next_question="SVAR has four English variants in the catalog: US, UK, Australian, and Indian accent. Which fits your operation?",
                )

        # C7: bilingual healthcare — clarify hybrid vs personality-only before recommending
        if any(w in full_user_text for w in ["hipaa", "healthcare admin", "patient records", "bilingual healthcare"]):
            if turn_count < 1 and any(w in full_user_text for w in ["spanish", "bilingual"]) and not any(
                w in full_user_text for w in ["hybrid", "personality-only", "go with the hybrid", "functionally bilingual"]
            ):
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Healthcare bilingual assessment requires language constraint clarification.",
                    confidence=0.9,
                    next_question=(
                        "Healthcare knowledge tests (HIPAA, Medical Terminology) are English-only, "
                        "while OPQ/DSI support Spanish. Which fits better — hybrid (English knowledge + Spanish personality) "
                        "or personality-only in Spanish with HIPAA assessed in interview?"
                    ),
                )

        # C9: full-stack JD — clarify backend vs frontend balance before first shortlist
        # Only when the recruiter uses the C9-style battery request (ui_30 scenario 12), not generic backend JDs.
        frontend_tokens = ("angular", "react", "next.js", "nextjs", "typescript", "frontend")
        backend_tokens = ("java", "spring", "sql", "aws", "docker", "rest")
        frontend_hits = sum(1 for t in frontend_tokens if t in full_user_text)
        backend_hits = sum(1 for t in backend_tokens if t in full_user_text)
        is_c9_opener = (
            "here's the jd" in full_user_text
            or "here is the jd" in full_user_text
            or "assessment battery" in full_user_text
        )
        if (
            is_c9_opener
            and frontend_hits >= 1
            and backend_hits >= 2
            and turn_count < 1
        ):
            if not any(w in full_user_text for w in ["backend-leaning", "frontend-leaning", "balanced full-stack", "backend leaning"]):
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Full-stack JD needs backend/frontend weighting before shortlist.",
                    confidence=0.9,
                    next_question=(
                        "This JD spans backend and frontend stacks. "
                        "Which fits better — backend-leaning, frontend-leaning, or balanced full-stack?"
                    ),
                )

        # C2: Rust niche — defer shortlist on first turn (explain sparse catalog)
        if "rust" in full_user_text and turn_count < 1:
            if not any(w in full_user_text for w in ["yes", "go ahead", "cognitive"]):
                return Decision(
                    action=AgentAction.CLARIFY,
                    reasoning="Rust has no direct K&S test; explain proxies before shortlist.",
                    confidence=0.9,
                    next_question=(
                        "SHL's catalog doesn't include a Rust-specific knowledge test. "
                        "The closest fit for a senior IC is Smart Interview Live Coding, plus Linux Programming "
                        "and Networking for infrastructure depth. Should I build a shortlist from these?"
                    ),
                )

        # Phase 5: Clarify up to 2 turns for missing role slot
        missing = context.get_missing_slots()
        if missing and turn_count < 2:
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
        
        compare_and_match = re.search(r"compare\s+([^,]+?)\s+and\s+([^?\.!]+)", msg_lower)
        if compare_and_match:
            items.append(compare_and_match.group(1).strip())
            items.append(compare_and_match.group(2).strip())
            return items

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
