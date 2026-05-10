import html
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# --- CONFIGURATION ---
BACKEND_URL = os.environ.get("BACKEND_URL", "https://assess-iq-backend.onrender.com")
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "catalog_processed.json"

TYPE_LABELS = {
    "K": "Knowledge",
    "A": "Ability",
    "P": "Personality",
}

CATEGORY_THEMES = {
    "technical": {"accent": "#2563eb", "bg": "#eff6ff", "border": "#bfdbfe", "text": "#1d4ed8"},
    "personality": {"accent": "#0f766e", "bg": "#ecfdf5", "border": "#a7f3d0", "text": "#0f766e"},
    "cognitive": {"accent": "#b45309", "bg": "#fffbeb", "border": "#fde68a", "text": "#b45309"},
    "leadership": {"accent": "#be123c", "bg": "#fff1f2", "border": "#fecdd3", "text": "#be123c"},
    "behavioral": {"accent": "#0f766e", "bg": "#ecfeff", "border": "#a5f3fc", "text": "#155e75"},
    "general": {"accent": "#334155", "bg": "#f8fafc", "border": "#e2e8f0", "text": "#334155"},
}

ROLE_WORD_RE = re.compile(r"[a-z0-9]+")

# --- UTILS ---
def init_session_state():
    """Initialize persistent session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    if "last_processed_signature" not in st.session_state:
        st.session_state.last_processed_signature = ""
    if "last_query_time" not in st.session_state:
        st.session_state.last_query_time = 0
    if "latest_recommendations" not in st.session_state:
        st.session_state.latest_recommendations = []
    if "latest_comparison" not in st.session_state:
        st.session_state.latest_comparison = None
    if "latest_user_query" not in st.session_state:
        st.session_state.latest_user_query = ""
    if "latest_reply" not in st.session_state:
        st.session_state.latest_reply = ""
    if "request_errors" not in st.session_state:
        st.session_state.request_errors = []
    if "request_in_progress" not in st.session_state:
        st.session_state.request_in_progress = False
    if "compare_selection" not in st.session_state:
        st.session_state.compare_selection = []


@st.cache_data(show_spinner=False)
def load_catalog_index() -> Dict[str, Dict[str, Any]]:
    """Load processed catalog metadata for frontend enrichment."""
    if not CATALOG_PATH.exists():
        return {}

    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assessments = payload.get("assessments", []) if isinstance(payload, dict) else payload
    index: Dict[str, Dict[str, Any]] = {}
    for item in assessments:
        name = str(item.get("name", "")).strip().lower()
        if name:
            index[name] = item
    return index


def _normalize_tokens(value: str) -> List[str]:
    return [token for token in ROLE_WORD_RE.findall(value.lower()) if len(token) > 1]


def _display_category(value: str) -> str:
    if not value:
        return "General"
    return str(value).replace("_", " ").title()


def _category_theme(category: str) -> Dict[str, str]:
    return CATEGORY_THEMES.get(str(category).lower(), CATEGORY_THEMES["general"])


def _infer_best_stage(category: str, difficulty: Optional[str], use_cases: List[str]) -> str:
    category_low = str(category).lower()
    if category_low in {"technical", "cognitive", "ability", "analytical"}:
        return "Screening"
    if category_low in {"leadership", "personality", "behavioral", "communication"}:
        return "Final-stage evaluation"
    if difficulty and str(difficulty).lower() == "advanced":
        return "Final-stage evaluation"
    if any("leadership" in str(item).lower() for item in use_cases):
        return "Shortlist / leadership review"
    return "Early screening"


def _build_recruiter_insight(meta: Dict[str, Any]) -> str:
    use_cases = meta.get("recruiter_use_cases") or []
    description = str(meta.get("description", "")).strip()
    if use_cases:
        return str(use_cases[0])
    if description:
        return description
    return "Catalog-grounded assessment for recruiter screening."


def _estimate_confidence(rec: Dict[str, Any], index: int, query_tokens: List[str]) -> int:
    name_tokens = set(_normalize_tokens(rec.get("name", "")))
    category_tokens = set(_normalize_tokens(str(rec.get("category", ""))))
    skill_tokens = set(_normalize_tokens(" ".join(rec.get("skill_tags", []))))
    role_tokens = set(_normalize_tokens(" ".join(rec.get("ideal_roles", []))))
    metadata_tokens = name_tokens | category_tokens | skill_tokens | role_tokens | set(_normalize_tokens(rec.get("description", "")))

    overlap = len(set(query_tokens).intersection(metadata_tokens))
    base = 94 - ((index - 1) * 5)
    adjustment = min(8, overlap * 2)
    score = max(70, min(99, base + adjustment))
    return int(score)


def _catalog_lookup(rec: Dict[str, Any], catalog_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    name_key = str(rec.get("name", "")).strip().lower()
    meta = catalog_index.get(name_key, {})
    category = meta.get("category") or rec.get("test_type", "K")
    duration = meta.get("duration_minutes")
    use_cases = meta.get("recruiter_use_cases") or []
    difficulty = meta.get("difficulty_level")
    stage = _infer_best_stage(category, difficulty, use_cases)
    insight = _build_recruiter_insight(meta)
    ideal_use_case = use_cases[0] if use_cases else meta.get("description", "Grounded catalog recommendation.")

    return {
        "name": rec.get("name", ""),
        "url": rec.get("url", ""),
        "test_type": rec.get("test_type", "K"),
        "category": _display_category(category),
        "category_slug": str(category).lower() if category else "general",
        "duration_minutes": duration if duration is not None else "N/A",
        "best_hiring_stage": stage,
        "recruiter_insight": insight,
        "ideal_use_case": ideal_use_case,
        "description": meta.get("description", ""),
        "difficulty_level": difficulty,
        "ideal_roles": meta.get("ideal_roles", []),
        "skill_tags": meta.get("skill_tags", []),
        "confidence": _estimate_confidence({**meta, **rec}, 1, []),
    }


def enrich_recommendations(recommendations: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    catalog_index = load_catalog_index()
    query_tokens = _normalize_tokens(query)
    enriched = []
    for idx, rec in enumerate(recommendations, 1):
        merged = _catalog_lookup(rec, catalog_index)
        merged["confidence"] = _estimate_confidence(merged, idx, query_tokens)
        merged["rank"] = idx
        enriched.append(merged)
    return enriched


def is_comparison_request(text: str) -> bool:
    text_low = text.lower()
    return any(
        phrase in text_low
        for phrase in ["compare", "comparison", "vs", "versus", "difference between", "top 2"]
    )


def _clean_message_text(text: str) -> str:
    return " ".join(str(text).split())


def submit_prompt(text: str) -> None:
    prompt = _clean_message_text(text)
    if not prompt:
        return
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()


def _current_signature(messages: List[Dict[str, Any]]) -> str:
    if not messages:
        return ""
    last = messages[-1]
    return f"{len(messages)}:{last.get('role','')}:{last.get('content','')}"

def send_chat_request(messages: List[Dict]) -> Optional[Dict]:
    """Send conversation history to backend."""
    try:
        start_time = time.time()
        payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in messages]}
        headers = {"X-Session-ID": st.session_state.conversation_id}
        
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.last_query_time = time.time() - start_time
            st.session_state.request_errors = []
            return data
        else:
            st.session_state.request_errors = [f"Backend Error: {response.status_code}"]
            return None
    except Exception as e:
        st.session_state.request_errors = [f"Connection Error: {e}"]
        return None

# --- UI COMPONENTS ---

def render_recommendation_card(rec: Dict[str, Any], index: int, compact: bool = False) -> None:
    """Render a polished assessment card with local catalog enrichment."""
    try:
        type_label = TYPE_LABELS.get(str(rec.get("test_type", "K")), "Assessment")
        theme = _category_theme(rec.get("category_slug", "general"))
        confidence = int(rec.get("confidence", 0))
        insight = html.escape(str(rec.get("recruiter_insight", "")))
        ideal_use_case = html.escape(str(rec.get("ideal_use_case", "")))
        stage = html.escape(str(rec.get("best_hiring_stage", "")))
        duration = html.escape(str(rec.get("duration_minutes", "N/A")))
        category = html.escape(str(rec.get("category", "General")))
        name = html.escape(str(rec.get("name", "Assessment")))
        url = html.escape(str(rec.get("url", "#")))

        compact_class = " compact" if compact else ""
        html_block = f"""
        <div class="recommendation-card{compact_class}" style="--theme-accent: {theme['accent']}; --theme-bg: {theme['bg']}; --theme-border: {theme['border']}; --theme-text: {theme['text']};">
            <div class="card-top-row">
                <div class="rank-pill">#{index}</div>
                <div class="score-pill">{confidence}% confidence</div>
            </div>

            <div class="card-title-row">
                <div>
                    <div class="assessment-name">{name}</div>
                    <div class="assessment-subtitle">{category} assessment</div>
                </div>
                <div class="type-pill">{type_label}</div>
            </div>

            <div class="badge-row">
                <span class="badge badge-category">{category}</span>
                <span class="badge badge-stage">{stage}</span>
                <span class="badge badge-duration">{duration} min</span>
            </div>

            <div class="insight-block">
                <div class="insight-label">Recruiter insight</div>
                <div class="insight-text">{insight}</div>
            </div>

            <div class="detail-grid">
                <div>
                    <div class="detail-label">Best hiring stage</div>
                    <div class="detail-value">{stage}</div>
                </div>
                <div>
                    <div class="detail-label">Ideal use case</div>
                    <div class="detail-value">{ideal_use_case}</div>
                </div>
            </div>

            <div class="card-footer">
                <a href="{url}" target="_blank" class="shl-button">Open SHL assessment</a>
            </div>
        </div>
        """
        st.markdown(html_block, unsafe_allow_html=True)
    except Exception:
        st.warning(f"Could not render card {index}")


def render_summary_metrics() -> None:
    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("157", "grounded assessments"),
        ("15/15", "evaluator suite"),
        ("10/10", "recruiter scenarios"),
        ("< 30s", "response budget"),
    ]
    for col, (value, label) in zip((col1, col2, col3, col4), metrics):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_workflow_section() -> None:
    st.markdown('<div class="section-title">How AssessIQ Works</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    steps = [
        ("1. Describe the role", "Share the role, seniority, and the skills that matter most for the hiring decision."),
        ("2. Reconstruct context", "AssessIQ turns your full conversation into a grounded hiring profile before it recommends anything."),
        ("3. Review the shortlist", "You get a recruiter-friendly shortlist, comparison support, and a clean export for internal sharing."),
    ]
    for col, (title, body) in zip((col1, col2, col3), steps):
        with col:
            st.markdown(
                f"""
                <div class="workflow-card">
                    <div class="workflow-title">{title}</div>
                    <div class="workflow-body">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_sample_prompts() -> None:
    st.markdown('<div class="section-title">Sample recruiter prompts</div>', unsafe_allow_html=True)
    prompt_rows = [
        ["Need assessments for a Senior Java Engineer", "Best tests for graduate hiring"],
        ["Compare cognitive vs personality assessments", "Leadership hiring for retail manager"],
    ]
    for row_index, row in enumerate(prompt_rows):
        cols = st.columns(2)
        for col, prompt in zip(cols, row):
            with col:
                if st.button(prompt, key=f"sample_prompt_{row_index}_{prompt}", use_container_width=True):
                    submit_prompt(prompt)


