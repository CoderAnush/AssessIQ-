"""
AssessIQ AI - Enterprise Assessment Selection Intelligence.
Clean production-ready frontend with robust response parsing and context awareness.
"""

import streamlit as st
import requests
import json
import os
import textwrap
import traceback
from datetime import datetime
from typing import List, Dict, Optional

# --- CONFIG ---
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessiq-nkp2.onrender.com")

# Configure page
st.set_page_config(
    page_title="AssessIQ | Enterprise AI Assessment Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL STYLING ---
st.markdown(textwrap.dedent("""
    <style>
        .stApp { background-color: #f8fafc; }
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }

        .main-header {
            font-size: 2.5rem; font-weight: 800; color: #0f172a; margin-bottom: 0.25rem;
            background: linear-gradient(90deg, #1e293b 0%, #3b82f6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .sub-header { font-size: 1.1rem; color: #64748b; margin-bottom: 2rem; }

        .recommendation-card {
            background: white; padding: 24px; border-radius: 16px; border: 1px solid #e2e8f0;
            margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        .recommendation-card:hover { transform: translateY(-4px); border-color: #3b82f6; }

        .badge-type { background: #f1f5f9; color: #475569; padding: 4px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; margin-right: 6px; }
        .badge-category { background: #eff6ff; color: #2563eb; padding: 4px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; }
        
        .score-box { background: #f0fdf4; padding: 8px 12px; border-radius: 8px; text-align: right; }
        .score-value { font-size: 1.5rem; font-weight: 800; color: #059669; }
        .score-label { font-size: 0.6rem; text-transform: uppercase; color: #059669; font-weight: 700; }

        .assessment-title { font-size: 1.3rem; font-weight: 700; color: #1e293b; margin: 8px 0; }
        .explanation-box { background: #f8fafc; padding: 14px; border-radius: 10px; border-left: 4px solid #3b82f6; margin: 16px 0; }
        
        .shl-button {
            display: inline-block; background: #2563eb; color: white !important;
            padding: 10px 20px; border-radius: 8px; text-decoration: none !important;
            font-weight: 600; font-size: 0.9rem;
        }
    </style>
    """), unsafe_allow_html=True)

# --- CORE LOGIC ---

def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conv_id" not in st.session_state:
        st.session_state.conv_id = f"conv_{datetime.now().strftime('%m%d_%H%M')}"

def send_chat_request(messages: List[Dict]):
    """Proven lightweight request logic using full history for context merging."""
    payload = {"messages": messages}
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json=payload,
            timeout=25
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Backend connection error: {str(e)}")
        return None

def render_recommendation(rec: Dict, index: int):
    score_pct = int(rec.get("score", 0.85) * 100)
    name = rec.get('name', 'Assessment')
    
    html = f"""
    <div class="recommendation-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <span class="badge-type">{rec.get('test_type', 'K')}</span>
                <span class="badge-category">{rec.get('category', 'Assessment')}</span>
                <div class="assessment-title">#{index} {name}</div>
            </div>
            <div class="score-box">
                <div class="score-value">{score_pct}%</div>
                <div class="score-label">{rec.get('match_label', 'Strong Match')}</div>
            </div>
        </div>
        <div class="explanation-box">
            <div style="font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Recruiter Insight</div>
            <div style="color: #334155; font-size: 0.95rem;">{rec.get('explanation')}</div>
        </div>
        <div style="margin-top: 15px;">
            <a href="{rec.get('url')}" target="_blank" class="shl-button" id="btn_{index}_{name.replace(' ', '_')}">View on SHL.com ↗</a>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def main():
    init_session()

    # Sidebar
    with st.sidebar:
        st.title("🎯 AssessIQ")
        st.markdown("---")
        st.info("Enterprise AI for SHL assessment selection. Grounded in SHL individual solutions catalog.")
        
        if st.button("🗑️ Clear Conversation", use_container_width=True, key="clear_conv_sidebar"):
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("---")
        st.caption(f"Connected to: {BACKEND_URL.split('//')[-1]}")

    # Header
    st.markdown('<h1 class="main-header">AssessIQ AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Strategic Conversational Intelligence for Assessment Selection</p>', unsafe_allow_html=True)

    # Empty State Welcome
    if not st.session_state.messages:
        st.markdown("""
        ### Welcome, Recruiter
        Describe the role you are hiring for, or ask to compare specific SHL assessments.
        """)
        
        cols = st.columns(3)
        prompts = [
            ("Java Backend Role", "I need assessments for a Senior Java engineer."),
            ("Sales Personality", "What's the best personality test for a high-volume sales role?"),
            ("Compare Top 2", "Compare the top 2 assessments for a leadership position.")
        ]
        for i, (title, text) in enumerate(prompts):
            with cols[i]:
                if st.button(title, key=f"sample_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": text})
                    st.rerun()

    # Display Chat History
    for i, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(msg["content"])
            if "recommendations" in msg and msg["recommendations"]:
                st.markdown("#### 📋 Top Recommendations")
                for idx, rec in enumerate(msg["recommendations"], 1):
                    render_recommendation(rec, idx)

    # Chat Input
    if prompt := st.chat_input("Describe the role or ask to compare assessments...", key="main_chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Process latest user message
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing requirements..."):
                # Clean messages for backend (only role and content)
                api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                response = send_chat_request(api_messages)
                
                if response:
                    reply = response.get("reply", "")
                    recs = response.get("recommendations", [])
                    clarification = response.get("clarification", "")
                    comparison = response.get("comparison", "")
                    
                    # Robust Parsing Logic: Ensure we show content if it exists
                    has_content = (
                        reply or recs or clarification or comparison
                    )
                    
                    if not has_content:
                        st.error("I couldn't generate a specific response. Please try rephrasing your request.")
                        return

                    # SUPPRESS FALLBACK ERROR IF RECS EXIST
                    display_text = reply
                    if recs and ("couldn't generate recommendations" in reply.lower() or not reply):
                        display_text = "Based on your requirements, here are the most relevant SHL assessments:"
                    
                    # PRIORITIZE CLARIFICATION/COMPARISON TEXT IF PRESENT
                    if clarification:
                        display_text = clarification
                    elif comparison and not recs: # Only use comparison text if it's the main response
                        display_text = comparison

                    # Render Text
                    st.markdown(display_text)
                    
                    # Render Recommendations (Independent of text)
                    if recs:
                        st.markdown("#### 📋 Top Recommendations")
                        for idx, rec in enumerate(recs, 1):
                            render_recommendation(rec, idx)
                    
                    # Store in history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": display_text,
                        "recommendations": recs
                    })
                else:
                    st.error("Failed to get response from AssessIQ.")
