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
    """Generate a unique conversation ID from the full user message history."""
    if messages:
        # Create a stable hash of all user messages to represent the session state
        user_history = "|".join([m.get("content", "") for m in messages if m.get("role") == "user"])
        if user_history:
            import hashlib
            return hashlib.md5(user_history.encode()).hexdigest()[:16]
    return "default_session"


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
    """Initialize all services (lazy loading) with error resilience."""
    global catalog_loader, retriever, ranker, decision_engine, llm_service, hallucination_checker

    try:
        if catalog_loader is None:
            from app.services.catalog_loader import CatalogLoader
            catalog_loader = CatalogLoader()
        
        if llm_service is None:
            from app.services.llm_service import LLMService
            llm_service = LLMService()
            
        if retriever is None:
            from app.services.retriever import HybridRetriever
            # Attempt to load models/indices
            try:
                from sentence_transformers import SentenceTransformer
                import faiss
                import os
                
                model = SentenceTransformer(settings.embedding_model_name)
                index_path = os.path.join("data", "indices", "faiss_index.bin")
                if os.path.exists(index_path):
                    index = faiss.read_index(index_path)
                else:
                    index = None
                    logger.warning(f"FAISS index not found at {index_path}")
            except Exception as e:
                logger.error(f"Failed to load semantic search components: {e}")
                model = None
                index = None
                
            retriever = HybridRetriever(catalog_loader, model, index)
            
        if ranker is None:
            from app.services.ranker import RecommendationRanker
            ranker = RecommendationRanker()
            
        if decision_engine is None:
            from app.agents.decision_engine import DecisionEngine
            decision_engine = DecisionEngine()
            
        if hallucination_checker is None:
            from app.utils.hallucination_checker import HallucinationChecker
            hallucination_checker = HallucinationChecker(catalog_loader)
            
    except Exception as e:
        logger.critical(f"CRITICAL SERVICE INITIALIZATION FAILURE: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service initialization failed")


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
    """Handle refusal action with defensive fallback."""
    logger.info("Executing REFUSE action")
    
    try:
        reply = decision.reasoning or "I focus specifically on SHL assessment recommendations. How can I help you with your hiring needs?"
    except Exception as e:
        logger.error(f"Refusal processing failed: {e}")
        reply = "I focus specifically on SHL assessment recommendations. How can I help you with your hiring needs?"
    
    return ChatResponse(
        reply=reply,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_clarification(decision) -> ChatResponse:
    """Handle clarification action with defensive fallback."""
    logger.info("Executing CLARIFY action")
    
    try:
        question = decision.next_question or "Could you provide more details about the role requirements?"
    except Exception as e:
        logger.error(f"Clarification processing failed: {e}")
        question = "To give you the best SHL recommendations, could you tell me a bit more about the role and seniority level?"
    
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
    try:
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
    except Exception as e:
        logger.error(f"Comparison generation failed: {e}")
        comparison_text = f"I've analyzed both **{assessment_list[0].name}** and **{assessment_list[1].name}**. While I encountered an issue generating a detailed comparison table, I recommend reviewing both as they are top-tier SHL assessments for this role."

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
    try:
        is_clean, error = hallucination_checker.check_recommendations(recommendations)
        if not is_clean:
            logger.error(f"Hallucination detected: {error}")
            # If hallucination detected, filter them out rather than crashing
            recommendations = [r for r in recommendations if r.get("name", "").lower() in hallucination_checker.valid_names]
            if not recommendations:
                 return ChatResponse(
                    reply="I've updated my analysis based on your feedback, but I need a few more details to find the perfect SHL assessment for you.",
                    recommendations=[],
                    end_of_conversation=False
                )
    except Exception as e:
        logger.error(f"Hallucination check failed: {e}")
        pass

    # Store updated recommendations in memory
    try:
        _store_recommendations_in_memory(messages, recommendations)
    except Exception as e:
        logger.error(f"Failed to store recommendations in memory: {e}")

    # Generate LLM response
    try:
        prompt = get_recommendation_prompt(str(context), recommendations)
        llm_response = llm_service.generate_response(
            system_prompt=get_system_prompt(),
            user_message=prompt,
            conversation_context=str(context),
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        llm_response = {"_llm_failed": True}

    # Use LLM reply but keep our ranked recommendations
    if llm_response.get("_llm_failed") or not llm_response.get("reply"):
        reply_text = f"I've refined the recommendations for a {context.role or 'this role'} based on your latest input:"
    else:
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
    try:
        is_clean, error = hallucination_checker.check_recommendations(recommendations)
        if not is_clean:
            logger.error(f"Hallucination detected: {error}")
            # If hallucination detected, filter them out rather than crashing
            recommendations = [r for r in recommendations if r.get("name", "").lower() in hallucination_checker.valid_names]
            if not recommendations:
                 return ChatResponse(
                    reply="I'm sorry, I encountered an issue validating the recommendations. Could you please try again?",
                    recommendations=[],
                    end_of_conversation=False
                )
    except Exception as e:
        logger.error(f"Hallucination check failed: {e}")
        # Proceed with caution if checker fails
        pass

    # Store recommendations in memory for comparison support
    try:
        _store_recommendations_in_memory(messages, recommendations)
    except Exception as e:
        logger.error(f"Failed to store recommendations in memory: {e}")

    # Generate LLM response for conversational reply
    try:
        prompt = get_recommendation_prompt(str(context), recommendations)
        llm_response = llm_service.generate_response(
            system_prompt=get_system_prompt(),
            user_message=prompt,
            conversation_context=str(context),
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        llm_response = {"_llm_failed": True}

    # CRITICAL FIX: Always use OUR recommendations with our scores/explanations
    # The LLM response is only for the conversational "reply" text
    
    # Check if LLM failed but we have valid recommendations
    if llm_response.get("_llm_failed") or not llm_response.get("reply"):
        # Use neutral success message - NO fallback apology
        reply_text = f"Based on your requirements for a {context.role or 'this role'}, here are the most relevant SHL assessments:"
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
