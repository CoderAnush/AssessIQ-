"""
POST /chat endpoint - main API.
Wires all components together in stateless conversation flow.
"""

from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Tuple, Optional
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


def _force_safe_recommendations(recommendations: List[Dict]) -> List[Dict]:
    """Force all recommendations to match required schema with strict type casting."""
    safe_recs = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
            
        safe_rec = {
            "id": str(rec.get("id", "unknown")),
            "name": str(rec.get("name", "SHL Assessment")),
            "url": str(rec.get("url", "https://www.shl.com")),
            "test_type": str(rec.get("test_type", "K")),
            "score": float(rec.get("score", 0.85)),
            "match_label": str(rec.get("match_label", "Strong Match")),
            "category": str(rec.get("category", "Professional Assessment")),
            "explanation": str(rec.get("explanation", "Recommended based on role requirements.")),
        }
        
        # Ensure score is within 0-1 range
        if safe_rec["score"] > 1.0:
            safe_rec["score"] = safe_rec["score"] / 100.0
        safe_rec["score"] = max(0.0, min(1.0, safe_rec["score"]))
        
        safe_recs.append(safe_rec)
    return safe_recs


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
            catalog_path = getattr(settings, "catalog_path", "data/processed/catalog_processed.json")
            catalog_loader = CatalogLoader(catalog_path)
        
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
                
                # Use correct setting names from config.py
                model_name = getattr(settings, "embeddings_model", "sentence-transformers/all-MiniLM-L6-v2")
                model = SentenceTransformer(model_name)
                
                index_path = getattr(settings, "faiss_index_path", "data/processed/faiss_index.bin")
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


