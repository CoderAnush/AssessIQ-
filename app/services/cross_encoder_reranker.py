"""
Cross-Encoder Reranker for AssessIQ.

Uses ms-marco-MiniLM-L-6-v2 to score (query, assessment) pairs.
Falls back to RRF scores if the cross-encoder is unavailable.

This replaces the heuristic ranker_v2.py scoring logic for technology relevance.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.logger_config.logger import get_logger

logger = get_logger("cross_encoder_reranker")

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """
    Reranks retriever candidates using a cross-encoder model.

    The cross-encoder sees the full (query, document) pair and produces a
    relevance score without any technology-specific constants.
    """

    def __init__(self, model_name: str = _MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info("CrossEncoderReranker: loaded '%s'", self.model_name)
        except Exception as exc:
            logger.warning(
                "CrossEncoderReranker: could not load model (%s) — will fall back to retriever scores",
                exc,
            )
            self._model = None

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Score and rerank candidates.

        Args:
            query:      The user query string (natural language job description).
            candidates: Output of HybridRetriever — list of dicts with at least
                        'name', 'description', 'hybrid_score'.
            top_k:      Number of candidates to return after reranking.

        Returns:
            Reranked candidate list (top_k items), with 'rerank_score' added.
        """
        if not candidates:
            return []

        if self._model is None:
            # Fallback: return by hybrid_score
            sorted_by_rrf = sorted(
                candidates, key=lambda x: x.get("hybrid_score", 0.0), reverse=True
            )
            for c in sorted_by_rrf:
                c["rerank_score"] = c.get("hybrid_score", 0.0)
            return sorted_by_rrf[:top_k]

        # Build (query, document) pairs
        pairs = [
            (query, self._build_doc_text(c))
            for c in candidates
        ]

        try:
            scores = self._model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.error("CrossEncoderReranker.rerank error: %s", exc)
            for c in candidates:
                c["rerank_score"] = c.get("hybrid_score", 0.0)
            return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]

        # Attach scores and sort
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        logger.info(
            "CrossEncoderReranker: reranked %d → top %d (top score=%.4f)",
            len(candidates), top_k, reranked[0]["rerank_score"] if reranked else 0.0,
        )
        return reranked[:top_k]

    @staticmethod
    def _build_doc_text(candidate: Dict[str, Any]) -> str:
        """Construct the document string for the cross-encoder."""
        name = candidate.get("name", "")
        desc = candidate.get("description", "")
        # Truncate to avoid exceeding 512-token limit
        desc_truncated = desc[:400] if len(desc) > 400 else desc
        return f"{name}. {desc_truncated}"
