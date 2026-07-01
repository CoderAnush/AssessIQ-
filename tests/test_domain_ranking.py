"""Unit tests for domain-specific ranking order."""

import pytest

from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.services.ranker import RecruiterRanker


@pytest.fixture(scope="module")
def catalog():
    loader = CatalogLoader("data/processed/catalog_processed.json")
    return {a.id: a for a in loader.get_all()}


def _rank_pool(catalog, role: str, tech_stack: set, pool_ids: list) -> list:
    ranker = RecruiterRanker()
    ctx = HiringContext(role=role, seniority="mid")
    ctx.query = role
    ctx.tech_stack = tech_stack
    retrieved = [{"id": pid, "hybrid_score": 0.05 - i * 0.001} for i, pid in enumerate(pool_ids)]
    return ranker.rank(retrieved, ctx, catalog, top_k=5)


def test_ai_engineer_ranking(catalog):
    pool = [
        "occupational-personality-questionnaire-opq32r",
        "ai-skills",
        "automata-data-science-new",
        "automata-front-end",
        "automata-selenium",
    ]
    results = _rank_pool(catalog, "ai engineer", {"python", "machine learning"}, pool)
    top_ids = [r.assessment.id for r in results[:3]]
    assert "ai-skills" in top_ids or "automata-data-science-new" in top_ids
    assert top_ids[0] in {"ai-skills", "automata-data-science-new", "data-science-new"}
    assert "automata-front-end" not in top_ids
    assert "automata-selenium" not in top_ids


def test_java_backend_ranking(catalog):
    pool = [
        "occupational-personality-questionnaire-opq32r",
        "core-java-advanced-level-new",
        "python-new",
        "automata-front-end",
    ]
    results = _rank_pool(catalog, "java backend developer", {"java"}, pool)
    assert results[0].assessment.id == "core-java-advanced-level-new"
    top3 = [r.assessment.id for r in results[:3]]
    assert "automata-front-end" not in top3


def test_react_frontend_ranking(catalog):
    pool = [
        "core-java-advanced-level-new",
        "javascript-new",
        "automata-front-end",
        "occupational-personality-questionnaire-opq32r",
    ]
    results = _rank_pool(catalog, "react developer", {"react", "javascript"}, pool)
    top3 = [r.assessment.id for r in results[:3]]
    assert any(i in top3 for i in ("javascript-new", "automata-front-end"))
    assert "core-java-advanced-level-new" not in top3[:2]


def test_devops_ranking(catalog):
    pool = [
        "linux-programming-general",
        "automata-front-end",
        "core-java-advanced-level-new",
    ]
    results = _rank_pool(catalog, "devops engineer", {"linux", "kubernetes"}, pool)
    assert results[0].assessment.id == "linux-programming-general"


def test_qa_ranking(catalog):
    pool = [
        "automata-selenium",
        "core-java-advanced-level-new",
        "occupational-personality-questionnaire-opq32r",
    ]
    results = _rank_pool(catalog, "qa engineer", set(), pool)
    assert results[0].assessment.id == "automata-selenium"
