"""
Stateless chat route for the SHL evaluator.

The endpoint reconstructs all context from the provided message history on every
request and returns a strict three-field response schema.
"""

from fastapi import APIRouter, Body, Request
from typing import List, Dict, Optional, Tuple
import time
import traceback
import re

from app.models.response import ChatRequest, ChatResponse, Message, Recommendation
from app.agents.decision_engine import AgentAction
from app.config import settings
from app.logger_config.logger import get_logger

logger = get_logger("chat_endpoint")
router = APIRouter()


def _turn_count(messages: List[dict]) -> int:
    return sum(1 for message in messages if message.get("role") == "user")


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value.strip())
    return ordered


def _build_query(context) -> str:
    parts: List[str] = []
    if getattr(context, "role", None):
        parts.append(context.role)
    if getattr(context, "domain", None):
        parts.append(context.domain)
    if getattr(context, "seniority", None):
        parts.append(context.seniority)
    parts.extend(sorted(getattr(context, "tech_stack", set())))
    parts.extend(sorted(getattr(context, "soft_skills", set())))
    parts.extend(sorted(getattr(context, "preferred_test_types", set())))
    return " ".join(_dedupe_preserve_order(parts)).strip()


def _find_catalog_mentions(messages: List[dict], catalog: Dict[str, object]) -> List[str]:
    names = sorted((getattr(a, "name", "") for a in catalog.values() if getattr(a, "name", "")), key=len, reverse=True)
    found: List[str] = []
    for message in messages:
        content = message.get("content", "")
        if not content:
            continue
        content_low = content.lower()
        for name in names:
            if name and name.lower() in content_low:
                found.append(name)
    return _dedupe_preserve_order(found)


def _resolve_assessment(query: str, catalog: Dict[str, object]):
    query_low = query.lower().strip()
    if query_low in catalog:
        return catalog[query_low]
    for assessment in catalog.values():
        name = getattr(assessment, "name", "")
        if query_low == name.lower() or query_low in name.lower() or name.lower() in query_low:
            return assessment
        if query_low == getattr(assessment, "id", "").lower():
            return assessment
    return None


def _assessment_to_recommendation(assessment) -> Recommendation:
    return Recommendation(
        name=str(getattr(assessment, "name", "")),
        url=str(getattr(assessment, "url", "")),
        test_type=str(getattr(getattr(assessment, "test_type", ""), "value", getattr(assessment, "test_type", "K"))),
    )


def _fallback_reply(action: AgentAction) -> str:
    if action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
        return "Here are the most relevant SHL assessments from the grounded catalog."
    if action == AgentAction.CLARIFY:
        return "Could you clarify the role, seniority, and assessment focus?"
    if action == AgentAction.COMPARE:
        return "I do not have enough grounded catalog data to compare these assessments."
    return "I specialize in recommending SHL assessments and cannot assist with unrelated topics."


