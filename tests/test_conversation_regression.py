"""
Conversation Regression Tests for AssessIQ.
Verifies golden conversational scenarios C1 to C10 and SHL evaluator schema compliance.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.domain_classifier import Domain
from app.services.requirement_resolver import RequirementResolver
from app.services.conversation_analyzer import HiringContext
from app.services.ranker import RecruiterRanker


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def catalog():
    from app.services.catalog_loader import CatalogLoader
    loader = CatalogLoader("data/processed/catalog_processed.json")
    return {a.id: a for a in loader.get_all()}


def _chat(client, messages):
    r = client.post("/chat", json={"messages": messages})
    assert r.status_code == 200
    return r.json()


def _recall_at_k(expected_substrings, rec_names, k=10):
    if not expected_substrings:
        return 1.0
    top = [n.lower() for n in rec_names[:k]]
    hits = sum(
        1 for exp in expected_substrings
        if any(exp.lower() in name for name in top)
    )
    return hits / len(expected_substrings)


def test_health_evaluator_schema(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_chat_response_strict_schema(client):
    data = _chat(client, [{"role": "user", "content": "I need an assessment."}])
    assert set(data.keys()) == {"reply", "recommendations", "end_of_conversation"}
    assert data["recommendations"] == []
    assert data["end_of_conversation"] is False
    for rec in data.get("recommendations", []):
        assert set(rec.keys()) == {"name", "url", "test_type"}
        assert rec["url"].startswith("https://www.shl.com/")


def test_vague_query_no_recommendations_turn1(client):
    data = _chat(client, [{"role": "user", "content": "I need an assessment."}])
    assert len(data["recommendations"]) == 0
    assert any(w in data["reply"].lower() for w in ["role", "hiring", "backend", "frontend"])


def test_java_recommendations_grounded(client):
    data = _chat(client, [{"role": "user", "content": "Senior Java Backend Engineer with Spring Boot"}])
    assert 1 <= len(data["recommendations"]) <= 10
    names = " ".join(r["name"].lower() for r in data["recommendations"])
    assert "java" in names or "spring" in names


def test_refusal_off_topic(client):
    data = _chat(client, [{"role": "user", "content": "Tell me a joke."}])
    assert len(data["recommendations"]) == 0
    assert "specialize" in data["reply"].lower() or "cannot assist" in data["reply"].lower()


def test_c1_c10_requirement_resolution():
    resolver = RequirementResolver()

    ctx_c1 = HiringContext(role="Senior Java Backend Engineer", seniority="senior")
    reqs_c1 = resolver.resolve(Domain.BACKEND, ctx_c1)
    assert "technical" in reqs_c1
    assert "cognitive" in reqs_c1
    assert "personality" in reqs_c1

    ctx_c2 = HiringContext(role="React Frontend Engineer", seniority="mid")
    reqs_c2 = resolver.resolve(Domain.FRONTEND, ctx_c2)
    assert "technical" in reqs_c2

    ctx_c5 = HiringContext(role="Sales Manager", seniority="senior")
    reqs_c5 = resolver.resolve(Domain.MANAGEMENT, ctx_c5)
    assert "personality" in reqs_c5
    assert "leadership_report" in reqs_c5

    ctx_c10 = HiringContext(role="Fresh Graduate Software Engineer", seniority="entry")
    reqs_c10 = resolver.resolve(Domain.GENERAL, ctx_c10)
    assert "cognitive" in reqs_c10
    assert "learning" in reqs_c10


def test_ranking_structured_scoring(catalog):
    ranker = RecruiterRanker()
    ctx = HiringContext(role="Java Developer", seniority="mid")
    ctx.query = "Java Developer"
    ctx.tech_stack = {"Java"}

    retrieved = [
        {"id": "core-java-advanced-level-new", "hybrid_score": 0.05},
        {"id": "occupational-personality-questionnaire-opq32r", "hybrid_score": 0.01},
    ]

    results = ranker.rank(retrieved, ctx, catalog, top_k=2)
    assert len(results) > 0
    assert results[0].assessment.id == "core-java-advanced-level-new"


SAMPLE_TRACES = {
    "C1_leadership": {
        "turns": [
            "We need a solution for senior leadership.",
            "The pool consists of CXOs, director-level postions; people with more than 15 years of experience.",
            "Selection — comparing candidates against a leadership benchmark.",
        ],
        "expected": ["opq", "leadership"],
        "min_recall": 0.5,
    },
    "C4_finance_grad": {
        "turns": [
            "Hiring graduate financial analysts — final-year students, no work experience. We need numerical reasoning and a finance knowledge test.",
        ],
        "expected": ["numerical", "financial", "graduate"],
        "min_recall": 0.33,
    },
    "C10_grad_mgmt": {
        "turns": [
            "We run a graduate management trainee scheme. We need a full battery — cognitive, personality, and situational judgement. All recent graduates.",
        ],
        "expected": ["verify", "graduate scenarios", "opq"],
        "min_recall": 0.33,
    },
}


@pytest.mark.parametrize("trace_id", list(SAMPLE_TRACES.keys()))
def test_sample_conversation_recall(client, trace_id):
    trace = SAMPLE_TRACES[trace_id]
    messages = []
    final_data = None
    for turn in trace["turns"]:
        messages.append({"role": "user", "content": turn})
        final_data = _chat(client, messages)
        messages.append({"role": "assistant", "content": final_data["reply"]})

    rec_names = [r["name"] for r in final_data["recommendations"]]
    recall = _recall_at_k(trace["expected"], rec_names, k=10)
    assert recall >= trace["min_recall"], f"{trace_id} recall {recall:.2f} below {trace['min_recall']}"


def test_refinement_drop_opq(client):
    messages = [
        {"role": "user", "content": "We run a graduate management trainee scheme. We need cognitive, personality, and situational judgement."},
    ]
    data1 = _chat(client, messages)
    messages.append({"role": "assistant", "content": data1["reply"]})
    messages.append({"role": "user", "content": "Drop the OPQ. Final list: Verify G+ and Graduate Scenarios."})
    data2 = _chat(client, messages)
    names = " ".join(r["name"].lower() for r in data2["recommendations"])
    assert "opq" not in names or len(data2["recommendations"]) <= 2


def test_compare_from_history(client):
    messages = [{"role": "user", "content": "Senior Java Backend Engineer with Spring Boot"}]
    data1 = _chat(client, messages)
    messages.append({"role": "assistant", "content": data1["reply"]})
    messages.append({"role": "user", "content": "Compare the top two recommendations."})
    data2 = _chat(client, messages)
    assert "Comparison" in data2["reply"] or "compare" in data2["reply"].lower()


def test_end_of_conversation_closure(client):
    messages = [{"role": "user", "content": "Senior Java Backend Engineer with Spring Boot"}]
    data1 = _chat(client, messages)
    messages.append({"role": "assistant", "content": data1["reply"]})
    messages.append({"role": "user", "content": "Perfect, thanks."})
    data2 = _chat(client, messages)
    assert data2["end_of_conversation"] is True
    assert len(data2["recommendations"]) >= 1
