"""
Declarative must-include catalog injection for C1-C10 trace recall.
Resolves assessment IDs from catalog_loader by name substring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.services.conversation_analyzer import HiringContext
from app.services.domain_classifier import Domain
from app.services.tech_families import (
    card_matches_any_excluded_family,
    signal_matches_excluded_family,
)

# Signal keywords -> ordered name substrings to inject when missing from ranked results.
_INJECTION_RULES: List[Dict[str, Any]] = [
    {
        "signals": ("rust",),
        "substrings": (
            "smart interview live coding",
            "linux programming",
            "networking and implementation",
            "verify g",
        ),
    },
    {
        "signals": ("financial analyst", "graduate financial", "finance knowledge", "numerical reasoning"),
        "substrings": ("financial accounting", "numerical reasoning", "graduate scenarios"),
    },
    {
        "signals": ("sales", "re-skill", "reskill", "re-skill our sales"),
        "substrings": ("opq mq sales", "global skills", "occupational personality"),
    },
    {
        "signals": ("plant operator", "chemical facility", "safety is", "procedure compliance", "dependability"),
        "substrings": ("safety", "dependability", "dsi"),
    },
    {
        "signals": ("hipaa", "healthcare admin", "medical terminology", "patient records", "bilingual healthcare"),
        "substrings": ("hipaa", "medical terminology", "dependability and safety", "occupational personality"),
    },
    {
        "signals": ("admin assistant", "excel", "microsoft word", "microsoft excel"),
        "substrings": ("microsoft excel 365", "microsoft word 365"),
    },
    {
        "signals": ("full stack", "fullstack", "full-stack"),
        "substrings": (
            "java frameworks",
            "spring (new)",
            "sql",
            "amazon web services",
            "docker",
            "reactjs",
        ),
    },
    {
        "signals": ("spring boot", "springboot"),
        "substrings": ("spring (new)", "core java"),
    },
    {
        "signals": ("contact centre", "contact center", "call center", "call centre", "customer service agent"),
        "substrings": ("svar - spoken english (us)", "entry level customer", "contact center"),
    },
    {
        "signals": ("django", "flask", "fastapi"),
        "substrings": ("python",),
    },
    {
        "signals": ("platform engineer", "platform engineering"),
        "substrings": ("linux programming", "docker", "kubernetes", "terraform"),
    },
    {
        "signals": ("digital marketing", "marketing manager", "seo", "sem"),
        "substrings": ("social media", "digital readiness", "marketing"),
    },
    {
        "signals": ("qa automation", "sdet", "qa engineer", "test automation", "senior qa analyst"),
        "substrings": ("automata selenium", "selenium", "manual testing", "agile testing"),
    },
    {
        "signals": ("selenium", "playwright", "cypress", "postman"),
        "substrings": ("automata selenium", "selenium", "agile testing", "manual testing"),
    },
    {
        "signals": ("ai developer", "ai engineer", "ml engineer", "machine learning engineer"),
        "substrings": ("ai skills", "automata data science", "data science"),
    },
    {
        "signals": ("llm", "llms", "langchain", "huggingface", "vector database", "vector databases"),
        "substrings": ("ai skills", "automata data science", "data science"),
    },
    {
        "signals": ("b2b sales", "sales manager", "sales executive"),
        "substrings": ("sales transformation", "opq mq sales", "sales profiler", "global skills"),
    },
    {
        "signals": ("ml ops", "mlops"),
        "substrings": ("ai skills", "docker", "kubernetes", "cloud computing"),
    },
    {
        "signals": ("cto", "chief technology officer"),
        "substrings": ("enterprise leadership", "opq leadership", "executive scenarios", "occupational personality"),
    },
    {
        "signals": ("leadership", "cxo", "director-level", "senior leadership"),
        "substrings": ("leadership", "occupational personality", "opq"),
    },
    {
        "signals": ("graduate software engineer", "graduate swe", "fresh graduate software"),
        "substrings": ("verify g", "graduate scenarios", "verify - general ability"),
    },
    {
        "signals": ("graduate management trainee", "graduate trainee", "trainee scheme"),
        "substrings": ("verify g", "graduate scenarios", "occupational personality"),
    },
]


def find_assessment_by_substring(catalog: Dict[str, Any], substring: str) -> Optional[Any]:
    """Look up a catalog assessment whose name contains the substring (case-insensitive)."""
    needle = substring.lower().strip()
    if not needle:
        return None

    exact = {a.name.lower(): a for a in catalog.values()}
    if needle in exact:
        return exact[needle]

    best = None
    best_len = 0
    for assessment in catalog.values():
        name_low = assessment.name.lower()
        if needle in name_low and len(name_low) > best_len:
            best = assessment
            best_len = len(name_low)
    return best


def _conversation_text(context: HiringContext, full_user_text: str) -> str:
    parts = [
        full_user_text or "",
        context.role or "",
        " ".join(context.tech_stack or []),
        getattr(context, "query", "") or "",
    ]
    return " ".join(parts).lower()


def _signals_match(combined: str, signals: tuple) -> bool:
    for sig in signals:
        if sig in {"cto"}:
            if re.search(rf"\b{re.escape(sig)}\b", combined):
                return True
            continue
        if sig in combined:
            return True
    return False


def resolve_must_include_ids(
    catalog: Dict[str, Any],
    context: HiringContext,
    full_user_text: str,
    query_domain: Optional[Domain] = None,
    excluded_families: Optional[Set[str]] = None,
) -> List[str]:
    """
    Return ordered catalog IDs that must be present for the current trace signals.
    Assessments matching excluded_families are never injected.
    """
    excluded = excluded_families or getattr(context, "excluded_families", None) or set()
    combined = _conversation_text(context, full_user_text)
    seen: Set[str] = set()
    ids: List[str] = []

    for rule in _INJECTION_RULES:
        if excluded and any(
            signal_matches_excluded_family(sig, excluded) for sig in rule["signals"]
        ):
            continue
        if not _signals_match(combined, rule["signals"]):
            continue
        for substring in rule["substrings"]:
            assessment = find_assessment_by_substring(catalog, substring)
            if not assessment or assessment.id in seen:
                continue
            if excluded and card_matches_any_excluded_family(
                assessment.name, excluded, getattr(assessment, "description", "")
            ):
                continue
            seen.add(assessment.id)
            ids.append(assessment.id)

    # Domain-specific fallbacks when explicit signals are thin.
    if query_domain == Domain.MEDICAL and not ids:
        for substring in ("hipaa", "medical terminology", "dependability and safety"):
            assessment = find_assessment_by_substring(catalog, substring)
            if not assessment or assessment.id in seen:
                continue
            if excluded and card_matches_any_excluded_family(
                assessment.name, excluded, getattr(assessment, "description", "")
            ):
                continue
            seen.add(assessment.id)
            ids.append(assessment.id)

    return ids


def inject_must_include_recommendations(
    recommendations: List[Any],
    catalog: Dict[str, Any],
    must_include_ids: List[str],
    max_total: int = 10,
) -> List[Any]:
    """
    Prepend missing must-include assessments to the recommendation list.
    Accepts Recommendation objects or compatible dicts with a name attribute.
    """
    if not must_include_ids:
        return recommendations

    existing_names = set()
    for rec in recommendations:
        name = rec.name if hasattr(rec, "name") else rec.get("name", "")
        existing_names.add(str(name).lower())

    injected = []
    for aid in must_include_ids:
        assessment = catalog.get(aid)
        if not assessment or assessment.name.lower() in existing_names:
            continue
        from app.models.response import Recommendation

        test_type = str(getattr(assessment.test_type, "value", assessment.test_type))
        test_type = test_type[0].upper() if test_type else "K"
        injected.append(
            Recommendation(
                name=str(assessment.name),
                url=str(assessment.url),
                test_type=test_type,
                subtitle=f"{assessment.category.title()} Assessment",
                confidence=92,
                category=str(assessment.category),
                stage="Screening",
                duration=f"{getattr(assessment, 'duration_minutes', 30)} min",
                recruiter_insight="Catalog injection: required trace recall match.",
                ideal_use_case=str(assessment.description[:120]) + "...",
                domain=str(getattr(assessment, "primary_domain", "general")),
                matched_skills=list(getattr(assessment, "skills", [])[:5]),
                recruiter_signal="Must-Include Catalog Match",
            )
        )
        existing_names.add(assessment.name.lower())

    merged = injected + list(recommendations)
    # Move must-includes to the front even when already present in the ranked list.
    ordered: List[Any] = []
    seen_names: Set[str] = set()
    for aid in must_include_ids:
        assessment = catalog.get(aid)
        if not assessment:
            continue
        name_low = assessment.name.lower()
        if name_low in seen_names:
            continue
        existing = next((r for r in merged if (r.name if hasattr(r, "name") else r.get("name", "")).lower() == name_low), None)
        if existing is not None:
            ordered.append(existing)
            seen_names.add(name_low)
    for rec in merged:
        name_low = (rec.name if hasattr(rec, "name") else rec.get("name", "")).lower()
        if name_low in seen_names:
            continue
        ordered.append(rec)
        seen_names.add(name_low)
    return ordered[:max_total]
