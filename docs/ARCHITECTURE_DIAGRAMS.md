# AssessIQ AI - System Architecture Diagrams

## 1. HIGH-LEVEL SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SHL EVALUATOR HARNESS                         │
│                    (Simulated User + Test Conversation)              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ HTTP POST /chat
                                 │ (with full conversation history)
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                               │
│                    (AssessIQ AI Application)                         │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1. REQUEST VALIDATION                                        │   │
│  │    - Validate ChatRequest schema                            │   │
│  │    - Extract messages                                       │   │
│  │    - Count turns (max 8)                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 2. CONTEXT EXTRACTION                                        │   │
│  │    - Parse conversation history                             │   │
│  │    - Extract: role, seniority, skills, etc.               │   │
│  │    - Build HiringContext                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 3. SAFETY CHECK                                              │   │
│  │    - Is off-topic? → REFUSE                                │   │
│  │    - Is prompt injection? → REFUSE                         │   │
│  │    - Is comparison? → Handle separately                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 4. DECISION ENGINE                                           │   │
│  │    - Check context sufficiency                              │   │
│  │    - Decide: CLARIFY / RECOMMEND / REFINE                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                 ↓                                    │
│              ┌─────────────────┬────────────────┐                   │
│              ↓                 ↓                ↓                   │
│        ┌──────────┐    ┌──────────┐    ┌──────────────┐           │
│        │ CLARIFY  │    │ RECOMMEND│    │ COMPARE/REFINE           │
│        └──────────┘    └──────────┘    └──────────────┘           │
│                              ↓                                      │
│        ┌─────────────────────────────────────────────────┐         │
│        │ 5. RETRIEVAL PIPELINE                           │         │
│        │    ┌──────────────────────────────────────────┐ │         │
│        │    │ Semantic Search (FAISS)     │ 70% weight │ │         │
│        │    │ Results: [A1(0.92), A2(0.85)]           │ │         │
│        │    └──────────────────────────────────────────┘ │         │
│        │    ┌──────────────────────────────────────────┐ │         │
│        │    │ BM25 Keyword Search        │ 30% weight │ │         │
│        │    │ Results: [B1(0.85), B2(0.70)]           │ │         │
│        │    └──────────────────────────────────────────┘ │         │
│        │    ┌──────────────────────────────────────────┐ │         │
│        │    │ Metadata Filtering                       │ │         │
│        │    │ Role: Developer, Seniority: Mid          │ │         │
│        │    └──────────────────────────────────────────┘ │         │
│        │    ┌──────────────────────────────────────────┐ │         │
│        │    │ Hybrid Fusion + Ranking                  │ │         │
│        │    │ Top 10 results                           │ │         │
│        │    └──────────────────────────────────────────┘ │         │
│        └─────────────────────────────────────────────────┘         │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 6. LLM GENERATION (Gemini 2.0 Flash)                         │   │
│  │    - Use system prompt for grounding                         │   │
│  │    - Pass retrieved context                                  │   │
│  │    - Generate response + recommendations                     │   │
│  │    - Return structured JSON                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 7. VALIDATION LAYER                                          │   │
│  │    - Schema compliance (Pydantic)                            │   │
│  │    - Hallucination detection                                 │   │
│  │    - URL validation (shl.com domain)                         │   │
│  │    - Recommendation count (0 or 1-10)                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 8. RESPONSE FORMATTING                                       │   │
│  │    {                                                          │   │
│  │      "reply": "Here are 5 assessments...",                  │   │
│  │      "recommendations": [                                    │   │
│  │        {"name": "OPQ32r", "url": "...", "test_type": "P"}  │   │
│  │      ],                                                       │   │
│  │      "end_of_conversation": false                            │   │
│  │    }                                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ JSON Response
                                 ↓
                         SHL Evaluator
                         (Scores Submission)
