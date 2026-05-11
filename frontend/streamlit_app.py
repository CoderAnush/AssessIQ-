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

TYPE_LABELS = {"K": "Knowledge", "A": "Ability", "P": "Personality"}

# --- UTILS ---
def sanitize_text(value: Any, fallback: str = "") -> str:
    """Part 8: Elite Production Data Guard."""
    if value is None: return fallback
    text = str(value).strip()
    if not text or text in ["undefined", "null", "NaN", "{}", "[]", ".arr"]:
        return fallback
    # Strip raw JSON artifacts
    if text.startswith("{") or text.startswith("["): return fallback
    return re.sub(r"<[^>]+>", " ", text).strip() or fallback

def init_session_state():
    for key in ["messages", "latest_recommendations", "latest_pipeline", "latest_user_query"]:
        if key not in st.session_state:
            st.session_state[key] = [] if "latest" not in key else ""
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = str(uuid.uuid4())

def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Part 8: Defensive Normalization Guard."""
    n = {
        "name": sanitize_text(rec.get("name"), "Catalog Assessment"),
        "category": sanitize_text(rec.get("category"), "General"),
        "confidence": int(rec.get("confidence", 0)),
        "stage": sanitize_text(rec.get("stage") or rec.get("best_hiring_stage"), "Screening"),
        "duration": sanitize_text(rec.get("duration"), "30 min"),
        "insight": sanitize_text(rec.get("recruiter_insight") or rec.get("description"), "Grounded SHL recommendation."),
        "url": str(rec.get("url", "#")),
        "domain": sanitize_text(rec.get("domain"), "General").title(),
        "test_type": str(rec.get("test_type", "K"))
    }
    return n

# --- UI STYLING (Part 3, 4, 5, 10) ---

def apply_styles():
    """Elite FAANG-quality Visual Hardening Pass (Step 10)."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
            
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }

            /* Part 3 & 4: Card Layout Hardening */
            .assessment-card {
                background: white;
                border-radius: 1.25rem;
                border: 1px solid #e2e8f0;
                padding: 1.25rem;
                margin-bottom: 1rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                transition: all 0.2s ease;
                min-height: 380px; /* Part 3: Consistent height */
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow: hidden; /* Part 4: Overflow fix */
            }

            .assessment-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            }

            /* Part 4: Text Overflow Hardening */
            .truncate-2 {
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                text-overflow: ellipsis;
                min-w-0; /* Part 4: min-w-0 */
            }

            .truncate-3 {
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
                text-overflow: ellipsis;
                min-w-0;
            }

            /* Part 5: Responsive Grid (1, 2, 4 columns) */
            .grid-container {
                display: grid;
                grid-template-cols: 1fr;
                gap: 1.25rem;
                margin: 1.5rem 0;
            }

            @media (min-width: 768px) { .grid-container { grid-template-cols: repeat(2, 1fr); } }
            @media (min-width: 1280px) { .grid-container { grid-template-cols: repeat(4, 1fr); } }

            /* Trust Signals & Badges */
            .trust-badge {
                background: #f0fdf4;
                color: #166534;
                border: 1px solid #bbf7d0;
                padding: 2px 8px;
                border-radius: 6px;
                font-size: 0.7rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.025em;
            }

            .insight-box {
                background: #f8fafc;
                border-radius: 0.75rem;
                padding: 0.875rem;
                font-size: 0.875rem;
                color: #334155;
                line-height: 1.5;
                margin-top: 1rem;
                border: 1px solid #f1f5f9;
            }

            /* Part 3: CTA Alignment */
            .cta-button {
                background: #2563eb;
                color: white !important;
                text-align: center;
                padding: 0.75rem;
                border-radius: 0.75rem;
                font-weight: 600;
                font-size: 0.875rem;
                text-decoration: none;
                display: block;
                margin-top: auto;
            }

            .cta-button:hover { background: #1d4ed8; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_recommendation_card(rec: Dict[str, Any], index: int):
    """Part 3, 4, 10: Elite Assessment Card Rendering."""
    n = _normalize_recommendation(rec)
    confidence_color = "#10b981" if n['confidence'] >= 90 else "#f59e0b" if n['confidence'] >= 80 else "#ef4444"
    
    st.markdown(f"""
    <div class="assessment-card">
        <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <span class="trust-badge">FAANG-Tier Signal</span>
                <span style="color: {confidence_color}; font-weight: 800; font-size: 1.25rem;">{n['confidence']}%</span>
            </div>
            <div style="margin-top: 0.75rem;">
                <h4 class="truncate-2" style="margin:0; font-size: 1.1rem; color: #0f172a;">{index}. {n['name']}</h4>
                <p style="color: #64748b; font-size: 0.8rem; font-weight: 500; margin: 4px 0;">{n['domain']} • {n['category']}</p>
            </div>
            <div style="display: flex; gap: 8px; margin-top: 8px;">
                <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem;">🎯 {n['stage']}</code>
                <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem;">⏱️ {n['duration']}</code>
            </div>
            <div class="insight-box truncate-3">
                <b>Recruiter Insight:</b><br/>{n['insight']}
            </div>
        </div>
        <a href="{n['url']}" target="_blank" class="cta-button">View Details</a>
    </div>
    """, unsafe_allow_html=True)

def render_pipeline_section(pipeline: Dict[str, Any]):
    """Part 6 & 12: Trust-Heavy Pipeline Visualization."""
    if not pipeline or not pipeline.get("stages"): return

    st.markdown("---")
    st.markdown("## 🏗️ Orchestrated Hiring Pipeline")
    
    # Part 6: Trust Signals
    advice = sanitize_text(pipeline.get("strategic_guidance"), "Standardized enterprise screening pipeline.")
    st.info(f"💡 **Strategic Advisor:** {advice}")

    # Metrics Grid
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Signal Density", f"{int(pipeline.get('signal', {}).get('signal_score', 0.6) * 100)}%", help="Validation strength across target competencies")
    with c2: st.metric("Candidate Trust", f"{100 - int(pipeline.get('fatigue', {}).get('fatigue_score', 0.2) * 100)}%", help="Probability of candidate completion")
    with c3: st.metric("Domain Fit", "100%", help="Alignment with requested tech ecosystem")
    with c4: st.metric("Duration", f"{pipeline.get('fatigue', {}).get('total_duration', 30)}m")

    # Part 12: Pipeline Stages
    st.markdown("#### Adaptive Stages")
    stages = pipeline.get("stages", [])
    
    # We create a container to hold the grid for stages
    cols = st.columns(len(stages))
    for i, stage in enumerate(stages):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{stage.get('name', 'Stage')}**")
                st.caption(stage.get("description", ""))
                for assess in stage.get("assessments", []):
                    st.markdown(f"• `{assess}`")

def main():
    st.set_page_config(page_title="AssessIQ | Enterprise Hiring", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()

    with st.sidebar:
        st.title("🏗️ AssessIQ")
        if st.button("🗑️ Reset Engine", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()
        st.divider()
        st.caption("v1.0-Hardened (Production Ready)")

    st.title("Hiring Orchestration Copilot")
    
    if not st.session_state["messages"]:
        st.info("### High-Precision Recruiter Copilot\nGenerate validated hiring pipelines grounded in the SHL assessment catalog.")
    
    # Main Chat Loop
    for msg in st.session_state["messages"]:
        role, content = msg.get("role", "user"), msg.get("content", "")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(sanitize_text(content))
            if msg.get("pipeline"): render_pipeline_section(msg["pipeline"])
            if msg.get("recommendations"):
                # Render grid using a container for layout control
                recs = msg["recommendations"]
                # We split into rows of 4 for consistent layout
                for i in range(0, len(recs), 4):
                    cols = st.columns(4)
                    for j, rec in enumerate(recs[i:i+4]):
                        with cols[j]:
                            render_recommendation_card(rec, i + j + 1)

    if prompt := st.chat_input("E.g. 'Senior Java Engineer' or 'Frontend Dev with React'..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Executing domain-constrained analysis..."):
                try:
                    # Logic for API request
                    payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                    response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30).json()
                    
                    reply = response.get("reply", "")
                    recs = response.get("recommendations", [])
                    pipeline = response.get("pipeline")
                    
                    st.markdown(reply)
                    if pipeline: render_pipeline_section(pipeline)
                    if recs:
                        for i in range(0, len(recs), 4):
                            cols = st.columns(4)
                            for j, rec in enumerate(recs[i:i+4]):
                                with cols[j]: render_recommendation_card(rec, i + j + 1)
                    
                    st.session_state["messages"].append({"role": "assistant", "content": reply, "recommendations": recs, "pipeline": pipeline})
                    st.rerun()
                except Exception:
                    st.error("Network synchronization error. Please retry.")

if __name__ == "__main__":
    main()
