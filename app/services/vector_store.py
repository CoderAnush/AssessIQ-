"""
Vector store service - FAISS-based semantic search for assessments.
Stores embeddings locally and enables ultra-fast retrieval.
"""

import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class VectorStore:
    """
    FAISS-based vector store for semantic search.
    Stores embeddings locally for production grounding.
    """

    def __init__(self, embedding_dim: int = 384):
        """
        Initialize vector store.

        Args:
            embedding_dim: Dimension of embeddings (384 for all-MiniLM-L6-v2)
        """
        self.embedding_dim = embedding_dim
        self.index = None
        self.id_to_assessment = {}
        self.assessment_to_id = {}
        self.embeddings = None

    def create_index(self):
        """Create FAISS index."""
        try:
            import faiss

            # L2 distance (Euclidean) - good for normalized embeddings
            self.index = faiss.IndexFlatL2(self.embedding_dim)
            logger.info("Created FAISS IndexFlatL2")
        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu")
            raise

    def add_embeddings(
        self, embeddings: np.ndarray, assessments: List[Dict]
    ) -> None:
        """
        Add embeddings and assessment mappings to index.

        Args:
            embeddings: Shape (n_assessments, embedding_dim)
            assessments: List of assessment dicts with 'id' and 'name'
        """

        if embeddings.shape[0] != len(assessments):
            raise ValueError(
                f"Embeddings count ({embeddings.shape[0]}) != assessments count ({len(assessments)})"
            )

        if embeddings.shape[1] != self.embedding_dim:
            raise ValueError(
                f"Embedding dim ({embeddings.shape[1]}) != expected ({self.embedding_dim})"
            )

        # Normalize embeddings for L2 distance
        embeddings_normalized = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)

        # Add to index
        self.index.add(embeddings_normalized.astype(np.float32))

        # Store ID mappings
        for idx, assessment in enumerate(assessments):
            assessment_id = assessment.get("id") or assessment.get("name", "").lower()
            self.id_to_assessment[idx] = assessment
            self.assessment_to_id[assessment_id] = idx

        logger.info(
            f"Added {len(assessments)} embeddings to index. "
            f"Total: {self.index.ntotal}"
        )

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        threshold: float = 0.5,
    ) -> List[Dict]:
        """
        Search for similar assessments.

        Args:
            query_embedding: Single embedding vector (1, embedding_dim)
            k: Number of results
            threshold: Similarity threshold (0-1)

        Returns:
            List of {
                'id': assessment_id,
                'name': assessment_name,
                'similarity': similarity_score,
                'distance': l2_distance
            }
        """

        if self.index is None or self.index.ntotal == 0:
            logger.warning("Index is empty")
            return []

        # Normalize query
        query_normalized = query_embedding / (
            np.linalg.norm(query_embedding) + 1e-10
        )

        # Search
        distances, indices = self.index.search(
            query_normalized.astype(np.float32), min(k, self.index.ntotal)
        )

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # Invalid result
                continue

            # Convert L2 distance to similarity (0-1)
            similarity = 1.0 / (1.0 + dist)

            if similarity < threshold:
                continue

            assessment = self.id_to_assessment.get(idx)
            if not assessment:
                continue

            results.append(
                {
                    "id": assessment.get("id", ""),
                    "name": assessment.get("name", ""),
                    "url": assessment.get("url", ""),
                    "similarity": float(similarity),
                    "distance": float(dist),
                    "assessment": assessment,
                }
            )

        return results

    def search_batch(
        self, query_embeddings: np.ndarray, k: int = 10
    ) -> List[List[Dict]]:
        """
        Search multiple queries at once.

        Args:
            query_embeddings: Shape (n_queries, embedding_dim)
            k: Results per query

        Returns:
            List of result lists
        """

        if self.index is None:
            return [[] for _ in query_embeddings]

        # Normalize
        query_normalized = query_embeddings / (
            np.linalg.norm(query_embeddings, axis=1, keepdims=True) + 1e-10
        )

        distances, indices = self.index.search(query_normalized.astype(np.float32), k)

        results = []
        for query_distances, query_indices in zip(distances, indices):
            query_results = []
            for dist, idx in zip(query_distances, query_indices):
                if idx == -1:
                    continue

                similarity = 1.0 / (1.0 + dist)
                assessment = self.id_to_assessment.get(idx)

                if assessment:
                    query_results.append(
                        {
                            "name": assessment.get("name", ""),
                            "similarity": float(similarity),
                            "distance": float(dist),
                        }
                    )

            results.append(query_results)

        return results

    def save(self, index_path: str, metadata_path: str) -> None:
        """
        Save index and metadata to disk.

        Args:
            index_path: Path to save FAISS index
            metadata_path: Path to save ID mappings
        """

        try:
            import faiss

            # Create directories
            Path(index_path).parent.mkdir(parents=True, exist_ok=True)
            Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            faiss.write_index(self.index, index_path)
            logger.info(f"Saved FAISS index to {index_path}")

            # Save metadata
            metadata = {
                "id_to_assessment": {
                    str(k): v for k, v in self.id_to_assessment.items()
                },
                "assessment_to_id": {
                    str(k): int(v) for k, v in self.assessment_to_id.items()
                },
                "embedding_dim": self.embedding_dim,
                "total_vectors": self.index.ntotal,
            }

            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved metadata to {metadata_path}")

        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
            raise

    @staticmethod
    def load(index_path: str, metadata_path: str) -> "VectorStore":
        """
        Load index and metadata from disk.

        Args:
            index_path: Path to FAISS index
            metadata_path: Path to metadata

        Returns:
            Loaded VectorStore instance
        """

        try:
            import faiss

            # Load metadata
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Create store
            store = VectorStore(embedding_dim=metadata["embedding_dim"])

            # Load FAISS index
            store.index = faiss.read_index(index_path)
            logger.info(f"Loaded FAISS index with {store.index.ntotal} vectors")

            # Restore mappings
            store.id_to_assessment = {
                int(k): v for k, v in metadata["id_to_assessment"].items()
            }
            store.assessment_to_id = {
                k: int(v) for k, v in metadata["assessment_to_id"].items()
            }

            logger.info(
                f"Loaded vector store with {len(store.id_to_assessment)} assessments"
            )
            return store

        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get store statistics."""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "embedding_dim": self.embedding_dim,
            "assessments_mapped": len(self.id_to_assessment),
        }
