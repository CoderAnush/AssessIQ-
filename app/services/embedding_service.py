"""
Embedding Service - DUMMY LIGHTWEIGHT VERSION.
Removed sentence-transformers dependency for production stability.
Returns zero embeddings and zero similarity to avoid breaking ranker.
"""

import numpy as np
from typing import List, Dict, Optional, Any
from pathlib import Path

from app.logger_config.logger import get_logger

logger = get_logger("embedding_service")

class EmbeddingService:
    """Dummy service for managing embeddings without heavy dependencies."""

    def __init__(self, model_name: str = "none"):
        """Initialize the dummy service."""
        self.model_name = "none"
        logger.info("Using DUMMY LIGHTWEIGHT Embedding Service (No Transformers)")

    def get_embedding(self, text: str) -> np.ndarray:
        """Return a zero embedding."""
        return np.zeros(384)

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Return zero embeddings."""
        if not texts:
            return np.array([])
        return np.zeros((len(texts), 384))

    def calculate_similarity(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> float:
        """Return zero similarity."""
        return 0.0

    def embed_assessment(self, assessment: Dict[str, Any]) -> np.ndarray:
        """Return zero embedding."""
        return np.zeros(384)

    def embed_catalog(self, assessments: List[Dict[str, Any]], cache_key: str = "default") -> np.ndarray:
        """Return zero embeddings."""
        return np.zeros((len(assessments), 384))

    def hybrid_score(
        self, 
        embedding_sim: float, 
        keyword_sim: float, 
        boost: float = 0.0,
        weights: Dict[str, float] = None
    ) -> float:
        """Calculate hybrid score (ignoring embedding_sim)."""
        if weights is None:
            weights = {
                "embedding": 0.0,
                "keyword": 0.8,
                "boost": 0.2
            }
        score = (
            weights["keyword"] * keyword_sim +
            weights["boost"] * boost
        )
        return float(score)
