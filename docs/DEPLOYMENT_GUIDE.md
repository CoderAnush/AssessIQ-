# AssessIQ Production Deployment Guide

## Quick Start

### Option 1: Local Development
```bash
# 1. Set up environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 2. Install dependencies
pip install -r requirements.txt

# 3. Build data pipeline (if not already built)
python scripts/build_pipeline.py

# 4. Run API server
python app/main.py
# API available at http://localhost:8000

# 5. In another terminal, run frontend
streamlit run frontend/streamlit_app.py
# UI available at http://localhost:8501
```

### Option 2: Docker Local Deployment
```bash
# 1. Build image
docker build -t assessiq:latest .

# 2. Run API server
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key_here assessiq:latest

# 3. In another container, run frontend
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key_here assessiq:latest \
  streamlit run frontend/streamlit_app.py
```

### Option 3: Docker Compose (Local)
```bash
# Create docker-compose.yml with API + Frontend
docker-compose up
```

### Option 4: Render Deployment
```bash
# 1. Connect GitHub repository to Render
# 2. Create new Web Service from render.yaml
# 3. Set environment variables:
#    - GEMINI_API_KEY: your-api-key
#    - ENVIRONMENT: production
# 4. Deploy
```

## Environment Setup

### Create `.env` File

```bash
# API Keys
GEMINI_API_KEY=your_gemini_api_key_here

# Data Paths
CATALOG_PATH=data/raw/catalog.json
FAISS_INDEX_PATH=data/processed/faiss_index.bin
BM25_INDEX_PATH=data/processed/bm25_index.pkl
EMBEDDINGS_PATH=data/processed/embeddings.npy

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0
ENVIRONMENT=production

# Retrieval Configuration
SEMANTIC_SEARCH_WEIGHT=0.7
BM25_SEARCH_WEIGHT=0.3
TOP_K_RETRIEVAL=20

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/assessiq.log

# Features
ENABLE_METRICS=true
DEBUG=false
```

## Data Pipeline

Before deployment, ensure data is prepared:

```bash
# 1. Build complete pipeline
python scripts/build_pipeline.py

# 2. Validate pipeline
python scripts/validate_pipeline.py

# Expected output files:
# - data/processed/catalog_processed.json
# - data/processed/faiss_index.bin
# - data/processed/faiss_metadata.json
# - data/processed/bm25_index.pkl
# - data/processed/embeddings.npy
```

## Deployment Platforms

### Render.com

**Advantages:**
- Automatic deployments from GitHub
- Built-in monitoring
- Easy scaling
- Free tier available

**Steps:**
1. Push code to GitHub
2. Connect repository to Render
3. Create Web Service from `render.yaml`
4. Set `GEMINI_API_KEY` in Environment
5. Deploy

**Monitor:**
- Render Dashboard: https://dashboard.render.com
- View logs in real-time
- Set up alerts for errors

### Streamlit Cloud (Frontend Only)

**Advantages:**
- Free hosting for Streamlit apps
- GitHub integration
- Automatic updates on push
- Optimized build times with lightweight `frontend/requirements.txt`

**Steps:**
1. Push code to GitHub
2. Go to https://streamlit.io/cloud
3. Create new app:
   - **Repository:** `CoderAnush/AssessIQ-`
   - **Main file path:** `frontend/streamlit_app.py`
4. Set **Advanced Settings > Secrets**:
   ```toml
   BACKEND_URL = "https://assessiq-nkp2.onrender.com"
   ```
5. Deploy

**Note:** `GEMINI_API_KEY` is NOT needed for the frontend as it calls the backend which handles LLM requests.

### AWS ECS (Docker)

**Prerequisites:**
- AWS Account
- ECR repository created
- ECS cluster ready

**Steps:**
1. Build and push Docker image to ECR
2. Create ECS task definition with `Dockerfile`
3. Set environment variables in task definition
4. Deploy to ECS cluster
5. Configure load balancer and health checks

### Self-Hosted (VPS)

**Requirements:**
- Server with 2GB+ RAM
- Docker installed
- Public IP or DNS

