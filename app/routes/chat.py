"""
Stateless chat route for the SHL evaluator.
Implements ABSOLUTE DOMAIN LOCKING safety guards.
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
from app.services.domain_classifier import DomainClassifier, Domain

logger = get_logger("chat_endpoint")
router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request_obj: Request, payload: Dict = Body(...)) -> ChatResponse:
    """
    Stateless chat endpoint with ABSOLUTE DOMAIN LOCKING (Step 4 Fix).
    """
    try:
        services = request_obj.app.state
        domain_classifier = DomainClassifier()

        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        else:
            return ChatResponse(reply="Invalid request.", recommendations=[], end_of_conversation=False)

        messages = [m.dict() for m in chat_request.messages]
        
        # 1. Analysis
        decision = services.decision_engine.decide(messages)
        context, _ = services.decision_engine.analyzer.analyze(messages)
        user_query = messages[-1]["content"] if messages else ""
        context.query = user_query

        if decision.action == AgentAction.REFUSE:
            return ChatResponse(reply=decision.reasoning, recommendations=[], end_of_conversation=False)

        if decision.action == AgentAction.CLARIFY:
            return ChatResponse(reply=decision.next_question, recommendations=[], end_of_conversation=False)

        if decision.action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
            # 2. Retrieval & Ranking
            query = f"{context.role} {context.seniority} {' '.join(context.tech_stack)}"
            retrieved = services.retriever.retrieve(query, context, top_k=20)
            
            catalog = {a.id: a for a in services.catalog_loader.get_all()}
            ranked_results = services.ranker.rank(retrieved, context, catalog, top_k=10)

            # 3. DETECT DOMAIN FOR FINAL SAFETY GUARD (Step 4 Fix)
            query_domain = domain_classifier.detect_query_domain(user_query)["primaryDomain"]

            recommendations = []
            for idx, res in enumerate(ranked_results):
                # FINAL SAFETY GUARD: ABSOLUTE ASSERTION (Step 4 Fix)
                assess_domain = getattr(res.assessment, "primary_domain", Domain.GENERAL)
                if not domain_classifier.is_allowed_domain(query_domain, assess_domain):
                    logger.warning(f"FINAL GUARD: Rejecting {res.assessment.name} ({assess_domain}) for query {query_domain}")
                    continue

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
                    domain=str(assess_domain),
                    matched_skills=list(res.matched_skills)
                ))
            
            # Part 7 Fix: Professional Empty State if final guard cleared everything
            if not recommendations:
                return ChatResponse(
                    reply="I couldn't find any assessments that strictly match the technical domain requirements for this role. Try broadening your search or specifying different skills.",
                    recommendations=[],
                    end_of_conversation=False
                )

            # 4. Orchestration
            # We must only orchestrate the items that passed the final guard
            filtered_ranked = [r for r in ranked_results if any(rec.name == r.assessment.name for rec in recommendations)]
            optimized = services.adaptive_orchestrator.orchestrate(filtered_ranked, context, catalog)
            
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

    except Exception:
        logger.exception("CHAT FATAL ERROR")
        return ChatResponse(reply="Technical synchronization issue. Please retry.", recommendations=[], end_of_conversation=False)
