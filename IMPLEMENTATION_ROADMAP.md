# AssessIQ AI - Complete Implementation Roadmap

## 📋 What Has Been Set Up

Your project now has:

✅ **Architecture documentation** (ARCHITECTURE.md)
✅ **Folder structure** (FOLDER_STRUCTURE.md)
✅ **Tech stack explanation** (docs/TECH_STACK.md)
✅ **Deployment guide** (docs/DEPLOYMENT.md)
✅ **Production-ready starter code** (all Python files)
✅ **Docker setup** (Dockerfile, docker-compose.yml)
✅ **Configuration management** (.env.example, config.py)
✅ **Pydantic models** (models/response.py, models/assessment.py)
✅ **Logging setup** (logging/logger.py)
✅ **Catalog sample** (data/raw/catalog.json)
✅ **Sample catalog loader** (services/catalog_loader.py)

---

## 🚀 Implementation Priority Order

### Phase 1: Data Pipeline (Day 1)
Build the retrieval foundation first.

**Tasks:**
1. ✅ Scraper (`scripts/scraper.py`)
   - Download SHL catalog from https://www.shl.com/solutions/products/product-catalog/
   - Extract: name, URL, description, type, duration
   - Save to `data/raw/catalog.json`
   - Handle errors, retries, duplicates

2. ✅ Embeddings Pipeline (`scripts/build_embeddings.py`)
   - Load catalog.json
   - Generate embeddings using sentence-transformers
   - Create FAISS index
   - Save to `data/vectorstore/faiss_index.bin`

3. ✅ Vector Store Service (`app/services/vector_store.py`)
   - Load FAISS index
   - Implement similarity search
   - Return top-K results

**Test:**
```bash
python scripts/scraper.py
python scripts/build_embeddings.py
python -c "from app.services.vector_store import VectorStore; vs = VectorStore(); print(vs.search('Java', k=5))"
```

---

### Phase 2: Retrieval Engine (Day 1-2)
Build semantic + keyword search.

**Tasks:**
1. ✅ Retriever Service (`app/services/retriever.py`)
   - Semantic search (vector similarity)
   - BM25 keyword search
   - Metadata filtering
   - Hybrid score fusion

2. ✅ Ranker Service (`app/services/ranker.py`)
   - Score assessments by relevance
   - Consider: semantic match, keyword match, role fit, seniority fit, skill overlap
   - Return top 1-10

**Test:**
```bash
pytest tests/unit/test_retriever.py
pytest tests/unit/test_ranker.py
```

---

### Phase 3: Agent Decision Logic (Day 2)
Build the conversational brain.

**Tasks:**
1. ✅ Decision Engine (`app/agents/decision_engine.py`)
   - Decide: REFUSE / CLARIFY / COMPARE / REFINE / RECOMMEND
   - Rules-based with context extraction

2. ✅ Context Extractor (`app/agents/context_extractor.py`)
   - Extract: role, seniority, skills, duration, etc.
   - Track changes across turns

3. ✅ Safety Checker (`app/agents/safety_checker.py`)
   - Detect off-topic requests
   - Detect prompt injection
   - Return SafetyCheck result

4. ✅ Comparison Handler (`app/agents/comparison_handler.py`)
   - Detect comparison requests
   - Retrieve assessment data
   - Generate comparison (no hallucination)

**Test:**
```bash
pytest tests/unit/test_decision_engine.py
pytest tests/unit/test_safety.py
```

---

### Phase 4: LLM Integration (Day 2-3)
Connect to Gemini.

**Tasks:**
1. ✅ Prompts (`app/prompts/`)
   - system_prompt.py - Core instructions
   - clarify_prompt.py - Clarification questions
   - recommend_prompt.py - Recommendations
   - compare_prompt.py - Comparisons
   - refuse_prompt.py - Refusals

2. ✅ LLM Service (`app/services/llm_service.py`)
   - Initialize Gemini client
   - Make requests with grounding
   - Parse structured responses
   - Handle timeouts

