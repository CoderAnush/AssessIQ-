"""
Shared technology family definitions for refinement, injection filtering, and diversity rules.
One token maps to one family; dropping JAVA removes Spring, JVM, etc.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Set

# Family name -> member tokens (normalized lowercase)
TECH_FAMILIES: Dict[str, Set[str]] = {
    "JAVA": {
        "java", "spring", "springboot", "spring boot", "jvm", "j2ee", "hibernate", "servlet",
    },
    "PYTHON": {
        "python", "django", "flask", "fastapi",
    },
    "JS": {
        "javascript", "typescript", "react", "reactjs", "angular", "vue", "node", "redux",
        "express", "nextjs", "next.js",
    },
    "DOTNET": {
        "dotnet", "asp.net", "csharp", "c#", "wpf",
    },
    "SQL": {
        "sql", "database", "postgresql", "mysql", "oracle",
    },
    "DEVOPS": {
        "kubernetes", "docker", "terraform", "aws", "cloud", "devops", "sre",
    },
    "ML": {
        "machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "ml",
    },
}

# Built at import: token -> family name
TOKEN_TO_FAMILY: Dict[str, str] = {}
for _family, _tokens in TECH_FAMILIES.items():
    for _token in _tokens:
        TOKEN_TO_FAMILY[_token] = _family


def family_for_token(token: str) -> Optional[str]:
    """Resolve a single token to its tech family, or None."""
    if not token:
        return None
    low = token.lower().strip()
    if low in TOKEN_TO_FAMILY:
        return TOKEN_TO_FAMILY[low]
    # Multi-word tokens (e.g. spring boot)
    for tok, fam in TOKEN_TO_FAMILY.items():
        if " " in tok and tok in low:
            return fam
    return None


def families_for_tokens(tokens: Set[str]) -> Set[str]:
    """Return all families represented in a token set."""
    found: Set[str] = set()
    for token in tokens:
        fam = family_for_token(token)
        if fam:
            found.add(fam)
    return found


def families_for_text(text: str) -> Set[str]:
    """Return families found in free text via word-boundary token scan."""
    tokens = set(re.findall(r"\b[a-z0-9.#+]+\b", text.lower()))
    return families_for_tokens(tokens)


def drop_tokens_for_family(family: str) -> Set[str]:
    """All member tokens for a family."""
    return set(TECH_FAMILIES.get(family.upper(), set()))


def card_matches_family(card_name: str, family: str, description: str = "") -> bool:
    """True if assessment name/description matches the given family."""
    text = f"{card_name} {description}".lower()
    family_up = family.upper()
    for token in TECH_FAMILIES.get(family_up, set()):
        if " " in token:
            if token in text:
                return True
        elif re.search(rf"\b{re.escape(token)}\b", text):
            return True
    return False


def card_matches_any_excluded_family(
    card_name: str,
    excluded_families: Set[str],
    description: str = "",
) -> bool:
    """True if card belongs to any excluded family."""
    for family in excluded_families:
        if card_matches_family(card_name, family, description):
            return True
    return False


def signal_matches_excluded_family(signal: str, excluded_families: Set[str]) -> bool:
    """True if an injection rule signal resolves to an excluded family."""
    if not excluded_families:
        return False
    fam = family_for_token(signal.split()[0])
    if fam and fam in excluded_families:
        return True
    return bool(families_for_text(signal) & excluded_families)


def family_key_for_business_rules(family: str) -> str:
    """Map uppercase family name to lowercase key used by business rules engine."""
    return family.lower()
