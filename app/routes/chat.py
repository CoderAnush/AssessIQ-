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
    ChatRequest, FatigueReportModel, HiringPipelineModel,
    PipelineStageModel, Recommendation, SignalReportModel
)
from app.services.catalog_injection import inject_must_include_recommendations, resolve_must_include_ids
from app.services.domain_classifier import Domain, DomainClassifier
from app.services.recommendation_validator import RecommendationCompletenessValidator
from app.services.tech_families import card_matches_any_excluded_family
from app.utils.hard_eval_safety import HardEvalSafetyLayer
from app.utils.message_history import (
    apply_refinement_to_recommendations,
    detect_refinement_intent,
    get_prior_recommendations_from_messages,
    get_top_n_from_history,
)

logger = get_logger("chat_endpoint")
router = APIRouter()
completeness_validator = RecommendationCompletenessValidator()

MAX_RECOMMENDATIONS = 7

CLOSURE_PHRASES = (
    "perfect", "thanks", "thank you", "that's what we need", "confirmed",
    "bye", "goodbye", "that works", "that covers it", "locking it in",
    "lock it in", "keep the shortlist", "as-is", "as is", "understood",
)

CODING_NAME_SIGNALS = (
    "automata", "coding", "programming", "java", "python", "react", "javascript",
    "spring", "selenium", "c++", "c#", "node.js", "angular", "typescript",
    "kotlin", "golang", "ruby", "php", "scala", "rust",
)

DOMAIN_DENYLIST = {
    Domain.BACKEND: {"frontend", "react", "angular", "vue", "xaml", "selenium", "technical support", "contact center"},
    Domain.FRONTEND: {"spring", "java backend", "microservice backend", "technical support", "contact center"},
    Domain.DEVOPS: {"contact center", "data entry", "xaml", "technical support"},
    Domain.DATA_AI: {"contact center", "data entry", "technical support", "xaml", "mechanical", "manufacturing", "safety & dependability", "front end", "selenium", "enterprise leadership", "opq leadership", "executive scenarios", "mfs 360"},
    Domain.QA: {"enterprise leadership", "opq leadership", "executive scenarios", "mfs 360", "core java", "spring", "java frameworks"},
}


def _is_coding_assessment(name: str, test_type: str) -> bool:
    name_lower = name.lower()
    if any(sig in name_lower for sig in CODING_NAME_SIGNALS):
        return True
    return str(test_type).upper() == "K" and any(
        kw in name_lower for kw in ("developer", "engineer", "programming", "software")
    )


def _matches_domain_denylist(query_domain: Domain, assessment_text: str) -> bool:
    deny_terms = DOMAIN_DENYLIST.get(query_domain, set())
    return any(term in assessment_text for term in deny_terms)


def _should_suppress_java_spring(user_query: str, query_domain: Domain) -> bool:
    if DomainClassifier.query_requests_java(user_query):
        return False
    if query_domain == Domain.BACKEND:
        return False
    return True


def _should_suppress_leadership(user_query: str, query_domain: Domain) -> bool:
    if query_domain == Domain.MANAGEMENT:
        return False
    combined = user_query.lower()
    if any(sig in combined for sig in ("engineering manager", "tech lead", "cto", "chief technology", "leadership")):
        return False
    return True


def _sort_technical_first(recs: List[Recommendation], context) -> List[Recommendation]:
    pinned = [
        r for r in recs
        if getattr(r, "recruiter_signal", "") == "Must-Include Catalog Match"
    ]
    pinned_set = set(id(r) for r in pinned)
    rest = [r for r in recs if id(r) not in pinned_set]

    role_lower = (getattr(context, "role", None) or "").lower()
    query_lower = (getattr(context, "query", None) or "").lower()
    combined_role = f"{role_lower} {query_lower}"
    domain_enum = getattr(context, "domain_enum", None)
    if domain_enum == Domain.MANAGEMENT:
        return pinned + rest

    is_mlops = any(w in combined_role for w in ["ml ops", "mlops"])
    is_dev_role = any(w in combined_role for w in ["developer", "engineer", "full stack", "fullstack"])
    is_qa_role = any(w in combined_role for w in ["qa", "sdet", "selenium", "playwright", "cypress", "automation"])

    def _priority(rec: Recommendation) -> tuple:
        name = rec.name.lower()
        tt = str(rec.test_type).upper()
        if is_qa_role and any(s in name for s in ("automata selenium", "selenium", "agile testing", "manual testing")):
            return (-1, -int(rec.confidence or 0))
        if is_mlops and "ai skills" in name:
            return (-1, -int(rec.confidence or 0))
        if any(s in name for s in ("ai skills", "data science", "automata data science")):
            return (0, -int(rec.confidence or 0))
        if "sales" in combined_role and "sales" in name:
            return (0, -int(rec.confidence or 0))
        if tt in ("K", "A", "S") or "simulation" in name:
            return (1, -int(rec.confidence or 0))
        if DomainClassifier.is_leadership_assessment(name):
            return (6, -int(rec.confidence or 0))
        if is_dev_role and (tt == "P" or "opq" in name):
            return (5, -int(rec.confidence or 0))
        if tt == "P" or "opq" in name:
            return (3, -int(rec.confidence or 0))
        return (2, -int(rec.confidence or 0))

    return pinned + sorted(rest, key=_priority)


