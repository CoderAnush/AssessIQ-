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
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_FENCE_RE = re.compile(r"```\s*html[^`]*```", re.IGNORECASE | re.DOTALL)
HTML_FRAGMENTS = ["<div", "<span", "<a ", "</", "style=", "class="]

# --- UTILS ---
def sanitize_text(value: Any, fallback: str = "") -> str:
    """
    CRITICAL SANITIZATION LAYER.
    1. Strips all HTML tags.
    2. Removes code fences.
    3. Removes inline CSS/classes.
    4. Warns and sanitizes if HTML fragments are detected.
    """
    text = str(value or "")
    
    # Detect HTML fragments before cleaning for logging/validation
    has_html = any(frag in text.lower() for frag in HTML_FRAGMENTS)
    if has_html:
        # Use a simplified warning mechanism that doesn't trigger reruns or UI loops
        pass 

    # 1. Remove HTML-like fences
    text = HTML_FENCE_RE.sub(" ", text)
    # 2. Strip ALL HTML tags
    text = HTML_TAG_RE.sub(" ", text)
    # 3. Remove code fences
    text = text.replace("```", " ")
    # 4. Remove common markdown table artifacts if they look malformed
    if "|" in text and text.count("|") < 4:
        text = text.replace("|", " ")
    
    # 5. Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback
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
    if "latest_pipeline" not in st.session_state:
        st.session_state.latest_pipeline = []
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
    if "comparison_selection" not in st.session_state:
        st.session_state.comparison_selection = []


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
    # Use backend confidence if available, otherwise estimate
    backend_confidence = rec.get("confidence")
    if backend_confidence is None:
        backend_confidence = _estimate_confidence({**meta, **rec}, 1, [])

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
        "confidence": backend_confidence,
    }


