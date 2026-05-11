"""
Embedding Service - Handles semantic embeddings for assessments and queries.
Uses sentence-transformers/all-MiniLM-L6-v2 for ultra-fast, local vector retrieval.
"""

import os
import json
import logging
import numpy as np
from typing import List, Dict, Optional, Any
from pathlib import Path
from sentence_transformers import SentenceTransformer, util
import torch

from app.logger_config.logger import get_logger

logger = get_logger("embedding_service")

class EmbeddingService:
    """Service for generating and managing embeddings using SentenceTransformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding service."""
        self.model_name = model_name
        self.model = None
        self._embedding_cache = {}
        self.cache_dir = Path("data/cache/embeddings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model lazily
        self._load_model()

    def _load_model(self):
        """Load the SentenceTransformer model."""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            if torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info("Using CUDA for embeddings")
            else:
                logger.info("Using CPU for embeddings")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            raise

    def get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a single text string."""
        if not text:
            return np.zeros(384)
            
        if text in self._embedding_cache:
            return self._embedding_cache[text]
            
        embedding = self.model.encode(text, convert_to_numpy=True)
        self._embedding_cache[text] = embedding
        return embedding

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of text strings."""
        if not texts:
            return np.array([])
            
        return self.model.encode(texts, convert_to_numpy=True)

    def calculate_similarity(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between query and documents."""
        # Ensure correct shapes
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        similarities = util.cos_sim(query_embedding, doc_embeddings)
        return similarities.flatten().cpu().numpy()

    def embed_assessment(self, assessment: Dict[str, Any]) -> np.ndarray:
        """Generate a composite embedding for an assessment."""
        # Combine key semantic fields for embedding
        name = assessment.get("name", "")
        description = assessment.get("description", "")
        skills = ", ".join(assessment.get("skills", []) or assessment.get("inferred_skills", []))
        tags = ", ".join(assessment.get("expanded_tags", []))
        categories = assessment.get("engineering_category", "")
        
        # Weighted combination for semantic indexing
        # Name is most important, then skills/tags, then description
        combined_text = f"{name}. {name}. {skills}. {tags}. {categories}. {description}"
        return self.get_embedding(combined_text)

    def embed_catalog(self, assessments: List[Dict[str, Any]], cache_key: str = "default") -> np.ndarray:
        """Generate and cache embeddings for an entire catalog."""
        cache_file = self.cache_dir / f"{cache_key}_embeddings.npy"
        
        if cache_file.exists():
            logger.info(f"Loading cached embeddings from {cache_file}")
            return np.load(cache_file)
            
        logger.info(f"Generating embeddings for {len(assessments)} assessments")
        embeddings = []
        for assessment in assessments:
            embeddings.append(self.embed_assessment(assessment))
            
        embeddings_array = np.array(embeddings)
        np.save(cache_file, embeddings_array)
        logger.info(f"Saved embeddings to {cache_file}")
        
        return embeddings_array

    def hybrid_score(
        self, 
        embedding_sim: float, 
        keyword_sim: float, 
        boost: float = 0.0,
        weights: Dict[str, float] = None
    ) -> float:
        """
        Calculate hybrid score based on semantic and keyword similarity.
        Weights: 0.55 embedding, 0.25 keyword, 0.20 boost.
        """
        if weights is None:
            weights = {
                "embedding": 0.55,
                "keyword": 0.25,
                "boost": 0.20
            }
            
        score = (
            weights["embedding"] * embedding_sim +
            weights["keyword"] * keyword_sim +
            weights["boost"] * boost
        )
        return float(score)
