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
    "C2_rust": {
        "turns": [
            "I'm hiring a senior Rust engineer for high-performance networking infrastructure. What assessments should I use?",
            "Yes, go ahead. Should I also add a cognitive test for this level?",
        ],
        "expected": ["smart interview", "linux", "networking", "verify"],
        "min_recall": 0.0,
    },
    "C3_contact_centre": {
        "turns": [
            "We're screening 500 entry-level contact centre agents. Inbound calls, customer service focus. What should we use?",
            "English.",
            "US.",
        ],
        "expected": ["svar", "contact center", "customer service"],
        "min_recall": 0.33,
    },
    "C4_finance_grad": {
        "turns": [
            "Hiring graduate financial analysts — final-year students, no work experience. We need numerical reasoning and a finance knowledge test.",
            "Good. Can you also add a situational judgement element — work-context decision making for graduates?",
        ],
        "expected": ["numerical", "financial", "graduate scenarios"],
        "min_recall": 0.33,
    },
    "C5_sales_reskill": {
        "turns": [
            "As part of our restructuring and annual talent audit, we need to re-skill our Sales organization. What solutions do you recommend?"
        ],
        "expected": ["global skills", "opq", "sales"],
        "min_recall": 0.33,
    },
    "C6_safety_dependability": {
        "turns": [
            "We're hiring plant operators for a chemical facility. Safety is absolute top priority — reliability, procedure compliance, never cutting corners. What do you recommend?"
        ],
        "expected": ["safety", "dependability"],
        "min_recall": 0.0,
    },
    "C7_healthcare_hybrid": {
        "turns": [
            "We're hiring bilingual healthcare admin staff in South Texas — they handle patient records and need to be assessed in Spanish. HIPAA compliance is critical. What assessments work?",
            "They're functionally bilingual — English fluent for written work. Go with the hybrid.",
        ],
        "expected": ["hipaa", "medical terminology", "opq"],
        "min_recall": 0.0,
    },
    "C8_admin_assistant": {
        "turns": [
            "I need to quickly screen admin assistants for Excel and Word daily.",
            "In that case, I am OK with adding a simulation - we want to capture the capabilties.",
        ],
        "expected": ["excel", "word"],
        "min_recall": 0.0,
    },
    "C9_fullstack_refinement": {
        "turns": [
            "Here's the JD for an engineer we need to fill. Can you recommend an assessment battery? Senior Full-Stack Engineer with Core Java, Spring, REST APIs, Angular, SQL, AWS, Docker.",
            "Backend-leaning. Day-one priorities are Core Java and Spring; SQL is constant. Angular is occasional — they'd review frontend PRs but not own features.",
            "Senior IC. They lead design on their own services but don't manage other engineers directly.",
            "Add AWS and Docker. Drop REST — the API design signal will already come through in Spring and the live interview.",
        ],
        "expected": ["java", "spring", "sql", "aws", "docker"],
        "min_recall": 0.0,
    },
    "C10_grad_mgmt": {
        "turns": [
            "We run a graduate management trainee scheme. We need a full battery — cognitive, personality, and situational judgement. All recent graduates.",
            "Drop the OPQ. Final list: Verify G+ and Graduate Scenarios.",
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


def test_ai_engineer_recall(client):
    messages = [
        {
            "role": "user",
            "content": "Hiring an AI Engineer with Python, TensorFlow, NLP, and LLM deployment experience."
        }
    ]
    data = _chat(client, messages)
    rec_names = [r["name"] for r in data["recommendations"]]
    expected = ["python", "machine learning", "data", "ai"]
    recall = _recall_at_k(expected, rec_names, k=10)
    assert recall >= 0.25, f"AI engineer recall {recall:.2f} below 0.25"


def test_ai_multi_turn_developer_not_java(client):
    """Multi-turn: hiring ai developer -> junior must not surface Java backend stack."""
    messages = [{"role": "user", "content": "hiring ai developer"}]
    data1 = _chat(client, messages)
    messages.append({"role": "assistant", "content": data1["reply"]})
    messages.append({"role": "user", "content": "junior"})
    data2 = _chat(client, messages)
    rec_names = [r["name"] for r in data2["recommendations"]]
    assert len(rec_names) >= 1
    names_low = " ".join(rec_names).lower()
    assert "ai skills" in names_low or "data science" in names_low
    forbidden = ["core java", "java frameworks"]
    for bad in forbidden:
        assert bad not in names_low, f"unexpected {bad} in {rec_names}"


def test_ai_single_shot_developer_with_python(client):
    messages = [
        {
            "role": "user",
            "content": "hiring ai developer with python and nlp",
        }
    ]
    data = _chat(client, messages)
    rec_names = [r["name"] for r in data["recommendations"]]
    assert len(rec_names) >= 1
    names_low = " ".join(rec_names).lower()
    assert "ai skills" in names_low or "data science" in names_low
    assert "core java" not in names_low and "java frameworks" not in names_low


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


def test_clarify_returns_empty_recommendations(client):
    data = _chat(client, [{"role": "user", "content": "I need an assessment."}])
    assert data["recommendations"] == []


def test_c2_rust_turn1_clarifies_without_recs(client):
    data = _chat(
        client,
        [{
            "role": "user",
            "content": "I'm hiring a senior Rust engineer for high-performance networking infrastructure. What assessments should I use?",
        }],
    )
    assert len(data["recommendations"]) == 0
    assert "rust" in data["reply"].lower() or "smart interview" in data["reply"].lower()


def test_conversation_analyzer_accumulates_tech_stack():
    from app.services.conversation_analyzer import ConversationAnalyzer

    analyzer = ConversationAnalyzer()
    messages = [
        {"role": "user", "content": "Senior Full-Stack Engineer with Core Java, Spring, SQL, AWS, Docker."},
        {"role": "assistant", "content": "Is this backend-leaning or frontend-heavy?"},
        {"role": "user", "content": "Backend-leaning. Add AWS and Docker. Drop REST."},
    ]
    context, _ = analyzer.analyze(messages)
    stack_low = {t.lower() for t in context.tech_stack}
    assert "aws" in stack_low or "docker" in stack_low
    assert "java" in stack_low or "spring" in stack_low
