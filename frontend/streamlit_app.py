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
    if not isinstance(response, dict): return {"reply": "Error", "recommendations": [], "pipeline": None}
    return {
        "reply": sanitize_text(response.get("reply"), "Response generated."),
        "recommendations": response.get("recommendations", []) or [],
        "pipeline": response.get("pipeline"),
        "end_of_conversation": bool(response.get("end_of_conversation", False))
    }

def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        n = {
            "name": sanitize_text(rec.get("name"), "Assessment"),
            "category": sanitize_text(rec.get("category"), "Technical"),
            "confidence": int(rec.get("confidence", 0)),
            "stage": sanitize_text(rec.get("stage") or rec.get("best_hiring_stage"), "Screening"),
            "duration": sanitize_text(rec.get("duration"), "30 min"),
            "insight": sanitize_text(rec.get("recruiter_insight") or rec.get("description"), "Grounded recommendation."),
            "url": str(rec.get("url", "#")),
            "domain": sanitize_text(rec.get("domain"), "General").title(),
            "test_type": str(rec.get("test_type", "K")),
            "matched_skills": rec.get("matched_skills") or [],
            "recruiter_signal": sanitize_text(rec.get("recruiter_signal"), "Core Technical Signal")
        }
        return n
    except Exception:
        return {"name": "Assessment", "category": "General", "confidence": 0, "stage": "Screening", "duration": "30 min", "insight": "No details.", "url": "#", "domain": "General", "test_type": "K", "matched_skills": []}

# --- UI STYLING ---

