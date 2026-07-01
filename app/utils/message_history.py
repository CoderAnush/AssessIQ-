"""
Stateless helpers: reconstruct prior recommendations from conversation history.
No server-side session storage required for evaluator compliance.
"""

import re
from typing import Dict, List, Optional

from app.models.response import Recommendation


def _resolve_catalog_assessment(name: str, catalog: Dict):
    """Resolve a free-text assessment reference against the catalog."""
    name_clean = name.strip().lower()
    if not name_clean:
        return None

    alias_map = {
        "opq32r": "occupational-personality-questionnaire-opq32r",
        "opq": "occupational-personality-questionnaire-opq32r",
        "java": "core-java-advanced-level-new",
        "gsa": "verify-general-ability-screen",
        "general ability assessment": "verify-general-ability-screen",
        "general ability": "verify-general-ability-screen",
    }
    if name_clean in alias_map:
        return catalog.get(alias_map[name_clean])

    by_name = {a.name.lower(): a for a in catalog.values()}
    if name_clean in by_name:
        return by_name[name_clean]

    for assessment in catalog.values():
        if (
            assessment.name.lower() == name_clean
            or name_clean in assessment.name.lower()
            or assessment.id.lower() == name_clean.replace(" ", "-")
        ):
            return assessment
    return None


def _recommendation_from_assessment(cat_ass) -> Recommendation:
    test_type = str(getattr(cat_ass.test_type, "value", cat_ass.test_type))
    test_type = test_type[0].upper() if test_type else "K"
    if test_type not in ("K", "A", "P"):
        test_type = "K"
    return Recommendation(
        name=str(cat_ass.name),
        url=str(cat_ass.url),
        test_type=test_type,
        subtitle="",
        confidence=80,
        category=str(cat_ass.category),
        stage="Screening",
        duration=f"{getattr(cat_ass, 'duration_minutes', 30)} min",
        recruiter_insight="",
        ideal_use_case="",
        domain=str(getattr(cat_ass, "primary_domain", "general")),
        matched_skills=[],
        recruiter_signal="",
    )


def parse_recommendations_from_plain_text(
    content: str,
    catalog: Dict,
) -> List[Recommendation]:
    """Parse comma-separated assessment names from a plain assistant reply."""
    if ":" in content:
        tail = content.split(":", 1)[1]
    else:
        tail = content

    recs: List[Recommendation] = []
    seen_names = set()
    for raw_name in re.split(r"[,;]", tail):
        name = raw_name.strip().strip(".")
        if not name or name.lower().startswith("here are"):
            continue
        cat_ass = _resolve_catalog_assessment(name, catalog)
        if not cat_ass or cat_ass.name.lower() in seen_names:
            continue
        seen_names.add(cat_ass.name.lower())
        recs.append(_recommendation_from_assessment(cat_ass))
    return recs


def parse_recommendations_from_assistant_content(
    content: str,
    catalog: Dict,
) -> List[Recommendation]:
    """Parse recommendation markdown table rows from an assistant reply."""
    if "|" not in content:
        return parse_recommendations_from_plain_text(content, catalog)

    recs: List[Recommendation] = []
    seen_names = set()
    by_name = {a.name.lower(): a for a in catalog.values()}
    by_url_slug = {}
    for a in catalog.values():
        slug = a.url.rstrip("/").split("/")[-1].lower()
        if slug:
            by_url_slug[slug] = a

    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            continue
        if parts[0].lower() in ("#", "name") or parts[1].lower() == "name":
            continue

        name = parts[1] if parts[0].isdigit() else parts[0]
        name = re.sub(r"^\d+\.\s*", "", name).strip()
        if not name or name.lower() in seen_names:
            continue

        url = ""
        if len(parts) >= 7:
            url_raw = parts[6]
            url_match = re.search(r"<(https://[^>]+)>", url_raw)
            url = url_match.group(1) if url_match else url_raw.strip("<>")

        cat_ass = by_name.get(name.lower())
        if not cat_ass and url:
            slug = url.rstrip("/").split("/")[-1].lower()
            cat_ass = by_url_slug.get(slug)
        if not cat_ass:
            for a in catalog.values():
                if a.name.lower() == name.lower() or name.lower() in a.name.lower():
                    cat_ass = a
                    break
        if not cat_ass:
            continue

        seen_names.add(name.lower())
        recs.append(_recommendation_from_assessment(cat_ass))
    return recs


