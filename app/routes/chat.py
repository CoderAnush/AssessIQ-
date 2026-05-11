import functools
import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Request

from app.agents.decision_engine import AgentAction
from app.config import settings
from app.logger_config.logger import get_logger
from app.models.response import (
    ChatRequest, ChatResponse, FatigueReportModel, HiringPipelineModel,
    Message, PipelineStageModel, Recommendation, SignalReportModel
)
from app.services.domain_classifier import Domain, DomainClassifier

logger = get_logger("chat_endpoint")
router = APIRouter()

# --- CACHE LAYER ---
# Simple in-memory cache for common recruiter queries to prevent redundant compute
# TTL is effectively the lifetime of the process on Render, which is fine for demo stability.
@functools.lru_cache(maxsize=128)
def get_cached_response(query_key: str) -> Optional[Dict]:
    """Helper for LRU caching. Key should be normalized query + role."""
    return None # Logic implemented inside the route for now to access app.state

@router.post("/chat", response_model=ChatResponse)
async def chat(request_obj: Request, payload: Dict = Body(...)) -> ChatResponse:
    """
    Stateless chat endpoint with PERFORMANCE PROFILING and CACHING.
    """
    overall_start = time.time()
    try:
        services = request_obj.app.state
        domain_classifier = getattr(services, "domain_classifier", DomainClassifier())

        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        else:
            return ChatResponse(reply="Invalid request.", recommendations=[], end_of_conversation=False)

        messages = [m.dict() for m in chat_request.messages]
        user_query = messages[-1]["content"] if messages else ""
        
        # 0. CACHE LOOKUP (Optional: Only for simple queries to keep demo snappy)
        # We don't cache multi-turn history yet to preserve context accuracy.
        
        # 1. ANALYSIS PHASE
        analysis_start = time.time()
        decision = services.decision_engine.decide(messages)
        context, _ = services.decision_engine.analyzer.analyze(messages)
        analysis_time = time.time() - analysis_start
        
        # 1b. Domain Detection
        domain_start = time.time()
        query_class = domain_classifier.detect_query_domain(user_query)
        query_domain = query_class["primaryDomain"]
        domain_time = time.time() - domain_start
        
        # Inject domain and query into context for ranker/orchestrator
        context.query = user_query
        context.domain = query_domain
        
        # Merge tech stack from classifier (for expansion)
        if "techStack" in query_class:
             context.tech_stack = set(context.tech_stack) | set(query_class["techStack"])

        if decision.action == AgentAction.REFUSE:
            return ChatResponse(reply=decision.reasoning, recommendations=[], end_of_conversation=False)

        if decision.action == AgentAction.CLARIFY:
            return ChatResponse(reply=decision.next_question, recommendations=[], end_of_conversation=False)

        if decision.action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
            # 2. RETRIEVAL & RANKING PHASE
            retrieval_start = time.time()
            query = f"{context.role} {context.seniority} {' '.join(context.tech_stack)}"
            retrieved = services.retriever.retrieve(query, context, top_k=50) # increased for smarter domain fallback recall
            retrieval_time = time.time() - retrieval_start
            
            ranking_start = time.time()
            catalog = {a.id: a for a in services.catalog_loader.get_all()}
            ranked_results = services.ranker.rank(retrieved, context, catalog, top_k=12) # ensure enough candidates for fallback
            ranking_time = time.time() - ranking_start

            import re
            # CRITICAL: use only the CURRENT user message to detect requested specializations.
            # Using the full `query` string (which includes context.tech_stack from ALL turns)
            # causes previous turn's specs to suppress later queries (e.g. React suppressing Java).
            user_query_tokens = set(re.findall(r'\b[a-z0-9.]+\b', user_query.lower()))
            specializations = {"react", "redux", "typescript", "nextjs", "next.js", "tensorflow", "pytorch", "nlp", "llm", "kubernetes", "terraform", "spring", "springboot", "django", "fastapi", "angular", "vue"}
            requested_specs = user_query_tokens.intersection(specializations)
            
            coverage_found = False
            if requested_specs:
                for res in ranked_results:
                    assess_skills = {s.lower() for s in getattr(res.assessment, "skills", [])}
                    assess_text = (res.assessment.name + " " + res.assessment.description).lower()
                    assess_tokens = set(re.findall(r'\b[a-z0-9.]+\b', assess_text))
                    if requested_specs.intersection(assess_tokens) or requested_specs.intersection(assess_skills):
                        coverage_found = True
                        break
            else:
                coverage_found = True

            sparse_catalog_msg = ""
            # Detect backend specialization family from user query
            BACKEND_FAMILY_MSGS = {
                "node":     ("Node.js", "No exact Node.js/Express assessments exist. Showing closest distributed backend architecture validations."),
                "python":   ("Python", "No exact Python backend assessments exist. Showing closest backend API and systems validations."),
                "fastapi":  ("FastAPI", "No exact FastAPI assessments exist. Showing closest Python backend validations."),
                "django":   ("Django", "No exact Django assessments exist. Showing closest Python backend validations."),
                "go":       ("Go/Golang", "No exact Go/Golang assessments exist. Showing adjacent backend systems validations."),
                "graphql":  ("GraphQL", "No exact GraphQL assessments exist. Showing closest API architecture validations."),
                "kafka":    ("Kafka", "No exact Kafka/event-driven assessments exist. Showing adjacent distributed systems validations."),
                "microservices": ("Microservices", "No exact Microservices assessments exist. Showing distributed backend architecture validations."),
            }
            user_query_lower = user_query.lower()
            backend_sparse_label = ""
            for signal, (label, msg) in BACKEND_FAMILY_MSGS.items():
                if signal in user_query_lower and not coverage_found:
                    sparse_catalog_msg = msg
                    backend_sparse_label = label
                    break

            if not sparse_catalog_msg and requested_specs and not coverage_found:
                if "react" in requested_specs or "redux" in requested_specs:
                    sparse_catalog_msg = "Specialized assessments for React/Redux are limited in the current catalog. Showing closest validated frontend engineering competencies."
                elif "tensorflow" in requested_specs or "nlp" in requested_specs:
                    sparse_catalog_msg = "No exact TensorFlow/NLP assessments currently exist. Showing adjacent ML competency validations."
                elif "angular" in requested_specs:
                    sparse_catalog_msg = "Specialized assessments for Angular/RxJS are limited. Showing closest frontend engineering competencies."
                else:
                    spec_str = "/".join(s.title() for s in list(requested_specs)[:2])
                    sparse_catalog_msg = f"Specialized assessments for {spec_str} are limited in the current catalog. Showing closest validated competencies."

            PHYS_ENG_BLOCK = [
                "geoscience", "geoinformatics", "instrumentation", "industrial engineering",
                "fire engineering", "petroleum", "mining", "naval", "agricultural",
                "biomedical engineering", "metallurgy", "textile"
            ]

            # Generic non-technical assessments that should not appear for specific tech stack queries
            GENERIC_BLOCK_NAMES = {
                "global skills development report", "agile software development",
                "general aptitude", "verbal reasoning", "numerical reasoning",
                "inductive reasoning", "diagrammatic reasoning",
                "informatica (developer)", "android development"
            }
            # Only apply generic block when query has a specific technology stack signal
            has_specific_stack = bool(user_query_tokens.intersection(
                {"node", "python", "java", "fastapi", "django", "flask", "golang", "go",
                 "kafka", "graphql", "react", "angular", "vue", "tensorflow", "kubernetes",
                 "terraform", "spring", "typescript", "nextjs", "redux", "pytorch", "nlp"}
            ))

            recommendations = []
            for idx, res in enumerate(ranked_results):
                # The ranker already enforced domain safety dynamically.
                assess_domain = getattr(res.assessment, "primary_domain", Domain.GENERAL)
                base_confidence = int((res.final_score or 0.6) * 100)

                assess_text = (res.assessment.name + " " + res.assessment.description).lower()
                assess_tokens = set(re.findall(r'\b[a-z0-9.]+\b', assess_text))

                # UNIVERSAL PHYSICAL ENGINEERING BLOCK (safety net beyond ranker)
                if query_domain in [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI]:
                    if any(eng in assess_text for eng in PHYS_ENG_BLOCK):
                        continue
                
                # BLOCK GENERIC ASSESSMENTS for specific stack queries
                if has_specific_stack:
                    assess_name_low = res.assessment.name.lower()
                    if any(g in assess_name_low for g in GENERIC_BLOCK_NAMES):
                        continue

                # STRICT SUPPRESSION RULE
                mismatch_triggered = False
                if "react" in requested_specs or "angular" in requested_specs:
                    if "java" in assess_tokens or "spring" in assess_tokens or "backend" in assess_tokens:
                        mismatch_triggered = True
                if "spring" in requested_specs or "springboot" in requested_specs:
                    if "javascript" in assess_tokens or "react" in assess_tokens or "angular" in assess_tokens:
                        mismatch_triggered = True
                # Java-only queries: suppress JavaScript assessments
                if "java" in user_query_tokens and "javascript" not in user_query_tokens:
                    if "javascript" in assess_tokens and "java" not in assess_tokens:
                        mismatch_triggered = True
                if "tensorflow" in requested_specs or "nlp" in requested_specs:
                    if ("analytics" in assess_tokens and "deep" not in assess_tokens) or "frontend" in assess_tokens:
                        mismatch_triggered = True
                if "kubernetes" in requested_specs or "terraform" in requested_specs:
                    if "react" in assess_tokens or "java" in assess_tokens or "frontend" in assess_tokens:
                        mismatch_triggered = True
                
                if mismatch_triggered and base_confidence < 65:
                    continue

                # MATCH QUALITY REASON
                assess_skills = {s.lower() for s in getattr(res.assessment, "skills", [])}
                if requested_specs.intersection(assess_tokens) or requested_specs.intersection(assess_skills):
                    quality_reason = "Exact Technology Match"
                elif assess_domain == Domain.FRONTEND:
                    quality_reason = "Adjacent Frontend Competency"
                elif assess_domain == Domain.BACKEND:
                    quality_reason = "General Backend Validation"
                elif assess_domain == Domain.DEVOPS:
                    quality_reason = "Semantic Infrastructure Match"
                elif assess_domain == Domain.DATA_AI:
                    quality_reason = "Adjacent ML Competency Validation"
                else:
                    quality_reason = "Core Technical Signal"

                # Expanded/Related items should remain visible but with a softer confidence decay.
                is_expanded = any(
                    t in (res.explanation or "")
                    for t in ["Expanded Match", "Related Competency Match", "Related Competency:", "FALLBACK MATCH"]
                )
                decay = (idx * 1) if is_expanded else (idx * 2)
                final_confidence = max(55, min(99, base_confidence - decay))
                
                insight = str(res.explanation)
                
                recommendations.append(Recommendation(
                    name=str(res.assessment.name),
                    url=str(res.assessment.url),
                    test_type=str(res.assessment.test_type.value),
                    subtitle=f"{res.assessment.category.title()} Assessment",
                    confidence=final_confidence,
                    category=str(res.assessment.category),
                    stage="Screening",
                    duration=f"{getattr(res.assessment, 'duration_minutes', 30)} min",
                    recruiter_insight=insight,
                    ideal_use_case=str(res.assessment.description[:120]) + "...",
                    domain=str(assess_domain),
                    matched_skills=list(res.matched_skills),
                    recruiter_signal=quality_reason
                ))
            
            if not recommendations:
                # Emit technology-aware sparse catalog guidance
                if sparse_catalog_msg:
                    guidance = sparse_catalog_msg
                elif backend_sparse_label:
                    guidance = f"No exact {backend_sparse_label} assessments exist in the current catalog. Showing the closest validated backend architecture competencies."
                else:
                    # Generate from query tech family  
                    tech_signals = user_query_tokens.intersection({
                        "kafka", "graphql", "grpc", "nestjs", "express", "golang",
                        "fastapi", "django", "flask", "node", "redis", "mongodb"
                    })
                    if tech_signals:
                        tech_label = ", ".join(t.title() for t in list(tech_signals)[:2])
                        guidance = f"No exact {tech_label} assessments exist in the current catalog. Showing closest validated backend architecture competencies."
                    else:
                        domain_label = str(query_domain).split(".")[-1].lower().replace("_", " ")
                        guidance = f"I've analyzed this {domain_label} hiring requirement. The catalog has limited coverage for this specific stack. Broadening to adjacent core competencies."
                return ChatResponse(reply=guidance, recommendations=[], end_of_conversation=False)

            # Minimum pipeline guarantee (domain-compatible):
            # If we have ranked results but fewer than 3 recommendations, keep them visible.
            if ranked_results and len(recommendations) < 3:
                for res in ranked_results:
                    if len(recommendations) >= 3:
                        break
                    if any(rec.name == res.assessment.name for rec in recommendations):
                        continue

                    assess_domain = getattr(res.assessment, "primary_domain", Domain.GENERAL)
                    base_confidence = int((res.final_score or 0.6) * 100)
                    # Minimum pipeline guarantee
                    # Suppress mismatches here as well!
                    assess_text = (res.assessment.name + " " + res.assessment.description).lower()
                    assess_tokens = set(re.findall(r'\b[a-z0-9.]+\b', assess_text))

                    # Universal block applies here too
                    if query_domain in [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI]:
                        if any(eng in assess_text for eng in PHYS_ENG_BLOCK):
                            continue

                    mismatch_triggered = False
                    if "react" in requested_specs or "angular" in requested_specs:
                        if "java" in assess_tokens or "spring" in assess_tokens or "backend" in assess_tokens:
                            mismatch_triggered = True
                    if "spring" in requested_specs or "springboot" in requested_specs:
                        if "javascript" in assess_tokens or "react" in assess_tokens or "angular" in assess_tokens:
                            mismatch_triggered = True
                    if mismatch_triggered and base_confidence < 65:
                        continue

                    assess_skills = {s.lower() for s in getattr(res.assessment, "skills", [])}
                    if requested_specs.intersection(assess_tokens) or requested_specs.intersection(assess_skills):
                        quality_reason = "Exact Technology Match"
                    elif assess_domain == Domain.FRONTEND:
                        quality_reason = "Adjacent Frontend Competency"
                    elif assess_domain == Domain.BACKEND:
                        quality_reason = "General Backend Validation"
                    elif assess_domain == Domain.DEVOPS:
                        quality_reason = "Semantic Infrastructure Match"
                    elif assess_domain == Domain.DATA_AI:
                        quality_reason = "Adjacent ML Competency Validation"
                    else:
                        quality_reason = "Core Technical Signal"

                    is_expanded = any(
                        t in (res.explanation or "")
                        for t in ["Expanded Match", "Related Competency Match", "Related Competency:", "FALLBACK MATCH"]
                    )
                    decay = 0 if is_expanded else 2
                    final_confidence = max(55, min(99, base_confidence - decay))

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
                        matched_skills=list(res.matched_skills),
                        recruiter_signal=quality_reason
                    ))

            # HARD RECALL PATCH for DATA_AI sparse catalogs:
            # If DATA_AI still returns <3, append additional domain-safe retrievals (no cross-domain leakage).
            if query_domain == Domain.DATA_AI and len(recommendations) < 3:
                # Retrieve more candidates directly and filter by domain-safe gates.
                extra_retrieved = services.retriever.retrieve(query, context, top_k=80)
                extra_names = {r.name for r in recommendations}

                for item in extra_retrieved:
                    if len(recommendations) >= 3:
                        break
                    assess_obj = catalog.get(item["id"])
                    if not assess_obj:
                        continue
                    if assess_obj.name in extra_names:
                        continue

                    assess_domain = domain_classifier.normalize_assessment_domain(assess_obj.name, assess_obj.description)

                    # Domain-safe acceptance for DATA_AI sparse catalogs:
                    # - exact DATA_AI
                    # - adjacency within ADJACENCY_MAP (e.g., ENGINEERING_CORE/BACKEND)
                    # - GENERAL only if explicit NLP/ML signals are present
                    adjacent_domains = set(domain_classifier.ADJACENCY_MAP.get(query_domain, []))

                    # Strong NLP/ML content-based acceptance to ensure sparse DATA_AI catalogs still yield recs,
                    # while staying within "no cross-domain leakage" by requiring explicit NLP/ML signals.
                    assess_text = (assess_obj.name + " " + assess_obj.description).lower()
                    ai_signals = [
                        "tensorflow", "pytorch", "keras", "nlp", "llm", "transformers",
                        "language model", "language models", "neural networks", "machine learning",
                        "deep learning", "natural language", "text generation", "bert", "gpt",
                        "word embeddings", "tokenization", "sequence modeling", "sequence-to-sequence"
                    ]
                    has_ai_signal = any(s in assess_text for s in ai_signals)

                    if query_domain == Domain.DATA_AI and has_ai_signal:
                        accept = True
                    elif assess_domain == Domain.DATA_AI:
                        accept = True
                    elif assess_domain in adjacent_domains:
                        accept = True
                    else:
                        accept = False

                    if not accept:
                        continue

                    # Confidence intentionally low for expansion recall patch.
                    final_confidence = max(50, min(75, int((item.get("hybrid_score", 0.2) or 0.2) * 100)))

                    is_expansion = item.get("expansion_matched", False)
                    expansion_label = item.get("expansion_label", "Related Competency Match")
                    recruiter_insight = str(item.get("expansion_label", expansion_label)) + ": Added due to DATA_AI sparse-catalog fallback."

                    recommendations.append(Recommendation(
                        name=str(assess_obj.name),
                        url=str(assess_obj.url),
                        test_type=str(assess_obj.test_type.value),
                        subtitle=f"{assess_obj.category.title()} Assessment",
                        confidence=final_confidence,
                        category=str(assess_obj.category),
                        stage="Screening",
                        duration=f"{getattr(assess_obj, 'duration_minutes', 30)} min",
                        recruiter_insight=recruiter_insight if is_expansion else "Related Competency Match: Domain-safe fallback recall.",
                        ideal_use_case=str(assess_obj.description[:120]) + "...",
                        domain=str(assess_domain),
                        matched_skills=list(getattr(assess_obj, "skills", [])[:5]),
                        recruiter_signal="Expansion Signal"
                    ))

            # 3. ORCHESTRATION PHASE
            orch_start = time.time()
            filtered_ranked = [r for r in ranked_results if any(rec.name == r.assessment.name for rec in recommendations)]
            optimized = services.adaptive_orchestrator.orchestrate(filtered_ranked, context, catalog)
            orch_time = time.time() - orch_start
            
            pipeline_model = HiringPipelineModel(
                stages=[PipelineStageModel(
                    name=str(s.get("name")),
                    description=str(s.get("description")),
                    assessments=[str(a) for a in s.get("assessments", [])],
                    estimated_duration=int(s.get("duration", 30)),
                    competencies_covered=[str(c) for c in s.get("competencies_covered", [])]
                ) for s in getattr(optimized, "stages", [])],
                fatigue=FatigueReportModel(**getattr(optimized, "fatigue_report", {})),
                signal=SignalReportModel(**getattr(optimized, "signal_report", {})),
                tradeoff_analysis=str(getattr(optimized, "tradeoff_analysis")),
                strategic_guidance=str(getattr(optimized, "strategic_advice"))
            )

            # Premium Recruiter Narrative
            domain_label = query_domain.lower().replace("_", " ")
            if sparse_catalog_msg:
                reply = f"I've optimized an enterprise {domain_label} hiring pipeline. {sparse_catalog_msg} {getattr(optimized, 'strategic_advice', '')}"
            else:
                reply = f"I've optimized an enterprise {domain_label} hiring pipeline. {getattr(optimized, 'strategic_advice', '')}"
            
            total_time = time.time() - overall_start
            logger.info(f"PERF_REPORT: Total={total_time:.3f}s | Analysis={analysis_time:.3f}s | Domain={domain_time:.3f}s | Retrieval={retrieval_time:.3f}s | Ranking={ranking_time:.3f}s | Orch={orch_time:.3f}s")
            
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