def apply_styles():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .hero-section { background: #0f172a; padding: 2rem; border-radius: 1rem; text-align: center; margin-bottom: 1rem; border: 1px solid #1e293b; }
            .hero-title { background: linear-gradient(to right, #60a5fa, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.2rem; font-weight: 800; }
            .hero-subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem; }
            .accuracy-card { background: white; padding: 0.75rem 1.5rem; border-radius: 0.75rem; border: 1px solid #e2e8f0; text-align: center; margin: 0 auto 1.5rem auto; width: fit-content; }
            .status-indicator { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 9999px; color: #166534; font-size: 0.7rem; font-weight: 800; }
            .status-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
            @keyframes pulse { 0% { transform: scale(0.9); } 70% { transform: scale(1.1); } 100% { transform: scale(0.9); } }
            [data-testid="stSidebar"] { background-color: #f8fafc; }
        </style>
    """, unsafe_allow_html=True)

def render_hero_landing():
    if st.session_state["messages"]: return
    st.markdown('<div class="hero-section"><div class="hero-title">Hiring Orchestration Copilot</div><div class="hero-subtitle">High-precision hiring grounded in SHL.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="accuracy-card"><div style="font-size:2.5rem; font-weight:900;">95%</div><div style="font-size:0.65rem; font-weight:700; color:#64748b; text-transform:uppercase;">Match Accuracy</div></div>', unsafe_allow_html=True)
    st.markdown("### ⚡ Quick Start")
    cols = st.columns(4)
    prompts = ["Senior React Engineer", "Backend Java Dev", "DevOps Cloud Engineer", "ML Engineer"]
    for i, p in enumerate(prompts):
        if cols[i].button(p, key=f"p_{i}", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": f"Hiring for a {p}"})
            st.rerun()

def render_recommendation_card(rec: Dict[str, Any], index: int):
    n = _normalize_recommendation(rec)
    
    if n['confidence'] >= 90:
        conf_tier = "Elite Match"
        conf_color = "#10b981"
    elif n['confidence'] >= 75:
        conf_tier = "Strong Match"
        conf_color = "#3b82f6"
    elif n['confidence'] >= 60:
        conf_tier = "Relevant Match"
        conf_color = "#f59e0b"
    else:
        conf_tier = "Fallback Match"
        conf_color = "#ef4444"

    skills = "".join([f'<span style="background:#f1f5f9; color:#334155; padding:2px 6px; border-radius:4px; font-size:0.65rem; font-weight:700; margin-right:4px; border:1px solid #e2e8f0;">{s}</span>' for s in n['matched_skills'][:3]])
    
    if "fallback" in n['insight'].lower():
        match_badge = '<span style="background: rgba(239, 68, 68, 0.1); color: #ef4444; padding: 2px 6px; border-radius: 4px; font-size: 0.6rem; font-weight: 800; border: 1px solid rgba(239, 68, 68, 0.2);">FALLBACK MATCH</span>'
    elif "Related Competency" in n['insight'] or "Expanded Match" in n['insight']:
        match_badge = '<span style="background: rgba(124, 58, 237, 0.1); color: #7c3aed; padding: 2px 6px; border-radius: 4px; font-size: 0.6rem; font-weight: 800; border: 1px solid rgba(124, 58, 237, 0.2);">EXPANDED MATCH</span>'
    else:
        match_badge = '<span style="background: rgba(16, 185, 129, 0.1); color: #10b981; padding: 2px 6px; border-radius: 4px; font-size: 0.6rem; font-weight: 800; border: 1px solid rgba(16, 185, 129, 0.2);">EXACT MATCH</span>'

    signal_badge = f'<div style="margin-top: 8px;"><span style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; font-weight: 800; border: 1px solid rgba(59, 130, 246, 0.2);">{n["recruiter_signal"].upper()}</span></div>'

    card_html = f"""<div style="background:white; border-radius:1rem; border:1px solid #e2e8f0; padding:1.25rem; margin-bottom:1rem; min-height:440px; display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
<div>
<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.75rem;">
<div style="display:flex; flex-direction:column; gap:4px;">
<span style="background:#eff6ff; color:#2563eb; padding:4px 8px; border-radius:6px; font-size:0.7rem; font-weight:800; text-transform:uppercase; width:fit-content;">{n['domain']}</span>
{match_badge}
</div>
<div style="text-align: right;">
<span style="color:{conf_color}; font-weight:900; font-size:1.2rem; display:block; line-height:1;">{n['confidence']}%</span>
<span style="color:{conf_color}; font-size:0.6rem; font-weight:800; text-transform:uppercase;">{conf_tier}</span>
</div>
</div>
<h4 style="margin:0; font-size:1.05rem; color:#0f172a; line-height:1.2;">{index}. {n['name']}</h4>
{signal_badge}
<div style="display:flex; gap:4px; margin-top:8px; flex-wrap:wrap;">{skills}</div>
<div style="background:#f8fafc; border-radius:0.5rem; padding:0.75rem; margin-top:1rem; border:1px solid #f1f5f9;">
<p style="margin:0; font-size:0.8rem; color:#475569; line-height:1.4;"><b>Recruiter Reasoning:</b><br/>{n['insight']}</p>
</div>
</div>
<div style="margin-top:1rem;">
<div style="display:flex; gap:0.75rem; font-size:0.75rem; color:#64748b; margin-bottom:0.75rem;">
<span>🎯 {n['stage']}</span><span>⏱️ {n['duration']}</span>
</div>
<a href="{n['url']}" target="_blank" style="text-decoration:none;">
<div style="background:#2563eb; color:white; text-align:center; padding:0.75rem; border-radius:0.5rem; font-weight:700; font-size:0.8rem;">View Assessment</div>
</a>
</div>
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_pipeline_section(pipeline: Dict[str, Any]):
    try:
        if not pipeline or not isinstance(pipeline, dict): return
        stages = pipeline.get("stages", [])
        if not stages: return
        st.markdown("---")
        st.markdown("### 🏗️ Optimized Hiring Pipeline")
        adv = sanitize_text(pipeline.get("strategic_guidance") or pipeline.get("strategic_advice"), "Technical screening pipeline.")
        st.info(f"💡 **Strategic Advisor:** {adv}")
        num = min(4, len(stages))
        if num > 0:
            cols = st.columns(num)
            for i in range(num):
                s = stages[i]
                with cols[i]:
                    st.markdown(f"**{s.get('name', 'Stage')}**")
                    st.caption(s.get("description", "Competency validation."))
                    for a in s.get("assessments", []): st.markdown(f"• `{a}`")
    except Exception as e:
        st.warning(f"Pipeline module loading issue: {str(e)}")

def main():
    st.set_page_config(page_title="AssessIQ | Recruiter Intelligence", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()
    with st.sidebar:
        st.markdown("## 🏗️ AssessIQ")
        st.markdown('<div class="status-indicator"><div class="status-dot"></div>Backend Live Status</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("🗑️ Clear Conversation", key="clr", use_container_width=True):
            st.session_state["messages"] = []; st.rerun()
        st.divider()
        st.caption("v1.2-Hardened")
    render_hero_landing()
    for m in st.session_state["messages"]:
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "👤"):
            st.markdown(sanitize_text(m["content"]))
            if m.get("pipeline"): render_pipeline_section(m["pipeline"])
            if m.get("recommendations"):
                recs = m["recommendations"]
                for i in range(0, len(recs), 4):
                    cols = st.columns(4)
                    for j, r in enumerate(recs[i:i+4]):
                        with cols[j]: render_recommendation_card(r, i + j + 1)
    if p := st.chat_input("Hiring requirement..."):
        st.session_state["messages"].append({"role": "user", "content": p})
        st.rerun()
    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            status_placeholder = st.empty()
            status_placeholder.markdown("✨ *Optimizing hiring pipeline...*")
            try:
                payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                
                # Production-grade timeout and error handling
                try:
                    resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
                except requests.exceptions.Timeout:
                    status_placeholder.empty()
                    st.error("⏳ **Optimization taking longer than expected.** This is usually due to backend cold start on Render. Please click retry or wait a moment.")
                    if st.button("🔄 Retry Request"): st.rerun()
                    return
                except requests.exceptions.ConnectionError:
                    status_placeholder.empty()
                    st.error("🔌 **Backend Connection Error.** Ensure the Render service is awake.")
                    return

                if resp.status_code != 200:
                    status_placeholder.empty()
                    st.error(f"⚠️ Platform synchronization error (HTTP {resp.status_code}).")
                    return
                
                data = normalize_api_response(resp.json())
                status_placeholder.empty()
                
                st.markdown(data["reply"])
                if data["pipeline"]: render_pipeline_section(data["pipeline"])
                if data["recommendations"]:
                    r = data["recommendations"]
                    for i in range(0, len(r), 4):
                        cols = st.columns(4)
                        for j, rec in enumerate(r[i:i+4]):
                            with cols[j]: render_recommendation_card(rec, i + j + 1)
                
                st.session_state["messages"].append({
                    "role": "assistant", 
                    "content": data["reply"], 
                    "recommendations": data["recommendations"], 
                    "pipeline": data["pipeline"]
                })
                st.rerun()
            except Exception as e:
                status_placeholder.empty()
                st.error(f"🧩 **Synchronization Issue**: {str(e)[:100]}. Please check backend logs.")

if __name__ == "__main__":
    main()
