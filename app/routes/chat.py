"""
REFACTORED Chat Route - Lightweight & Resilient.
Uses pre-initialized services from app state.
"""

from fastapi import APIRouter, HTTPException, Body, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Tuple, Optional
import time
import traceback
import json
import psutil

from app.models.response import ChatRequest, ChatResponse, Message
from app.agents.decision_engine import AgentAction
from app.prompts.system_prompt import (
    get_system_prompt,
    get_recommendation_prompt,
)
from app.config import settings
from app.logging.logger import get_logger

logger = get_logger("chat_endpoint")
router = APIRouter()

# Conversation memory (keep for now, but monitor RAM)
_conversation_memory: Dict[str, List[Dict]] = {}


def _get_conversation_id(messages: List[dict]) -> str:
    if messages:
        user_history = "|".join([m.get("content", "") for m in messages if m.get("role") == "user"])
        if user_history:
            import hashlib
            return hashlib.md5(user_history.encode()).hexdigest()[:16]
    return "default_session"


@router.post("/chat")
async def chat(request_obj: Request, payload: Dict = Body(...)) -> ChatResponse:
    """
    Lightweight chat endpoint.
    """
    start_time = time.time()
    
    print("\n" + "="*60)
    print("CHAT REQUEST RECEIVED")
    print(f"Memory: {psutil.virtual_memory().percent}% used")
    
    # STEP 0: MINIMAL TEST BYPASS (Uncomment if needed for emergency test)
    # if payload.get("messages") and payload["messages"][0].get("content") == "ping":
    #     return ChatResponse(reply="pong", recommendations=[], end_of_conversation=False)

    try:
        # 1. Access Services from App State
        services = request_obj.app.state
        
        # 2. Payload Parsing
        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        elif "message" in payload:
            chat_request = ChatRequest(messages=[Message(role="user", content=payload["message"])])
        else:
            return JSONResponse(status_code=200, content={"reply": "Invalid format", "success": False})

        messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]
        
        # 3. Decision Engine
        print("CHAT: Decision Engine start")
        decision = services.decision_engine.decide(messages)
        print(f"CHAT: Action decided: {decision.action}")

        # 4. Handle Action
        response = None
        
        if decision.action == AgentAction.REFUSE:
            response = ChatResponse(reply=decision.reasoning, recommendations=[])
            
        elif decision.action == AgentAction.CLARIFY:
            response = ChatResponse(reply=decision.next_question, recommendations=[])
            
        elif decision.action == AgentAction.RECOMMEND:
            print("CHAT: Executing RECOMMEND (Lightweight)")
            context = services.decision_engine.get_context_from_messages(messages)
            query = f"{context.role or ''} {' '.join(context.soft_skills)} {' '.join(context.tech_stack)}"
            
            # Retrieval
            retrieved = services.retriever.retrieve(query, context, top_k=5)
            
            # Ranking
            all_assessments = {a.id: a for a in services.catalog_loader.get_all()}
            ranked = services.ranker.rank(retrieved, context, all_assessments)
            recommendations = services.ranker.get_top_recommendations(ranked, 3)
            
            # LLM Reply
            prompt = get_recommendation_prompt(str(context), recommendations)
            llm_res = services.llm_service.generate_response(
                system_prompt=get_system_prompt(),
                user_message=prompt
            )
            
            response = ChatResponse(
                reply=llm_res.get("reply", "Here are your recommendations:"),
                recommendations=recommendations,
                end_of_conversation=services.decision_engine.is_conversation_complete(messages)
            )
        
        else:
            # Fallback for COMPARE/REFINE for simplicity during debugging
            print(f"CHAT: Falling back to generic handler for {decision.action}")
            response = ChatResponse(reply="I'm processing your request. How else can I help?", recommendations=[])

        print(f"CHAT: Successfully processed in {time.time() - start_time:.2f}s")
        return response

    except Exception as e:
        print(f"FATAL ERROR IN CHAT: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=200,
            content={
                "reply": "I encountered a technical issue. Please try a simpler query.",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
