"""
Enterprise Streamlit frontend for AssessIQ.
Provides professional recruiter interface for conversation-based assessment recommendations.
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

# --- CONFIGURATION ---
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessiq-nkp2.onrender.com")

# Configure page
st.set_page_config(
    page_title="AssessIQ | Enterprise Assessment Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL STYLING ---
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1e293b;
        margin-bottom: 0.5rem;
        letter-spacing: -0.025em;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #64748b;
        margin-bottom: 2rem;
    }

    /* Recommendation Card Styling */
    .recommendation-card {
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 16px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .recommendation-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #3b82f6;
    }

    .badge-type {
        background-color: #eff6ff;
        color: #1d4ed8;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .confidence-high { color: #059669; font-weight: 700; }
    .confidence-medium { color: #d97706; font-weight: 700; }
    .confidence-low { color: #dc2626; font-weight: 700; }

    .explanation-text {
        font-size: 0.975rem;
        color: #334155;
        margin: 16px 0;
        line-height: 1.6;
    }

    .shl-link {
        display: inline-flex;
        align-items: center;
        color: #2563eb;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    .shl-link:hover {
        text-decoration: underline;
    }

    /* Sidebar and utility styling */
    .metric-container {
        background: white;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def get_api_response(messages: List[Dict]) -> Optional[Dict]:
    """Call AssessIQ Production API with error handling."""
    try:
        # Standardize messages for API
        api_payload = {"messages": messages}
        
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json=api_payload,
            timeout=45,  # Increased timeout for cold starts/LLM latency
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 429:
            st.warning("⚠️ Rate limit reached. Please wait a moment before sending another message.")
            return None
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        st.error("🕒 Connection timed out. The backend might be starting up (cold start). Please try again in 30 seconds.")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"🌐 Could not connect to AssessIQ at {BACKEND_URL}. Verify backend service status.")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None


def render_recommendation_card(rec: Dict, index: int) -> None:
    """Render a polished enterprise-grade recommendation card."""
    # Handle missing confidence gracefully
    conf_pct = rec.get("score", 0.85) * 100  # Default to 85 if ranker score missing
    
    if conf_pct >= 80:
        conf_style = "confidence-high"
        match_label = "Strong Match"
    elif conf_pct >= 60:
        conf_style = "confidence-medium"
        match_label = "Good Match"
    else:
        conf_style = "confidence-low"
        match_label = "Partial Match"

    st.markdown(f"""
    <div class="recommendation-card">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
                <span class="badge-type">{rec.get('test_type', 'Assessment')}</span>
                <h3 style="margin: 8px 0 4px 0; font-size: 1.25rem;">{rec.get('name')}</h3>
                <p style="margin: 0; color: #64748b; font-size: 0.85rem;">
                    Assessment ID: <code>{rec.get('id', 'N/A')}</code>
                </p>
            </div>
            <div style="text-align: right;">
                <div class="{conf_style}" style="font-size: 1.5rem;">{int(conf_pct)}%</div>
                <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">{match_label}</div>
            </div>
        </div>
        
        <div class="explanation-text">
            {rec.get('description', 'High-validity SHL assessment grounded in your specific hiring requirements.')}
        </div>
        
        <div style="display: flex; gap: 16px; margin-top: 16px;">
            <a href="{rec.get('url')}" target="_blank" class="shl-link">
                View on SHL.com ↗
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main Streamlit entry point."""
    init_session_state()

    # --- HEADER ---
    st.markdown('<h1 class="main-header">AssessIQ AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Agentic Conversational Intelligence for SHL Assessments</p>', unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://www.shl.com/wp-content/uploads/SHL-Logo-Primary-RGB-1.png", width=120)
        st.markdown("---")
        
        st.subheader("🛠️ Session Control")
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.rerun()

        st.markdown("---")
        st.subheader("💡 Tips")
        st.info("Start by describing the role, seniority, and key technical or soft skills you need to assess.")
        
        st.markdown("---")
        st.caption(f"Connected to: {BACKEND_URL}")
        st.caption("Grounded in SHL Catalog v1.0")

    # --- CHAT INTERFACE ---
    # Container for messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])
            
            # Render recommendations if stored in message history
            if "recommendations" in msg:
                st.markdown("#### 📋 Targeted Recommendations")
                for i, rec in enumerate(msg["recommendations"], 1):
                    render_recommendation_card(rec, i)

    # User Input
    if prompt := st.chat_input("E.g., I need assessments for a Senior Java Developer with leadership skills..."):
        # Add and display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # Get response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🧠 Analyzing requirements and ranking SHL assessments..."):
                # Filter metadata out for API request
                api_msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                response = get_api_response(api_msgs)
                
                if response:
                    reply = response.get("reply", "I'm processing your request.")
                    recs = response.get("recommendations", [])
                    
                    st.markdown(reply)
                    
                    if recs:
                        st.markdown("#### 📋 Targeted Recommendations")
                        for i, rec in enumerate(recs, 1):
                            render_recommendation_card(rec, i)
                    
                    # Store assistant message with recommendations
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": reply,
                        "recommendations": recs
                    })
                else:
                    # Error handled inside get_api_response
                    pass

    # --- FOOTER ---
    st.markdown("---")
    footer_cols = st.columns([3, 1])
    with footer_cols[0]:
        st.caption("© 2026 AssessIQ AI | Powered by SHL Individual Test Solutions Research")
    with footer_cols[1]:
        st.caption("Confidential | Recruiter Access")


if __name__ == "__main__":
    main()