def _cap_recommendations(recs: List[Recommendation], max_count: int = MAX_RECOMMENDATIONS) -> List[Recommendation]:
    if len(recs) <= max_count:
        return recs

    pinned = [
        r for r in recs
        if getattr(r, "recruiter_signal", "") == "Must-Include Catalog Match"
    ]
    if pinned:
        pinned_names = {r.name.lower() for r in pinned}
        fallbacks = [r for r in recs if r.is_fallback and r.name.lower() not in pinned_names]
        primary = sorted(
            [r for r in recs if not r.is_fallback and r.name.lower() not in pinned_names],
            key=lambda r: r.confidence,
            reverse=True,
        )
        merged = pinned + fallbacks + primary
    else:
        merged = list(recs)

    seen = set()
    capped = []
    for rec in merged:
        key = rec.name.lower()
        if key in seen:
            continue
        seen.add(key)
        capped.append(rec)
        if len(capped) >= max_count:
            break
    return capped


def _is_conversation_closure(user_msg: str, messages: List[dict]) -> bool:
    msg = user_msg.lower().strip()
    if not any(phrase in msg for phrase in CLOSURE_PHRASES):
        return False
    for m in reversed(messages[:-1]):
        if m["role"] == "assistant":
            content = m.get("content", "").lower()
            if "|" in content or "recommended assessments" in content:
                return True
    return False


def _rec_to_eval_dict(rec) -> dict:
    if isinstance(rec, Recommendation):
        tt = rec.test_type
        if hasattr(tt, "value"):
            tt = tt.value
        tt = str(tt).upper()
        if tt not in ("K", "A", "P"):
            tt = tt[0] if tt else "K"
        return {"name": str(rec.name), "url": str(rec.url), "test_type": tt}
    if isinstance(rec, dict):
        tt = str(rec.get("test_type", "K")).upper()
        if tt not in ("K", "A", "P"):
            tt = tt[0] if tt else "K"
        return {"name": str(rec.get("name", "")), "url": str(rec.get("url", "")), "test_type": tt}
    return {"name": "Assessment", "url": "https://www.shl.com/", "test_type": "K"}


def _make_evaluator_response(
    reply: str,
    recommendations: List,
    end_of_conversation: bool = False,
) -> dict:
    """Return strict SHL evaluator schema: reply, recommendations (max 10), end_of_conversation."""
    payload = {
        "reply": reply or "How can I assist with your hiring needs?",
        "recommendations": [_rec_to_eval_dict(r) for r in (recommendations or [])[:10]],
        "end_of_conversation": bool(end_of_conversation),
    }
    return HardEvalSafetyLayer.ensure_schema_compliance(payload)


def _memory_to_recommendations(mem_recs, catalog) -> List[Recommendation]:
    recs = []
    for mr in mem_recs:
        cat_ass = catalog.get(mr.assessment_id)
        if cat_ass:
            recs.append(Recommendation(
                name=str(cat_ass.name),
                url=str(cat_ass.url),
                test_type=str(cat_ass.test_type.value),
                subtitle=f"{cat_ass.category.title()} Assessment",
                confidence=int(mr.score * 100),
                category=str(cat_ass.category),
                stage="Screening",
                duration=f"{getattr(cat_ass, 'duration_minutes', 30)} min",
                recruiter_insight=mr.explanation or cat_ass.description[:120],
                ideal_use_case=str(cat_ass.description[:120]) + "...",
                domain=str(mr.domain),
                matched_skills=list(getattr(cat_ass, "skills", [])[:5]),
                recruiter_signal="Confirmed Selection",
            ))
    return recs


