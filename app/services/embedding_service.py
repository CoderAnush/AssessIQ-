"""
Real Embedding Service — sentence-transformers all-MiniLM-L6-v2.
Replaces the previous dummy that returned zero vectors.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from app.logger_config.logger import get_logger

logger = get_logger("embedding_service")


class EmbeddingService:
    """
    Sentence-transformer embedding service.
    Model: all-MiniLM-L6-v2 (384-dim, fast, strong on technical text).
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info("EmbeddingService: loaded model '%s'", self.model_name)
        except Exception as exc:
            logger.error("EmbeddingService: could not load model — %s", exc)
            self._model = None

    # ------------------------------------------------------------------
    # Assessment text construction
    # ------------------------------------------------------------------

    @staticmethod
    def build_assessment_text(assessment: Dict[str, Any]) -> str:
        """
        Construct a rich text representation of an assessment for embedding.
        Format: <name> | <skills> | <description> | <roles>
        This vocabulary alignment means query and document texts share terminology.
        """
        name = assessment.get("name", "")
        desc = assessment.get("description", "")
        skills = " ".join(assessment.get("skills", []))
        roles = " ".join(
            assessment.get("ideal_roles", [])
            or assessment.get("inferred_roles", [])
            or assessment.get("recommended_roles", [])
        )
        return f"{name} | {skills} | {desc} | {roles}"

    @staticmethod
    def build_query_text(context: Any, raw_query: str) -> str:
        """
        Construct the query text to embed, mirroring assessment text structure.
        Format: <normalized_role> | <tech_stack> | <raw_query>
        """
        role = getattr(context, "role", "") or ""
        tech_stack = getattr(context, "tech_stack", set()) or set()
        tech_str = " ".join(sorted(tech_stack))
        return f"{role} | {tech_str} | {raw_query}"

    # ------------------------------------------------------------------
    # Core embedding methods
    # ------------------------------------------------------------------

    def get_embedding(self, text: str) -> np.ndarray:
        """Embed a single string. Returns zeros if model unavailable."""
        if self._model is None:
            return np.zeros(384, dtype=np.float32)
        try:
            vec = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return vec.astype(np.float32)
        except Exception as exc:
            logger.error("EmbeddingService.get_embedding error: %s", exc)
            return np.zeros(384, dtype=np.float32)

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Embed a list of strings. Returns zero matrix if model unavailable."""
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        if self._model is None:
            return np.zeros((len(texts), 384), dtype=np.float32)
        try:
            vecs = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=64,
                show_progress_bar=False,
            )
            return vecs.astype(np.float32)
        except Exception as exc:
            logger.error("EmbeddingService.get_embeddings error: %s", exc)
            return np.zeros((len(texts), 384), dtype=np.float32)

    def embed_catalog(
        self, assessments: List[Dict[str, Any]], cache_key: str = "default"
    ) -> np.ndarray:
        """Embed all assessments using the rich text format."""
        texts = [self.build_assessment_text(a) for a in assessments]
        logger.info("EmbeddingService: embedding %d assessments", len(texts))
        return self.get_embeddings(texts)

    def embed_assessment(self, assessment: Dict[str, Any]) -> np.ndarray:
        return self.get_embedding(self.build_assessment_text(assessment))

    def calculate_similarity(
        self, query_embedding: np.ndarray, doc_embeddings: np.ndarray
    ) -> np.ndarray:
        """Cosine similarity. Embeddings are already L2-normalised."""
        if doc_embeddings.ndim == 1:
            return float(np.dot(query_embedding, doc_embeddings))
        return doc_embeddings @ query_embedding

    @property
    def is_available(self) -> bool:
        return self._model is not None