def render_workflow_examples() -> None:
    with st.expander("Recruiter workflow examples", expanded=False):
        st.markdown(
            """
            - **Technical hiring:** Start with role and stack, then narrow by seniority and screening focus.
            - **Leadership hiring:** Clarify people management scope, behavioral fit, and final-stage evaluation.
            - **Graduate hiring:** Use learning agility and cognitive ability to build the early funnel.
            - **Customer support hiring:** Prioritize communication, empathy, and service orientation.
            """
        )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="hero-panel">
            <div class="hero-kicker">Enterprise recruiter copilot</div>
            <h2>Find the right SHL assessments without the clutter.</h2>
            <p>
                AssessIQ is a grounded assistant for recruiter workflow, comparison, and shortlist export.
                It keeps recommendations catalog-only while staying fast, explainable, and demo-ready.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_summary_metrics()
    render_workflow_section()
    render_sample_prompts()
    render_workflow_examples()


def _format_recommendation_table(recommendations: List[Dict[str, Any]]) -> str:
    if not recommendations:
        return ""
    rows = ["| Rank | Assessment | Category | Confidence | Stage | Duration | Use case |", "|---|---|---|---:|---|---:|---|"]
    for idx, rec in enumerate(recommendations, 1):
        rows.append(
            f"| {idx} | {rec['name']} | {rec['category']} | {rec['confidence']}% | {rec['best_hiring_stage']} | {rec['duration_minutes']} min | {rec['ideal_use_case']} |"
        )
    return "\n".join(rows)


