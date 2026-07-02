import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
MAX_USER_TURNS = 8
TYPE_LABELS = {"K": "Knowledge", "A": "Ability", "P": "Personality", "S": "Simulation", "B": "Biodata", "C": "Competency"}


def count_user_turns(messages: List[dict]) -> int:
    return sum(1 for m in messages if m.get("role") == "user")


def looks_like_fresh_role_query(text: str) -> bool:
    low = text.lower().strip()
    if any(p in low for p in ("compare", "add ", "remove ", "drop ", "perfect", "thank", "what did you")):
        return False
    return bool(
        re.search(r"\b(hiring|need|looking for|recruit|screening)\b", low)
        or re.search(r"\b(developer|engineer|manager|analyst|scientist|devops)\b", low)
    )


def sanitize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return re.sub(r"<[^>]+>", " ", text).strip() or fallback


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []


def check_health() -> tuple[str, str]:
    try:
        t0 = time.time()
        r = requests.get(f"{BACKEND_URL}/health", timeout=15)
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200 and r.json().get("status") == "ok":
            return "ok", f"Connected ({ms} ms)"
        return "warn", f"HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return "warn", "Cold start — retry in ~60s"
    except requests.exceptions.ConnectionError:
        return "error", "Cannot reach backend"


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
        .assessiq-header { background: #1e3a5f; color: white; padding: 1.25rem 1.5rem;
            border-radius: 0.5rem; margin-bottom: 1rem; }
        .assessiq-header h1 { margin: 0; font-size: 1.5rem; }
        .assessiq-header p { margin: 0.25rem 0 0; opacity: 0.85; font-size: 0.9rem; }
        .clarify-banner { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 0.5rem;
            padding: 0.75rem 1rem; margin: 0.5rem 0 1rem; color: #1e40af; font-size: 0.9rem; }
        .rec-card { background: white; border: 1px solid #e2e8f0; border-radius: 0.5rem;
            padding: 1rem; margin-bottom: 0.75rem; min-height: 160px; }
        .rec-type { display: inline-block; background: #1e3a5f; color: white; font-size: 0.65rem;
            font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def strip_table_from_reply(reply: str) -> str:
    if "| # |" in reply or "|---|" in reply:
        return reply.split("| # |")[0].split("|---|")[0].strip()
    return reply


def render_comparison_block(reply: str) -> None:
    if "### Comparison:" not in reply:
        return
    st.markdown("#### Assessment comparison")
    st.markdown(reply)


def render_cards(recs: List[Dict[str, Any]]) -> None:
    if not recs:
        return
    for i in range(0, len(recs), 2):
        cols = st.columns(2)
        for j, rec in enumerate(recs[i : i + 2]):
            tt = str(rec.get("test_type", "K")).split(",")[0].strip().upper()
            with cols[j]:
                st.markdown(
                    f"""<div class="rec-card">
                    <span class="rec-type">{TYPE_LABELS.get(tt, tt)}</span>
                    <h4 style="margin:0.5rem 0 0.25rem;">{sanitize_text(rec.get('name'))}</h4>
                    <p style="font-size:0.8rem;color:#64748b;margin:0;">
                    {sanitize_text(rec.get('duration'), '—')} · {sanitize_text(rec.get('category'), 'SHL')}</p>
                    <p style="font-size:0.8rem;color:#475569;margin-top:0.5rem;">
                    {sanitize_text(rec.get('recruiter_insight') or rec.get('description'), 'Catalog-grounded recommendation.')[:140]}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )
                url = rec.get("url", "#")
                if url and url != "#":
                    st.link_button("View on SHL", url, use_container_width=True)


def build_export_markdown(messages: List[dict]) -> str:
    lines = [
        "# AssessIQ Recruiter Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Backend:** {BACKEND_URL}",
        "",
    ]
    for m in messages:
        role = m["role"].title()
        lines.append(f"## {role}")
        lines.append(m.get("content", ""))
        lines.append("")
        for rec in m.get("recommendations") or []:
            lines.append(f"- **{rec.get('name')}** ({rec.get('test_type')}) — {rec.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    st.set_page_config(page_title="AssessIQ", page_icon="📋", layout="wide")
    init_session_state()
    apply_styles()

    with st.sidebar:
        st.markdown("### AssessIQ")
        status, detail = check_health()
        if status == "ok":
            st.success(detail)
        elif status == "warn":
            st.warning(detail)
        else:
            st.error(detail)
        st.caption(f"API: `{BACKEND_URL}`")
        turns = count_user_turns(st.session_state["messages"])
        st.caption(f"Turns: {turns}/{MAX_USER_TURNS}")
        if turns >= MAX_USER_TURNS - 1:
            st.warning("Near turn limit — clear or start a new role to avoid stale results.")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()
        if st.session_state["messages"]:
            st.download_button(
                "Download Markdown Report",
                build_export_markdown(st.session_state["messages"]),
                file_name="assessiq_report.md",
                mime="text/markdown",
                use_container_width=True,
            )

    st.markdown(
        '<div class="assessiq-header"><h1>AssessIQ</h1>'
        "<p>Conversational SHL assessment recommendations for recruiters</p></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state["messages"]:
        st.markdown("**Try a sample query:**")
        c1, c2, c3, c4 = st.columns(4)
        starters = [
            ("Leadership hiring", "We need a solution for senior leadership."),
            ("Contact centre", "Screening entry-level contact centre agents for US inbound calls."),
            ("Java backend", "Hiring a Java Spring Boot backend developer."),
            ("Vague query", "programmer"),
        ]
        for col, (label, prompt) in zip([c1, c2, c3, c4], starters):
            if col.button(label, use_container_width=True):
                st.session_state["messages"].append({"role": "user", "content": prompt})
                st.rerun()

    for m in st.session_state["messages"]:
        with st.chat_message(m["role"]):
            reply = sanitize_text(m.get("content"))
            recs = m.get("recommendations") or []
            if m["role"] == "assistant":
                if "### Comparison:" in reply:
                    render_comparison_block(reply)
                else:
                    display = strip_table_from_reply(reply) if recs else reply
                    st.markdown(display)
                if not recs and "?" in reply:
                    st.markdown(
                        '<div class="clarify-banner">Gathering requirements — no shortlist until context is clear.</div>',
                        unsafe_allow_html=True,
                    )
                render_cards(recs)
            else:
                st.markdown(reply)

    if prompt := st.chat_input("Describe the role or hiring need..."):
        user_turns = count_user_turns(st.session_state["messages"])
        if user_turns >= MAX_USER_TURNS or (
            user_turns >= 6 and looks_like_fresh_role_query(prompt)
        ):
            st.session_state["messages"] = []
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("_Thinking..._")
            try:
                payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=120)
                if resp.status_code != 200:
                    placeholder.empty()
                    st.error(f"Backend returned HTTP {resp.status_code}.")
                    return
                data = resp.json()
                placeholder.empty()
                reply = sanitize_text(data.get("reply"))
                recs = data.get("recommendations") or []
                if "### Comparison:" in reply:
                    render_comparison_block(reply)
                else:
                    st.markdown(strip_table_from_reply(reply) if recs else reply)
                if not recs and "?" in reply:
                    st.markdown(
                        '<div class="clarify-banner">Gathering requirements — no shortlist until context is clear.</div>',
                        unsafe_allow_html=True,
                    )
                render_cards(recs)
                st.session_state["messages"].append(
                    {"role": "assistant", "content": reply, "recommendations": recs}
                )
                st.rerun()
            except requests.exceptions.Timeout:
                placeholder.empty()
                st.error("Request timed out. The backend may be waking up — try again.")
            except requests.exceptions.ConnectionError:
                placeholder.empty()
                st.error("Cannot connect to the backend. Check BACKEND_URL and that the API is running.")


if __name__ == "__main__":
    main()
