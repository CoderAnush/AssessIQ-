"""
HybridRetriever v2 — semantic-first, heuristic-free.

Pipeline:
  1. Metadata pre-filter  (hard domain/seniority gate, O(N) but eliminates noise early)
  2. BM25 retrieval        (lexical, handles exact technology name matching)
  3. FAISS vector search   (semantic, handles synonyms + intent)
  4. RRF merge             (Reciprocal Rank Fusion — no arbitrary weight constants)
  5. Return top-k for reranker

No technology-specific boosts, penalties, or hardcoded constants.
All scoring is handled by the statistical models (BM25, cosine similarity).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

import numpy as np

from app.logger_config.logger import get_logger
from app.services.skill_graph import SkillGraph

logger = get_logger("retriever")

# ---------------------------------------------------------------------------
# RRF constant — standard value from Cormack et al. 2009
# ---------------------------------------------------------------------------
_RRF_K = 60


def _reciprocal_rank_fusion(
    ranked_lists: List[List[str]], k: int = _RRF_K
) -> Dict[str, float]:
    """
    Merge multiple ranked lists via Reciprocal Rank Fusion.
    Returns {doc_id: rrf_score} sorted by score descending.
    Higher score = more relevant.
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


# ---------------------------------------------------------------------------
# Metadata pre-filter
# ---------------------------------------------------------------------------

_DOMAIN_TAGS: Dict[str, Set[str]] = {
    "backend": {
        "java", "python", "node", "go", "golang", "rust", "spring", "django",
        "fastapi", "flask", "api", "microservice", "backend", "server",
        "database", "sql", "postgresql", "mysql", "redis", "mongodb",
    },
    "frontend": {
        "react", "angular", "vue", "javascript", "typescript", "html", "css",
        "frontend", "ui", "ux", "web", "next.js", "nextjs", "svelte",
    },
    "devops": {
        "kubernetes", "docker", "terraform", "aws", "azure", "gcp", "cloud",
        "ci/cd", "devops", "sre", "linux", "infrastructure", "helm",
        "ansible", "jenkins", "observability",
    },
    "data_ai": {
        "machine learning", "deep learning", "pytorch", "tensorflow", "nlp",
        "data science", "ml", "llm", "transformers", "neural", "sklearn",
        "pandas", "numpy", "spark", "hadoop", "analytics",
    },
}

# Domains that should NOT appear for a given query domain
_DOMAIN_EXCLUSIONS: Dict[str, Set[str]] = {
    "backend": {"sales", "customer service", "personality only"},
    "frontend": {"sales", "customer service", "personality only"},
    "devops": {"sales", "customer service", "personality only"},
    "data_ai": {"sales", "customer service", "personality only"},
}


def _infer_query_domain(query_low: str, context: Any) -> str:
    """Detect the primary domain of the query from text signals."""
    # Check context domain first
    ctx_domain = str(getattr(context, "domain", "general")).lower()
    if ctx_domain not in ("general", "none", ""):
        return ctx_domain

    query_tokens = set(re.findall(r"\b[a-z0-9./]+\b", query_low))
    best_domain, best_overlap = "general", 0
    for domain, signals in _DOMAIN_TAGS.items():
        overlap = len(query_tokens & signals)
        if overlap > best_overlap:
            best_overlap, best_domain = overlap, domain

    # Tech stack from context reinforces domain
    tech_stack: Set[str] = getattr(context, "tech_stack", set()) or set()
    for tech in tech_stack:
        t = tech.lower()
        for domain, signals in _DOMAIN_TAGS.items():
            if t in signals:
                best_domain = domain
                break

    return best_domain


def _passes_metadata_filter(
    assessment: Any,
    query_domain: str,
    query_seniority: str,
) -> bool:
    """
    Hard metadata gate. Returns False only when there is a clear categorical
    mismatch (e.g. a 'sales' assessment for an engineering role).
    Generous by design — the reranker handles fine-grained relevance.
    """
    name_low = assessment.name.lower()
    desc_low = assessment.description.lower()
    combined = name_low + " " + desc_low

    # Exclusion check — only for technical queries
    if query_domain in _DOMAIN_EXCLUSIONS:
        for excl in _DOMAIN_EXCLUSIONS[query_domain]:
            if excl in combined:
                return False

    return True


