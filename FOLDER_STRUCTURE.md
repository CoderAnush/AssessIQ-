# AssessIQ AI: Complete Folder Structure & Responsibilities

```
AssessIQ-AI/
│
├── app/                                    # Backend application
│   ├── __init__.py
│   ├── main.py                            # FastAPI app entry point
│   ├── config.py                          # Configuration management
│   │
│   ├── routes/                            # API endpoints
│   │   ├── __init__.py
│   │   ├── health.py                      # GET /health
│   │   └── chat.py                        # POST /chat
│   │
│   ├── services/                          # Business logic
│   │   ├── __init__.py
│   │   ├── catalog_loader.py              # Load SHL catalog from JSON
│   │   ├── embedding_service.py           # Generate embeddings
│   │   ├── vector_store.py                # FAISS operations
│   │   ├── retriever.py                   # Hybrid retrieval logic
│   │   ├── ranker.py                      # Ranking system
│   │   └── conversation_cache.py          # Context extraction
│   │
│   ├── agents/                            # Agent logic
│   │   ├── __init__.py
│   │   ├── decision_engine.py             # Decide: ask/recommend/refine/compare/refuse
│   │   ├── context_extractor.py           # Extract hiring context
│   │   ├── comparison_handler.py          # Handle comparison requests
│   │   └── safety_checker.py              # Detect off-topic, injection
│   │
│   ├── retriever/                         # Advanced retrieval (optional extra folder)
│   │   ├── __init__.py
│   │   ├── semantic.py                    # Semantic search
│   │   ├── bm25.py                        # BM25 keyword search
│   │   └── hybrid.py                      # Hybrid fusion
│   │
│   ├── prompts/                           # LLM prompts
│   │   ├── __init__.py
│   │   ├── system_prompt.py               # System instructions
│   │   ├── clarify_prompt.py              # Clarification question generation
│   │   ├── recommend_prompt.py            # Recommendation generation
│   │   ├── compare_prompt.py              # Comparison generation
│   │   └── refuse_prompt.py               # Refusal generation
│   │
│   ├── models/                            # Pydantic models (schemas)
│   │   ├── __init__.py
│   │   ├── request.py                     # ChatRequest, Message
│   │   ├── response.py                    # ChatResponse, Recommendation
│   │   ├── assessment.py                  # Assessment, CatalogEntry
│   │   └── context.py                     # HiringContext, ContextState
│   │
│   ├── utils/                             # Utility functions
│   │   ├── __init__.py
│   │   ├── validators.py                  # Validate responses
│   │   ├── hallucination_checker.py       # Detect hallucinations
│   │   ├── url_validator.py               # Validate SHL URLs
│   │   └── text_utils.py                  # String processing
│   │
│   ├── evaluation/                        # Testing & evaluation
│   │   ├── __init__.py
│   │   ├── test_scenarios.py              # Test conversation scenarios
│   │   ├── eval_metrics.py                # Recall@K, other metrics
│   │   └── conversation_replayer.py       # Replay saved conversations
│   │
│   └── logging/                           # Monitoring & logging
│       ├── __init__.py
│       ├── logger.py                      # Structured logging
│       ├── metrics.py                     # Metrics collection
│       └── error_reporter.py              # Error tracking
│
├── frontend/                              # Optional Streamlit UI
│   ├── streamlit_app.py                   # Main Streamlit app
│   └── components/                        # Reusable UI components
│       ├── chat_interface.py
│       └── recommendation_card.py
│
├── data/                                  # Data storage
│   ├── raw/                               # Raw scraped data
│   │   └── catalog.json                   # SHL catalog (from scraper)
│   │
│   ├── processed/                         # Processed data
│   │   ├── assessments.jsonl              # Processed assessments
│   │   └── metadata.json                  # Metadata index
│   │
│   └── vectorstore/                       # FAISS indices
│       ├── faiss_index.bin                # FAISS index file
│       └── index_metadata.json            # Index mapping
│
├── scripts/                               # One-off scripts
│   ├── __init__.py
│   ├── scraper.py                         # Scrape SHL catalog
│   ├── build_embeddings.py                # Generate embeddings & FAISS
│   ├── validate_catalog.py                # Validate catalog integrity
│   └── test_retrieval.py                  # Test retrieval locally
│
├── tests/                                 # Test suite
│   ├── __init__.py
│   ├── conftest.py                        # Pytest fixtures
│   ├── unit/
│   │   ├── test_decision_engine.py        # Test decision logic
│   │   ├── test_retriever.py              # Test retrieval
│   │   ├── test_ranker.py                 # Test ranking
│   │   ├── test_validators.py             # Test validation
│   │   └── test_safety.py                 # Test safety checks
│   ├── integration/
│   │   ├── test_api_endpoints.py          # Test /health, /chat
│   │   ├── test_conversation_flow.py      # Test full conversations
│   │   └── test_hallucination.py          # Test hallucination prevention
│   └── e2e/
│       ├── test_public_traces.py          # Test with public test cases
│       └── test_edge_cases.py             # Test edge cases
│
├── docs/                                  # Documentation
│   ├── API.md                             # API documentation
│   ├── DEPLOYMENT.md                      # Deployment guide
│   ├── PROMPT_ENGINEERING.md              # Prompt design decisions
│   ├── RETRIEVAL.md                       # Retrieval system docs
│   └── EXAMPLES.md                        # Example conversations
│
├── .env.example                           # Environment template
├── requirements.txt                       # Python dependencies
├── Dockerfile                             # Container image
├── docker-compose.yml                     # Local dev setup
├── ARCHITECTURE.md                        # This architecture guide
├── README.md                              # Project README
└── .gitignore                             # Git ignore rules
```