```

---

## 2. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│ SETUP PHASE (Run Once)                                              │
└─────────────────────────────────────────────────────────────────────┘

SHL Website
    ↓
    │ BeautifulSoup + Requests
    ↓
data/raw/catalog.json (7+ assessments)
    ├── id: "opq32r"
    ├── name: "OPQ32r"
    ├── description: "..."
    ├── url: "https://www.shl.com/..."
    └── skills: [...]
    ↓
    │ Load + Parse
    ↓
Memory: List[AssessmentWithMetadata] (100+ items)
    ├── A1: OPQ32r
    ├── A2: GSA
    ├── A3: Java 8
    └── ...
    ↓
    │ sentence-transformers (all-MiniLM-L6-v2)
    ↓
embeddings = [
    [0.12, -0.45, 0.67, ..., 0.23],  # A1 embedding (384-dim)
    [0.34, 0.56, -0.78, ..., 0.12],  # A2 embedding
    [...],                             # A3 embedding
]
    ↓
    │ FAISS IndexFlatL2
    ↓
data/vectorstore/faiss_index.bin (~10MB)
    (Ready for fast similarity search)


┌─────────────────────────────────────────────────────────────────────┐
│ RUNTIME PHASE (Every Request)                                       │
└─────────────────────────────────────────────────────────────────────┘

User Message: "Hiring Java developer with communication skills"
    ↓
    │ Embeddings
    ↓
Query Vector: [0.89, 0.12, -0.34, ..., 0.56]  (384-dim)
    ↓
    ├─→ FAISS Search ─→ distances=[0.2, 0.4, 0.6, ...]
    │                    indices=[0, 2, 1, ...]
    │                    → Candidates: [A1(0.92), A3(0.82), A2(0.75)]
    │
    └─→ BM25 Search  ─→ scores=[2.15, 1.85, 0.95, ...]
                        → Candidates: [A3(Java), A1(communication), A2(...)]

    Hybrid Fusion:
    A1: 0.7 × 0.92 + 0.3 × 0.85 = 0.897 ← Highest
    A3: 0.7 × 0.82 + 0.3 × 0.95 = 0.870
    A2: 0.7 × 0.75 + 0.3 × 0.80 = 0.765
    ↓
    │ Metadata Filtering
    │ (seniority: mid, role: developer, skills: Java, communication)
    ↓
    Ranked Results: [A1, A3, A2, ...]
    ↓
    │ LLM Generation
    │ (with retrieved context)
    ↓
LLM Response:
{
    "reply": "Great! Based on your needs, here are 5 assessments...",
    "recommendations": [
        {"name": "OPQ32r", "url": "...", "test_type": "P"},
        {"name": "Java 8", "url": "...", "test_type": "K"},
        ...
    ],
    "end_of_conversation": false
}
    ↓
    │ Validation
    │ (schema, hallucination check)
    ↓
Response to User
```

---

## 3. AGENT DECISION LOGIC FLOW

```
User Message
    ↓
    ├─→ SAFETY CHECK
    │   ├─→ Is off-topic?
    │   │   ├─→ YES → REFUSE ("I only discuss SHL assessments")
    │   │   └─→ NO ↓
    │   ├─→ Is prompt injection?
    │   │   ├─→ YES → REFUSE ("Can't help with that")
    │   │   └─→ NO ↓
    │   └─→ Is comparison?
    │       ├─→ YES → COMPARE (handle specially)
    │       └─→ NO ↓
    ↓
    ├─→ CONTEXT EXTRACTION
    │   Extract: {
    │     role: "Java developer" or None,
    │     seniority: "mid-level" or None,
    │     skills: ["communication"] or [],
    │     duration: 30 or None,
    │     test_type: "P" or None
    │   }
    ↓
    ├─→ SUFFICIENCY CHECK
    │   Is context sufficient? (role + seniority + 1+ skill)
    │   ├─→ NO → CLARIFY
    │   │   Ask: "What seniority level?" or
    │   │         "What skills are important?" or
    │   │         "What test type?" or
    │   │         "Any duration preference?"
    │   └─→ YES ↓
    ↓
    ├─→ REFINEMENT CHECK
    │   Did constraints change from last turn?
    │   ├─→ YES → REFINE
    │   │   "Actually, add leadership tests"
    │   │   → Re-search with new criteria
    │   │   → Update recommendations
    │   └─→ NO ↓
    ↓
    ├─→ RECOMMENDATION CHECK
    │   Have we recommended before?
    │   ├─→ NO → RECOMMEND
    │   │   Generate top 1-10 assessments
    │   └─→ YES → Already recommended this turn
    ↓
    └─→ GENERATE RESPONSE
        {
            "reply": "...",
            "recommendations": [...],
            "end_of_conversation": true/false
        }
```

