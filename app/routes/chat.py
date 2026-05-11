"""
Stateless chat route for the SHL evaluator.
Final Production Hardening Pass (Empty States + Data Safety).
"""

from fastapi import APIRouter, Body, Request
from typing import List, Dict, Optional, Tuple
import time
import re

from app.models.response import (
    ChatRequest, ChatResponse, Message, Recommendation,
    HiringPipelineModel, PipelineStageModel, FatigueReportModel, SignalReportModel
)
from app.agents.decision_engine import AgentAction
from app.config import settings
from app.logger_config.logger import get_logger

logger = get_logger("chat_endpoint")
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request_obj: Request, payload: Dict = Body(...)) -> ChatResponse:
    """
    Stateless chat endpoint with elite empty state handling (Part 7 Fix).
    """
    try:
        services = request_obj.app.state

        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        else:
            return ChatResponse(reply="Invalid request.", recommendations=[], end_of_conversation=False)

        messages = [m.dict() for m in chat_request.messages]
        
        # Analysis
        decision = services.decision_engine.decide(messages)
        context, _ = services.decision_engine.analyzer.analyze(messages)
        context.query = messages[-1]["content"] if messages else ""

        if decision.action == AgentAction.REFUSE:
            return ChatResponse(reply=decision.reasoning, recommendations=[], end_of_conversation=False)

        if decision.action == AgentAction.CLARIFY:
            return ChatResponse(reply=decision.next_question, recommendations=[], end_of_conversation=False)

        if decision.action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
            query = f"{context.role} {context.seniority} {' '.join(context.tech_stack)}"
            retrieved = services.retriever.retrieve(query, context, top_k=20)
            
            catalog = {a.id: a for a in services.catalog_loader.get_all()}
            ranked_results = services.ranker.rank(retrieved, context, catalog, top_k=10)

            # Part 7 Fix: Empty State Safety
            if not ranked_results:
                return ChatResponse(
                    reply="No highly aligned assessments found for this specific role profile. Try broadening the technical requirements or seniority level to see broader catalog matches.",
                    recommendations=[],
                    end_of_conversation=False
                )

            recommendations = []
            for idx, res in enumerate(ranked_results):
                # Data Hardening (Part 8)
                base_confidence = int((res.final_score or 0.6) * 100)
                final_confidence = max(60, min(99, base_confidence - (idx * 3)))
                
                recommendations.append(Recommendation(
                    name=str(res.assessment.name),
                    url=str(res.assessment.url),
                    test_type=str(res.assessment.test_type.value),
                    subtitle=f"{res.assessment.category.title()} Assessment",
                    confidence=final_confidence,
                    category=str(res.assessment.category),
                    stage="Screening",
                    duration=f"{getattr(res.assessment, 'duration_minutes', 30)} min",
                    recruiter_insight=str(res.explanation),
                    ideal_use_case=str(res.assessment.description[:120]) + "...",
                    domain=str(getattr(res.assessment, "primary_domain", "GENERAL")),
                    matched_skills=list(res.matched_skills)
                ))
            
            # Orchestration
            optimized = services.adaptive_orchestrator.orchestrate(ranked_results, context, catalog)
            
            pipeline_model = HiringPipelineModel(
                stages=[PipelineStageModel(
                    name=str(s.get("name", "Stage")),
                    description=str(s.get("description", "Assessment stage.")),
                    assessments=[str(a) for a in s.get("assessments", [])],
                    estimated_duration=int(s.get("duration", 30)),
                    competencies_covered=[str(c) for c in s.get("competencies_covered", [])]
                ) for s in getattr(optimized, "stages", [])],
                fatigue=FatigueReportModel(**getattr(optimized, "fatigue_report", {})),
                signal=SignalReportModel(**getattr(optimized, "signal_report", {})),
                tradeoff_analysis=str(getattr(optimized, "tradeoff_analysis", "Balanced")),
                strategic_guidance=str(getattr(optimized, "strategic_advice", "Standard approach."))
            )

            reply = f"I've optimized a {len(optimized.stages)}-stage hiring pipeline for {context.role or 'this role'}. {getattr(optimized, 'strategic_advice', '')}"
            
            return ChatResponse(
                reply=reply,
                recommendations=recommendations,
                pipeline=pipeline_model,
                end_of_conversation=False
            )

        return ChatResponse(reply="How can I assist with your hiring orchestration today?", recommendations=[], end_of_conversation=False)

    except Exception as e:
        logger.exception("CHAT FATAL ERROR")
        return ChatResponse(reply="Technical synchronization issue. Please retry.", recommendations=[], end_of_conversation=False)
