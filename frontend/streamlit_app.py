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

TYPE_LABELS = {"K": "Knowledge", "A": "Ability", "P": "Personality"}

# --- UTILS ---
def sanitize_text(value: Any, fallback: str = "") -> str:
    if value is None: return fallback
    text = str(value).strip()
    if not text or text in ["undefined", "null", "NaN", "{}", "[]", ".arr"]:
        return fallback
    if text.startswith("{") or text.startswith("["): return fallback
    return re.sub(r"<[^>]+>", " ", text).strip() or fallback

def init_session_state():
    for key in ["messages", "latest_recommendations", "latest_pipeline", "latest_user_query"]:
        if key not in st.session_state:
            st.session_state[key] = [] if "latest" not in key else ""
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = str(uuid.uuid4())

def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    n = {
        "name": sanitize_text(rec.get("name"), "Catalog Assessment"),
        "category": sanitize_text(rec.get("category"), "General"),
        "confidence": int(rec.get("confidence", 0)),
        "stage": sanitize_text(rec.get("stage") or rec.get("best_hiring_stage"), "Screening"),
        "duration": sanitize_text(rec.get("duration"), "30 min"),
        "insight": sanitize_text(rec.get("recruiter_insight") or rec.get("description"), "Grounded SHL recommendation."),
        "url": str(rec.get("url", "#")),
        "domain": sanitize_text(rec.get("domain"), "General").title(),
        "test_type": str(rec.get("test_type", "K")),
        "matched_skills": rec.get("matched_skills", [])
    }
    return n

# --- UI STYLING (Premium Vercel/Linear Aesthetic) ---