---

## 4. RETRIEVAL PIPELINE DETAIL

```
Query: "Java developer, mid-level, communication"
    ↓
┌─────────────────────────────────────┐
│ 1. SEMANTIC SEARCH (FAISS)          │
│    (70% weight)                     │
├─────────────────────────────────────┤
│ Algorithm: L2 distance in            │
│ embedding space (384-dim)            │
│                                      │
│ Step 1: Encode query                │
│   query_vector = model.encode(...)  │
│                                      │
│ Step 2: Search index                │
│   distances, indices = index.search( │
│       query_vector, k=20            │
│   )                                 │
│                                      │
│ Results:                            │
│   0: opq32r (dist=0.08) → score 0.92│
│   1: leadership7 (dist=0.15) → 0.85 │
│   2: 16pf (dist=0.22) → 0.78        │
│   3: gsa (dist=0.35) → 0.65         │
│   ...                               │
│                                      │
│ Score = 1 / (1 + distance)          │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. BM25 KEYWORD SEARCH              │
│    (30% weight)                     │
├─────────────────────────────────────┤
│ Algorithm: Probabilistic            │
│ keyword ranking                     │
│                                      │
│ Step 1: Tokenize query              │
│   tokens = ["java", "developer",    │
│             "mid", "level",         │
│             "communication"]        │
│                                      │
│ Step 2: Score each document         │
│   Document: "Java 8: Knowledge..."  │
│   → Match: "Java" (1 hit)           │
│   → Score: 0.95                     │
│                                      │
│   Document: "OPQ32r: Personality..." │
│   → Match: "communication" (1 hit)  │
│   → Score: 0.75                     │
│                                      │
│ Results:                            │
│   0: java_8 → score 0.95            │
│   1: opq32r → score 0.75            │
│   2: gsa → score 0.60               │
│   ...                               │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. HYBRID FUSION                    │
│                                      │
│ For each assessment:                │
│   final_score =                     │
│     (0.7 × semantic) +              │
│     (0.3 × bm25)                    │
│                                      │
│ opq32r:   0.7 × 0.92 + 0.3 × 0.75 = │
│           0.644 + 0.225 = 0.869 ← 1st│
│ java_8:   0.7 × 0.65 + 0.3 × 0.95 = │
│           0.455 + 0.285 = 0.740 ← 2nd│
│ gsa:      0.7 × 0.65 + 0.3 × 0.60 = │
│           0.455 + 0.180 = 0.635 ← 3rd│
│                                      │
│ Ranked: [opq32r, java_8, gsa, ...]  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. METADATA FILTERING               │
│                                      │
│ Keep assessments where:             │
│   seniority ∈ [mid, senior]        │
│   role ∈ [developer, ...]           │
│   skills ⊇ {communication}          │
│   duration ≤ 45 min                │
│                                      │
│ Filter out:                         │
│   - Junior-only assessments         │
│   - Non-dev assessments             │
│   - >45 min duration                │
│                                      │
│ Result: [opq32r, java_8, ...]       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5. FINAL RANKING                    │
│                                      │
│ Additional scoring:                 │
│   score += role_fit_bonus           │
│   score += seniority_fit_bonus      │
│   score += skill_overlap_bonus      │
│                                      │
│ Top 10:                             │
│   1. opq32r (0.92)                  │
│   2. java_8 (0.88)                  │
│   3. leadership7 (0.85)             │
│   4. gsa (0.80)                     │
│   5. ...                            │
└─────────────────────────────────────┘
    ↓
LLM receives: top 10 assessments
→ Generates recommendations
→ Returns to user
```

---

## 5. STATELESS CONVERSATION FLOW

