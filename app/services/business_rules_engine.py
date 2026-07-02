"""
Business Rules Engine — post-reranking diversity and completeness rules.

Applied AFTER cross-encoder reranking. No scoring constants.
Rules are deterministic and transparent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from app.logger_config.logger import get_logger
from app.services.tech_families import TECH_FAMILIES, card_matches_family, family_key_for_business_rules

logger = get_logger("business_rules_engine")

# Maximum assessments from the same technology family in final top-10
_MAX_PER_TECH_FAMILY = 3

# Test type codes
_PERSONALITY_TYPE = "P"
_ABILITY_TYPE = "A"
_KNOWLEDGE_TYPE = "K"


def _get_tech_family(candidate: Dict[str, Any]) -> str:
    for family in TECH_FAMILIES:
        if card_matches_family(candidate.get("name", ""), family, candidate.get("description", "")):
            return family_key_for_business_rules(family)
    return "other"


class BusinessRulesEngine:
    """
    Applies lightweight post-reranking rules:
    1. Cap assessments per technology family (diversity)
    2. Deduplicate near-identical titles
    3. Ensure at least one behavioral/personality assessment for senior roles
    4. Return final top-k
    """

    def apply(
        self,
        candidates: List[Dict[str, Any]],
        context: Any,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Apply business rules to reranked candidates.

        Args:
            candidates: Reranked list from CrossEncoderReranker.
            context:    HiringContext (for seniority, domain checks).
            top_k:      Final number of recommendations to return.

        Returns:
            Final top-k diverse and complete recommendations.
        """
        seniority = getattr(context, "seniority", "mid") or "mid"
        needs_behavioral = seniority in ("senior", "executive", "lead")

        family_counts: Dict[str, int] = {}
        seen_titles: Set[str] = set()
        results: List[Dict[str, Any]] = []
        behavioral_included = False

        for candidate in candidates:
            if len(results) >= top_k:
                break

            # Rule 1: Near-duplicate title deduplication
            base_title = self._normalise_title(candidate.get("name", ""))
            if base_title in seen_titles:
                continue
            seen_titles.add(base_title)

            # Rule 2: Technology family cap
            family = _get_tech_family(candidate)
            if family_counts.get(family, 0) >= _MAX_PER_TECH_FAMILY:
                continue

            # Track behavioral assessments
            if candidate.get("test_type") == _PERSONALITY_TYPE:
                behavioral_included = True

            family_counts[family] = family_counts.get(family, 0) + 1
            results.append(candidate)

        # Rule 3: Ensure behavioral assessment for senior roles
        if needs_behavioral and not behavioral_included:
            behavioral = self._find_behavioral(candidates, seen_titles)
            if behavioral:
                # Replace the lowest-scored result to maintain top_k
                if len(results) >= top_k:
                    results[-1] = behavioral
                else:
                    results.append(behavioral)
                logger.info(
                    "BusinessRulesEngine: injected behavioral assessment '%s' for senior role",
                    behavioral.get("name"),
                )

        logger.info(
            "BusinessRulesEngine: %d → %d results after rules",
            len(candidates), len(results),
        )
        return results

    @staticmethod
    def _normalise_title(title: str) -> str:
        """Strip version numbers and level qualifiers for dedup comparison."""
        import re
        t = title.lower()
        t = re.sub(r"\s*(entry level|advanced level|level [0-9]|v[0-9]+|[0-9]+\.[0-9]+|\(new\))\s*", " ", t)
        return t.strip()

    @staticmethod
    def _find_behavioral(
        candidates: List[Dict[str, Any]], already_seen: Set[str]
    ) -> Dict[str, Any] | None:
        for c in candidates:
            if c.get("test_type") == _PERSONALITY_TYPE:
                title = BusinessRulesEngine._normalise_title(c.get("name", ""))
                if title not in already_seen:
                    return c
        return None
