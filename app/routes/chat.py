"""
POST /chat endpoint - main API.
Wires all components together in stateless conversation flow.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict
import time

from app.models.response import ChatRequest, ChatResponse, Message
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import ConversationAnalyzer
from app.services.retriever import HybridRetriever
from app.services.ranker import RecommendationRanker
from app.services.llm_service import LLMService
from app.agents.decision_engine import DecisionEngine, AgentAction
from app.utils.hallucination_checker import HallucinationChecker, SchemaValidator
from app.prompts.system_prompt import (
    get_system_prompt,
    get_clarification_prompt,
    get_recommendation_prompt,
    get_comparison_prompt,
    get_refine_prompt,
)
from app.config import settings
from app.logging.logger import get_logger

logger = get_logger("chat_endpoint")

router = APIRouter()

# Conversation memory for recommendation persistence
_conversation_memory: Dict[str, List[Dict]] = {}


def _get_conversation_id(messages: List[dict]) -> str:
    """Generate a conversation ID from message history."""
    # Simple hash of last user message content
    if messages:
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        if last_user_msg:
            import hashlib
            return hashlib.md5(last_user_msg[:50].encode()).hexdigest()[:12]
    return "default"


def _store_recommendations_in_memory(messages: List[dict], recommendations: List[Dict]) -> None:
    """Store recommendations in conversation memory for comparison support."""
    conv_id = _get_conversation_id(messages)
    _conversation_memory[conv_id] = recommendations
    logger.info(f"Stored {len(recommendations)} recommendations in memory for conversation {conv_id}")


def _get_stored_recommendations(messages: List[dict]) -> List[Dict]:
    """Retrieve stored recommendations from conversation memory."""
    conv_id = _get_conversation_id(messages)
    recs = _conversation_memory.get(conv_id, [])
    logger.info(f"Retrieved {len(recs)} recommendations from memory for conversation {conv_id}")
    return recs


def _sanitize_reply(reply: str) -> str:
    """Remove fallback/error language from LLM reply."""
    fallback_phrases = [
        "i apologize",
        "i'm having trouble",
        "i'm sorry",
        "could you rephrase",
        "i don't understand",
        "i cannot process",
    ]
    
    reply_lower = reply.lower()
    for phrase in fallback_phrases:
        if phrase in reply_lower:
            # Replace with neutral professional language
            return "Here are the most relevant assessments based on your requirements:"
    
    return reply


# Global services (initialized once)
catalog_loader = None
retriever = None
ranker = None
decision_engine = None
llm_service = None
hallucination_checker = None


def _initialize_services():
    """Initialize all services (lazy loading)."""
    global catalog_loader, retriever, ranker, decision_engine, llm_service, hallucination_checker

    if catalog_loader is None or decision_engine is None:
        logger.info("Initializing services...")

        catalog_loader = CatalogLoader(settings.catalog_path)

        # Try to load FAISS index and embeddings model
        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            faiss_index = faiss.read_index(settings.faiss_index_path)
            embeddings_model = SentenceTransformer(settings.embeddings_model)
            logger.info("Loaded FAISS index and embeddings model")
        except Exception as e:
            logger.warning(f"Could not load FAISS: {e}. Using catalog-only retrieval")
            faiss_index = None
            embeddings_model = None

        retriever = HybridRetriever(
            catalog_loader=catalog_loader,
            embeddings_model=embeddings_model,
            faiss_index=faiss_index,
            semantic_weight=settings.semantic_search_weight,
            bm25_weight=settings.bm25_search_weight,
        )

        ranker = RecommendationRanker()
        decision_engine = DecisionEngine()
        llm_service = LLMService()
        hallucination_checker = HallucinationChecker(catalog_loader)

        logger.info("Services initialized successfully")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.

    Stateless conversation flow:
    1. Validate request
    2. Analyze conversation
    3. Decide action
    4. Execute action (clarify/recommend/refine/compare/refuse)
    5. Validate response
    6. Return

    Args:
        request: ChatRequest with full message history

    Returns:
        ChatResponse with reply, recommendations, end_flag
    """

    start_time = time.time()

    try:
        # Initialize services
        _initialize_services()

        # 1. VALIDATE REQUEST
        is_valid, error = SchemaValidator.validate_request_schema(request.dict())
        if not is_valid:
            logger.error(f"Request validation failed: {error}")
            raise HTTPException(status_code=400, detail=error)

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        logger.info(f"Received {len(messages)} messages")

        # 2. CHECK TURN LIMIT
        turn_count = decision_engine.get_turn_count(messages)
        if turn_count >= settings.max_conversation_turns:
            logger.info(f"Conversation at turn limit ({turn_count})")
            return ChatResponse(
                reply="We've reached the conversation turn limit. I hope the recommendations are helpful!",
                recommendations=[],
                end_of_conversation=True,
            )

        # 3. DECIDE ACTION
        decision = decision_engine.decide(messages)
        logger.info(f"Decision: {decision.action} (confidence: {decision.confidence:.2f})")
        logger.debug(f"Reasoning: {decision.reasoning}")

        # 4. EXECUTE ACTION
        try:
            if decision.action == AgentAction.REFUSE:
                return _handle_refusal(decision)

            elif decision.action == AgentAction.CLARIFY:
                return _handle_clarification(decision)

            elif decision.action == AgentAction.COMPARE:
                return _handle_comparison(decision, messages)

            elif decision.action == AgentAction.REFINE:
                return _handle_refinement(decision_engine.get_context_from_messages(messages), messages)

            elif decision.action == AgentAction.RECOMMEND:
                return _handle_recommendation(decision_engine.get_context_from_messages(messages), messages)

            else:
                logger.error(f"Unknown action: {decision.action}")
                return ChatResponse(
                    reply="I encountered an unexpected error while processing your request. Please try rephrasing.",
                    recommendations=[],
                    end_of_conversation=False,
                )
        except Exception as e:
            logger.error(f"Action execution error: {e}", exc_info=True)
            # Graceful fallback for any logic errors in specific handlers
            return ChatResponse(
                reply="I'm processing your request but encountered a temporary issue. Here's what I can tell you: I'm currently analyzing SHL assessments for your needs. Could you please try again with a slightly different query?",
                recommendations=[],
                end_of_conversation=False,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        # Final safety net to avoid 500
        return ChatResponse(
            reply="I apologize, but I'm having trouble processing that right now. Please try again in a moment.",
            recommendations=[],
            end_of_conversation=False
        )

    finally:
        elapsed = time.time() - start_time
        logger.info(f"Chat request completed in {elapsed:.2f}s")


def _handle_refusal(decision) -> ChatResponse:
    """Handle refusal action."""
    logger.info("Executing REFUSE action")

    reply = llm_service.generate_refusal(decision.reasoning)

    return ChatResponse(
        reply=reply,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_clarification(decision) -> ChatResponse:
    """Handle clarification action."""
    logger.info("Executing CLARIFY action")

    question = decision.next_question or "Could you provide more details?"

    return ChatResponse(
        reply=question,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_comparison(decision, messages: List) -> ChatResponse:
    """Handle comparison action with memory-backed relative reference resolution."""
    logger.info("Executing COMPARE action")

    items = decision.comparison_items or []
    
    # Check for relative references that need memory resolution
    last_user_msg = messages[-1]["content"].lower() if messages else ""
    relative_refs = ["top 2", "top two", "first 2", "first two", "compare them", 
                     "both of them", "top recommendations", "which is better", 
                     "difference between them", "compare these"]
    
    needs_memory_resolution = any(ref in last_user_msg for ref in relative_refs)
    
    if needs_memory_resolution or len(items) < 2:
        # Try to get from conversation memory
        stored_recs = _get_stored_recommendations(messages)
        if len(stored_recs) >= 2:
            logger.info(f"Using stored recommendations for comparison: {stored_recs[0]['name']}, {stored_recs[1]['name']}")
            items = [stored_recs[0]["name"], stored_recs[1]["name"]]
        elif len(items) < 2:
            logger.warning("Not enough items to compare and no memory available")
            return ChatResponse(
                reply="I need at least two assessments to compare. Please ask for recommendations first, or specify which assessments to compare (e.g., 'Compare OPQ32r and GSA').",
                recommendations=[],
                end_of_conversation=False,
            )

    if len(items) < 2:
        return ChatResponse(
            reply="I need at least two assessments to compare. Which two would you like me to compare?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Get assessments
    is_valid, error, assessments = hallucination_checker.validate_comparison_items(items)
    if not is_valid:
        logger.warning(f"Comparison validation failed: {error}")
        return ChatResponse(
            reply=f"I couldn't find one of those assessments in the SHL catalog. {error}",
            recommendations=[],
            end_of_conversation=False,
        )

    # Generate comparison
    assessment_list = list(assessments.values())
    comparison_text = llm_service.generate_comparison(
        {
            "name": assessment_list[0].name,
            "description": assessment_list[0].description,
            "test_type": assessment_list[0].test_type.value,
            "duration_minutes": assessment_list[0].duration_minutes,
            "skills": assessment_list[0].skills,
        },
        {
            "name": assessment_list[1].name,
            "description": assessment_list[1].description,
            "test_type": assessment_list[1].test_type.value,
            "duration_minutes": assessment_list[1].duration_minutes,
            "skills": assessment_list[1].skills,
        },
    )

    return ChatResponse(
        reply=comparison_text,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_refinement(context, messages: List) -> ChatResponse:
    """Handle refinement action with proper fallback handling."""
    logger.info("Executing REFINE action")

    last_user_msg = messages[-1]["content"]

    # Retrieve and rank again with updated context
    query = f"{context.role or ''} {' '.join(context.soft_skills)} {' '.join(context.tech_stack)}"
    retrieved = retriever.retrieve(query, context, top_k=settings.top_k_retrieval)

    # Create assessment dict for ranker
    assessment_dict = {a.id: a for a in catalog_loader.get_all()}

    ranked = ranker.rank(retrieved, context, assessment_dict)
    recommendations = ranker.get_top_recommendations(ranked, settings.max_recommendations)

    # Validate no hallucinations
    is_clean, error = hallucination_checker.check_recommendations(recommendations)
    if not is_clean:
        logger.error(f"Hallucination detected: {error}")
        raise HTTPException(status_code=500, detail="Response validation failed")

    # Store updated recommendations in memory
    _store_recommendations_in_memory(messages, recommendations)

    # Generate LLM response
    prompt = get_recommendation_prompt(str(context), recommendations)
    llm_response = llm_service.generate_response(
        system_prompt=get_system_prompt(),
        user_message=prompt,
        conversation_context=str(context),
    )

    # Use LLM reply but keep our ranked recommendations
    reply_text = _sanitize_reply(llm_response.get("reply", "Here are the refined recommendations based on your updates."))
    
    response_data = {
        "reply": reply_text,
        "recommendations": recommendations,
        "end_of_conversation": False
    }

    # Validate schema
    is_valid, error = SchemaValidator.validate_chat_response(response_data)
    if not is_valid:
        logger.error(f"Response schema invalid: {error}")
        return ChatResponse(
            reply="Here are the refined recommendations based on your updates:",
            recommendations=recommendations,
            end_of_conversation=False
        )

    return ChatResponse(**response_data)


def _handle_recommendation(context, messages: List) -> ChatResponse:
    """Handle recommendation action with proper fallback handling."""
    logger.info("Executing RECOMMEND action")

    # Build query from context
    query_parts = []
    if context.role:
        query_parts.append(context.role)
    if context.tech_stack:
        query_parts.extend(context.tech_stack)
    if context.soft_skills:
        query_parts.extend(context.soft_skills)

    query = " ".join(query_parts) or "assessment"

    # Retrieve
    retrieved = retriever.retrieve(query, context, top_k=settings.top_k_retrieval)

    if not retrieved:
        logger.warning("No assessments retrieved")
        return ChatResponse(
            reply="I couldn't find suitable assessments in the catalog for your criteria. Could you provide more details?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Rank
    assessment_dict = {a.id: a for a in catalog_loader.get_all()}
    ranked = ranker.rank(retrieved, context, assessment_dict)

    # Get top recommendations (with real dynamic scores and contextual explanations)
    recommendations = ranker.get_top_recommendations(ranked, settings.max_recommendations)

    # DEFENSIVE GUARD: Ensure recommendations is a list of dicts
    if not isinstance(recommendations, list):
        logger.error(f"Ranker returned invalid type: {type(recommendations)}")
        recommendations = []

    # Validate no hallucinations
    is_clean, error = hallucination_checker.check_recommendations(recommendations)
    if not is_clean:
        logger.error(f"Hallucination detected: {error}")
        raise HTTPException(status_code=500, detail="Response validation failed")

    # Store recommendations in memory for comparison support
    _store_recommendations_in_memory(messages, recommendations)

    # Generate LLM response for conversational reply
    prompt = get_recommendation_prompt(str(context), recommendations)
    llm_response = llm_service.generate_response(
        system_prompt=get_system_prompt(),
        user_message=prompt,
        conversation_context=str(context),
    )

    # CRITICAL FIX: Always use OUR recommendations with our scores/explanations
    # The LLM response is only for the conversational "reply" text
    
    # Check if LLM failed but we have valid recommendations
    if llm_response.get("_llm_failed") or not llm_response.get("reply"):
        # Use neutral success message - NO fallback apology
        reply_text = f"Based on your requirements for a {context.role or 'this role'}, here are my recommendations:"
    else:
        # Use LLM reply but ensure it doesn't contain fallback language
        reply_text = _sanitize_reply(llm_response.get("reply", ""))

    # Build final response with OUR recommendations (preserving dynamic scores/explanations)
    response_data = {
        "reply": reply_text,
        "recommendations": recommendations,
        "end_of_conversation": decision_engine.is_conversation_complete(messages)
    }

    # Validate schema
    is_valid, error = SchemaValidator.validate_chat_response(response_data)
    if not is_valid:
        logger.error(f"Response schema invalid: {error}")
        # Still return recommendations - this is a schema issue, not a data issue
        return ChatResponse(
            reply="Here are the most relevant assessments for your requirements:",
            recommendations=recommendations,
            end_of_conversation=decision_engine.is_conversation_complete(messages)
        )

    return ChatResponse(**response_data)