**Test:**
```bash
# Set GEMINI_API_KEY first
export GEMINI_API_KEY=your_key
pytest tests/unit/test_llm_service.py
```

---

### Phase 5: API Endpoints (Day 3)
Build FastAPI endpoints.

**Tasks:**
1. ✅ Health Endpoint (`app/routes/health.py`)
   - GET /health
   - Returns {"status": "ok"}

2. ✅ Chat Endpoint (`app/routes/chat.py`)
   - POST /chat
   - Request validation
   - Call decision engine
   - Call retriever + LLM
   - Return exact schema
   - Validation + error handling

3. ✅ Hallucination Checker (`app/utils/hallucination_checker.py`)
   - Check all recommendations from catalog
   - Check all URLs
   - Raise error if hallucination detected

**Test:**
```bash
pytest tests/integration/test_api_endpoints.py
```

---

### Phase 6: Validation & Safety (Day 3-4)
Ensure responses are safe.

**Tasks:**
1. ✅ Response Validator (`app/utils/validators.py`)
   - Validate schema compliance
   - Validate recommendation count (0 or 1-10)
   - Validate end_of_conversation flag

2. ✅ URL Validator (`app/utils/url_validator.py`)
   - Check all URLs from shl.com
   - Check URL format

**Test:**
```bash
pytest tests/unit/test_validators.py
```

---

### Phase 7: Testing & Evaluation (Day 4-5)
Test everything thoroughly.

**Tasks:**
1. ✅ Unit Tests
   - Each service tested independently
   - Each agent component tested

2. ✅ Integration Tests
   - Full conversation flows
   - Edge cases
   - Error handling

3. ✅ E2E Tests
   - Test with public conversation traces
   - Simulate SHL evaluator

**Test:**
```bash
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/test_public_traces.py
```

---

### Phase 8: Documentation (Day 5)
Document everything.

**Tasks:**
1. ✅ README.md - Getting started
2. ✅ ARCHITECTURE.md - Design decisions
3. ✅ docs/API.md - API reference
4. ✅ docs/DEPLOYMENT.md - Deployment steps
5. ✅ docs/PROMPT_ENGINEERING.md - Prompt design
6. ✅ Docstrings in all code files

---

### Phase 9: Deployment (Day 5-6)
Get it running.

**Tasks:**
1. ✅ Local Docker
   ```bash
   docker-compose up
   ```

2. ✅ Test locally
   ```bash
   pytest tests/e2e/
   ```

3. ✅ Render deployment
   - Create Render account
   - Connect GitHub
   - Deploy service
   - Test publicly

4. ✅ Monitoring
   - Setup logging
   - Monitor errors
   - Track performance

---

## 📁 File Implementation Order

```
Priority 1 (Must do first):
├── scripts/scraper.py
├── scripts/build_embeddings.py
├── app/services/vector_store.py
└── data/raw/catalog.json

Priority 2:
├── app/services/retriever.py
├── app/services/ranker.py
├── app/services/conversation_cache.py
└── tests/unit/test_retriever.py

Priority 3:
├── app/agents/decision_engine.py
├── app/agents/context_extractor.py
├── app/agents/safety_checker.py
├── app/agents/comparison_handler.py
└── tests/unit/test_decision_engine.py

Priority 4:
├── app/prompts/system_prompt.py
├── app/prompts/clarify_prompt.py
├── app/prompts/recommend_prompt.py
├── app/services/llm_service.py
└── tests/unit/test_llm_service.py

Priority 5:
├── app/routes/chat.py
├── app/utils/hallucination_checker.py
├── app/utils/validators.py
└── tests/integration/test_api_endpoints.py

Priority 6:
├── tests/e2e/test_public_traces.py
├── docs/API.md
└── docs/PROMPT_ENGINEERING.md
```

---

## 🔑 Critical Implementation Details