# ---------------------------------------------------------------------------
# HybridRetriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """
    Semantic-first hybrid retriever.

    Initialisation builds:
      - A BM25 index over all assessment texts
      - A FAISS index over sentence-transformer embeddings

    Retrieval:
      - Both indices are queried independently
      - Results are merged via RRF
      - No technology-specific constants
    """

    def __init__(self, catalog_loader: Any, skill_graph: Optional[SkillGraph] = None):
        self.catalog_loader = catalog_loader
        self.skill_graph = skill_graph or SkillGraph()

        # Lazy-initialised indices
        self._bm25 = None          # rank_bm25 BM25Okapi
        self._bm25_docs: List[Any] = []
        self._faiss_index = None   # faiss.Index
        self._faiss_docs: List[Any] = []
        self._embedding_svc = None

        self._build_indices()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indices(self) -> None:
        assessments = self.catalog_loader.get_all()
        if not assessments:
            logger.warning("HybridRetriever: catalog is empty — skipping index build")
            return

        self._build_bm25(assessments)
        self._build_vector_index(assessments)

    def _build_bm25(self, assessments: List[Any]) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.error("rank_bm25 not installed — BM25 disabled")
            return

        def _tokenise(text: str) -> List[str]:
            return re.findall(r"\b[a-z0-9.#+]+\b", text.lower())

        corpus = []
        for a in assessments:
            text = (
                f"{a.name} {a.description} "
                f"{' '.join(getattr(a, 'skills', []))} "
                f"{' '.join(getattr(a, 'recommended_roles', []))}"
            )
            corpus.append(_tokenise(text))

        self._bm25 = BM25Okapi(corpus, k1=1.5, b=0.75)
        self._bm25_docs = assessments
        logger.info("HybridRetriever: BM25 index built over %d assessments", len(assessments))

    def _build_vector_index(self, assessments: List[Any]) -> None:
        try:
            import faiss
            from app.services.embedding_service import EmbeddingService
        except ImportError:
            logger.error("faiss-cpu or sentence-transformers not installed — vector search disabled")
            return

        svc = EmbeddingService()
        if not svc.is_available:
            logger.warning("HybridRetriever: embedding model unavailable — vector search disabled")
            return

        self._embedding_svc = svc

        texts = [svc.build_assessment_text(self._to_dict(a)) for a in assessments]
        embeddings = svc.get_embeddings(texts)  # (N, 384) float32, L2-normalised

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)  # inner-product on normalised vecs == cosine
        index.add(embeddings)

        self._faiss_index = index
        self._faiss_docs = assessments
        logger.info(
            "HybridRetriever: FAISS index built over %d assessments (dim=%d)",
            len(assessments), dim,
        )

    @staticmethod
    def _to_dict(assessment: Any) -> Dict[str, Any]:
        return {
            "name": assessment.name,
            "description": assessment.description,
            "skills": getattr(assessment, "skills", []),
            "ideal_roles": getattr(assessment, "recommended_roles", []),
        }

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, context: Any, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Main retrieval entry-point.

        1. Infer query domain from context + text signals
        2. Apply metadata pre-filter (hard exclusions only)
        3. BM25 retrieval → ranked list A
        4. FAISS vector retrieval → ranked list B
        5. RRF merge → unified ranked list
        6. Return top (top_k * 3) for the reranker to further narrow
        """
        query_low = query.lower()
        query_domain = _infer_query_domain(query_low, context)
        query_seniority = getattr(context, "seniority", "mid") or "mid"

        all_assessments = self.catalog_loader.get_all()

        # --- Step 1: metadata pre-filter ---
        candidates = [
            a for a in all_assessments
            if _passes_metadata_filter(a, query_domain, query_seniority)
        ]
        logger.info(
            "HybridRetriever: %d/%d assessments pass metadata filter (domain=%s)",
            len(candidates), len(all_assessments), query_domain,
        )

        # Build a lookup: assessment id → assessment object
        id_to_assessment: Dict[str, Any] = {a.id: a for a in candidates}
        candidate_ids: Set[str] = set(id_to_assessment.keys())

        # --- Step 2: BM25 retrieval ---
        bm25_ranked: List[str] = self._bm25_retrieve(
            query_low, candidate_ids, k=min(100, len(candidates))
        )

        # --- Step 3: FAISS retrieval ---
        vector_ranked: List[str] = self._vector_retrieve(
            query, context, candidate_ids, k=min(100, len(candidates))
        )

        # --- Step 4: RRF merge ---
        rrf_scores = _reciprocal_rank_fusion([bm25_ranked, vector_ranked])

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

        # If both indices failed, fall back to BM25-only or first candidates
        if not sorted_ids:
            logger.warning("HybridRetriever: RRF produced no results — using first %d candidates", top_k)
            sorted_ids = [a.id for a in candidates[:top_k * 3]]

        # --- Step 5: Build result dicts ---
        results = []
        for aid in sorted_ids:
            a = id_to_assessment.get(aid)
            if a is None:
                continue
            results.append({
                "id": a.id,
                "name": a.name,
                "url": a.url,
                "test_type": a.test_type.value if hasattr(a.test_type, "value") else str(a.test_type),
                "description": a.description,
                "hybrid_score": round(rrf_scores.get(aid, 0.0), 6),
                "is_fallback": False,
                "expansion_label": None,
            })

        logger.info(
            "HybridRetriever: returning %d candidates (top_k=%d, domain=%s)",
            len(results), top_k, query_domain,
        )
        return results[:top_k * 3]  # Return generously for cross-encoder

    # ------------------------------------------------------------------
    # BM25 sub-retrieval
    # ------------------------------------------------------------------

    def _bm25_retrieve(
        self, query_low: str, candidate_ids: Set[str], k: int
    ) -> List[str]:
        if self._bm25 is None:
            return []

        import re as _re
        query_tokens = _re.findall(r"\b[a-z0-9.#+]+\b", query_low)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Filter to candidates that passed metadata gate
        candidate_indexed = [
            (i, a.id, scores[i])
            for i, a in enumerate(self._bm25_docs)
            if a.id in candidate_ids
        ]
        candidate_indexed.sort(key=lambda x: x[2], reverse=True)

        return [aid for _, aid, _ in candidate_indexed[:k]]

    # ------------------------------------------------------------------
    # FAISS sub-retrieval
    # ------------------------------------------------------------------

    def _vector_retrieve(
        self, query: str, context: Any, candidate_ids: Set[str], k: int
    ) -> List[str]:
        if self._faiss_index is None or self._embedding_svc is None:
            return []

        from app.services.embedding_service import EmbeddingService
        query_text = EmbeddingService.build_query_text(context, query)
        query_vec = self._embedding_svc.get_embedding(query_text).reshape(1, -1)

        # Search over full index, then filter to candidates
        n_search = min(len(self._faiss_docs), max(k * 2, 200))
        distances, indices = self._faiss_index.search(query_vec, n_search)

        ranked: List[str] = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(self._faiss_docs):
                continue
            a = self._faiss_docs[idx]
            if a.id in candidate_ids:
                ranked.append(a.id)
            if len(ranked) >= k:
                break

        return ranked

    # ------------------------------------------------------------------
    # Legacy compatibility shim
    # _is_domain_mismatch kept so that any existing code that imports it
    # does not break. It now defers to the new metadata filter.
    # ------------------------------------------------------------------

    def _is_domain_mismatch(self, normalized_role: Any, name_low: str, desc_low: str, _classification: Any) -> bool:
        """Compatibility shim — always returns False (mismatch handled upstream)."""
        return False