def build_export_report() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    recommendations = st.session_state.latest_recommendations
    comparison = st.session_state.latest_comparison
    latest_query = st.session_state.latest_user_query or "No recruiter query captured yet."
    latest_reply = st.session_state.latest_reply or "No assistant response captured yet."

    lines = [
        "# AssessIQ Recruiter Report",
        "",
        f"Generated: {timestamp}",
        "",
        "## Recruiter Query",
        latest_query,
        "",
        "## Assistant Summary",
        latest_reply,
        "",
    ]

    if recommendations:
        lines.extend([
            "## Recommendations",
            _format_recommendation_table(recommendations),
            "",
        ])

    if comparison:
        lines.extend([
            "## Comparison Results",
            comparison.get("summary", ""),
            "",
            _format_recommendation_table(comparison.get("items", [])),
            "",
        ])

    lines.extend([
        "## Conversation Transcript",
    ])

    for message in st.session_state.messages:
        role = message.get("role", "user").title()
        content = _clean_message_text(message.get("content", ""))
        lines.append(f"- **{role}:** {content}")

    return "\n".join(lines).strip() + "\n"


def render_comparison_section(comparison: Dict[str, Any]) -> None:
    items = comparison.get("items", [])
    if len(items) < 2:
        return

    summary = comparison.get("summary", "")
    left, right = items[0], items[1]

    st.markdown('<div class="section-title">Comparison Intelligence</div>', unsafe_allow_html=True)
    if summary:
        st.markdown(f'<div class="comparison-summary">{html.escape(summary)}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="comparison-winner">Recommended winner</div>', unsafe_allow_html=True)
        render_recommendation_card(left, 1, compact=True)
    with col2:
        render_recommendation_card(right, 2, compact=True)

    rows = [
        ("Best for", left.get("best_hiring_stage", ""), right.get("best_hiring_stage", "")),
        ("Category", left.get("category", ""), right.get("category", "")),
        ("Confidence", f"{left.get('confidence', 0)}%", f"{right.get('confidence', 0)}%"),
        ("Duration", f"{left.get('duration_minutes', 'N/A')} min", f"{right.get('duration_minutes', 'N/A')} min"),
        ("Ideal use case", left.get("ideal_use_case", ""), right.get("ideal_use_case", "")),
        ("Recruiter insight", left.get("recruiter_insight", ""), right.get("recruiter_insight", "")),
    ]

    table_rows = [
        "<table class='comparison-table'>",
        "<thead><tr><th>Dimension</th><th>Assessment A</th><th>Assessment B</th></tr></thead>",
        "<tbody>",
    ]
    for label, left_value, right_value in rows:
        table_rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{html.escape(str(left_value))}</td><td>{html.escape(str(right_value))}</td></tr>"
        )
    table_rows.extend(["</tbody></table>"])
    st.markdown("".join(table_rows), unsafe_allow_html=True)