### Stateless Conversation
```python
# Every request is self-contained
@app.post("/chat")
async def chat(request: ChatRequest):
    messages = request.messages  # Full history
    
    # Process: don't lookup session state
    # No: session[user_id] = context
    # Do: extract context from messages
    
    context = extract_context(messages)
    action = decide_action(messages)
    
    # Generate response
    if action == "RECOMMEND":
        retrieved = retriever.search(context)
        ranked = ranker.rank(retrieved, context)
        recommendations = ranked[:10]
    
    return {
        "reply": reply,
        "recommendations": recommendations,
        "end_of_conversation": should_end
    }
```

### Hallucination Prevention
```python
# Every recommendation MUST be from catalog

@app.post("/chat")
async def chat(request: ChatRequest):
    # ... generate recommendations ...
    
    # Before returning, validate
    for rec in recommendations:
        # Check in catalog
        if not catalog.get_by_id(rec["id"]):
            raise HallucinationError(f"Unknown assessment: {rec['id']}")
        
        # Check URL matches
        catalog_entry = catalog.get_by_id(rec["id"])
        if rec["url"] != catalog_entry["url"]:
            raise HallucinationError(f"URL mismatch")
    
    return response
```

### Agent Decision Logic
```python
def decide_action(conversation):
    messages = conversation["messages"]
    
    # 1. Safety first
    if is_off_topic(messages[-1]):
        return "REFUSE"
    
    # 2. Check what user is asking
    if is_comparison(messages[-1]):
        return "COMPARE"
    
    # 3. Extract context
    context = extract_context(messages)
    
    # 4. Check sufficiency
    if not is_sufficient(context):
        return "CLARIFY"
    
    # 5. Check for changes
    if has_context_changed(context, previous_context):
        return "REFINE"
    
    # 6. Default to recommend
    return "RECOMMEND"
```

---

## ✅ Readiness Checklist

Before submitting:

- [ ] All tests pass: `pytest tests/`
- [ ] No hardcoded credentials
- [ ] API key in .env
- [ ] Catalog.json has 50+ assessments
- [ ] FAISS index builds successfully
- [ ] Health endpoint works: `curl /health`
- [ ] Chat endpoint works with sample request
- [ ] Responses match exact schema
- [ ] Hallucination checker catches errors
- [ ] Turn limit enforced (max 8)
- [ ] Timeout under 30 seconds
- [ ] Public traces pass: `pytest tests/e2e/`
- [ ] Deployed to Render successfully
- [ ] Approach document written (2 pages max)
- [ ] README updated

---

## 🆘 Common Issues & Solutions

### "FAISS index not found"
```bash
# Rebuild
python scripts/build_embeddings.py
```

### "API key not set"
```bash
# Set in .env
export GEMINI_API_KEY=your_key
```

### "Timeout on /chat"
```python
# Profile retrieval:
import time
start = time.time()
retrieved = retriever.search(query)
print(f"Retrieval: {time.time() - start:.2f}s")

# Reduce if needed:
TOP_K_RETRIEVAL=10  # Instead of 20
```

### "Response not matching schema"
```python
# Validate before returning
from app.models.response import ChatResponse
response = ChatResponse(**response_dict)
# If invalid, raises ValidationError
```

### "Hallucination detected"
```python
# Check recommendation validation
from app.utils.hallucination_checker import check_hallucinations
check_hallucinations(recommendations, catalog)
# Raises if any hallucination found
```

---

## 📞 Quick Reference

### Start local dev:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Build data:
```bash
python scripts/scraper.py
python scripts/build_embeddings.py
```

### Run tests:
```bash
pytest tests/
pytest tests/e2e/test_public_traces.py -v
```

### Deploy:
```bash
docker-compose up
# Or: deploy to Render
```

### Test API:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Java dev"}]}'
```

---

## 🎯 Success Criteria

Your submission is complete when:

1. ✅ All code is written and tested
2. ✅ API deployed publicly (Render)
3. ✅ Health check passes
4. ✅ Chat endpoint works
5. ✅ Public conversation traces pass
6. ✅ No hallucinations detected
7. ✅ Schema always correct
8. ✅ Approach document written
9. ✅ Everything documented

---

**You're ready! Start with the scraper, build upward, test thoroughly, and deploy with confidence. Good luck! 🚀**
