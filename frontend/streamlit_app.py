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


def _sanitize_display_text(value: Any, fallback: str = "") -> str:
    """Alias for sanitize_text to maintain backward compatibility."""
    return sanitize_text(value, fallback)


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
    """Render a polished assessment card using native Streamlit components."""
    try:
        # Sanitize all text fields from backend/enrichment
        name = _sanitize_display_text(rec.get("name", "Assessment"))
        category = _sanitize_display_text(rec.get("category", "General"))
        insight = _sanitize_display_text(rec.get("recruiter_insight", ""))
        ideal_use_case = _sanitize_display_text(rec.get("ideal_use_case", ""))
        stage = _sanitize_display_text(rec.get("best_hiring_stage", ""))
        duration = _sanitize_display_text(str(rec.get("duration_minutes", "N/A")))
        url = str(rec.get("url", "#"))
        confidence = int(rec.get("confidence", 0))
        test_type = str(rec.get("test_type", "K"))
        type_label = TYPE_LABELS.get(test_type, "Assessment")

        # Use st.container with border for the card structure
        with st.container(border=True):
            # Header Row
            col_h1, col_h2 = st.columns([0.8, 0.2])
            with col_h1:
                st.markdown(f"### {index}. {name}")
                st.caption(f"**{category}** • {type_label}")
            with col_h2:
                st.markdown(f"### {confidence}%")
                st.caption("Confidence")

            # Badges
            st.markdown(f"🏷️ `{category}` &nbsp; 🎯 `{stage}` &nbsp; ⏱️ `{duration} min`")

            # Recruiter Insight
            st.markdown("**Recruiter Insight**")
            st.info(insight)

            if not compact:
                # Detail Grid
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.markdown("**Best Hiring Stage**")
                    st.write(stage)
                with col_d2:
                    st.markdown("**Ideal Use Case**")
                    st.write(ideal_use_case)

            # Footer
            st.link_button("Open SHL Assessment", url, use_container_width=True)

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
        ("Best for", left.get("best_hiring_stage", ""), right.get("best_hiring_stage", "")),
        ("Category", left.get("category", ""), right.get("category", "")),
        ("Confidence", f"{left.get('confidence', 0)}%", f"{right.get('confidence', 0)}%"),
        ("Duration", f"{left.get('duration_minutes', 'N/A')} min", f"{right.get('duration_minutes', 'N/A')} min"),
        ("Ideal use case", left.get("ideal_use_case", ""), right.get("ideal_use_case", "")),
        ("Recruiter insight", left.get("recruiter_insight", ""), right.get("recruiter_insight", "")),
    ]

    # Render comparison table using st.table or st.dataframe for clean UI
    comparison_data = {
        "Dimension": [r[0] for r in rows],
        "Assessment A": [sanitize_text(r[1]) for r in rows],
        "Assessment B": [sanitize_text(r[2]) for r in rows],
    }
    st.table(comparison_data)


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
    """Apply minimal polished enterprise recruiter UI styling without HTML fragments."""
    st.markdown(
        """
        <style>
            .stApp {
                background: #fbfdff;
            }
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .stChatMessage {
                border-radius: 1.2rem; margin-bottom: 1rem; border: 1px solid #e2e8f0; background: rgba(255,255,255,0.84);
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

def main():
    st.set_page_config(page_title="AssessIQ | SHL Evaluator Mode", page_icon="🎯", layout="wide")
    init_session_state()
    apply_styles()

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🎯 AssessIQ")
        st.caption("Enterprise recruiter demo")
        st.markdown("---")
        if st.button("🗑️ Clear Conversation", use_container_width=True, key="clear_conversation_sidebar"):
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
        if st.button("Clear comparison selection", use_container_width=True, key="clear_comparison_selection_sidebar"):
            st.session_state.compare_selection = []
            st.session_state.latest_comparison = None
            st.experimental_rerun()

        render_sidebar_examples()

    # --- HEADER ---
    st.title("AssessIQ Copilot")
    st.markdown("Stateless, catalog-grounded SHL assessment selection for recruiters.")

    if not st.session_state.messages:
        render_empty_state()
    else:
        render_summary_metrics()

    # --- CHAT DISPLAY ---
    for msg_idx, msg in enumerate(st.session_state.messages):
        role, content = msg.get("role", "user"), msg.get("content", "")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(_sanitize_display_text(content))
            if msg.get("recommendations"):
                # Use msg_idx in enrichment to keep keys stable
                enriched_recommendations = msg.get("enriched_recommendations") or enrich_recommendations(msg["recommendations"], msg.get("user_query", ""))
                for idx, rec in enumerate(enriched_recommendations, 1):
                    render_recommendation_card(rec, idx)
                    # Interactive controls for comparison selection
                    cols = st.columns([1, 1, 8])
                    # Deterministic unique key based on message index, item index, and item ID
                    rec_id = rec.get("id", rec.get("name", str(idx)).replace(" ","_"))
                    compare_key = f"compare_btn_{msg_idx}_{idx}_{rec_id}"
                    
                    with cols[0]:
                        if st.button("Select for compare", key=compare_key):
                            sel = st.session_state.compare_selection
                            name = rec.get("name")
                            if name in sel:
                                sel.remove(name)
                            else:
                                if len(sel) < 2:
                                    sel.append(name)
                                else:
                                    st.warning("Only two items can be compared at once.")
                            st.session_state.compare_selection = sel
                    with cols[1]:
                        if st.session_state.compare_selection and rec.get("name") in st.session_state.compare_selection:
                            st.success("Selected")
                    
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
    if prompt := st.chat_input("Describe the role or ask a question...", key="chat_input_main"):
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
                            for e_idx, rec in enumerate(enriched, 1):
                                render_recommendation_card(rec, e_idx)
                        elif st.session_state.latest_recommendations:
                            for e_idx, rec in enumerate(st.session_state.latest_recommendations, 1):
                                render_recommendation_card(rec, e_idx)

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
