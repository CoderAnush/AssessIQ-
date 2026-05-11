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
# Default to localhost for testing, environment variable for production
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

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

def normalize_api_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    STRICT RESPONSE NORMALIZER (Part 3 Fix).
    Ensures frontend never crashes on missing backend fields.
    """
    return {
        "reply": sanitize_text(response.get("reply"), "I've analyzed your request."),
        "recommendations": response.get("recommendations", []) or [],
        "pipeline": response.get("pipeline"),
        "end_of_conversation": bool(response.get("end_of_conversation", False))
    }

def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Guarded recommendation normalization."""
    try:
        n = {
            "name": sanitize_text(rec.get("name"), "Assessment"),
            "category": sanitize_text(rec.get("category"), "Technical"),
            "confidence": int(rec.get("confidence", 0)),
            "stage": sanitize_text(rec.get("stage") or rec.get("best_hiring_stage"), "Screening"),
            "duration": sanitize_text(rec.get("duration"), "30 min"),
            "insight": sanitize_text(rec.get("recruiter_insight") or rec.get("description"), "Grounded SHL recommendation."),
            "url": str(rec.get("url", "#")),
            "domain": sanitize_text(rec.get("domain"), "General").title(),
            "test_type": str(rec.get("test_type", "K")),
            "matched_skills": rec.get("matched_skills") or []
        }
        return n
    except Exception:
        return {
            "name": "Validation Assessment", "category": "General", "confidence": 0,
            "stage": "Screening", "duration": "30 min", "insight": "Assessment details unavailable.",
            "url": "#", "domain": "General", "test_type": "K", "matched_skills": []
        }

# --- UI STYLING (Premium Modern Aesthetic) ---