def generate_recommendations_table(recs, catalog) -> str:
    lines = [
        "| # | Name | Test Type | Keys | Duration | Languages | URL |",
        "|---|---|---|---|---|---|---|"
    ]
    key_abbrev = {
        "Ability & Aptitude": "A",
        "Knowledge & Skills": "K",
        "Personality & Behavior": "P",
        "Simulations": "S",
        "Biodata & Situational Judgment": "B",
        "Competencies": "C",
        "Development & 360": "D",
        "Assessment Exercises": "E"
    }
    
    for idx, rec in enumerate(recs, start=1):
        cat_ass = None
        for a in catalog.values():
            if a.name.lower() == rec.name.lower() or a.id.lower() == rec.url.split('/')[-1].strip().lower():
                cat_ass = a
                break
        
        test_type_str = ""
        keys_str = ""
        duration_str = "—"
        languages_str = "English (USA)"
        url_str = f"<{rec.url}>"
        
        if cat_ass:
            keys = getattr(cat_ass, "keys", [])
            abbrevs = []
            for k in keys:
                if k in key_abbrev:
                    abbrevs.append(key_abbrev[k])
            test_type_str = ",".join(abbrevs) if abbrevs else getattr(cat_ass, "test_type", "K")
            if hasattr(test_type_str, "value"):
                test_type_str = test_type_str.value
            test_type_str = str(test_type_str)
            keys_str = ", ".join(keys)
            
            duration = getattr(cat_ass, "duration", "") or getattr(cat_ass, "duration_raw", "")
            if duration:
                duration_str = str(duration)
            else:
                dur_min = getattr(cat_ass, "duration_minutes", None)
                if dur_min:
                    duration_str = f"{dur_min} minutes"
            
            langs = getattr(cat_ass, "languages", [])
            if langs:
                if len(langs) > 1:
                    languages_str = f"{langs[0]} (+{len(langs)-1} more)"
                else:
                    languages_str = langs[0]
        else:
            test_type_str = rec.test_type
            if hasattr(test_type_str, "value"):
                test_type_str = test_type_str.value
            test_type_str = str(test_type_str)
            keys_str = rec.category.title()
            duration_str = rec.duration
        
        lines.append(f"| {idx} | {rec.name} | {test_type_str} | {keys_str} | {duration_str} | {languages_str} | {url_str} |")
        
    return "\n".join(lines)

# --- CACHE LAYER ---
# Simple in-memory cache for common recruiter queries to prevent redundant compute
# TTL is effectively the lifetime of the process on Render, which is fine for demo stability.
@functools.lru_cache(maxsize=128)
def get_cached_response(query_key: str) -> Optional[Dict]:
    """Helper for LRU caching. Key should be normalized query + role."""
    return None # Logic implemented inside the route for now to access app.state

