# AssessIQ AI - Complete Deployment Guide

## Table of Contents
1. Local Development
2. Docker Setup
3. Render Deployment
4. Streamlit Cloud Deployment
5. Production Monitoring
6. Troubleshooting

---

## 1. LOCAL DEVELOPMENT

### Prerequisites

```bash
# Python 3.11+
python --version

# pip
pip --version

# Optional: Docker
docker --version
```

### Setup Steps

```bash
# 1. Clone repository
git clone <repo>
cd AssessIQ-AI

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env

# 5. Edit .env with your API key
# GEMINI_API_KEY=your_actual_key
nano .env

# 6. Prepare data
python scripts/scraper.py          # Scrape SHL catalog
python scripts/build_embeddings.py # Build FAISS index

# 7. Run server
uvicorn app.main:app --reload

# 8. Visit API docs
open http://localhost:8000/docs
```

### Testing Locally

```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I need help hiring a Java developer"}
    ]
  }'

# Run test suite
pytest tests/

# Run with public conversation traces
pytest tests/e2e/test_public_traces.py -v
```

---

## 2. DOCKER SETUP

### Local Docker Development

```bash
# Build image
docker build -t assessiq:latest .

# Run container
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  assessiq:latest

# Visit
open http://localhost:8000/docs
```

### Docker Compose (Recommended for Local)

```bash
# Set environment
export GEMINI_API_KEY=your_key

# Start services
docker-compose up

# Stop services
docker-compose down

# View logs
docker-compose logs api -f

# Run tests inside container
docker-compose exec api pytest tests/
```

### Docker Build Optimization

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. RENDER DEPLOYMENT

### Step-by-Step Render Setup

#### 1. Prepare Repository

```bash
# Ensure files are committed
git add .
git commit -m "Ready for deployment"
git push origin main
```

#### 2. Create Render Service

