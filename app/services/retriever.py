"""
Hybrid retrieval engine - combines semantic + BM25 + metadata filtering.
Returns relevant assessments grounded in catalog.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from rank_bm25 import BM25Okapi
import faiss
from app.models.assessment import AssessmentWithMetadata
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.logging.logger import get_logger

logger = get_logger("retriever")


class HybridRetriever:
    """
    Advanced hybrid retrieval combining:
    - Semantic search (FAISS vector similarity)
    - BM25 keyword search
    - Metadata filtering
    - Score fusion
    """

    def __init__(
        self,
        catalog_loader: CatalogLoader,
        embeddings_model=None,
        faiss_index=None,
        semantic_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ):
        """
        Initialize retriever.

        Args:
            catalog_loader: CatalogLoader instance
            embeddings_model: sentence-transformers model
            faiss_index: Pre-loaded FAISS index
            semantic_weight: Weight for semantic search
            bm25_weight: Weight for BM25 search
        """
        self.catalog_loader = catalog_loader
        self.embeddings_model = embeddings_model
        self.faiss_index = faiss_index
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight

        # Build BM25 index from catalog
        self._build_bm25_index()

    def _build_bm25_index(self) -> None:
        """Build BM25 index from catalog."""
        corpus = []
        for assessment in self.catalog_loader.get_all():
            # Combine text fields for BM25
            text = f"{assessment.name} {assessment.description} {' '.join(assessment.skills)}"
            corpus.append(text.lower().split())

        self.bm25 = BM25Okapi(corpus)
        logger.info(f"Built BM25 index for {len(corpus)} assessments")

    def retrieve(
        self,
        query: str,
        context: HiringContext,
        top_k: int = 10,
    ) -> List[Dict]:
        """
        Retrieve relevant assessments using hybrid approach.

        Args:
            query: User query string
            context: Extracted hiring context
            top_k: Number of results to return

        Returns:
            List of assessments with scores
        """

        # 1. Semantic search
        semantic_results = self._semantic_search(query, top_k=20)
        logger.debug(f"Semantic search returned {len(semantic_results)} results")

        # 2. BM25 search
        bm25_results = self._bm25_search(query, top_k=20)
        logger.debug(f"BM25 search returned {len(bm25_results)} results")

        # 3. Metadata filtering
        all_assessments = self.catalog_loader.get_all()
        filtered = self._apply_metadata_filters(all_assessments, context)
        logger.debug(f"Metadata filtering kept {len(filtered)} assessments")

        # 4. Hybrid fusion
        fused_results = self._fuse_results(
            semantic_results, bm25_results, filtered, context
        )

        # 5. Final ranking and truncation
        final_results = sorted(
            fused_results, key=lambda x: x["hybrid_score"], reverse=True
        )[:top_k]

        logger.info(f"Retrieved {len(final_results)} assessments")
        return final_results

    def _semantic_search(self, query: str, top_k: int = 20) -> List[Dict]:
        """
        Semantic search using FAISS.

        Returns list of {id, semantic_score}
        """

        if not self.embeddings_model or not self.faiss_index:
            logger.warning("Embeddings model or FAISS index not available")
            return []

        try:
            # Encode query
            query_embedding = self.embeddings_model.encode(query, convert_to_numpy=True)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            # Search FAISS index
            distances, indices = self.faiss_index.search(query_embedding, k=min(top_k, self.faiss_index.ntotal))

            # Convert distances to similarity scores (0-1)
            # Using 1 / (1 + distance) formula
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx >= 0:  # Valid result
                    assessment = self.catalog_loader.get_all()[idx]
                    # Convert L2 distance to similarity
                    similarity = 1.0 / (1.0 + float(distance))
                    results.append(
                        {
                            "id": assessment.id,
                            "semantic_score": float(similarity),
                        }
                    )

            return results
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _bm25_search(self, query: str, top_k: int = 20) -> List[Dict]:
        """
        BM25 keyword search.

        Returns list of {id, bm25_score}
        """

        try:
            # Tokenize query
            tokens = query.lower().split()

            # Score all documents
            scores = self.bm25.get_scores(tokens)

            # Get top-k
            top_indices = np.argsort(scores)[::-1][:top_k]

            results = []
            assessments = self.catalog_loader.get_all()
            for idx in top_indices:
                if scores[idx] > 0:  # Only include if there's a match
                    assessment = assessments[idx]
                    # Normalize BM25 score to 0-1 (rough approximation)
                    normalized_score = min(float(scores[idx]) / 10.0, 1.0)
                    results.append(
                        {
                            "id": assessment.id,
                            "bm25_score": normalized_score,
                        }
                    )

            return results
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def _apply_metadata_filters(
        self, assessments: List[AssessmentWithMetadata], context: HiringContext
    ) -> List[AssessmentWithMetadata]:
        """
        Filter assessments by metadata (role, seniority, skills, etc.).

        Returns assessments that match context.
        """

        # For small catalogs, we want high recall. 
        # Ranking will handle the precise relevance.
        return assessments

    def _fuse_results(
        self,
        semantic_results: List[Dict],
        bm25_results: List[Dict],
        filtered_assessments: List[AssessmentWithMetadata],
        context: HiringContext,
    ) -> List[Dict]:
        """
        Fuse semantic + BM25 + metadata results.

        Returns combined scored results.
        """

        # Create ID → score mappings
        semantic_scores = {r["id"]: r["semantic_score"] for r in semantic_results}
        bm25_scores = {r["id"]: r["bm25_score"] for r in bm25_results}
        filtered_ids = {a.id for a in filtered_assessments}

        # Build fused results
        fused = []

        # Only include assessments that passed metadata filters
        for assessment in filtered_assessments:
            # Get scores (default 0 if not found)
            semantic_score = semantic_scores.get(assessment.id, 0.0)
            bm25_score = bm25_scores.get(assessment.id, 0.0)

            # Hybrid score: weighted average
            hybrid_score = (self.semantic_weight * semantic_score +
                           self.bm25_weight * bm25_score)

            # Add bonus for explicit context matches
            if assessment.communication_focus and context.soft_skills and "communication" in context.soft_skills:
                hybrid_score += 0.1

            if assessment.leadership_focus and context.leadership_needs:
                hybrid_score += 0.1

            # Skill overlap bonus
            if context.technical_skills:
                skill_overlap = sum(
                    1
                    for skill in context.technical_skills
                    if any(s.lower() in skill.lower() or skill.lower() in s.lower()
                           for s in assessment.skills)
                )
                if skill_overlap > 0:
                    hybrid_score += 0.05 * skill_overlap

            fused.append(
                {
                    "id": assessment.id,
                    "name": assessment.name,
                    "url": assessment.url,
                    "test_type": assessment.test_type.value,
                    "description": assessment.description,
                    "semantic_score": semantic_score,
                    "bm25_score": bm25_score,
                    "hybrid_score": min(hybrid_score, 1.0),  # Cap at 1.0
                }
            )

        return fused

    def get_assessment_by_name(self, name: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by name for comparisons."""
        return self.catalog_loader.get_by_name(name)

    def get_assessment_by_id(self, assessment_id: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by ID."""
        return self.catalog_loader.get_by_id(assessment_id)
