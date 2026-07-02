"""
Token-normalized intent detection for vague assessment requests.
No hardcoded phrase lists — uses normalized tokens and synonym mapping.
"""

from __future__ import annotations

import re
from typing import Set

from app.services.tech_families import families_for_tokens

# Synonyms collapse to canonical hiring-intent tokens
_TOKEN_SYNONYMS = {
    "tests": "test",
    "testing": "test",
    "assessments": "assessment",
    "assessing": "assessment",
    "suggests": "suggest",
    "suggestion": "suggest",
    "recommends": "recommend",
    "recommendation": "recommend",
    "recommendations": "recommend",
    "hiring": "hire",
    "recruiting": "hire",
    "screening": "screen",
    "evaluating": "evaluate",
    "shortlists": "shortlist",
    "assists": "assist",
    "assistance": "assist",
}

HIRING_INTENT_TOKENS = {
    "assessment", "test", "screen", "evaluate", "recommend", "suggest",
    "help", "assist", "shortlist", "hire", "battery",
}

ROLE_TOKENS = {
    "developer", "engineer", "manager", "analyst", "architect", "lead",
    "director", "executive", "scientist", "operator", "administrator",
    "admin", "trainee", "specialist", "consultant", "designer",
    "programmer", "coder", "sre", "cto", "cxo", "vp",
}

DOMAIN_HINT_TOKENS = {
    "backend", "frontend", "fullstack", "devops", "qa", "sdet", "mobile",
    "android", "ios", "security", "cyber", "sales", "marketing", "hr",
    "healthcare", "financial", "graduate", "leadership", "contact",
    "centre", "center", "plant", "civil", "mechanical", "electrical",
    "chemical", "aeronautical", "aerospace", "data", "machine", "learning",
    "ai", "ml", "nlp", "cloud", "infrastructure", "platform", "api",
    "microservice", "full", "stack", "customer", "support", "service",
    "entry", "personality", "cognitive", "behaviour", "behavior", "situational",
    "rust", "java", "python", "spring", "react", "selenium", "hipaa",
}


def normalize_tokens(text: str) -> Set[str]:
    """Lowercase, strip punctuation, apply synonym map."""
    raw = set(re.findall(r"\b[a-z0-9]+\b", text.lower()))
    normalized: Set[str] = set()
    for token in raw:
        normalized.add(_TOKEN_SYNONYMS.get(token, token))
    # Compound hints from adjacent tokens
    low = text.lower()
    if "full stack" in low or "fullstack" in low:
        normalized.add("fullstack")
    if "machine learning" in low or "data science" in low:
        normalized.add("machine")
        normalized.add("learning")
    if "contact centre" in low or "contact center" in low:
        normalized.add("contact")
    return normalized


def is_vague_request(last_message: str) -> bool:
    """
    True when the user seeks assessments but provides no actionable role, tech, or domain signal.
    Covers paraphrases: 'Need a test', 'Suggest an assessment', 'Recommend assessment help', etc.
    """
    if not last_message or not last_message.strip():
        return False

    tokens = normalize_tokens(last_message)
    hiring_intent = tokens & HIRING_INTENT_TOKENS
    role_signals = tokens & ROLE_TOKENS
    tech_families = families_for_tokens(tokens)
    domain_hints = tokens & DOMAIN_HINT_TOKENS

    # Must express hiring/assessment intent without actionable specificity
    if not hiring_intent:
        return False
    if role_signals or tech_families or domain_hints:
        return False
    return True
