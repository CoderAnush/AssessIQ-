"""
Resolve named assessment comparison targets against the SHL catalog.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.catalog_injection import find_assessment_by_substring

COMPARE_ALIASES = {
    "java ee": "java platform enterprise edition",
    "java ee 7": "java platform enterprise edition",
    "j2ee": "java platform enterprise edition",
    "spring": "spring (new)",
    "spring boot": "spring (new)",
    "springboot": "spring (new)",
    "opq32r": "occupational personality questionnaire",
    "opq": "occupational personality questionnaire",
    "verify g+": "verify g+",
    "verify g": "verify g+",
    "gsa": "verify general ability",
}

_NOISE_TOKENS = frozenset({"assessments", "assessment", "tests", "test", "the", "shl"})


def _clean_compare_item(item: str) -> str:
    low = item.lower().strip()
    for noise in _NOISE_TOKENS:
        low = re.sub(rf"\b{re.escape(noise)}\b", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _token_overlap_score(needle: str, assessment_name: str) -> float:
    needle_tokens = set(re.findall(r"\b[a-z0-9+]+\b", needle))
    name_tokens = set(re.findall(r"\b[a-z0-9+]+\b", assessment_name.lower()))
    if not needle_tokens:
        return 0.0
    return len(needle_tokens & name_tokens) / len(needle_tokens)


def resolve_compare_item(catalog: Dict[str, Any], raw_item: str) -> Optional[Any]:
    """Resolve a single comparison item to a catalog assessment."""
    cleaned = _clean_compare_item(raw_item)
    if not cleaned:
        return None

    if cleaned in COMPARE_ALIASES:
        cleaned = COMPARE_ALIASES[cleaned]

    direct = find_assessment_by_substring(catalog, cleaned)
    if direct:
        return direct

    best = None
    best_score = 0.0
    for assessment in catalog.values():
        name_low = assessment.name.lower()
        score = _token_overlap_score(cleaned, name_low)
        if cleaned in name_low:
            score += 0.5
        if score > best_score:
            best_score = score
            best = assessment
    return best if best_score >= 0.34 else None


def resolve_compare_targets(
    items: List[str],
    catalog: Dict[str, Any],
) -> Tuple[Optional[Any], Optional[Any]]:
    """Resolve up to two distinct catalog assessments for a compare request."""
    if len(items) < 2:
        return None, None

    a1 = resolve_compare_item(catalog, items[0])
    a2 = resolve_compare_item(catalog, items[1])

    if a1 and a2 and a1.id == a2.id:
        a2 = None

    return a1, a2


def suggest_compare_clarification(items: List[str]) -> str:
    """Clarify message when explicit names were given but resolution failed."""
    cleaned = [_clean_compare_item(i) for i in items[:2]]
    if "java" in " ".join(cleaned) and "spring" in " ".join(cleaned):
        return (
            "I couldn't find both assessments in the catalog. "
            "Did you mean Java Platform Enterprise Edition 7 (Java EE 7) and Spring (New)?"
        )
    names = " and ".join(items[:2]) if items else "those assessments"
    return (
        f"I couldn't find both assessments ({names}). "
        "Please provide the exact SHL assessment names."
    )
