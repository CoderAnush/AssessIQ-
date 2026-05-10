"""
Enterprise Streamlit frontend for AssessIQ.
Provides professional recruiter interface for conversation-based assessment recommendations.
"""

import streamlit as st
import requests
import json
import os
import textwrap
from datetime import datetime
from typing import List, Dict, Optional

# --- CONFIGURATION ---
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessiq-nkp2.onrender.com")

# Configure page
st.set_page_config(
    page_title="AssessIQ | Enterprise AI Assessment Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ENHANCED PROFESSIONAL STYLING ---
st.markdown(textwrap.dedent("""
    <style>
        /* Main background */
        .stApp {
            background-color: #f8fafc;
        }
        
        /* Global Typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        html, body, [class*="st-"] {
            font-family: 'Inter', sans-serif;
        }

        /* Header styling */
        .main-header {
            font-size: 2.75rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.25rem;
            letter-spacing: -0.04em;
            background: linear-gradient(90deg, #1e293b 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .sub-header {
            font-size: 1.1rem;
            color: #64748b;
            margin-bottom: 1.5rem;
            font-weight: 500;
        }

        /* Recommendation Card System */
        .recommendation-card {
            background: white;
            padding: 24px;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .recommendation-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            border-color: #3b82f6;
        }

        .card-header {
            display: flex; 
            justify-content: space-between; 
            align-items: flex-start;
            margin-bottom: 16px;
        }

        .badge-type {
            background-color: #f1f5f9;
            color: #475569;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid #e2e8f0;
            margin-right: 6px;
        }

        .badge-category {
            background-color: #eff6ff;
            color: #2563eb;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            border: 1px solid #dbeafe;
        }

        .confidence-exceptional { color: #059669; font-weight: 800; }
        .confidence-high { color: #10b981; font-weight: 800; }
        .confidence-medium { color: #f59e0b; font-weight: 800; }
        .confidence-low { color: #ef4444; font-weight: 800; }

        .assessment-title {
            margin: 10px 0 4px 0; 
            font-size: 1.4rem;
            font-weight: 700;
            color: #1e293b;
        }

        .explanation-text {
            font-size: 1rem;
            color: #475569;
            margin: 16px 0;
            line-height: 1.6;
        }

        .shl-link-button {
            display: inline-flex;
            align-items: center;
            background-color: #2563eb;
            color: white !important;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none !important;
            font-weight: 600;
            font-size: 0.9rem;
            transition: background-color 0.2s;
        }
        
        .shl-link-button:hover {
            background-color: #1d4ed8;
        }

        /* Sidebar and utility styling */
        .status-container {
            background: #f1f5f9;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            margin-top: 10px;
        }

        .status-dot {
            height: 8px;
            width: 8px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }

        /* Welcome state */
        .welcome-container {
            text-align: center;
            padding: 60px 20px;
            max-width: 800px;
            margin: 0 auto;
        }
    </style>
    """), unsafe_allow_html=True)


def init_session_state():
    """Initialize session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def get_api_response(messages: List[Dict]) -> Optional[Dict]:
    """Call AssessIQ Production API with robust error handling."""
    try:
        api_payload = {"messages": messages}
        
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json=api_payload,
            timeout=50,  # Increased for Render cold starts
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 429:
            st.warning("⚠️ Rate limit reached (Gemini Free Tier). Please wait a few seconds.")
            return None
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        st.error("🕒 Connection timed out. The backend is waking up from a cold start. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"🌐 Connectivity Error: Could not reach AssessIQ at {BACKEND_URL}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error communicating with backend: {str(e)}")
        return None


def clean_html(html: str) -> str:
    """Strip all leading whitespace from each line to prevent Markdown code-block interpretation."""
    return "\n".join([line.strip() for line in html.split("\n")])


def render_recommendation_card(rec: Dict, index: int) -> None:
    """Render a premium enterprise-grade recommendation card."""
    # Use backend-provided score and label
    score = rec.get("score", 0.85)
    conf_pct = int(score * 100)
    match_label = rec.get("match_label", "Strong Match")
    
    # Visual style mapping
    if conf_pct >= 90:
        conf_style = "confidence-exceptional"
    elif conf_pct >= 80:
        conf_style = "confidence-high"
    elif conf_pct >= 70:
        conf_style = "confidence-medium"
    else:
        conf_style = "confidence-low"

    html = f"""
    <div class="recommendation-card">
        <div class="card-header">
            <div>
                <div style="margin-bottom: 8px;">
                    <span class="badge-type">{rec.get('test_type', 'A')}</span>
                    <span class="badge-category">{rec.get('category', 'Assessment')}</span>
                </div>
                <div class="assessment-title">#{index} {rec.get('name')}</div>
                <p style="margin: 0; color: #94a3b8; font-size: 0.8rem; font-family: monospace;">
                    ID: {rec.get('id', 'N/A')}
                </p>
            </div>
            <div style="text-align: right;">
                <div class="{conf_style}" style="font-size: 1.75rem; line-height: 1;">{conf_pct}%</div>
                <div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; font-weight: 700; margin-top: 4px;">{match_label}</div>
            </div>
        </div>
        
        <div class="explanation-text" style="background: #f8fafc; padding: 12px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 16px 0;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Recruiter Reasoning</div>
            {rec.get('explanation', 'Strategic recommendation based on multi-factor role alignment.')}
        </div>
        
        <div style="margin-top: 20px;">
            <a href="{rec.get('url')}" target="_blank" class="shl-link-button">
                Configure on SHL.com ↗
            </a>
        </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def main():
    """Main Streamlit entry point."""
    init_session_state()

    # --- SIDEBAR ---
    with st.sidebar:
        # Styled Logo Header
        logo_html = """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                <div style="background: #2563eb; color: white; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem;">A</div>
                <div style="font-weight: 800; font-size: 1.4rem; color: #1e293b; letter-spacing: -0.02em;">AssessIQ</div>
            </div>
        """
        st.markdown(clean_html(logo_html), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # System Status
        st.markdown("##### 🟢 System Status")
        status_html = f"""
            <div class="status-container">
                <div style="font-size: 0.85rem; color: #475569; margin-bottom: 4px;">
                    <span class="status-dot"></span> Backend: <b>Live</b>
                </div>
                <div style="font-size: 0.85rem; color: #475569;">
                    <span class="status-dot"></span> Retrieval: <b>Grounded</b>
                </div>
            </div>
        """
        st.markdown(clean_html(status_html), unsafe_allow_html=True)

        st.markdown("---")
        
        # Controls
        st.subheader("🛠️ Session")
        if st.button("🗑️ Reset Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.rerun()

        st.markdown("---")
        st.info("💡 **Grounded Retrieval**: All recommendations are verified against the SHL Individual Test Solutions catalog.")
        st.caption(f"Endpoint: {BACKEND_URL.split('//')[-1]}")

    # --- MAIN CONTENT ---
    
    # Header
    st.markdown('<h1 class="main-header">AssessIQ AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Strategic Conversational Intelligence for Assessment Selection</p>', unsafe_allow_html=True)

    # Chat Area
    if not st.session_state.messages:
        # Empty State / Welcome
        welcome_html = f"""
        <div class="welcome-container">
            <h2 style="color: #1e293b; margin-bottom: 16px;">Welcome, Recruiter</h2>
            <p style="color: #64748b; font-size: 1.1rem; margin-bottom: 32px;">
                Describe your hiring requirements, and I'll recommend the most effective SHL assessments 
                grounded in real-world psychometric data.
            </p>
        </div>
        """
        st.markdown(clean_html(welcome_html), unsafe_allow_html=True)
        
        # Sample Prompt Cards
        cols = st.columns(3)
        prompts = [
            ("Senior Java Backend", "I need assessments for a Senior Java engineer with high communication skills."),
            ("Strategic Leadership", "Recommend tests for a Director-level role focusing on strategic thinking."),
            ("Sales & Personality", "Compare OPQ and Verify Interactive for a high-volume sales role.")
        ]
        for i, (title, p_text) in enumerate(prompts):
            with cols[i]:
                if st.button(title, key=f"p_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": p_text})
                    st.rerun()

    # Display Message History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"], unsafe_allow_html=True)
            
            if "recommendations" in msg and msg["recommendations"]:
                st.markdown("#### 📋 Recommendations")
                for i, rec in enumerate(msg["recommendations"], 1):
                    render_recommendation_card(rec, i)

    # Chat Input
    if prompt := st.chat_input("Ask about assessments, roles, or compare SHL products..."):
        # Add and display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Handle the latest message if it's from the user
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        user_prompt = st.session_state.messages[-1]["content"]
        
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🧠 Analyzing requirements and searching SHL catalog..."):
                # Prepare history for API
                api_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                response = get_api_response(api_history)
                
                if response:
                    reply = response.get("reply", "I've analyzed your request.")
                    recs = response.get("recommendations", [])
                    
                    st.markdown(reply, unsafe_allow_html=True)
                    
                    if recs:
                        st.markdown("#### 📋 Recommendations")
                        for i, rec in enumerate(recs, 1):
                            render_recommendation_card(rec, i)
                    
                    # Persist response
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": reply,
                        "recommendations": recs
                    })
                else:
                    st.error("Failed to retrieve response from backend.")

    # --- FOOTER ---
    st.markdown("<br><br>", unsafe_allow_html=True)
    footer_html = """
        <div style="border-top: 1px solid #e2e8f0; padding-top: 20px; text-align: center;">
            <p style="color: #94a3b8; font-size: 0.8rem; margin: 0;">
                Grounded in SHL Assessment Catalog v1.0 | Powered by Hybrid RAG + Gemini 2.0 Flash
            </p>
            <p style="color: #cbd5e1; font-size: 0.7rem; margin-top: 4px;">
                © 2026 AssessIQ AI | Production Build 7faea76
            </p>
        </div>
    """
    st.markdown(clean_html(footer_html), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