**Steps:**
```bash
# 1. SSH into server
ssh user@your-server.com

# 2. Clone repository
git clone https://github.com/yourusername/assessiq.git
cd assessiq

# 3. Create .env with GEMINI_API_KEY

# 4. Build and run
docker build -t assessiq:latest .
docker run -d \
  -p 8000:8000 \
  -p 8501:8501 \
  -e GEMINI_API_KEY=your_key \
  --name assessiq \
  assessiq:latest
```

## Pre-Deployment Checklist

- [ ] `.env` file created with `GEMINI_API_KEY` set
- [ ] Data pipeline built (`python scripts/build_pipeline.py`)
- [ ] Pipeline validated (`python scripts/validate_pipeline.py`)
- [ ] Tests pass locally:
  ```bash
  python app/main.py  # In one terminal
  python scripts/production_execution_verify.py  # In another
  ```
- [ ] Docker builds successfully: `docker build -t assessiq:latest .`
- [ ] All dependencies in requirements.txt
- [ ] README and documentation updated
- [ ] .gitignore configured (includes `.env`, `logs/`, `data/raw/`)
- [ ] GitHub repository public or access configured
- [ ] Deployment platform credentials configured

## Monitoring & Health Checks

### API Health Check
```bash
curl http://localhost:8000/health
# Returns: {"status": "ok"}
```

### API Monitoring Endpoints
- `/health` - Basic health check
- `/docs` - Swagger API documentation
- `/redoc` - ReDoc API documentation

### Logs
```bash
# View API logs
tail -f logs/assessiq.log

# View Docker logs
docker logs -f assessiq
```

### Metrics
```bash
# View evaluation metrics
python scripts/analyze_metrics.py --output metrics_report.txt
```

## Performance Optimization

### Startup Time
- Target: <3 seconds to ready
- FAISS index loads first (binary format, ~1s)
- BM25 index loads second (pickle format, ~0.5s)
- LLM service initializes (~0.5s)

### Response Latency
- Target: <500ms p95
- Retrieval: ~50ms (FAISS + BM25)
- LLM generation: ~200-300ms (Gemini)
- Total: ~250-350ms average

### Memory Usage
- FAISS index: ~150MB
- BM25 index: ~50MB
- Embeddings: ~100MB
- Total: ~300-400MB base + LLM overhead

### Scaling
```bash
# Run multiple API instances behind load balancer
for i in {1..3}; do
  docker run -d \
    -p $((8000+i)):8000 \
    -e GEMINI_API_KEY=key \
    assessiq:latest
done

# Configure nginx to balance traffic
```

## Troubleshooting

### API Won't Start
```bash
# Check for port conflicts
lsof -i :8000

# Check logs
cat logs/assessiq.log

# Verify environment
python -c "from app.config import validate_config; validate_config()"
```

### Gemini API Errors
```bash
# Check API key
echo $GEMINI_API_KEY

# Test connectivity
python -c "from app.services.llm_service import LLMService; LLMService()"
```

### High Latency
```bash
# Check FAISS index size
ls -lh data/processed/faiss_index.bin

# Monitor API latency in logs
grep "latency" logs/assessiq.log

# Consider reducing TOP_K_RETRIEVAL in .env
```

### Out of Memory
```bash
# Monitor memory
docker stats assessiq

# Increase container memory
docker run -m 2g ...

# Or reduce TOP_K_RETRIEVAL (default: 20)
```

## Rollback Procedure

If deployment fails:

```bash
# 1. Identify issue
docker logs assessiq

# 2. Stop current deployment
docker stop assessiq

# 3. Switch to previous version
git checkout HEAD~1
docker build -t assessiq:previous .
docker run -d --name assessiq assessiq:previous

# 4. Investigate issue locally
# 5. Fix and redeploy
```

## Security

- [ ] `.env` file with `GEMINI_API_KEY` is in `.gitignore`
- [ ] API is behind HTTPS in production (use reverse proxy)
- [ ] CORS is configured appropriately
- [ ] Rate limiting enabled (if needed)
- [ ] Logs don't contain sensitive data
- [ ] No API keys in commit history

## Support

For issues, see:
- [README.md](../README.md) - Project overview
- [TESTING_GUIDE.md](../docs/TESTING_GUIDE.md) - Testing documentation
- [PRODUCTION_HANDOFF.md](../PRODUCTION_HANDOFF.md) - Architecture and guarantees
- GitHub Issues: Open an issue for bugs or feature requests