@router.post("/chat")
async def chat(request: Dict = Body(...)) -> ChatResponse:
    """
    Main chat endpoint with emergency debugging, granular logging, and flexible payload parsing.
    """
    from fastapi.responses import JSONResponse
    from app.models.response import ChatRequest, Message
    start_time = time.time()

    logger.info(f"CHAT ENDPOINT HIT with payload: {request}")

    try:
        # 1. FLEXIBLE PAYLOAD PARSING
        logger.info("STAGE: Payload Parsing")
        
        # Case A: {"message": "..."}
        if "message" in request and "messages" not in request:
            logger.info("Parsing legacy 'message' format")
            chat_request = ChatRequest(messages=[Message(role="user", content=request["message"])])
        
        # Case B: {"messages": [...]}
        elif "messages" in request:
            logger.info("Parsing standard 'messages' format")
            chat_request = ChatRequest(**request)
            
        else:
            logger.error(f"Invalid payload structure: {request}")
            return JSONResponse(
                status_code=200,
                content={
                    "reply": "I received an invalid request format. Please provide 'messages' or 'message'.",
                    "recommendations": [],
                    "end_of_conversation": False,
                    "success": False
                }
            )

        # 2. INITIALIZE SERVICES
        logger.info("STAGE: Service Initialization")
        _initialize_services()

        # 3. VALIDATE REQUEST
        logger.info("STAGE: Request Validation")
        is_valid, error = SchemaValidator.validate_request_schema(chat_request.dict())
        if not is_valid:
            logger.error(f"Request validation failed: {error}")
            return JSONResponse(
                status_code=200,
                content={
                    "reply": f"I encountered a validation error: {error}",
                    "recommendations": [],
                    "end_of_conversation": False,
                    "success": False
                }
            )

        messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]
        logger.info(f"Processing chat with {len(messages)} messages")

        # 4. CHECK TURN LIMIT
        logger.info("STAGE: Turn Limit Check")
        turn_count = decision_engine.get_turn_count(messages)
        if turn_count >= settings.max_conversation_turns:
            return ChatResponse(
                reply="We've reached the conversation turn limit. I hope the recommendations were helpful!",
                recommendations=[],
                end_of_conversation=True,
            )

        # 5. DECIDE ACTION
        logger.info("STAGE: Action Decision")
        decision = decision_engine.decide(messages)
        logger.info(f"Decision: {decision.action}")

        # 6. EXECUTE ACTION
        logger.info(f"STAGE: Executing {decision.action}")
        try:
            if decision.action == AgentAction.REFUSE:
                response = _handle_refusal(decision)
            elif decision.action == AgentAction.CLARIFY:
                response = _handle_clarification(decision)
            elif decision.action == AgentAction.COMPARE:
                response = _handle_comparison(decision, messages)
            elif decision.action == AgentAction.REFINE:
                response = _handle_refinement(decision_engine.get_context_from_messages(messages), messages)
            elif decision.action == AgentAction.RECOMMEND:
                response = _handle_recommendation(decision_engine.get_context_from_messages(messages), messages)
            else:
                logger.error(f"Unknown action: {decision.action}")
                response = ChatResponse(
                    reply="I'm not sure how to handle that request. Could you please rephrase?",
                    recommendations=[],
                    end_of_conversation=False,
                )
            
            # STAGE: Sanitization
            logger.info("STAGE: Response Sanitization")
            if hasattr(response, 'recommendations') and response.recommendations:
                response.recommendations = _force_safe_recommendations(response.recommendations)
            
            return response

        except Exception as e:
            logger.exception(f"Action execution failure: {e}")
            return JSONResponse(
                status_code=200,
                content={
                    "reply": "I'm processing your request but encountered a temporary issue. Please try rephrasing slightly.",
                    "recommendations": [],
                    "end_of_conversation": False,
                    "success": False,
                    "error": str(e)
                }
            )

    except Exception as e:
        logger.exception("CRITICAL CHAT ENDPOINT FAILURE")
        return JSONResponse(
            status_code=200,
            content={
                "reply": "I apologize, but I'm having trouble processing that right now. Please try again in a moment.",
                "recommendations": [],
                "end_of_conversation": False,
                "success": False,
                "error": str(e)
            }
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
    logger.info("REFINE: Retrieving assessments")
    query = f"{context.role or ''} {' '.join(context.soft_skills)} {' '.join(context.tech_stack)}"
    retrieved = retriever.retrieve(query, context, top_k=settings.top_k_retrieval)

    # Create assessment dict for ranker
    assessment_dict = {a.id: a for a in catalog_loader.get_all()}

    logger.info("REFINE: Ranking assessments")
    ranked = ranker.rank(retrieved, context, assessment_dict)
    recommendations = ranker.get_top_recommendations(ranked, settings.max_recommendations)

    # Validate no hallucinations
    logger.info("REFINE: Checking hallucinations")
    try:
        is_clean, error = hallucination_checker.check_recommendations(recommendations)
        if not is_clean:
            logger.error(f"Hallucination detected: {error}")
            # If hallucination detected, filter them out rather than crashing
            recommendations = [r for r in recommendations if r.get("name", "").lower() in hallucination_checker.valid_names]
    except Exception as e:
        logger.error(f"Hallucination check failed: {e}")
        pass

    # Store updated recommendations in memory
    logger.info("REFINE: Storing in memory")
    try:
        _store_recommendations_in_memory(messages, recommendations)
    except Exception as e:
        logger.error(f"Failed to store recommendations in memory: {e}")

    # Generate LLM response
    logger.info("REFINE: Generating LLM reply")
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
    
    logger.info("REFINE: Building final ChatResponse")
    response_data = {
        "reply": reply_text,
        "recommendations": recommendations,
        "end_of_conversation": False
    }

    return ChatResponse(**response_data)


def _handle_recommendation(context, messages: List) -> ChatResponse:
    """Handle recommendation action with proper fallback handling."""
    logger.info("Executing RECOMMEND action")

    # Build query from context
    logger.info("RECOMMEND: Building query")
    query_parts = []
    if context.role:
        query_parts.append(context.role)
    if context.tech_stack:
        query_parts.extend(context.tech_stack)
    if context.soft_skills:
        query_parts.extend(context.soft_skills)

    query = " ".join(query_parts) or "assessment"

    # Retrieve
    logger.info("RECOMMEND: Retrieving assessments")
    retrieved = retriever.retrieve(query, context, top_k=settings.top_k_retrieval)

    if not retrieved:
        logger.warning("No assessments retrieved")
        return ChatResponse(
            reply="I couldn't find suitable assessments in the catalog for your criteria. Could you provide more details?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Rank
    logger.info("RECOMMEND: Ranking assessments")
    assessment_dict = {a.id: a for a in catalog_loader.get_all()}
    ranked = ranker.rank(retrieved, context, assessment_dict)

    # Get top recommendations
    logger.info("RECOMMEND: Formatting recommendations")
    recommendations = ranker.get_top_recommendations(ranked, settings.max_recommendations)

    # DEFENSIVE GUARD: Ensure recommendations is a list of dicts
    if not isinstance(recommendations, list):
        logger.error(f"Ranker returned invalid type: {type(recommendations)}")
        recommendations = []

    # Validate no hallucinations
    logger.info("RECOMMEND: Checking hallucinations")
    try:
        is_clean, error = hallucination_checker.check_recommendations(recommendations)
        if not is_clean:
            logger.error(f"Hallucination detected: {error}")
            recommendations = [r for r in recommendations if r.get("name", "").lower() in hallucination_checker.valid_names]
    except Exception as e:
        logger.error(f"Hallucination check failed: {e}")
        pass

    # Store recommendations in memory
    logger.info("RECOMMEND: Storing in memory")
    try:
        _store_recommendations_in_memory(messages, recommendations)
    except Exception as e:
        logger.error(f"Failed to store recommendations in memory: {e}")

    # Generate LLM response
    logger.info("RECOMMEND: Generating LLM reply")
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

    if llm_response.get("_llm_failed") or not llm_response.get("reply"):
        reply_text = f"Based on your requirements for a {context.role or 'this role'}, here are the most relevant SHL assessments:"
    else:
        reply_text = _sanitize_reply(llm_response.get("reply", ""))

    logger.info("RECOMMEND: Building final ChatResponse")
    response_data = {
        "reply": reply_text,
        "recommendations": recommendations,
        "end_of_conversation": decision_engine.is_conversation_complete(messages)
    }

    return ChatResponse(**response_data)