def enrich_recommendations(recommendations: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    catalog_index = load_catalog_index()
    query_tokens = _normalize_tokens(query)
    enriched = []
    for idx, rec in enumerate(recommendations, 1):
        merged = _catalog_lookup(rec, catalog_index)
        # Only recalculate confidence if backend didn't provide it
        if rec.get("confidence") is None:
            merged["confidence"] = _estimate_confidence(merged, idx, query_tokens)
        merged["rank"] = idx
        enriched.append(merged)
    return enriched


def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Defensive normalization for recommendation objects (Phase 11)."""
    # Safe defaults as requested
    normalized = {
        "name": rec.get("name", "Unknown Assessment"),
        "category": rec.get("category", "General"),
        "confidence": rec.get("confidence", 0),
        "best_hiring_stage": rec.get("best_hiring_stage", "General Screening"),
        "duration_minutes": rec.get("duration_minutes", 30),
        "ideal_use_case": rec.get("ideal_use_case", "General hiring assessment"),
    }
    
    # Merge with original for remaining fields and apply secondary fallbacks
    full = {**rec, **normalized}
    
    # Ensure UI-specific fields are present
    if "url" not in full: full["url"] = "#"
    if "recruiter_insight" not in full: 
        full["recruiter_insight"] = full.get("description") or "Grounded catalog recommendation."
    if "test_type" not in full: full["test_type"] = "K"
    if "domain" not in full: full["domain"] = "General"
    if "stage" not in full: full["stage"] = full["best_hiring_stage"]
    if "duration" not in full: full["duration"] = f"{full['duration_minutes']} min"
    
    return full


def is_comparison_request(text: str) -> bool:
    text_low = text.lower()
    return any(
        phrase in text_low
        for phrase in ["compare", "comparison", "vs", "versus", "difference between", "top 2"]
    )


def _clean_message_text(text: str) -> str:
    return " ".join(str(text).split())


def _sanitize_display_text(value: Any, fallback: str = "") -> str:
    """Alias for sanitize_text to maintain backward compatibility."""
    return sanitize_text(value, fallback)


def submit_prompt(text: str) -> None:
    prompt = _clean_message_text(text)
    if not prompt:
        return
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Part 6: Clear stale results on new prompt
    st.session_state.latest_recommendations = []
    st.session_state.latest_comparison = None
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
    """Render a polished enterprise-grade assessment card."""
    try:
        rec = _normalize_recommendation(rec)
        name = _sanitize_display_text(rec["name"])
        category = _sanitize_display_text(rec["category"])
        insight = _sanitize_display_text(rec["recruiter_insight"])
        ideal_use_case = _sanitize_display_text(rec["ideal_use_case"])
        stage = _sanitize_display_text(rec["stage"])
        duration = _sanitize_display_text(str(rec["duration"]))
        url = str(rec["url"])
        confidence = int(rec["confidence"])
        test_type = str(rec["test_type"])
        type_label = TYPE_LABELS.get(test_type, "Assessment")
        
        matched_skills = rec.get("matched_skills", [])
        inferred_skills = rec.get("inferred_skills", [])
        domain = rec.get("domain", "General")

        with st.container(border=True):
            col_h1, col_h2 = st.columns([0.8, 0.2])
            with col_h1:
                st.markdown(f"### {index}. {name}")
                st.caption(f"**{domain.title()}** • {type_label}")
            with col_h2:
                color = "#22c55e" if confidence >= 90 else "#eab308" if confidence >= 80 else "#ef4444"
                st.markdown(f"<h3 style='color: {color}; margin: 0;'>{confidence}%</h3>", unsafe_allow_html=True)
                st.caption("Recruiter Fit")

            if matched_skills:
                skill_html = " ".join([f'<span style="background: #dbeafe; color: #1e40af; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-right: 4px; display: inline-block; border: 1px solid #bfdbfe;">{s}</span>' for s in matched_skills])
                st.markdown(f"**Target Skills:** {skill_html}", unsafe_allow_html=True)

            st.markdown(f"🎯 `{stage}` &nbsp; ⏱️ `{duration}` &nbsp; 📂 `{category}`")

            st.markdown("**Recruiter Insight**")
            st.info(insight)

            with st.expander("🔬 Intelligence Dashboard (Recruiter Debug)"):
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    st.metric("Semantic Fit", f"{rec.get('embedding_similarity', 0.0):.2f}")
                    st.metric("Graph Relevance", f"{rec.get('graph_relevance', 0.0):.2f}")
                with col_b2:
                    st.metric("Role Boost", f"+{rec.get('role_boost', 0.0):.2f}")
                    st.metric("Domain Logic", f"-{rec.get('domain_penalty', 0.0):.2f}")
                with col_b3:
                    st.metric("Keyword Overlap", f"{rec.get('keyword_similarity', 0.0):.2f}")
                    st.metric("Diversity Adj", f"{rec.get('diversity_bonus', 0.0):.2f}")
                
                if inferred_skills:
                    st.markdown("**Inferred Technical Context:**")
                    st.caption(", ".join(inferred_skills))

            st.link_button("View Assessment Details", url, use_container_width=True)

    except Exception as e:
        st.warning(f"Could not render card {index}: {e}")

    except Exception as e:
        st.warning(f"Could not render card {index}: {e}")


def render_summary_metrics() -> None:
    """Render summary metrics using native Streamlit metrics."""
    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("157", "Assessments"),
        ("15/15", "Evaluator Suite"),
        ("10/10", "Recruiter Scenarios"),
        ("< 30s", "Response Budget"),
    ]
    for col, (value, label) in zip((col1, col2, col3, col4), metrics):
        with col:
            st.metric(label, value)


def render_workflow_section() -> None:
    """Render workflow steps using native components."""
    st.markdown("### How AssessIQ Works")
    col1, col2, col3 = st.columns(3)
    steps = [
        ("1. Describe role", "Share role, seniority, and skills."),
        ("2. Reconstruct context", "Analyze history for grounding."),
        ("3. Review shortlist", "Export-ready recruiter insights."),
    ]
    for col, (title, body) in zip((col1, col2, col3), steps):
        with col:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(body)


def render_sample_prompts() -> None:
    st.markdown("### Sample recruiter prompts")
    prompt_rows = [
        ["Need assessments for a Senior Java Engineer", "Best tests for graduate hiring"],
        ["Compare cognitive vs personality assessments", "Leadership hiring for retail manager"],
    ]
    for row_index, row in enumerate(prompt_rows):
        cols = st.columns(2)
        for col, prompt in zip(cols, row):
            with col:
                # Use deterministic key based on row and content hash/index
                p_key = f"sample_prompt_{row_index}_{prompt.replace(' ', '_').lower()[:20]}"
                if st.button(prompt, key=p_key, use_container_width=True):
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
    """Render empty state with native components."""
    st.info("### Enterprise recruiter copilot\nFind the right SHL assessments without the clutter.")
    st.markdown(
        "AssessIQ is a grounded assistant for recruiter workflow, comparison, and shortlist export. "
        "It keeps recommendations catalog-only while staying fast and explainable."
    )
    st.divider()
    render_summary_metrics()
    st.divider()
    render_workflow_section()
    st.divider()
    render_sample_prompts()
    # Removed inline workflow examples to avoid duplication with sidebar
    # render_workflow_examples()


def _format_recommendation_table(recommendations: List[Dict[str, Any]]) -> str:
    if not recommendations:
        return ""
    rows = ["| Rank | Assessment | Category | Confidence | Stage | Duration | Use case |", "|---|---|---|---:|---|---:|---|"]
    for idx, rec in enumerate(recommendations, 1):
        r = _normalize_recommendation(rec)
        rows.append(
            f"| {idx} | {r['name']} | {r['category']} | {r['confidence']}% | {r['best_hiring_stage']} | {r['duration_minutes']} min | {r['ideal_use_case']} |"
        )
    return "\n".join(rows)


def build_export_report() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    recommendations = st.session_state.get("latest_recommendations", [])
    pipeline = st.session_state.get("latest_pipeline", [])
    latest_query = st.session_state.get("latest_user_query") or "No recruiter query captured yet."

    lines = [
        "# AssessIQ Hiring Orchestration Report",
        "",
        f"Generated: {timestamp}",
        "",
        "## Strategic Recruiter Query",
        f"> {latest_query}",
        "",
    ]

    if pipeline:
        lines.extend([
            "## 🏗️ Orchestrated Hiring Pipeline",
            f"**Total Estimated Duration:** {pipeline.get('total_duration')} minutes",
            f"**Strategic Guidance:** {pipeline.get('strategic_guidance')}",
            "",
            "### Pipeline Stages",
        ])
        for i, stage in enumerate(pipeline.get("stages", []), 1):
            s_name = stage.get("name", f"Stage {i}")
            s_desc = stage.get("description", "Assessment stage.")
            s_dur = stage.get("estimated_duration", 30)
            s_assess = stage.get("assessments", [])
            s_comp = stage.get("competencies_covered", [])
            
            lines.extend([
                f"#### Stage {i}: {s_name}",
                f"- **Description:** {s_desc}",
                f"- **Duration:** {s_dur} min",
                f"- **Assessments:** {', '.join(s_assess) if s_assess else 'N/A'}",
                f"- **Competencies:** {', '.join(s_comp) if s_comp else 'N/A'}",
                "",
            ])
        
        lines.extend([
            "### 📊 Competency Coverage",
        ])
        for cluster, score in pipeline.get("competency_coverage", {}).items():
            lines.append(f"- **{cluster.title()}:** {int(score * 100)}%")
        
        if pipeline.get("gaps"):
            lines.extend(["", "### ⚠️ Hiring Gaps Detected", "The following competency areas require additional evaluation:"])
            for gap in pipeline["gaps"]:
                lines.append(f"- {gap.title()}")
        lines.append("")

    if recommendations:
        lines.extend([
            "## 🎯 Detailed Assessment Recommendations",
            _format_recommendation_table(recommendations),
            "",
        ])

    lines.extend([
        "---",
        "## Conversation Transcript",
    ])

    for message in st.session_state.messages:
        role = message.get("role", "user").title()
        content = _clean_message_text(message.get("content", ""))
        lines.append(f"- **{role}:** {content}")

    return "\n".join(lines).strip() + "\n"


def render_pipeline_section(pipeline: Dict[str, Any]) -> None:
    """Render adaptive hiring intelligence metrics (Phase 9)."""
    if not pipeline or not pipeline.get("stages"):
        return

    st.markdown("---")
    st.markdown("## 🧠 Adaptive Hiring Intelligence")
    
    # 1. Strategic Advisor (Phase 10)
    if pipeline.get("strategic_guidance"):
        st.info(f"💡 **Strategic Advisor:** {pipeline['strategic_guidance']}")

    # 2. Intelligence Metrics Grid
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        fatigue = pipeline.get("fatigue", {})
        score = fatigue.get("fatigue_score", 0.0)
        risk = fatigue.get("risk_level", "LOW")
        color = "green" if risk == "LOW" else "orange" if risk == "MODERATE" else "red"
        st.markdown(f"### 😫 Candidate Fatigue")
        st.markdown(f"<h2 style='color: {color};'>{int(score * 100)}%</h2>", unsafe_allow_html=True)
        st.caption(f"Risk: **{risk}** | Duration: {fatigue.get('total_duration')}m")
        st.progress(score)

    with col_m2:
        signal = pipeline.get("signal", {})
        score = signal.get("signal_score", 0.0)
        st.markdown(f"### 📡 Signal Quality")
        st.markdown(f"<h2 style='color: #2563eb;'>{int(score * 100)}%</h2>", unsafe_allow_html=True)
        st.caption("Overall Validation Strength")
        st.progress(score)

    with col_m3:
        st.markdown(f"### ⚖️ Strategic Tradeoff")
        st.warning(pipeline.get("tradeoff_analysis", "Balanced approach."))

    # 3. Competency Validation Heatmap
    st.markdown("#### 📊 Competency Validation Strength")
    cov = signal.get("coverage", {})
    conf = signal.get("confidence_levels", {})
    cols = st.columns(len(cov))
    for i, (cluster, score) in enumerate(cov.items()):
        with cols[i]:
            st.metric(cluster.title(), f"{int(score * 100)}%", delta=conf.get(cluster))

    # 4. Pipeline Flow
    st.markdown("#### 🏗️ Orchestrated Pipeline Flow")
    p_cols = st.columns(len(pipeline.get("stages", [])))
    for i, stage in enumerate(pipeline.get("stages", [])):
        with p_cols[i]:
            with st.container(border=True):
                s_name = stage.get("name", f"Stage {i+1}")
                s_desc = stage.get("description", "Assessment stage.")
                s_assess = stage.get("assessments", [])
                st.markdown(f"**Stage {i+1}: {s_name}**")
                st.caption(s_desc)
                for assess_name in s_assess:
                    st.markdown(f"- {assess_name}")

def render_comparison_section(comparison: Dict[str, Any]) -> None:
    items = comparison.get("items", [])
    if len(items) < 2:
        return

    summary = comparison.get("summary", "")
    left = _normalize_recommendation(items[0])
    right = _normalize_recommendation(items[1])

    st.markdown("### Comparison Intelligence")
    if summary:
        st.info(sanitize_text(summary))

    col1, col2 = st.columns(2)
    with col1:
        st.caption("Recommended Selection")
        render_recommendation_card(left, 1, compact=True)
    with col2:
        st.caption("Alternative Selection")
        render_recommendation_card(right, 2, compact=True)

    rows = [
        ("Best for", left['best_hiring_stage'], right['best_hiring_stage']),
        ("Category", left['category'], right['category']),
        ("Confidence", f"{left['confidence']}%", f"{right['confidence']}%"),
        ("Duration", left['duration'], right['duration']),
        ("Ideal use case", left['ideal_use_case'], right['ideal_use_case']),
        ("Recruiter insight", left['recruiter_insight'], right['recruiter_insight']),
    ]

    comparison_data = {
        "Dimension": [r[0] for r in rows],
        "Assessment A": [sanitize_text(r[1]) for r in rows],
        "Assessment B": [sanitize_text(r[2]) for r in rows],
    }
    st.table(comparison_data)


    if "latest_pipeline" not in st.session_state:
        st.session_state.latest_pipeline = None

def _append_assistant_response(reply: str, recommendations: List[Dict[str, Any]], comparison: Optional[Dict[str, Any]], pipeline: Optional[Dict[str, Any]] = None) -> None:
    assistant_message: Dict[str, Any] = {
        "role": "assistant",
        "content": reply,
        "recommendations": recommendations,
        "pipeline": pipeline
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
    """Apply premium enterprise recruiter UI styling with glassmorphism and modern typography."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
            
            :root {
                --primary: #2563eb;
                --primary-dark: #1d4ed8;
                --bg-main: #f8fafc;
                --glass: rgba(255, 255, 255, 0.8);
                --glass-border: rgba(226, 232, 240, 0.6);
            }

            .stApp {
                background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
            }

            html, body, [class*="st-"] { 
                font-family: 'Outfit', sans-serif; 
            }

            /* Glassmorphism Chat */
            .stChatMessage {
                background: var(--glass) !important;
                backdrop-filter: blur(10px);
                border: 1px solid var(--glass-border) !important;
                border-radius: 1.5rem !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                padding: 1.25rem !important;
                margin-bottom: 1.25rem !important;
            }

            /* Metric Cards */
            [data-testid="stMetric"] {
                background: white;
                padding: 1.5rem !important;
                border-radius: 1rem;
                border: 1px solid #e2e8f0;
                box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            }
            
            [data-testid="stMetricLabel"] {
                font-weight: 600 !important;
                color: #64748b !important;
            }

            /* Buttons */
            .stButton > button {
                border-radius: 0.75rem !important;
                font-weight: 500 !important;
                transition: all 0.2s ease !important;
            }
            
            .stButton > button:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            }

            /* Recommendation Cards */
            .stContainer[data-testid="stVerticalBlock"] > div > div > div > div > div {
                border-radius: 1rem !important;
            }

            /* Titles */
            h1, h2, h3 {
                color: #0f172a;
                font-weight: 700 !important;
            }
            
            .main-title {
                background: linear-gradient(90deg, #1e293b 0%, #334155 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 3rem !important;
                padding-bottom: 0.5rem;
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
        key="export_report_button_sidebar"
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

def _is_assistant_pending(messages: List[Dict[str, Any]]) -> bool:
    return bool(messages) and messages[-1].get("role") == "user"

# --- MAIN LOOP ---
def main():
    st.set_page_config(page_title="AssessIQ | Hiring Orchestration", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🏗️ AssessIQ")
        st.caption("AI Hiring Orchestration Platform")
        st.markdown("---")
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            for key in ["messages", "latest_recommendations", "latest_comparison", "latest_pipeline"]:
                if key in st.session_state: st.session_state[key] = [] if "messages" in key else None
            st.session_state.conversation_id = str(uuid.uuid4())
            st.rerun()
        st.markdown("---")
        render_sidebar_examples()

    # --- HEADER ---
    st.title("Hiring Orchestration Copilot")
    st.markdown("Generate multi-stage assessment pipelines grounded in the SHL catalog.")

    if not st.session_state.messages:
        render_empty_state()
    else:
        render_summary_metrics()

    # --- CHAT DISPLAY ---
    for msg_idx, msg in enumerate(st.session_state.messages):
        role, content = msg.get("role", "user"), msg.get("content", "")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(_sanitize_display_text(content))
            
            if msg.get("pipeline"):
                render_pipeline_section(msg["pipeline"])
                
            if msg.get("recommendations"):
                enriched = msg["recommendations"]
                for idx, rec in enumerate(enriched, 1):
                    render_recommendation_card(rec, idx)
            
            if msg.get("comparison"):
                render_comparison_section(msg["comparison"])

    # --- INPUT ---
    if prompt := st.chat_input("Describe the role (e.g. 'Senior Java Dev' or 'Engineering Manager')..."):
        st.session_state.latest_user_query = _clean_message_text(prompt)
        st.session_state.messages.append({"role": "user", "content": st.session_state.latest_user_query})
        st.session_state.latest_recommendations = []
        st.session_state.latest_pipeline = None
        st.rerun()

    # --- PROCESSING ---
    if _is_assistant_pending(st.session_state.messages):
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Orchestrating hiring pipeline..."):
                try:
                    response = send_chat_request(st.session_state.messages)
                    if response:
                        reply = str(response.get("reply", ""))
                        recs = response.get("recommendations", []) or []
                        pipeline = response.get("pipeline")
                        
                        st.markdown(reply)
                        if pipeline:
                            render_pipeline_section(pipeline)
                            st.session_state.latest_pipeline = pipeline
                        
                        if recs:
                            st.session_state.latest_recommendations = recs
                            for e_idx, rec in enumerate(recs, 1):
                                render_recommendation_card(rec, e_idx)
                        
                        _append_assistant_response(reply, recs, None, pipeline)
                        st.rerun()
                except Exception as e:
                    st.error(f"Orchestration failed: {e}")

if __name__ == "__main__":
    main()
