"""
POST /chat endpoint - main API.
Wires all components together in stateless conversation flow.
"""

from fastapi import APIRouter, HTTPException
from typing import List
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
                reply="I encountered an unexpected error. Please try again.",
                recommendations=[],
                end_of_conversation=False,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request",
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
    """Handle comparison action."""
    logger.info("Executing COMPARE action")

    items = decision.comparison_items or []

    if len(items) < 2:
        logger.warning("Not enough items to compare")
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
    """Handle refinement action."""
    logger.info("Executing REFINE action")

    last_user_msg = messages[-1]["content"]

    # Retrieve and rank again
    query = f"{context.role or ''} {' '.join(context.soft_skills)} {' '.join(context.technical_skills)}"
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

    # Generate LLM response
    # Pass the full ranked metadata for grounded reasoning
    prompt = get_recommendation_prompt(
        str(context),
        recommendations,
    )

    llm_response = llm_service.generate_response(
        system_prompt=get_system_prompt(),
        user_message=prompt,
        conversation_context=str(context),
    )

    # Use LLM reply but keep our ranked recommendations
    # This preserves the dynamic scores and categories
    llm_response["recommendations"] = recommendations

    # Validate schema
    is_valid, error = SchemaValidator.validate_chat_response(llm_response)
    if not is_valid:
        logger.error(f"Response schema invalid: {error}")
        # Fallback to simple valid response if LLM failed schema
        return ChatResponse(
            reply=llm_response.get("reply", "Here are the refined recommendations based on your updates."),
            recommendations=recommendations,
            end_of_conversation=False
        )

    return ChatResponse(**llm_response)


def _handle_recommendation(context, messages: List) -> ChatResponse:
    """Handle recommendation action."""
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

    # Get top recommendations
    recommendations = ranker.get_top_recommendations(ranked, settings.max_recommendations)

    # Validate
    is_clean, error = hallucination_checker.check_recommendations(recommendations)
    if not is_clean:
        logger.error(f"Hallucination detected: {error}")
        raise HTTPException(status_code=500, detail="Response validation failed")

    # Generate response via LLM
    # Pass the full recommendations list (which now includes score, match_label, category, etc.)
    prompt = get_recommendation_prompt(
        str(context),
        recommendations,
    )

    llm_response = llm_service.generate_response(
        system_prompt=get_system_prompt(),
        user_message=prompt,
        conversation_context=str(context),
    )

    # Use LLM reply but keep our ranked recommendations (preserving scores/labels)
    llm_response["recommendations"] = recommendations

    # Validate schema
    is_valid, error = SchemaValidator.validate_chat_response(llm_response)
    if not is_valid:
        logger.error(f"Response schema invalid: {error}")
        # Fallback to ensure we don't crash the UI
        return ChatResponse(
            reply=llm_response.get("reply", "Based on your requirements, I've selected the most relevant SHL assessments."),
            recommendations=recommendations,
            end_of_conversation=decision_engine.is_conversation_complete(messages)
        )

    # Check if conversation should end
    llm_response["end_of_conversation"] = decision_engine.is_conversation_complete(messages)

    return ChatResponse(**llm_response)