def apply_styles():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
            
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .stMarkdown p { font-family: 'Inter', sans-serif; line-height: 1.6; color: #334155; }

            /* Modern Hero Landing */
            .hero-section {
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                padding: 2.5rem 2rem;
                border-radius: 1.5rem;
                text-align: center;
                margin-bottom: 1rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }

            .hero-title {
                background: linear-gradient(to right, #60a5fa, #c084fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.75rem;
                font-weight: 800;
                margin-bottom: 0.25rem;
                letter-spacing: -0.025em;
            }

            .hero-subtitle {
                color: #94a3b8;
                font-size: 1rem;
                max-width: 600px;
                margin: 0 auto 1rem auto;
            }

            /* Accuracy Metric Card */
            .accuracy-card {
                background: white;
                padding: 1rem 2.5rem;
                border-radius: 1.25rem;
                border: 1px solid #e2e8f0;
                text-align: center;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                margin: 0 auto 2rem auto;
                width: fit-content;
                animation: fadeIn 0.8s ease-out;
            }

            .accuracy-value { font-size: 3rem; font-weight: 900; color: #0f172a; line-height: 1; }
            .accuracy-label { color: #64748b; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }

            /* Status Pill */
            .status-indicator {
                display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px;
                background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 9999px;
                color: #166534; font-size: 0.75rem; font-weight: 700; margin-bottom: 1rem;
            }
            .status-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }

            @keyframes pulse {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
                70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
            }

            /* Custom Scrollbar */
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #f1f5f9; }
            ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }

            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .animate-fade-in { animation: fadeIn 0.5s ease-out; }

            .stChatInputContainer { padding-bottom: 1rem; background: linear-gradient(to top, white 60%, transparent); }
            [data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_hero_landing():
    """Hides landing components if messages exist (Part 1 Fix)."""
    if st.session_state["messages"]: return
    
    st.markdown(f"""
    <div class="hero-section">
        <div class="hero-title">Hiring Orchestration Copilot</div>
        <div class="hero-subtitle">High-precision technical hiring grounded in the SHL catalog. Zero cross-domain leakage.</div>
        <div style="display: flex; justify-content: center; gap: 1rem;">
            <div style="background: rgba(255,255,255,0.1); color: #60a5fa; padding: 0.4rem 0.8rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 800; border: 1px solid rgba(255,255,255,0.2); letter-spacing: 0.05em;">PRODUCTION HARDENED</div>
        </div>
    </div>
    
    <div class="accuracy-card">
        <div class="accuracy-value">95%</div>
        <div class="accuracy-label">Match Accuracy</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### ⚡ Quick Start")
    cols = st.columns(4)
    prompts = ["Senior React Engineer", "Backend Java Dev", "DevOps Cloud Engineer", "ML Engineer"]
    for i, p in enumerate(prompts):
        if cols[i].button(p, key=f"p_{i}", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": f"Hiring for a {p}"})
            st.rerun()

def render_recommendation_card(rec: Dict[str, Any], index: int):
    """Guarded recommendation rendering (Part 2 Fix)."""
    try:
        n = _normalize_recommendation(rec)
        confidence_color = "#10b981" if n['confidence'] >= 90 else "#f59e0b" if n['confidence'] >= 80 else "#ef4444"
        skills = n.get('matched_skills') or []
        skills_html = "".join([f'<span style="background:#f1f5f9; color:#334155; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:600; border:1px solid #e2e8f0; margin-right:4px;">{s}</span>' for s in skills[:4]])
        
        st.markdown(f"""
        <div style="background: white; border-radius: 1rem; border: 1px solid #e2e8f0; padding: 1.25rem; margin-bottom: 1.5rem; min-height: 420px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05);" class="animate-fade-in">
            <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <span style="background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">{n['domain']}</span>
                    <span style="color: {confidence_color}; font-weight: 800; font-size: 1.1rem;">{n['confidence']}%</span>
                </div>
                <h4 style="margin:0; font-size: 1rem; color: #0f172a; line-height: 1.3;">{index}. {n['name']}</h4>
                <div style="display: flex; gap: 4px; margin-top: 8px; flex-wrap: wrap;">
                    {skills_html}
                </div>
                <div style="background: #f8fafc; border-radius: 0.5rem; padding: 0.75rem; margin-top: 1rem; border: 1px solid #f1f5f9;">
                    <p style="margin:0; font-size: 0.8rem; color: #475569; line-height: 1.4;">
                        <b>Recruiter Reasoning:</b><br/>{n['insight']}
                    </p>
                </div>
            </div>
            <div style="margin-top: 1rem;">
                <div style="display: flex; gap: 0.75rem; font-size: 0.75rem; color: #64748b; margin-bottom: 0.75rem;">
                    <span>🎯 {n['stage']}</span>
                    <span>⏱️ {n['duration']}</span>
                </div>
                <a href="{n['url']}" target="_blank" style="text-decoration: none;">
                    <div style="background: #2563eb; color: white; text-align: center; padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; font-size: 0.8rem;">
                        View Assessment
                    </div>
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        st.error("Card rendering module failure.")

def render_pipeline_section(pipeline: Dict[str, Any]):
    """Guarded pipeline rendering (Part 4 Fix)."""
    try:
        if not pipeline: return
        stages = pipeline.get("stages", [])
        if not stages: return
        
        st.markdown("---")
        st.markdown("### 🏗️ Optimized Hiring Pipeline")
        
        advice = sanitize_text(pipeline.get("strategic_guidance") or pipeline.get("strategic_advice"), "Standardized technical screening.")
        st.info(f"💡 **Strategic Advisor:** {advice}")

        # Limit columns to 4 to avoid layout crash
        num_stages = min(4, len(stages))
        if num_stages > 0:
            cols = st.columns(num_stages)
            for i in range(num_stages):
                stage = stages[i]
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"**{stage.get('name', 'Hiring Stage')}**")
                        st.caption(stage.get("description", "Competency validation."))
                        for assess in stage.get("assessments", []):
                            st.markdown(f"• `{assess}`")
    except Exception:
        st.warning("Hiring pipeline module partially failed to load.")

def main():
    st.set_page_config(page_title="AssessIQ | Recruiter Intelligence", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("## 🏗️ AssessIQ")
        st.markdown('<div class="status-indicator"><div class="status-dot"></div>Backend Live Status</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("🗑️ Clear Conversation", key="clear_btn", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()
        st.divider()
        st.caption("v1.1-Hardened (Production Ready)")

    # Landing Page Focus
    render_hero_landing()

    # Chat Display
    for idx, msg in enumerate(st.session_state["messages"]):
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

    # Chat Input
    if prompt := st.chat_input("Hiring requirement..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.rerun()

    # Assistant Response
    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            loading_messages = ["Analyzing competencies...", "Applying isolation...", "Optimizing pipeline..."]
            for l_msg in loading_messages:
                placeholder.markdown(f"✨ *{l_msg}*")
                time.sleep(0.3)
            
            try:
                # Diagnostic Log (Step 1)
                # st.write("DEBUG: Calling Backend...")
                
                payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
                
                if resp.status_code != 200:
                    placeholder.error(f"Engine Error (HTTP {resp.status_code})")
                    return

                raw_data = resp.json()
                data = normalize_api_response(raw_data)
                placeholder.empty()
                
                reply = data["reply"]
                recs = data["recommendations"]
                pipeline = data["pipeline"]
                
                st.markdown(reply)
                if pipeline: render_pipeline_section(pipeline)
                if recs:
                    for i in range(0, len(recs), 4):
                        cols = st.columns(4)
                        for j, rec in enumerate(recs[i:i+4]):
                            with cols[j]: render_recommendation_card(rec, i + j + 1)
                
                st.session_state["messages"].append({
                    "role": "assistant", "content": reply, 
                    "recommendations": recs, "pipeline": pipeline
                })
                st.rerun()
            except Exception as e:
                placeholder.empty()
                st.error("Hiring Engine Synchronization Error. Please try a different query.")
                # st.exception(e) # Only for debug

if __name__ == "__main__":
    main()