def _is_assistant_pending(messages: List[Dict[str, Any]]) -> bool:
    return bool(messages) and messages[-1].get("role") == "user"


def _append_assistant_response(reply: str, recommendations: List[Dict[str, Any]], comparison: Optional[Dict[str, Any]]) -> None:
    assistant_message: Dict[str, Any] = {
        "role": "assistant",
        "content": reply,
        "recommendations": recommendations,
    }
    if comparison:
        assistant_message["comparison"] = comparison
    st.session_state.messages.append(assistant_message)


def _build_comparison_context(reply: str) -> Optional[Dict[str, Any]]:
    if not st.session_state.latest_recommendations or len(st.session_state.latest_recommendations) < 2:
        return None

    items = st.session_state.latest_recommendations[:2]
    summary = reply.strip() or "Use Assessment A for high-volume screening. Use Assessment B for final-stage leadership evaluation."
    return {
        "summary": summary,
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

def apply_styles():
    """Apply polished enterprise recruiter UI styling."""
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(37, 99, 235, 0.08), transparent 25%),
                    radial-gradient(circle at top right, rgba(15, 118, 110, 0.06), transparent 20%),
                    #fbfdff;
            }
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
            .main-header {
                font-size: 2.75rem; font-weight: 800; color: #0f172a; margin-bottom: 0.25rem;
                background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 45%, #0f766e 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                letter-spacing: -0.02em;
            }
            .sub-header { font-size: 1.06rem; color: #64748b; margin-bottom: 1.75rem; font-weight: 400; max-width: 54rem; }
            .hero-panel {
                background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(15, 118, 110, 0.94));
                color: white; border-radius: 24px; padding: 28px 28px 26px 28px; margin-bottom: 1.4rem;
                box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16);
            }
            .hero-kicker {
                display: inline-block; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.18em;
                font-weight: 800; color: rgba(255, 255, 255, 0.8); margin-bottom: 0.85rem;
            }
            .hero-panel h2 { font-size: 2rem; line-height: 1.12; margin: 0 0 0.7rem 0; font-weight: 800; }
            .hero-panel p { margin: 0; color: rgba(255, 255, 255, 0.88); max-width: 46rem; font-size: 1rem; line-height: 1.55; }
            .section-title {
                font-size: 1rem; font-weight: 800; color: #0f172a; margin: 1.35rem 0 0.9rem 0;
                text-transform: uppercase; letter-spacing: 0.12em;
            }
            .metric-card, .workflow-card {
                background: rgba(255, 255, 255, 0.9); border: 1px solid #e2e8f0; border-radius: 18px;
                padding: 16px 16px 14px 16px; box-shadow: 0 10px 25px rgba(15, 23, 42, 0.04);
                height: 100%;
            }
            .metric-value { font-size: 1.45rem; font-weight: 800; color: #0f172a; line-height: 1.1; }
            .metric-label { font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; font-weight: 600; }
            .workflow-title { font-weight: 800; color: #0f172a; margin-bottom: 0.35rem; }
            .workflow-body { color: #475569; line-height: 1.55; font-size: 0.95rem; }
            .recommendation-card {
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.92));
                padding: 18px 18px 16px 18px; border-radius: 18px; border: 1px solid var(--theme-border, #e2e8f0);
                margin-bottom: 16px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
                transition: all 0.2s ease;
                position: relative;
                overflow: hidden;
            }
            .recommendation-card::before {
                content: ""; position: absolute; inset: 0 auto auto 0; width: 5px; height: 100%;
                background: linear-gradient(180deg, var(--theme-accent, #2563eb), transparent);
            }
            .recommendation-card.compact { margin-bottom: 12px; }
            .recommendation-card:hover { transform: translateY(-2px); box-shadow: 0 16px 34px rgba(15, 23, 42, 0.1); }
            .card-top-row, .card-title-row { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
            .card-top-row { margin-bottom: 10px; }
            .assessment-name { font-size: 1.16rem; font-weight: 800; color: #0f172a; line-height: 1.2; }
            .assessment-subtitle { font-size: 0.82rem; color: #64748b; margin-top: 0.2rem; }
            .rank-pill {
                background: var(--theme-bg, #eff6ff); color: var(--theme-text, #1d4ed8); border: 1px solid var(--theme-border, #dbeafe);
                border-radius: 999px; padding: 4px 10px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.02em;
            }
            .score-pill {
                background: linear-gradient(135deg, var(--theme-accent, #2563eb), #0f172a);
                color: white; border-radius: 999px; padding: 5px 11px; font-size: 0.76rem; font-weight: 800;
            }
            .type-pill {
                background: #f8fafc; color: #334155; border: 1px solid #e2e8f0; border-radius: 999px;
                padding: 4px 10px; font-size: 0.75rem; font-weight: 700; white-space: nowrap;
            }
            .badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 12px; }
            .badge {
                padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; border: 1px solid transparent;
            }
            .badge-category { background: var(--theme-bg, #eff6ff); color: var(--theme-text, #1d4ed8); border-color: var(--theme-border, #dbeafe); }
            .badge-stage { background: #f8fafc; color: #334155; border-color: #e2e8f0; }
            .badge-duration { background: #ecfeff; color: #155e75; border-color: #a5f3fc; }
            .insight-block {
                background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;
            }
            .insight-label { font-size: 0.72rem; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.35rem; }
            .insight-text { color: #0f172a; line-height: 1.55; font-size: 0.95rem; }
            .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
            .detail-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 800; color: #64748b; margin-bottom: 0.25rem; }
            .detail-value { color: #0f172a; font-size: 0.94rem; line-height: 1.45; }
            .comparison-summary {
                background: #0f172a; color: #e2e8f0; padding: 14px 16px; border-radius: 16px; margin-bottom: 12px;
                border: 1px solid rgba(255,255,255,0.08);
            }
            .comparison-winner {
                display: inline-block; margin-bottom: 10px; background: #ecfeff; color: #155e75;
                border: 1px solid #a5f3fc; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 800;
            }
            .comparison-table {
                width: 100%; border-collapse: collapse; margin-top: 12px; overflow: hidden; border-radius: 16px;
                border: 1px solid #e2e8f0; background: white;
            }
            .comparison-table th, .comparison-table td {
                padding: 12px 14px; border-bottom: 1px solid #e2e8f0; vertical-align: top; text-align: left;
            }
            .comparison-table th { background: #f8fafc; color: #0f172a; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.12em; }
            .comparison-table td { color: #334155; }
            .card-footer { margin-top: 12px; }
            .shl-button {
                display: inline-block; background: linear-gradient(135deg, #2563eb, #0f766e); color: white !important; padding: 10px 16px;
                border-radius: 12px; text-decoration: none !important; font-weight: 700; font-size: 0.88rem;
                transition: transform 0.2s ease, box-shadow 0.2s ease; text-align: center; width: 100%;
            }
            .shl-button:hover { transform: translateY(-1px); box-shadow: 0 12px 24px rgba(37, 99, 235, 0.22); }
            .stChatMessage {
                border-radius: 1.2rem; margin-bottom: 1rem; border: 1px solid #e2e8f0; background: rgba(255,255,255,0.84);
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0f172a 0%, #111827 100%); color: white;
            }
            [data-testid="stSidebar"] .stButton button {
                border-radius: 12px; border: 1px solid rgba(255,255,255,0.12);
            }
            [data-testid="stChatInput"] {
                position: sticky;
                bottom: 0;
                background: linear-gradient(180deg, rgba(251,253,255,0.12), rgba(251,253,255,0.96));
                backdrop-filter: blur(10px);
                padding-top: 10px;
                z-index: 20;
            }
            @media (max-width: 768px) {
                .main-header { font-size: 2.2rem; }
                .hero-panel { padding: 22px 20px; border-radius: 20px; }
                .hero-panel h2 { font-size: 1.55rem; }
                .detail-grid { grid-template-columns: 1fr; }
                .card-title-row, .card-top-row { flex-direction: column; align-items: flex-start; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_export() -> None:
    export_report = build_export_report()
    has_content = bool(st.session_state.messages)
    st.download_button(
        "⬇️ Export recruiter report",
        data=export_report,
        file_name=f"assessiq_recruiter_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
        use_container_width=True,
        disabled=not has_content,
    )


def render_sidebar_examples() -> None:
    st.markdown("### Recruiter workflow")
    st.caption("Built for fast hiring discovery, comparison, and shareable export.")
    st.markdown(
        """
        - Clarify the role and seniority
        - Review a grounded shortlist
        - Compare the top two options
        - Export the result for stakeholders
        """
    )
    st.markdown("---")
    render_sidebar_export()

def main():
    st.set_page_config(page_title="AssessIQ | SHL Evaluator Mode", page_icon="🎯", layout="wide")
    init_session_state()
    apply_styles()

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🎯 AssessIQ")
        st.caption("Enterprise recruiter demo")
        st.markdown("---")
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_id = str(uuid.uuid4())
            st.session_state.last_processed_signature = ""
            st.session_state.latest_recommendations = []
            st.session_state.latest_comparison = None
            st.session_state.latest_user_query = ""
            st.session_state.latest_reply = ""
            st.session_state.request_errors = []
            st.rerun()
        st.markdown("---")
        st.markdown("#### Comparison")
        sel = st.session_state.compare_selection or []
        if sel:
            for name in sel:
                st.markdown(f"- {name}")
        if st.button("Clear comparison selection", use_container_width=True):
            st.session_state.compare_selection = []
            st.session_state.latest_comparison = None
            st.experimental_rerun()

        render_sidebar_examples()

    # --- HEADER ---
    st.markdown('<h1 class="main-header">AssessIQ Copilot</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Stateless, catalog-grounded SHL assessment selection for recruiters who need a clean shortlist, a clear comparison, and a shareable export.</p>',
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        render_empty_state()
    else:
        render_summary_metrics()

    # --- CHAT DISPLAY ---
    for msg in st.session_state.messages:
        role, content = msg.get("role", "user"), msg.get("content", "")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(content)
            if msg.get("recommendations"):
                enriched_recommendations = msg.get("enriched_recommendations") or enrich_recommendations(msg["recommendations"], msg.get("user_query", ""))
                for idx, rec in enumerate(enriched_recommendations, 1):
                    render_recommendation_card(rec, idx)
                    # Interactive controls for comparison selection
                    cols = st.columns([1, 1, 8])
                    compare_key = f"compare_{idx}_{rec.get('name','').replace(' ','_')}_{st.session_state.conversation_id}"
                    with cols[0]:
                        if st.button("Select for compare", key=compare_key):
                            sel = st.session_state.compare_selection
                            name = rec.get("name")
                            if name in sel:
                                sel.remove(name)
                            else:
                                sel.append(name)
                            st.session_state.compare_selection = sel
                    with cols[1]:
                        if st.session_state.compare_selection and rec.get("name") in st.session_state.compare_selection:
                            st.markdown("<div style='font-weight:800;color:#0f766e;'>Selected</div>", unsafe_allow_html=True)
                    # If two items selected, build and render comparison
                    if len(st.session_state.compare_selection) == 2:
                        c_items = []
                        catalog_index = load_catalog_index()
                        for sel_name in st.session_state.compare_selection:
                            meta = catalog_index.get(sel_name.lower(), {})
                            # map to expected comparison item shape
                            c_items.append({
                                "name": meta.get("name", sel_name),
                                "url": meta.get("url", "#"),
                                "category": meta.get("category", "General"),
                                "confidence": 95,
                                "duration_minutes": meta.get("duration_minutes", "N/A"),
                                "ideal_use_case": (meta.get("recruiter_use_cases") or [meta.get("description", "")])[0],
                                "recruiter_insight": (meta.get("recruiter_use_cases") or [meta.get("description", "")])[0],
                                "best_hiring_stage": _infer_best_stage(meta.get("category"), meta.get("difficulty_level"), meta.get("recruiter_use_cases") or []),
                            })
                        comparison = {"summary": "Comparison generated by recruiter selection.", "items": c_items}
                        st.session_state.latest_comparison = comparison
                        render_comparison_section(comparison)
            if msg.get("comparison"):
                render_comparison_section(msg["comparison"])

    # --- INPUT ---
    if prompt := st.chat_input("Describe the role or ask a question..."):
        st.session_state.latest_user_query = _clean_message_text(prompt)
        st.session_state.messages.append({"role": "user", "content": st.session_state.latest_user_query})
        st.rerun()

    # --- PROCESSING ---
    if _is_assistant_pending(st.session_state.messages):
        signature = _current_signature(st.session_state.messages)
        if signature != st.session_state.last_processed_signature:
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Reconstructing context..."):
                    # Prevent duplicate requests from multiple reruns
                    if st.session_state.request_in_progress:
                        st.info("Request already in progress — waiting for result...")
                        response = None
                    else:
                        st.session_state.request_in_progress = True
                        try:
                            start_t = time.time()
                            response = send_chat_request(st.session_state.messages)
                            st.session_state.last_query_time = time.time() - start_t
                        except Exception as e:
                            response = None
                            st.session_state.request_errors.append(f"Request failed: {e}")
                        finally:
                            st.session_state.request_in_progress = False

                    if response:
                        reply = str(response.get("reply", ""))
                        recs = response.get("recommendations", []) or []
                        enriched = enrich_recommendations(recs, st.session_state.latest_user_query)
                        comparison = _build_comparison_context(reply) if is_comparison_request(st.session_state.latest_user_query) else None

                        st.markdown(reply)
                        if comparison:
                            st.session_state.latest_comparison = comparison
                            render_comparison_section(comparison)

                        if enriched:
                            st.session_state.latest_recommendations = enriched
                            for idx, rec in enumerate(enriched, 1):
                                render_recommendation_card(rec, idx)
                        elif st.session_state.latest_recommendations:
                            for idx, rec in enumerate(st.session_state.latest_recommendations, 1):
                                render_recommendation_card(rec, idx)

                        st.session_state.latest_reply = reply
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": reply,
                                "recommendations": recs,
                                "enriched_recommendations": enriched,
                                "comparison": comparison,
                                "user_query": st.session_state.latest_user_query,
                            }
                        )

                        st.session_state.last_processed_signature = signature

                        if comparison:
                            st.session_state.latest_comparison = comparison

                        st.caption(f"Latency: {st.session_state.last_query_time:.2f}s | Schema: Strict")
                    else:
                        if st.session_state.request_errors:
                            st.error(st.session_state.request_errors[-1])

if __name__ == "__main__":
    main()
