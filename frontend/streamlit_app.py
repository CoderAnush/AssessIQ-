"""
CLEAN ISOLATED FRONTEND - Network Debug Build.
Goal: Prove whether requests.post() can reach Render.
"""

import streamlit as st
import requests
import json
import traceback
import socket
import os
from datetime import datetime

# --- CONFIG ---
BACKEND_URL = os.getenv("BACKEND_URL", "https://assessiq-nkp2.onrender.com")

st.set_page_config(page_title="AssessIQ | Network Debug", layout="wide")

st.title("AssessIQ Network Isolation Test")
st.write(f"Target Backend: `{BACKEND_URL}`")

def test_backend_direct():
    """Step 2: Isolated Minimal POST Request."""
    url = f"{BACKEND_URL}/chat"
    payload = {"messages": [{"role": "user", "content": "test"}]}

    st.subheader("🚀 Direct POST Test")
    st.write(f"Sending to: `{url}`")
    st.json(payload)

    print("DEBUG: STARTING requests.post") # Also visible in Streamlit logs
    st.write("⏱️ **Executing requests.post...**")
    
    try:
        start = datetime.now()
        response = requests.post(
            url,
            json=payload,
            timeout=20,
            headers={"Content-Type": "application/json"}
        )
        duration = (datetime.now() - start).total_seconds()
        
        st.success(f"✅ SUCCESS in {duration:.2f}s")
        st.write(f"Status: {response.status_code}")
        st.code(response.text, language="json")
        print(f"DEBUG: SUCCESS {response.status_code}")

    except Exception as e:
        st.error(f"❌ REQUEST FAILED: {str(e)}")
        st.code(traceback.format_exc())
        print(f"DEBUG: FAILURE {str(e)}")

def diagnostic_test():
    """Step 9: DNS and Socket Tests."""
    st.subheader("🔍 Network Diagnostics")
    
    domain = BACKEND_URL.replace("https://", "").replace("http://", "").split("/")[0]
    st.write(f"Analyzing domain: `{domain}`")
    
    # 1. DNS Resolution
    try:
        ip = socket.gethostbyname(domain)
        st.success(f"DNS Resolution: `{ip}`")
    except Exception as e:
        st.error(f"DNS Resolution Failed: {e}")

    # 2. Socket Connectivity
    try:
        s = socket.create_connection((domain, 443), timeout=5)
        st.success("Socket Port 443: **CONNECTED**")
        s.close()
    except Exception as e:
        st.error(f"Socket Connection Failed: {e}")

    # 3. Simple GET /health
    try:
        st.write("Testing GET /health...")
        r = requests.get(f"{BACKEND_URL}/health", timeout=10)
        st.write(f"Health Status: {r.status_code}")
        st.code(r.text)
    except Exception as e:
        st.error(f"Health GET Failed: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Debug Controls")
    if st.button("🚀 DIRECT NETWORK TEST", use_container_width=True):
        test_backend_direct()
    
    if st.button("🔍 RUN DIAGNOSTICS", use_container_width=True):
        diagnostic_test()
    
    if st.button("🔓 TEST WITH VERIFY=FALSE", use_container_width=True):
        try:
            st.write("Testing POST with verify=False...")
            r = requests.post(f"{BACKEND_URL}/chat", json={"messages":[{"role":"user","content":"test"}]}, timeout=15, verify=False)
            st.write(f"Status: {r.status_code}")
            st.code(r.text)
        except Exception as e:
            st.error(str(e))

# --- MAIN UI ---
st.info("Click the buttons in the sidebar to start isolation tests.")
st.markdown("""
### Purpose of this build:
1. Remove all complex session/memory logic.
2. Remove all async/threading conflicts.
3. Call `requests.post` directly and synchronously.
4. Catch exact network-level exceptions.

**If the POST test times out but DNS/GET works, the issue is likely a Render-side rejection of the POST payload or a protocol mismatch.**
""")
