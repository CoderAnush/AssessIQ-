"""
AssessIQ AI - Enterprise Assessment Selection Intelligence.
Stable Production Build with Render-Safe Networking.
"""

import streamlit as st
import requests
import json
import os
import textwrap
import traceback
import uuid
from datetime import datetime
from typing import List, Dict, Optional

# --- CONFIGURATION ---
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessiq-nkp2.onrender.com")

def init_session_state():
    """Harden session state initialization."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    if "latest_recommendations" not in st.session_state:
        st.session_state.latest_recommendations = []
    if "request_in_progress" not in st.session_state:
        st.session_state.request_in_progress = False

def send_chat_request(messages: List[Dict]):
    """Execute backend call safely within interaction handler."""
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
        st.error(f"⚠️ Communication Error: {str(e)}")
        return None

def render_recommendation_card(rec: Dict, index: int):
    """Render a single recommendation card with safety wrapper."""
    try:
        score_pct = int(rec.get("score", 0.85) * 100)
        name = rec.get('name', 'Assessment')
        
        # Use unique key for the card structure via HTML ID
        html_id = f"card_{index}_{name.replace(' ', '_')}"
        
        html = f"""
        <div class="recommendation-card" id="{html_id}">
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
                <div style="font-size: 0.75rem; font-weight: 800; color: #475569; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.05em;">Recruiter Decision Logic</div>
                <div style="color: #1e293b; font-size: 1rem; font-weight: 500;">{rec.get('explanation')}</div>
            </div>
            <div style="margin-top: 15px;">
                <a href="{rec.get('url')}" target="_blank" class="shl-button">View on SHL.com ↗</a>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Could not render card {index}")
        st.exception(e)

def apply_styles():
    """Apply professional enterprise CSS."""
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

            .badge-type { background: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; margin-right: 8px; border: 1px solid #e2e8f0; }
            .badge-category { background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; border: 1px solid #dbeafe; }
            
            .score-box { background: #f0fdf4; padding: 10px 16px; border-radius: 12px; text-align: right; border: 1px solid #dcfce7; }
            .score-value { font-size: 1.6rem; font-weight: 800; color: #166534; line-height: 1; }
            .score-label { font-size: 0.65rem; text-transform: uppercase; color: #166534; font-weight: 700; margin-top: 4px; letter-spacing: 0.05em; }

            .assessment-title { font-size: 1.4rem; font-weight: 700; color: #1e293b; margin: 12px 0 8px 0; letter-spacing: -0.01em; }
            .explanation-box { background: #f8fafc; padding: 18px; border-radius: 12px; border-left: 5px solid #3b82f6; margin: 18px 0; line-height: 1.5; }
            
            .shl-button {
                display: inline-block; background: #2563eb; color: white !important;
                padding: 12px 24px; border-radius: 10px; text-decoration: none !important;
                font-weight: 700; font-size: 0.95rem; transition: background 0.2s;
            }
            .shl-button:hover { background: #1d4ed8; }
        </style>
    """), unsafe_allow_html=True)

def main():
    """Main UI Loop."""
    st.set_page_config(
        page_title="AssessIQ | Enterprise AI Assessment Intelligence",
        page_icon="🎯",
        layout="wide"
    )
    
    apply_styles()
    init_session_state()
    
    # Startup Confirmation
    st.success("✅ Frontend Loaded Successfully")

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🎯 AssessIQ")
        st.markdown("---")
        st.info("Strategic AI for assessment selection.")
        
        if st.button("🗑️ Clear Conversation", use_container_width=True, key="clear_conv_sidebar"):
            st.session_state.messages = []
            st.session_state.conversation_id = str(uuid.uuid4())
            st.rerun()
        
        st.markdown("---")
        st.caption(f"Backend: {BACKEND_URL.split('//')[-1]}")

    # --- HEADER ---
    st.markdown('<h1 class="main-header">AssessIQ AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Strategic Conversational Intelligence for Assessment Selection</p>', unsafe_allow_html=True)

    # --- WELCOME STATE / SAMPLE PROMPTS ---
    if not st.session_state.messages:
        st.markdown("### Welcome, Recruiter")
        st.write("Describe your hiring requirements to get started.")
        
        cols = st.columns(3)
        samples = [
            ("Java Backend", "I need assessments for a Senior Java engineer."),
            ("Sales Talent", "What's the best personality test for a sales role?"),
            ("Leadership", "Compare assessments for a Director position.")
        ]
        for i, (label, text) in enumerate(samples):
            with cols[i]:
                if st.button(label, key=f"sample_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": text})
                    st.rerun()

    # --- MESSAGE DISPLAY ---
    for i, msg in enumerate(st.session_state.messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        recs = msg.get("recommendations", [])
        
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(content)
            if recs:
                st.markdown("#### 📋 Top Recommendations")
                for idx, r in enumerate(recs, 1):
                    render_recommendation_card(r, idx)

    # --- INPUT HANDLER ---
    if prompt := st.chat_input("Describe the role or ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # --- ASSISTANT LOGIC ---
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        # Check if we already processed this
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Processing intent..."):
                # Clean history for API
                history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                response = send_chat_request(history)
                
                if response:
                    # Robust Parsing
                    reply = response.get("reply", "")
                    recs = response.get("recommendations", [])
                    clarification = response.get("clarification", "")
                    
                    # Selection Logic
                    display_text = reply
                    if clarification:
                        display_text = clarification
                    
                    if recs and ("couldn't generate" in reply.lower() or not reply):
                        display_text = "Based on your requirements, here are the most relevant SHL assessments:"
                    
                    if not display_text and not recs:
                        display_text = "I've analyzed your request. How can I further assist?"

                    # Render
                    st.markdown(display_text)
                    if recs:
                        st.markdown("#### 📋 Top Recommendations")
                        for idx, r in enumerate(recs, 1):
                            render_recommendation_card(r, idx)
                    
                    # Save
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": display_text,
                        "recommendations": recs
                    })
                else:
                    st.error("I'm having trouble connecting to the intelligence engine. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Prevent blank screen on crash
        st.error("🛑 CRITICAL RENDERING FAILURE")
        st.write("The application encountered a fatal error during render.")
        st.exception(e)
        # Log to console
        print(f"FATAL UI CRASH: {e}")
        traceback.print_exc()