---

## FILE RESPONSIBILITIES

### app/main.py
```
Creates FastAPI app
Mounts routes (/health, /chat)
Loads catalog at startup
Initializes FAISS index
Sets up middleware (logging, CORS)
Handles lifecycle (startup, shutdown)
```

### app/config.py
```
Loads environment variables
Defines configuration classes
Sets API keys, paths, thresholds
Returns config object to app
```

### app/routes/health.py
```
GET /health endpoint
Returns {"status": "ok"}
Checks dependencies alive
Used for readiness probes
```

### app/routes/chat.py
```
POST /chat endpoint
Validates request schema
Handles conversation flow
Calls decision engine
Generates response
Validates response
Returns to client
```

### app/services/catalog_loader.py
```
Loads catalog.json from disk
Builds searchable index
Returns assessment objects
Called at app startup
```

### app/services/embedding_service.py
```
Uses sentence-transformers
Converts text to vectors
Caches embeddings
Called during setup & comparison
```

### app/services/vector_store.py
```
Initializes FAISS index
Loads saved index from disk
Performs similarity search
Returns top-k results
```

### app/services/retriever.py
```
Orchestrates retrieval pipeline
Semantic search + BM25 + metadata filtering
Combines results (hybrid fusion)
Returns ranked candidates
```

### app/services/ranker.py
```
Takes candidates, ranks by relevance
Uses multiple scoring signals
Returns top 1-10 assessments
Called before response generation
```

### app/services/conversation_cache.py
```
Extracts hiring context from history
Tracks what we know about user
Detects context changes (for refinement)
Suggests next clarification question
```

### app/agents/decision_engine.py
```
Core decision logic
Determines: refuse/clarify/compare/refine/recommend
Returns action enum + reasoning
Called for every user message
```

### app/agents/context_extractor.py
```
Analyzes messages for hiring intent
Builds HiringContext object
Tracks: role, seniority, skills, budget, etc.
Used by decision engine
```

### app/agents/comparison_handler.py
```
Detects comparison questions
Retrieves assessment data
Generates comparison response
Uses only catalog data (no hallucination)
```

### app/agents/safety_checker.py
```
Detects off-topic requests
Detects prompt injection
Detects legal/hiring advice requests
Returns SafetyCheckResult
```

### app/prompts/system_prompt.py
```
Defines system instruction for LLM
Sets tone, scope, constraints
Instructs on grounding, hallucination prevention
Returned to every LLM call
```

### app/prompts/clarify_prompt.py
```
Template for asking clarification questions
Instructs LLM what context is missing
Returns high-value questions
Uses current context to decide next question
```