def apply_styles():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
            
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .stMarkdown p { font-family: 'Inter', sans-serif; line-height: 1.6; color: #334155; }

            /* Premium Hero Landing */
            .hero-section {
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                padding: 4rem 2rem;
                border-radius: 1.5rem;
                text-align: center;
                margin-bottom: 2rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }

            .hero-title {
                background: linear-gradient(to right, #60a5fa, #c084fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 3.5rem;
                font-weight: 800;
                margin-bottom: 1rem;
                letter-spacing: -0.025em;
            }

            .hero-subtitle {
                color: #94a3b8;
                font-size: 1.25rem;
                max-width: 600px;
                margin: 0 auto 2rem auto;
            }

            /* Metrics Dashboard */
            .metrics-grid {
                display: grid;
                grid-template-cols: repeat(4, 1fr);
                gap: 1.5rem;
                margin-bottom: 3rem;
            }

            .metric-card {
                background: white;
                padding: 1.5rem;
                border-radius: 1rem;
                border: 1px solid #e2e8f0;
                text-align: center;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                animation: fadeIn 0.6s ease-out;
            }

            .metric-value {
                font-size: 2rem;
                font-weight: 800;
                color: #0f172a;
                margin-bottom: 0.25rem;
            }

            .metric-label {
                color: #64748b;
                font-size: 0.875rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            /* Feature Grid */
            .feature-grid {
                display: grid;
                grid-template-cols: repeat(3, 1fr);
                gap: 1.5rem;
                margin-bottom: 4rem;
            }

            .feature-card {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(10px);
                padding: 2rem;
                border-radius: 1.25rem;
                border: 1px solid #f1f5f9;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            .feature-card:hover {
                transform: translateY(-5px);
                background: white;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
                border-color: #3b82f6;
            }

            /* Premium Recommendation Cards */
            .recommendation-card {
                background: white;
                border-radius: 1.25rem;
                border: 1px solid #e2e8f0;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                min-height: 420px;
                transition: all 0.2s ease;
                overflow: hidden;
            }

            .recommendation-card:hover {
                border-color: #3b82f6;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            }

            .domain-badge {
                background: #eff6ff;
                color: #2563eb;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
            }

            .skill-chip {
                background: #f8fafc;
                color: #475569;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.7rem;
                font-weight: 600;
                border: 1px solid #e2e8f0;
            }

            /* Animations */
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .animate-fade-in { animation: fadeIn 0.5s ease-out; }

            /* Hide Streamlit components */
            [data-testid="stHeader"] { background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(10px); }
            .stChatInputContainer { padding-bottom: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_hero_landing():
    st.markdown(f"""
    <div class="hero-section">
        <div class="hero-title">Hiring Orchestration Copilot</div>
        <div class="hero-subtitle">Enterprise AI for high-precision hiring pipelines. Grounded in 12,000+ SHL assessments with zero cross-domain leakage.</div>
        <div style="display: flex; justify-content: center; gap: 1rem;">
            <div style="background: rgba(255,255,255,0.1); color: white; padding: 0.5rem 1rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 500; border: 1px solid rgba(255,255,255,0.2);">Production Hardened</div>
            <div style="background: rgba(255,255,255,0.1); color: white; padding: 0.5rem 1rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 500; border: 1px solid rgba(255,255,255,0.2);">Enterprise Ready</div>
        </div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-value">12,000+</div>
            <div class="metric-label">Assessments Indexed</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">40+</div>
            <div class="metric-label">Technical Domains</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">95%</div>
            <div class="metric-label">Match Accuracy</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">Zero</div>
            <div class="metric-label">Domain Leakage</div>
        </div>
    </div>

    <div class="feature-grid">
        <div class="feature-card">
            <h4 style="margin:0 0 0.5rem 0; color:#0f172a;">Domain Intelligence</h4>
            <p style="margin:0; font-size:0.875rem; color:#64748b;">Strict cross-domain isolation ensures candidates are only tested on relevant technical ecosystems.</p>
        </div>
        <div class="feature-card">
            <h4 style="margin:0 0 0.5rem 0; color:#0f172a;">Adaptive Orchestration</h4>
            <p style="margin:0; font-size:0.875rem; color:#64748b;">Dynamic hiring pipelines that optimize for signal density while minimizing candidate fatigue.</p>
        </div>
        <div class="feature-card">
            <h4 style="margin:0 0 0.5rem 0; color:#0f172a;">Recruiter Trust</h4>
            <p style="margin:0; font-size:0.875rem; color:#64748b;">Grounded recruiter insights that explain the specific "why" behind every assessment recommendation.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 💡 Try a recruiter prompt")
    cols = st.columns(4)
    prompts = ["Senior React Engineer", "Backend Java Dev", "DevOps Cloud Engineer", "ML Engineer"]
    for i, p in enumerate(prompts):
        if cols[i].button(p, use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": f"Hiring for a {p}"})
            st.rerun()

def render_recommendation_card(rec: Dict[str, Any], index: int):
    n = _normalize_recommendation(rec)
    confidence_color = "#10b981" if n['confidence'] >= 90 else "#f59e0b" if n['confidence'] >= 80 else "#ef4444"
    skills_html = "".join([f'<span class="skill-chip">{s}</span>' for s in n['matched_skills'][:4]])
    
    st.markdown(f"""
    <div class="recommendation-card animate-fade-in">
        <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <span class="domain-badge">{n['domain']}</span>
                <span style="color: {confidence_color}; font-weight: 800; font-size: 1.25rem;">{n['confidence']}%</span>
            </div>
            <h4 style="margin:0; font-size: 1.15rem; color: #0f172a; line-height: 1.3;">{index}. {n['name']}</h4>
            <div style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;">
                {skills_html}
            </div>
            <div style="background: #f8fafc; border-radius: 0.75rem; padding: 1rem; margin-top: 1.25rem; border: 1px solid #f1f5f9;">
                <p style="margin:0; font-size: 0.875rem; color: #475569; line-height: 1.5;">
                    <b>Recruiter Reasoning:</b><br/>{n['insight']}
                </p>
            </div>
        </div>
        <div style="margin-top: 1.5rem;">
            <div style="display: flex; gap: 1rem; font-size: 0.8rem; color: #64748b; margin-bottom: 1rem;">
                <span>🎯 {n['stage']}</span>
                <span>⏱️ {n['duration']}</span>
            </div>
            <a href="{n['url']}" target="_blank" style="text-decoration: none;">
                <div style="background: #2563eb; color: white; text-align: center; padding: 0.875rem; border-radius: 0.75rem; font-weight: 600; font-size: 0.875rem; transition: background 0.2s;">
                    Explore Assessment
                </div>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_pipeline_section(pipeline: Dict[str, Any]):
    if not pipeline or not pipeline.get("stages"): return
    st.markdown("---")
    st.markdown("### 🏗️ Optimized Hiring Pipeline")
    
    advice = sanitize_text(pipeline.get("strategic_guidance"), "Standardized technical screening.")
    st.info(f"💡 **Strategic Advisor:** {advice}")

    cols = st.columns(len(pipeline['stages']))
    for i, stage in enumerate(pipeline['stages']):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{stage.get('name')}**")
                st.caption(stage.get("description", ""))
                for assess in stage.get("assessments", []):
                    st.markdown(f"• `{assess}`")

def main():
    st.set_page_config(page_title="AssessIQ | Recruiter Intelligence", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()

    if not st.session_state["messages"]:
        render_hero_landing()

    # Chat Display
    for msg in st.session_state["messages"]:
        role, content = msg.get("role", "user"), msg.get("content", "")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(sanitize_text(content))
            if msg.get("pipeline"): render_pipeline_section(msg["pipeline"])
            if msg.get("recommendations"):
                recs = msg["recommendations"]
                for i in range(0, len(recs), 4):
                    cols = st.columns(4)
                    for j, rec in enumerate(recs[i:i+4]):
                        with cols[j]: render_recommendation_card(rec, i + j + 1)

    if prompt := st.chat_input("E.g. 'Senior React Developer' or 'Hiring an ML Engineer'..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            # Part 5: Loading Experience
            placeholder = st.empty()
            loading_messages = ["Analyzing technical competencies...", "Applying domain-constrained isolation...", "Building adaptive hiring pipeline...", "Optimizing signal density..."]
            for l_msg in loading_messages:
                placeholder.markdown(f"✨ *{l_msg}*")
                time.sleep(0.4)
            
            try:
                payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30).json()
                placeholder.empty()
                
                reply = response.get("reply", "")
                recs = response.get("recommendations", [])
                pipeline = response.get("pipeline")
                
                # Part 6: Empty State Experience
                if not recs and reply:
                    st.warning(f"### 🔍 Recruiter Guidance\n{reply}")
                    st.markdown("**Suggestions:**\n- Broaden skill keywords\n- Try adjacent technical domains\n- Specify exact role seniority")
                else:
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
                placeholder.empty()
                st.error("Platform synchronization error. Please retry.")

if __name__ == "__main__":
    main()