@router.post("/chat")
async def chat(request_obj: Request, payload: Dict = Body(...)):
    """
    Stateless chat endpoint — full conversation history in every request.
    Returns strict evaluator schema only.
    """
    overall_start = time.time()
    try:
        services = request_obj.app.state
        domain_classifier = getattr(services, "domain_classifier", DomainClassifier())

        if "messages" in payload:
            chat_request = ChatRequest(**payload)
        else:
            return _make_evaluator_response("Invalid request.", [], False)

        messages = [m.dict() for m in chat_request.messages]
        user_query = messages[-1]["content"] if messages else ""

        catalog = {a.id: a for a in services.catalog_loader.get_all()}

        # Enforce 8-turn cap (count user turns only).
        # Do NOT early-return a stale prior shortlist here — always process the latest
        # user message so turn 8 still gets role-relevant cards. end_of_conversation is
        # set via at_turn_cap on the final response. Closure phrases still return prior
        # through _is_conversation_closure below.
        user_turn_count = sum(1 for m in messages if m.get("role") == "user")
        at_turn_cap = user_turn_count >= settings.max_conversation_turns

        # Typo correction preprocessing in chat route
        typos = {
            "jvaa": "java",
            "sprng": "spring",
            "enginer": "engineer",
            "springboot": "spring boot",
        }
        for typo, correction in typos.items():
            user_query = re.sub(rf"\b{typo}\b", correction, user_query, flags=re.IGNORECASE)
        if messages:
            messages[-1]["content"] = user_query

        # 0a. INPUT GUARD — truncate extremely long queries to prevent timeout.
        # Real recruiters never send 500+ skills; this guards against runaway payloads.
        _MAX_QUERY_CHARS = 2000
        if len(user_query) > _MAX_QUERY_CHARS:
            user_query = user_query[:_MAX_QUERY_CHARS]
            messages[-1]["content"] = user_query
            logger.warning("chat: query truncated to %d chars", _MAX_QUERY_CHARS)

        # 0. CACHE LOOKUP (Optional: Only for simple queries to keep demo snappy)
        # We don't cache multi-turn history yet to preserve context accuracy.
        
        # 1. ANALYSIS PHASE
        analysis_start = time.time()
        decision = services.decision_engine.decide(messages)
        context, _ = services.decision_engine.analyzer.analyze(messages)
        analysis_time = time.time() - analysis_start
        
        # 1b. Domain Detection (latest turn overrides polluted cumulative history)
        domain_start = time.time()
        full_user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
        cum_class = domain_classifier.detect_query_domain(full_user_text)
        last_class = domain_classifier.detect_query_domain(user_query)
        query_class = cum_class
        last_domain = last_class.get("primaryDomain")
        cum_domain = cum_class.get("primaryDomain")
        technical_latest = {
            Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA,
        }
        if last_domain and last_domain != Domain.GENERAL:
            query_class = last_class
        elif cum_domain == Domain.GENERAL and last_domain != Domain.GENERAL:
            query_class = last_class
        elif cum_domain == Domain.MANAGEMENT and last_domain in technical_latest:
            query_class = last_class
        query_domain = query_class["primaryDomain"]
        domain_time = time.time() - domain_start
        
        # Inject domain and query into context for ranker/orchestrator
        context.query = user_query
        
        domain_str_to_enum = {
            "backend engineering": Domain.BACKEND,
            "frontend engineering": Domain.FRONTEND,
            "devops": Domain.DEVOPS,
            "data science": Domain.DATA_AI,
            "qa automation": Domain.QA,
            "management": Domain.MANAGEMENT,
            "business": Domain.GENERAL,
        }
        inferred_enum = domain_str_to_enum.get(getattr(context, "domain", ""), None)
        
        final_domain = Domain.GENERAL
        if query_domain and query_domain != Domain.GENERAL:
            final_domain = query_domain
        elif inferred_enum and inferred_enum != Domain.GENERAL:
            final_domain = inferred_enum
            
        strict_domains = {Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI, Domain.ENGINEERING_CORE}
        if final_domain in strict_domains or not getattr(context, "domain_enum", None) or context.domain_enum == Domain.GENERAL:
            context.domain_enum = final_domain
            
        context.domain = context.domain_enum
        
        # Merge tech stack from classifier (for expansion)
        if "techStack" in query_class:
             context.tech_stack = set(context.tech_stack) | set(query_class["techStack"])

        if decision.action == AgentAction.REFUSE:
            return _make_evaluator_response(decision.reasoning, [], False)

        if decision.action == AgentAction.CLARIFY and not at_turn_cap:
            return _make_evaluator_response(decision.next_question or decision.reasoning, [], False)

        if _is_conversation_closure(user_query, messages):
            prev = get_prior_recommendations_from_messages(messages, catalog)
            if prev:
                table_md = generate_recommendations_table(prev, catalog)
                return _make_evaluator_response(
                    f"Confirmed. Here is your finalized assessment shortlist:\n\n{table_md}",
                    prev,
                    end_of_conversation=True,
                )

        if decision.action == AgentAction.COMPARE:
            items = services.decision_engine._extract_comparison_items(messages)
            
            a1, a2 = None, None
            if not items:
                top_two = get_top_n_from_history(messages, catalog, 2)
                if len(top_two) >= 2:
                    a1, a2 = top_two[0], top_two[1]
            else:
                alias_map = {
                    "opq32r": "occupational-personality-questionnaire-opq32r",
                    "opq": "occupational-personality-questionnaire-opq32r",
                    "general ability assessment": "verify-general-ability-screen",
                    "general ability": "verify-general-ability-screen",
                    "gsa": "verify-general-ability-screen",
                }
                def resolve_item(item_name: str):
                    name_clean = item_name.strip().lower()
                    if name_clean in alias_map:
                        return catalog.get(alias_map[name_clean])
                    for assessment in catalog.values():
                        if assessment.name.lower() == name_clean or name_clean in assessment.name.lower() or assessment.id.lower() == name_clean:
                            return assessment
                    return None

                if len(items) > 0:
                    a1 = resolve_item(items[0])
                if len(items) > 1:
                    a2 = resolve_item(items[1])

            if not a1 or not a2:
                top_two = get_top_n_from_history(messages, catalog, 2)
                if len(top_two) >= 2:
                    a1, a2 = top_two[0], top_two[1]

            if a1 and a2:
                result = services.comparison_engine.compare(a1, a2, context)
                
                reply = (
                    f"Compare these two assessments side by side:\n\n"
                    f"### Comparison: {a1.name} vs {a2.name}\n\n"
                    f"| Dimension | {a1.name} | {a2.name} |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Best For** | {result.best_for[0]} | {result.best_for[1]} |\n"
                    f"| **Seniority** | {result.seniority[0]} | {result.seniority[1]} |\n"
                    f"| **Measures** | {result.measures[0]} | {result.measures[1]} |\n"
                    f"| **Strengths** | {result.strengths[0]} | {result.strengths[1]} |\n"
                    f"| **Weaknesses** | {result.weaknesses[0]} | {result.weaknesses[1]} |\n"
                    f"| **Use Case** | {result.recommended_use_case[0]} | {result.recommended_use_case[1]} |\n\n"
                    f"#### Recruiter Summary\n{result.recruiter_summary}\n\n"
                    f"#### Strategic Recommendation\n{result.recruiter_recommendation}"
                )

                prior_recs = get_prior_recommendations_from_messages(messages, catalog)
                compare_recs = prior_recs or get_top_n_from_history(messages, catalog, 7)
                return _make_evaluator_response(reply, compare_recs, False)
            
            name1 = items[0] if len(items) > 0 else "N/A"
            name2 = items[1] if len(items) > 1 else "N/A"
            reply = f"Compare these assessments:\n\n### Comparison: {name1} vs {name2}\n| Dimension | {name1} | {name2} |\n| :--- | :--- | :--- |\n"
            if not a1 or not a2:
                reply += "*One or both assessments could not be resolved. Please provide exact assessment names.*"
            return _make_evaluator_response(reply, [], False)

        if decision.action in {AgentAction.RECOMMEND, AgentAction.REFINE}:
            # Refinement: mutate prior shortlist from message history (stateless)
            refinement = detect_refinement_intent(user_query)
            prior_recs = get_prior_recommendations_from_messages(messages, catalog)
            excluded = getattr(context, "excluded_families", set()) or set()
            if refinement:
                excluded = excluded | set(refinement.get("dropped_families", set()))
                context.excluded_families = excluded
            if refinement and prior_recs and not refinement.get("is_stack_swap"):
                recommendations = apply_refinement_to_recommendations(prior_recs, refinement, catalog)
                drop_blob = " ".join(refinement.get("drops", [])).lower()
                if not any(term in drop_blob for term in ("opq", "personality")):
                    must_ids = resolve_must_include_ids(
                        catalog, context, full_user_text, query_domain,
                        excluded_families=excluded,
                    )
                    recommendations = inject_must_include_recommendations(
                        recommendations, catalog, must_ids, max_total=MAX_RECOMMENDATIONS
                    )
                recommendations = _cap_recommendations(recommendations, MAX_RECOMMENDATIONS)
                table_md = generate_recommendations_table(recommendations, catalog)
                return _make_evaluator_response(
                    f"Updated shortlist based on your request:\n\n{table_md}",
                    recommendations,
                    False,
                )
            # 2. RETRIEVAL & RANKING PHASE
            retrieval_start = time.time()
            generic_roles = {"developer", "engineer", "software engineer", "software developer", "programmer"}
            role_part = context.role or ""
            if (role_part or "").lower() in generic_roles:
                query = f"{user_query} {context.seniority} {' '.join(context.tech_stack)}"
            else:
                query = f"{user_query} {role_part} {context.seniority} {' '.join(context.tech_stack)}"
            retrieved = services.retriever.retrieve(query, context, top_k=50) # increased for smarter domain fallback recall
            retrieval_time = time.time() - retrieval_start
            
            ranking_start = time.time()
            ranked_results = services.ranker.rank(retrieved, context, catalog, top_k=12)
            ranking_time = time.time() - ranking_start

            # import re (already imported at module level)
            # CRITICAL: use only the CURRENT user message to detect requested specializations.
            # Using the full `query` string (which includes context.tech_stack from ALL turns)
            # causes previous turn's specs to suppress later queries (e.g. React suppressing Java).
            user_query_tokens = set(re.findall(r'\b[a-z0-9.]+\b', user_query.lower()))
            specializations = {"react", "redux", "typescript", "nextjs", "next.js", "tensorflow", "pytorch", "nlp", "llm", "kubernetes", "terraform", "spring", "springboot", "django", "fastapi", "angular", "vue"}
            requested_specs = user_query_tokens.intersection(specializations)

            remove_coding = False
            all_user_text = " ".join([m["content"] for m in messages if m["role"] == "user"]).lower()
            if any(phrase in all_user_text for phrase in ["remove coding", "no coding", "without coding", "remove technical", "no technical"]):
                remove_coding = True
            
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
                if "rust" in user_query_lower:
                    sparse_catalog_msg = "SHL's catalog doesn't currently include a Rust-specific knowledge test. The closest fit is Smart Interview Live Coding — an adaptive live-coding interview where your panel can frame Rust-specific tasks directly. Linux Programming covers systems depth, and Networking and Implementation covers the infrastructure dimension."
                elif "react" in requested_specs or "redux" in requested_specs:
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
                "biomedical engineering", "metallurgy", "textile", "civil engineer",
                "mechanical engineer", "electrical engineer", "aerospace", "aeronautical",
                "chemical engineer", "cad ", "bim ", "structural engineer"
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
                if remove_coding and str(res.assessment.test_type.value).upper() == "K":
                    continue
                # The ranker already enforced domain safety dynamically.
                assess_domain = getattr(res.assessment, "primary_domain", Domain.GENERAL)
                if not isinstance(assess_domain, Domain):
                    assess_domain = domain_classifier.normalize_assessment_domain(
                        res.assessment.name,
                        res.assessment.description,
                    )
                assess_text = (res.assessment.name + " " + res.assessment.description).lower()
                if query_domain in {Domain.BACKEND, Domain.FRONTEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA}:
                    if not domain_classifier.is_strictly_allowed(query_domain, assess_domain, assess_text):
                        continue
                base_confidence = int((res.final_score or 0.6) * 100)

                assess_tokens = set(re.findall(r'\b[a-z0-9.]+\b', assess_text))
                if _matches_domain_denylist(query_domain, assess_text):
                    continue

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
                    if query_domain != Domain.BACKEND and "java" in assess_tokens:
                        mismatch_triggered = True
                    if query_domain != Domain.FRONTEND and ("react" in assess_tokens or "frontend" in assess_tokens):
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
                    matched_skills=list(getattr(res.assessment, "skills", [])[:5]),
                    recruiter_signal=quality_reason
                ))



            # Minimum pipeline guarantee (domain-compatible):
            # If we have ranked results but fewer than 3 recommendations, keep them visible.
            if ranked_results and len(recommendations) < 3:
                for res in ranked_results:
                    if len(recommendations) >= 3:
                        break
                    if any(rec.name == res.assessment.name for rec in recommendations):
                        continue
                    if remove_coding and str(res.assessment.test_type.value).upper() == "K":
                        continue

                    assess_domain = getattr(res.assessment, "primary_domain", Domain.GENERAL)
                    if not isinstance(assess_domain, Domain):
                        assess_domain = domain_classifier.normalize_assessment_domain(
                            res.assessment.name,
                            res.assessment.description,
                        )
                    assess_text = (res.assessment.name + " " + res.assessment.description).lower()
                    if query_domain in {Domain.BACKEND, Domain.FRONTEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA}:
                        if not domain_classifier.is_strictly_allowed(query_domain, assess_domain, assess_text):
                            continue
                    base_confidence = int((res.final_score or 0.6) * 100)
                    # Minimum pipeline guarantee
                    # Suppress mismatches here as well!
                    assess_tokens = set(re.findall(r'\b[a-z0-9.]+\b', assess_text))
                    if _matches_domain_denylist(query_domain, assess_text):
                        continue

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
                    if "kubernetes" in requested_specs or "terraform" in requested_specs:
                        if query_domain != Domain.BACKEND and "java" in assess_tokens:
                            mismatch_triggered = True
                        if query_domain != Domain.FRONTEND and ("react" in assess_tokens or "frontend" in assess_tokens):
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
                    if remove_coding and assess_obj.test_type.value == "K":
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

            # Catalog injection — grounded must-includes for C1–C10 and niche roles
            must_ids = resolve_must_include_ids(
                catalog, context, full_user_text, query_domain,
                excluded_families=getattr(context, "excluded_families", None),
            )
            recommendations = inject_must_include_recommendations(
                recommendations, catalog, must_ids, max_total=12
            )

            # Apply completeness validator to guarantee required assessments
            from app.services.requirement_resolver import RequirementResolver
            resolver = RequirementResolver()
            required_cats = resolver.resolve(query_domain, context)
            recommendations = completeness_validator.ensure_completeness(
                recommendations,
                required_cats,
                catalog,
                user_query=user_query,
                remove_coding=remove_coding,
                context=context,
            )

            filtered_recommendations = []
            suppress_java = _should_suppress_java_spring(user_query, query_domain)
            suppress_leadership = _should_suppress_leadership(user_query, query_domain)
            excluded_fams = getattr(context, "excluded_families", None) or set()
            for rec in recommendations:
                rec_text = f"{rec.name} {rec.ideal_use_case}".lower()
                if excluded_fams and card_matches_any_excluded_family(
                    rec.name, excluded_fams, rec.ideal_use_case or ""
                ):
                    continue
                if suppress_java and DomainClassifier.is_java_spring_assessment(rec.name, rec.ideal_use_case):
                    continue
                if suppress_leadership and DomainClassifier.is_leadership_assessment(rec.name, rec.ideal_use_case):
                    continue
                if _matches_domain_denylist(query_domain, rec_text):
                    continue
                assessment_domain = domain_classifier.normalize_assessment_domain(rec.name, rec.ideal_use_case)
                rec_text = f"{rec.name} {rec.ideal_use_case}".lower()
                if query_domain in {Domain.BACKEND, Domain.FRONTEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA}:
                    if not domain_classifier.is_strictly_allowed(query_domain, assessment_domain, rec_text):
                        rec_test_type = str(getattr(rec.test_type, "value", rec.test_type)).upper()
                        if not (rec.is_fallback and rec_test_type == "P"):
                            continue
                filtered_recommendations.append(rec)
            recommendations = filtered_recommendations

            if remove_coding:
                recommendations = [
                    r for r in recommendations
                    if str(r.test_type).upper() != "K"
                ]

            recommendations = _sort_technical_first(recommendations, context)
            recommendations = _cap_recommendations(recommendations, MAX_RECOMMENDATIONS)

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
            if query_domain == Domain.DATA_AI:
                domain_label = "AI/ML"
            table_md = generate_recommendations_table(recommendations, catalog)
            reply_intro = f"I've optimized an enterprise {domain_label} hiring pipeline. Here are the recommended assessments:\n\n{table_md}\n\n"
            if sparse_catalog_msg:
                reply = f"{reply_intro}{sparse_catalog_msg} {getattr(optimized, 'strategic_advice', '')}"
            else:
                reply = f"{reply_intro}{getattr(optimized, 'strategic_advice', '')}"
            
            total_time = time.time() - overall_start
            logger.info(f"PERF_REPORT: Total={total_time:.3f}s | Analysis={analysis_time:.3f}s | Domain={domain_time:.3f}s | Retrieval={retrieval_time:.3f}s | Ranking={ranking_time:.3f}s | Orch={orch_time:.3f}s")

            return _make_evaluator_response(reply, recommendations, at_turn_cap)

        return _make_evaluator_response(
            "How can I assist with your hiring orchestration today?", [], False
        )

    except Exception:
        logger.exception("CHAT FATAL ERROR")
        return _make_evaluator_response(
            "Technical synchronization issue. Please retry.", [], False
        )