### app/prompts/recommend_prompt.py
```
Template for generating recommendations
Takes retrieved candidates + ranking
Instructs LLM to create friendly recommendation message
Ensures schema compliance
```

### app/models/request.py
```
Pydantic model for POST /chat request
Validates "messages" field
Defines Message structure
Used by FastAPI for validation
```

### app/models/response.py
```
Pydantic model for POST /chat response
Defines reply, recommendations, end_of_conversation
Used by FastAPI for serialization
Ensures schema compliance
```

### app/models/assessment.py
```
Pydantic models for assessment data
Assessment, CatalogEntry, AssessmentMetadata
Used throughout codebase
Validates assessment properties
```

### app/utils/validators.py
```
Validates response structure
Checks schema compliance
Validates recommendation fields
Raises ValidationError if invalid
```

### app/utils/hallucination_checker.py
```
Detects hallucinated assessments
Checks all recommendations against catalog
Checks all URLs
Raises HallucinationError if found
```

### app/utils/url_validator.py
```
Validates SHL assessment URLs
Checks domain is shl.com
Checks URL structure
Returns boolean or raises exception
```

### app/logging/logger.py
```
Structured logging setup
Returns logger instance
Logs: decisions, retrievals, responses, errors
Outputs to stdout or file
```

### scripts/scraper.py
```
Scrapes SHL catalog from website
Uses BeautifulSoup to parse HTML
Extracts: name, description, URL, duration, type, skills, roles
Saves to catalog.json
Handles retries, errors, duplicates
```

### scripts/build_embeddings.py
```
Takes catalog.json
Generates embeddings for each assessment
Creates FAISS index
Saves index to disk
Run once during setup
```

### tests/
```
Unit tests: test individual functions
Integration tests: test API endpoints + flows
E2E tests: test with public conversation traces
Pytest fixtures: shared test data
```

---

## DATA FILES

### data/raw/catalog.json
```json
{
  "assessments": [
    {
      "id": "opq32r",
      "name": "OPQ32r",
      "description": "...",
      "url": "https://www.shl.com/solutions/products/opq32r/",
      "duration_minutes": 30,
      "test_type": "P",
      "skills": ["communication", "leadership"],
      "recommended_roles": ["manager", "lead", "developer"],
      "seniority_levels": ["mid", "senior"]
    }
  ]
}
```

### data/processed/assessments.jsonl
```jsonl
{"id": "opq32r", "name": "OPQ32r", "embedding": [...]}
{"id": "gsa", "name": "GSA", "embedding": [...]}
```

### data/vectorstore/faiss_index.bin
```
Binary FAISS index file
Created by scripts/build_embeddings.py
Loaded at app startup
Read-only during operation
```

---

## ENVIRONMENT VARIABLES (.env)

```
# LLM
GEMINI_API_KEY=<your-key>

# Paths
CATALOG_PATH=data/raw/catalog.json
FAISS_INDEX_PATH=data/vectorstore/faiss_index.bin

# API
API_PORT=8000
API_HOST=0.0.0.0

# Retrieval
BM25_WEIGHT=0.3
SEMANTIC_WEIGHT=0.7
TOP_K_RETRIEVAL=20

# Response
MAX_RECOMMENDATIONS=10
MAX_TURNS=8
REQUEST_TIMEOUT=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Monitoring
SENTRY_DSN=<optional>
```

---

## KEY FILES TO START WITH

**When implementing:**

1. Start with `data/raw/catalog.json` (scraper output)
2. Generate `data/vectorstore/faiss_index.bin` (setup)
3. Implement `app/services/retriever.py` (core logic)
4. Implement `app/agents/decision_engine.py` (core logic)
5. Implement `app/routes/chat.py` (API)
6. Add tests in `tests/`
7. Deploy with `Dockerfile`

**Critical for SHL evaluator:**

- Ensure `app/models/response.py` matches exact schema
- Ensure `app/utils/hallucination_checker.py` catches all issues
- Ensure `app/agents/safety_checker.py` refuses bad requests
- Ensure `tests/` covers all 10 public traces
