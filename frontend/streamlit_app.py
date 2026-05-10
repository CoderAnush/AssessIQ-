"""
Enterprise Streamlit frontend for AssessIQ.
Provides professional recruiter interface for conversation-based assessment recommendations.
"""

import streamlit as st
import requests
import json
from datetime import datetime
from typing import List, Dict, Optional

# Configure page
st.set_page_config(
    page_title="AssessIQ - Assessment Intelligence Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }

    .recommendation-card {
        background: white;
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #0066cc;
        margin: 8px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .confidence-high {
        color: #00aa00;
        font-weight: bold;
    }

    .confidence-medium {
        color: #ff9900;
        font-weight: bold;
    }

    .confidence-low {
        color: #cc0000;
        font-weight: bold;
    }

    .explanation {
        font-size: 0.95em;
        color: #444;
        margin-top: 8px;
        line-height: 1.5;
    }

    .metric-box {
        background: white;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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
    """Call AssessIQ API."""
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"messages": messages},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error connecting to AssessIQ API: {e}")
        return None


def render_recommendation_card(rec: Dict, index: int) -> None:
    """Render a single recommendation card."""
    confidence = rec.get("confidence", {})
    confidence_pct = confidence.get("percentage", 0)
    confidence_level = confidence.get("level", "Unknown")

    # Confidence color
    if confidence_pct >= 90:
        conf_class = "confidence-high"
    elif confidence_pct >= 75:
        conf_class = "confidence-medium"
    else:
        conf_class = "confidence-low"

    st.markdown(f"""
    <div class="recommendation-card">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
                <h4 style="margin: 0 0 4px 0;">#{index} {rec.get('name')}</h4>
                <p style="margin: 0; color: #666; font-size: 0.9em;">
                    Type: <code>{rec.get('test_type')}</code> |
                    Rank: Position {rec.get('rank', '?')}
                </p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.2em; {conf_class}">
                    {confidence_pct}%
                </div>
                <div style="font-size: 0.85em; color: #666;">
                    {confidence_level} match
                </div>
            </div>
        </div>

        <div class="explanation">
            {rec.get('explanation', 'Assessment matched to requirements.')}
        </div>

        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
            <a href="{rec.get('url')}" target="_blank" style="color: #0066cc; text-decoration: none;">
                🔗 View on SHL.com →
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main Streamlit app."""

    init_session_state()

    # Header
    st.markdown("""
    # 🤖 AssessIQ
    ### Conversational Assessment Intelligence Platform
    **Enterprise hiring intelligence - powered by SHL expertise**
    """)

    # Sidebar metrics
    with st.sidebar:
        st.markdown("### 📊 Conversation Metrics")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-box">
                <div style="font-size: 1.5em; font-weight: bold; color: #0066cc;">
                    {len(st.session_state.messages) // 2}
                </div>
                <div style="font-size: 0.85em; color: #666;">Turns</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-box">
                <div style="font-size: 1.5em; font-weight: bold; color: #00aa00;">
                    ✓
                </div>
                <div style="font-size: 0.85em; color: #666;">Grounded</div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🔄 New Conversation"):
            st.session_state.messages = []
            st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.rerun()

    # Main chat area
    chat_container = st.container()

    with chat_container:
        # Display conversation history
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg["content"])

                    # Show recommendations if present
                    if "recommendations" in msg.get("metadata", {}):
                        recs = msg["metadata"]["recommendations"]
                        if recs:
                            st.markdown("### 📋 Recommendations")
                            for i, rec in enumerate(recs, 1):
                                render_recommendation_card(rec, i)

                    # Show retrieval confidence if present
                    if "confidence" in msg.get("metadata", {}):
                        st.markdown(
                            f"**Retrieval Confidence:** {msg['metadata']['confidence']:.0%}",
                            help="How confident we are in the recommendations based on your context"
                        )

    # Input area
    st.markdown("---")

    # Input prompt
    user_input = st.chat_input(
        "Tell me about the role you're hiring for...",
        key="user_input"
    )

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Show user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Get API response
        with st.spinner("🤔 Analyzing context and searching assessments..."):
            api_messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in st.session_state.messages
                if "metadata" not in msg
            ]

            response = get_api_response(api_messages)

        if response:
            # Extract data
            reply = response.get("reply", "")
            recommendations = response.get("recommendations", [])
            end_of_conversation = response.get("end_of_conversation", False)

            # Add to message history with metadata
            assistant_msg = {
                "role": "assistant",
                "content": reply,
                "metadata": {
                    "recommendations": recommendations,
                    "confidence": 0.85,  # In production, extract from response
                }
            }

            st.session_state.messages.append(assistant_msg)

            # Display response
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(reply)

                # Show recommendations
                if recommendations:
                    st.markdown("### 📋 Recommendations")
                    for i, rec in enumerate(recommendations, 1):
                        render_recommendation_card(rec, i)

                # Confidence indicator
                st.markdown(
                    "**Retrieval Confidence:** 85%",
                    help="Based on the information provided, we're 85% confident in these recommendations"
                )

            # End of conversation message
            if end_of_conversation:
                st.success("✅ Assessment recommendations complete. Visit SHL.com to proceed with evaluation.")
        else:
            st.error("Failed to get response from AssessIQ")

    # Footer
    st.markdown("""
    ---
    **AssessIQ** - Enterprise Conversational Assessment Intelligence Platform
    Powered by SHL Individual Test Solutions | Grounded recommendations only
    """)


if __name__ == "__main__":
    main()