```
┌──────────────────────────────────────────────────┐
│ TURN 1: User asks vague question                 │
│                                                  │
│ Request:                                         │
│ POST /chat                                       │
│ {                                                │
│   "messages": [                                  │
│     {"role": "user", "content": "Hiring..."}    │
│   ]                                              │
│ }                                                │
│                                                  │
│ Server:                                          │
│ - No session lookup needed                       │
│ - Extract context from messages                 │
│ - Decide: CLARIFY                               │
│ - Generate response                             │
│                                                  │
│ Response:                                        │
│ {                                                │
│   "reply": "What role specifically?",           │
│   "recommendations": [],                         │
│   "end_of_conversation": false                  │
│ }                                                │
│                                                  │
│ Server forgets: ← KEY POINT                     │
│ - No session stored                              │
│ - No memory kept                                 │
│ - Everything stateless                          │
└──────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────┐
│ TURN 2: User provides more info                 │
│                                                  │
│ Request:                                         │
│ POST /chat                                       │
│ {                                                │
│   "messages": [  ← FULL HISTORY                 │
│     {"role": "user", "content": "Hiring..."},   │
│     {"role": "assistant", "content": "What...?"}, │
│     {"role": "user", "content": "Java dev..."}  │
│   ]                                              │
│ }                                                │
│                                                  │
│ Server:                                          │
│ - No session lookup                             │
│ - All context from messages                     │
│ - Extract: role="Java dev", seniority=missing   │
│ - Decide: CLARIFY (need seniority)             │
│                                                  │
│ Response:                                        │
│ {                                                │
│   "reply": "What seniority level?",            │
│   "recommendations": [],                         │
│   "end_of_conversation": false                  │
│ }                                                │
│                                                  │
│ Server forgets: ← AGAIN STATELESS              │
└──────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────┐
│ TURN 3: User provides enough info               │
│                                                  │
│ Request:                                         │
│ POST /chat                                       │
│ {                                                │
│   "messages": [  ← FULL HISTORY (now 5 msgs)   │
│     {"role": "user", "content": "Hiring..."},   │
│     {"role": "assistant", "content": "What...?"}, │
│     {"role": "user", "content": "Java dev..."},  │
│     {"role": "assistant", "content": "Seniority?"}, │
│     {"role": "user", "content": "Mid-level"}    │
│   ]                                              │
│ }                                                │
│                                                  │
│ Server:                                          │
│ - Extract context (role, seniority, now complete) │
│ - Decide: RECOMMEND (sufficient info)           │
│ - Search & rank assessments                     │
│ - Generate response with recommendations        │
│                                                  │
│ Response:                                        │
│ {                                                │
│   "reply": "Here are 5 assessments...",         │
│   "recommendations": [                           │
│     {"name": "OPQ32r", "url": "...", ...},      │
│     {"name": "Java 8", "url": "...", ...},      │
│     ...                                          │
│   ],                                             │
│   "end_of_conversation": false                  │
│ }                                                │
│                                                  │
│ Server forgets: ← YET AGAIN STATELESS           │
└──────────────────────────────────────────────────┘

Key Insight:
- Each request is independent
- All context in messages array
- No server state needed
- Scales infinitely
- Perfect for serverless
- Easy to test and debug
```

---

## 6. ERROR HANDLING FLOW

```
Request → Validate Schema
            ↓
            If Invalid → 400 Bad Request
                        {error: "..."}
            ↓ If Valid
        Extract Context
            ↓
            If Extraction Error → 500 Internal Error
                                 {error: "..."}
            ↓ If Valid
        Safety Check
            ↓
            If Unsafe → 200 OK
                       {reply: "I can't help with that",
                        recommendations: [],
                        end_of_conversation: false}
            ↓ If Safe
        Retrieve Candidates
            ↓
            If Retrieval Error → 500 Internal Error
            ↓ If Success
        Generate LLM Response
            ↓
            If LLM Error → 504 Timeout / 500 Error
            ↓ If Success
        Validate Response
            ↓
            If Invalid → 500 Internal Error
                        {error: "Response validation failed"}
            ↓ If Valid
        Return 200 OK
        {reply: "...",
         recommendations: [...],
         end_of_conversation: bool}
```

---

These diagrams show how all pieces fit together. Reference when building each component!