def get_prior_recommendations_from_messages(
    messages: List[dict],
    catalog: Dict,
) -> List[Recommendation]:
    """Return the most recent assistant shortlist found in message history."""
    for m in reversed(messages[:-1]):
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "")
        content_low = content.lower()
        if content_low.startswith("compare these") or "### comparison:" in content_low:
            continue
        recs = parse_recommendations_from_assistant_content(content, catalog)
        if recs:
            return recs
    return []


def get_top_n_from_history(
    messages: List[dict],
    catalog: Dict,
    n: int = 2,
) -> List:
    """Return top N catalog assessment objects from prior assistant shortlist."""
    recs = get_prior_recommendations_from_messages(messages, catalog)
    if len(recs) >= n:
        result = []
        for rec in recs[:n]:
            slug = rec.url.rstrip("/").split("/")[-1].lower()
            for a in catalog.values():
                if a.name.lower() == rec.name.lower() or a.id.lower() == slug:
                    result.append(a)
                    break
        if len(result) >= n:
            return result

    # Fall back to the most recent comparison reply (e.g. "Compare OPQ32r and GSA" turn).
    for m in reversed(messages[:-1]):
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "")
        if "### comparison:" not in content.lower():
            continue
        match = re.search(
            r"### Comparison:\s*(.+?)\s+vs\s+(.+?)(?:\n|$)",
            content,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        result = []
        for raw_name in (match.group(1).strip(), match.group(2).strip()):
            cat_ass = _resolve_catalog_assessment(raw_name, catalog)
            if cat_ass:
                result.append(cat_ass)
        if len(result) >= min(n, 2):
            return result[:n]
    return []


def detect_refinement_intent(user_msg: str) -> Optional[Dict]:
    """Detect drop/add/remove refinement commands."""
    msg = user_msg.lower().strip()
    drop_patterns = [
        r"drop\s+(?:the\s+)?(.+?)(?:\.|$|,|\s+and\s+)",
        r"remove\s+(?:the\s+)?(.+?)(?:\.|$|,|\s+and\s+)",
        r"without\s+(?:the\s+)?(.+?)(?:\.|$|,)",
    ]
    add_patterns = [
        r"add\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\.|$|,|\s+and\s+)",
        r"also\s+add\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\.|$|,)",
        r"include\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\.|$|,)",
    ]

    drops = []
    for pat in drop_patterns:
        m = re.search(pat, msg)
        if m:
            drops.append(m.group(1).strip())

    adds = []
    for pat in add_patterns:
        m = re.search(pat, msg)
        if m:
            adds.append(m.group(1).strip())

    if not drops and not adds:
        return None
    return {"drops": drops, "adds": adds}


def apply_refinement_to_recommendations(
    prior: List[Recommendation],
    refinement: Dict,
    catalog: Dict,
) -> List[Recommendation]:
    """Mutate prior shortlist based on drop/add intents."""
    result = list(prior)
    drops = refinement.get("drops", [])
    adds = refinement.get("adds", [])

    for drop in drops:
        drop_low = drop.lower()
        result = [
            r for r in result
            if drop_low not in r.name.lower()
            and not (drop_low in ("opq", "opq32r") and "opq" in r.name.lower())
            and not (drop_low in ("rest", "restful") and "rest" in r.name.lower())
            and not (
                any(term in drop_low for term in ("coding", "technical", "knowledge", "programming"))
                and str(r.test_type).upper() == "K"
            )
            and not (
                any(term in drop_low for term in ("coding", "programming"))
                and any(term in r.name.lower() for term in ("java", "react", "programming", "coding", "automata"))
            )
        ]

    for add_term in adds:
        add_low = add_term.lower()
        existing_names = {r.name.lower() for r in result}
        for a in catalog.values():
            text = (a.name + " " + a.description).lower()
            if add_low in text or add_low in a.name.lower():
                if a.name.lower() not in existing_names:
                    result.append(_recommendation_from_assessment(a))
                    break
    return result[:10]