@router.post("/chat", response_model=ChatResponse)
async def chat(request_obj: Request, payload: Dict = Body(...)) -> ChatResponse:
    """
    Stateless chat endpoint with strict schema compliance.
    """
    start_time = time.time()

    try:
        services = request_obj.app.state

        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        elif "message" in payload:
            chat_request = ChatRequest(messages=[Message(role="user", content=payload["message"])])
        else:
            return ChatResponse(reply="Invalid request format.", recommendations=[], end_of_conversation=False)

        messages = [m.dict() for m in chat_request.messages]
        turn_count = _turn_count(messages)
        turn_limit_reached = turn_count >= settings.max_conversation_turns
        conversation_complete = turn_limit_reached

        decision = services.decision_engine.decide(messages)
        context = services.decision_engine.get_context_from_messages(messages)
        
        # Part 7: Detect and handle new hiring request context reset
        from app.services.conversation_memory import get_memory_store
        memory = get_memory_store()
        session_id = request_obj.headers.get("X-Session-ID", "default_session")
        
        # Check if the LATEST user message was a new hiring request
        latest_user_msg = messages[-1].get("content", "") if messages[-1]["role"] == "user" else ""
        if latest_user_msg and services.decision_engine.analyzer.is_new_hiring_request(latest_user_msg, context):
            logger.info(f"CHAT: New hiring request detected. Resetting session context for {session_id}")
            memory.reset_session_context(session_id)
            # Re-analyze context after reset if needed (though analyze_conversation already does boundary check)
            
        logger.info("CHAT: action=%s turns=%s completeness=%.2f", decision.action, turn_count, context.get_completeness_score())

        catalog = {assessment.id: assessment for assessment in services.catalog_loader.get_all()}

        if decision.action == AgentAction.REFUSE:
            reply = decision.reasoning or _fallback_reply(decision.action)
            return ChatResponse(reply=reply, recommendations=[], end_of_conversation=conversation_complete)

        if decision.action == AgentAction.CLARIFY:
            reply = decision.next_question or _fallback_reply(decision.action)
            return ChatResponse(reply=reply, recommendations=[], end_of_conversation=conversation_complete)

        if decision.action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
            query = _build_query(context)
            if not query and messages:
                query = messages[-1].get("content", "")

            retrieved = services.retriever.retrieve(query, context, top_k=20)
            ranked, _ = await services.ranker.rank(retrieved, context, catalog, top_k=settings.max_recommendations)

            if ranked:
                # Use the ranker's structured API method (already provides reply and recommendations)
                ranker_payload = await services.ranker.get_recommendations_for_api(ranked, context, top_k=settings.max_recommendations)
                reply = ranker_payload.get("reply", _fallback_reply(decision.action))
                recommendations = [Recommendation(**rec) for rec in ranker_payload.get("recommendations", [])]
            else:
                recommendations = []
                for item in retrieved[:1]:
                    if item.get("name") and item.get("url"):
                        recommendations.append(Recommendation(
                            name=str(item.get("name", "")),
                            url=str(item.get("url", "")),
                            test_type=str(item.get("test_type", "K")),
                            subtitle="Knowledge assessment",
                            confidence=70,
                            category="General",
                            stage="Early screening",
                            duration="30 min",
                            recruiter_insight="Grounded catalog recommendation.",
                            ideal_use_case="Initial screening focus."
                        ))
                
                if not recommendations and services.catalog_loader.get_all():
                    first_item = services.catalog_loader.get_all()[0]
                    recommendations = [Recommendation(
                        name=str(first_item.name),
                        url=str(first_item.url),
                        test_type=str(first_item.test_type.value),
                        subtitle="Knowledge assessment",
                        confidence=60,
                        category="General",
                        stage="Early screening",
                        duration="30 min",
                        recruiter_insight="Catalog-grounded fallback.",
                        ideal_use_case="General assessment."
                    )]
                reply = _fallback_reply(decision.action)

            return ChatResponse(
                reply=reply,
                recommendations=recommendations,
                end_of_conversation=conversation_complete,
            )

        if decision.action == AgentAction.COMPARE:
            items = decision.comparison_items or _find_catalog_mentions(messages, catalog)
            if len(items) < 2:
                reply = "Which assessments would you like me to compare? Please specify at least two names."
                return ChatResponse(reply=reply, recommendations=[], end_of_conversation=conversation_complete)

            first = _resolve_assessment(items[0], catalog)
            second = _resolve_assessment(items[1], catalog)
            if not first or not second:
                return ChatResponse(
                    reply="I do not have enough grounded catalog data to compare these assessments.",
                    recommendations=[],
                    end_of_conversation=conversation_complete,
                )

            comparison_result = services.comparison_engine.compare(first, second, context)
            return ChatResponse(
                reply=comparison_result.recruiter_summary,
                recommendations=[],
                end_of_conversation=conversation_complete,
            )

        return ChatResponse(
            reply="I specialize in recommending SHL assessments and cannot assist with unrelated topics.",
            recommendations=[],
            end_of_conversation=conversation_complete,
        )

    except Exception as e:
        logger.error(f"FATAL ERROR IN CHAT: {e}")
        trace_str = traceback.format_exc()
        logger.debug("CRITICAL EXCEPTION:\n%s", trace_str)
        return ChatResponse(
            reply="I encountered a technical issue while processing your request. Please try a simpler SHL assessment query.",
            recommendations=[],
            end_of_conversation=False,
        )