1. Go to [render.com](https://render.com)
2. Sign up / log in
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: `assessiq-api`
   - **Runtime**: Python 3.11
   - **Build command**: `pip install -r requirements.txt && python scripts/build_embeddings.py`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - **Plan**: Free or Paid (Pro for guaranteed uptime)

#### 3. Set Environment Variables

In Render dashboard:
1. Go to Service → Environment
2. Add variables:

```
GEMINI_API_KEY=your_actual_key
CATALOG_PATH=data/raw/catalog.json
FAISS_INDEX_PATH=data/vectorstore/faiss_index.bin
MAX_CONVERSATION_TURNS=8
REQUEST_TIMEOUT_SECONDS=30
LOG_LEVEL=INFO
```

#### 4. Configure Health Check

1. Go to Health Check tab
2. Set:
   - **Endpoint**: `/health`
   - **Path**: `/health`
   - **Check interval**: 30s
   - **Failure threshold**: 3

#### 5. Deploy

1. Click "Create Web Service"
2. Render builds and deploys automatically
3. View logs in "Logs" tab
4. Get public URL: `https://assessiq-api.onrender.com`

### Important Notes

**Cold Starts**: Render free tier spins down after 15 minutes of inactivity. First request takes ~2 minutes. SHL evaluator allows up to 2 minutes for first /health call.

**Data Persistence**: Render ephemeral filesystem resets on redeploy. Keep `data/raw/catalog.json` and FAISS index in:
1. Git repo (for catalog)
2. External storage (S3, etc.)

**Workaround for Data**:

```bash
# In build command on Render:
pip install -r requirements.txt && \
  python scripts/scraper.py && \
  python scripts/build_embeddings.py && \
  echo "Data prepared"
```

This ensures data is built fresh on each deploy.

---

## 4. STREAMLIT CLOUD DEPLOYMENT (Optional Frontend)

### Streamlit App Setup

```bash
# Create streamlit app
mkdir -p frontend

# Create requirements for frontend
echo "streamlit==1.28.1" > frontend/requirements.txt
echo "requests==2.31.0" >> frontend/requirements.txt
```

### frontend/streamlit_app.py

```python
import streamlit as st
import requests
import json

st.set_page_config(
    page_title="AssessIQ AI",
    page_icon="🤖",
    layout="wide"
)

st.title("AssessIQ AI 🤖")
st.markdown("Conversational SHL Assessment Recommender")

# Configuration
API_URL = st.secrets.get("api_url", "http://localhost:8000")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# User input
if user_input := st.chat_input("Tell me about your hiring needs..."):
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    with st.chat_message("user"):
        st.write(user_input)
    
    # Get assistant response
    try:
        response = requests.post(
            f"{API_URL}/chat",
            json={"messages": st.session_state.messages},
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": data["reply"]
        })
        
        with st.chat_message("assistant"):
            st.write(data["reply"])
            
            # Show recommendations if any
            if data.get("recommendations"):
                st.markdown("### Recommended Assessments")
                for rec in data["recommendations"]:
                    st.markdown(f"""
                    **{rec['name']}** [{rec['test_type']}]
                    
                    [View Assessment]({rec['url']})
                    """)
            
            # Check if conversation ended
            if data.get("end_of_conversation"):
                st.success("✅ Conversation complete!")
                st.info("Feel free to ask more questions or refine your search.")
                
    except Exception as e:
        st.error(f"Error: {e}")
```

### Deploy to Streamlit Cloud

1. Push frontend code to GitHub
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
3. Click "Deploy an app"
4. Select your repo and `frontend/streamlit_app.py`
5. In "Advanced settings", add secrets:

```toml
[api_url]
"https://assessiq-api.onrender.com"
```

---

## 5. PRODUCTION MONITORING

### Logs

```bash
# View logs on Render
# In Render dashboard → Service → Logs

# Or locally
tail -f logs/assessiq.log

# Parse JSON logs
cat logs/assessiq.log | python -m json.tool
```

### Metrics to Track

```python
# Key metrics:
- Response time (should be <5 seconds)
- Error rate (should be <1%)
- Hallucination rate (should be 0%)
- Recommendation accuracy (Recall@10)
- Turn count distribution
- Common refusal reasons
```

### Monitoring with Sentry (Optional)

```python
# In app/main.py
import sentry_sdk

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1
    )
```

Add to .env:
```
SENTRY_DSN=https://xxx@yyy.ingest.sentry.io/zzz
```

---

## 6. PRODUCTION CHECKLIST

Before deploying to production:

- [ ] All tests pass: `pytest tests/`
- [ ] No hardcoded credentials
- [ ] Environment variables configured
- [ ] API key security: never in git/logs
- [ ] Catalog validated: `python scripts/validate_catalog.py`
- [ ] FAISS index built: `python scripts/build_embeddings.py`
- [ ] Health endpoint working: `curl /health`
- [ ] Chat endpoint working with sample request
- [ ] Response times under 30s
- [ ] Error handling in place
- [ ] Logging configured
- [ ] Docker builds successfully
- [ ] docker-compose runs without errors
- [ ] Documentation updated
- [ ] Public traces pass: `pytest tests/e2e/test_public_traces.py`

---

## 7. TROUBLESHOOTING

### Issue: FAISS Index Not Found

```
Error: FAISS index not found at data/vectorstore/faiss_index.bin
```

**Solution**:
```bash
python scripts/build_embeddings.py
# Or in build command on Render
```

### Issue: API Key Not Set

```
Error: GEMINI_API_KEY not configured
```

**Solution**:
```bash
# Local: Set in .env
export GEMINI_API_KEY=your_key

# Render: Add to Environment variables
```

### Issue: Timeout on /chat

```
Error: Request timeout (>30 seconds)
```

**Solution**:
1. Check FAISS index size
2. Profile retrieval speed
3. Reduce TOP_K_RETRIEVAL
4. Check LLM latency
5. Consider caching

### Issue: Out of Memory

```
Error: Cannot allocate memory for FAISS
```

**Solution**:
1. Use faiss-cpu instead of faiss-gpu
2. Reduce catalog size
3. Use quantization

### Issue: Cold Start Slow

```
Render cold start takes >2 minutes
```

**Solution**:
1. Expected behavior on free tier
2. Upgrade to Paid tier for guaranteed performance
3. SHL evaluator allows 2 minutes for first /health call

---

## 8. PERFORMANCE OPTIMIZATION

### Response Time Optimization

```python
# 1. Cache FAISS index in memory
# 2. Cache embeddings
# 3. Reduce TOP_K_RETRIEVAL if needed
# 4. Profile LLM calls

import time

start = time.time()
# Your code here
elapsed = time.time() - start
logger.info(f"Operation took {elapsed:.2f}s")
```

### Deployment Strategy

**Development**:
```bash
docker-compose up
```

**Staging** (on Render):
- Free tier for testing
- Full production data
- Full monitoring

**Production** (on Render):
- Paid tier for guaranteed uptime
- Monitoring enabled
- Sentry enabled
- Health checks active

---

## 9. ROLLBACK & RECOVERY

### Render Rollback

1. Go to Render dashboard
2. Select service
3. Click "Deployments"
4. Find previous working version
5. Click "Redeploy"

### Data Recovery

If FAISS index corrupted:
```bash
python scripts/validate_catalog.py
python scripts/build_embeddings.py
git push  # Render redeploys automatically
```

---

## 10. COST ESTIMATION

### Render Pricing
- **Free**: $0 (cold starts, slower)
- **Starter**: $7/month (faster, better for demos)
- **Pro**: $12/month (guaranteed uptime)

### Gemini API Pricing
- **Free tier**: $0 (with limits)
- **Pay-as-you-go**: ~$0.075 per 1M input tokens

For ~100 conversations/day:
- Render: $7-12/month
- Gemini: ~$0-2/month
- **Total**: <$15/month

---

## Next Steps

1. Follow "Local Development" section
2. Test with public conversation traces
3. Deploy to Render staging
4. Validate with SHL evaluator
5. Deploy to production
6. Monitor and iterate

Good luck! 🚀
