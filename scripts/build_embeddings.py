"""
Embedding generation pipeline for assessments.
Uses sentence-transformers to generate high-quality semantic embeddings.
Batched processing for efficiency.
"""

import numpy as np
import logging
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings for assessments using sentence-transformers.
    Optimized for batch processing and memory efficiency.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        max_length: int = 512,
    ):
        """
        Initialize embedding generator.

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
            batch_size: Batch size for processing
            max_length: Max token length per input
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.model = None
        self.embedding_dim = None

    def load_model(self) -> None:
        """Load sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)

            # Test embedding to get dimension
            test_embedding = self.model.encode("test")
            self.embedding_dim = len(test_embedding)

            logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")

        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise

    def _prepare_text(self, assessment: Dict) -> str:
        """
        Prepare assessment text for embedding.

        Combines name, description, and metadata into a single text.
        """

        parts = [
            assessment.get("name", ""),
            assessment.get("description", ""),
        ]

        # Add skills if available
        skills = assessment.get("skills", [])
        if skills:
            parts.append("Skills: " + ", ".join(skills))

        # Add inferred skills if available
        inferred = assessment.get("inferred_skills", {})
        if inferred:
            skill_strs = [f"{k}: {', '.join(v)}" for k, v in inferred.items()]
            parts.append("Measured: " + "; ".join(skill_strs))

        # Add roles if available
        roles = assessment.get("inferred_roles", [])
        if roles:
            parts.append("For roles: " + ", ".join(roles))

        text = "\n".join(filter(None, parts))

        # Truncate if too long
        if len(text) > 1000:
            text = text[:1000]

        return text

    def generate_embeddings(
        self, assessments: List[Dict]
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Generate embeddings for multiple assessments.

        Args:
            assessments: List of assessment dicts

        Returns:
            (embeddings_array, assessment_ids)
        """

        if self.model is None:
            self.load_model()

        logger.info(f"Generating embeddings for {len(assessments)} assessments")

        texts = [self._prepare_text(a) for a in assessments]
        ids = [a.get("id") or a.get("name", "").lower() for a in assessments]

        embeddings_list = []
        failed_indices = []

        # Process in batches
        for batch_start in range(0, len(texts), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]

            try:
                batch_embeddings = self.model.encode(
                    batch_texts,
                    batch_size=self.batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )

                embeddings_list.append(batch_embeddings)

                if (batch_end) % (self.batch_size * 10) == 0:
                    logger.info(f"Processed {batch_end}/{len(texts)} assessments")

            except Exception as e:
                logger.error(f"Error embedding batch {batch_start}-{batch_end}: {e}")
                # Add zero embeddings for failed items
                batch_embeddings = np.zeros(
                    (batch_end - batch_start, self.embedding_dim)
                )
                embeddings_list.append(batch_embeddings)
                failed_indices.extend(range(batch_start, batch_end))

        # Concatenate all batches
        embeddings = np.vstack(embeddings_list)

        if failed_indices:
            logger.warning(f"Failed to embed {len(failed_indices)} assessments")

        logger.info(
            f"Generated {len(embeddings)} embeddings "
            f"with shape {embeddings.shape}"
        )

        return embeddings, ids

    def save_embeddings(
        self, embeddings: np.ndarray, assessment_ids: List[str], save_path: str
    ) -> None:
        """
        Save embeddings to disk as numpy file.

        Args:
            embeddings: Embedding array (n_assessments, embedding_dim)
            assessment_ids: Assessment IDs corresponding to rows
            save_path: Path to save embeddings file
        """

        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)

            # Save embeddings
            np.save(save_path, embeddings)
            logger.info(f"Saved {len(embeddings)} embeddings to {save_path}")

            # Save ID mapping
            id_map_path = str(save_path).replace(".npy", "_ids.txt")
            with open(id_map_path, "w") as f:
                for aid in assessment_ids:
                    f.write(f"{aid}\n")

            logger.info(f"Saved ID mapping to {id_map_path}")

        except Exception as e:
            logger.error(f"Error saving embeddings: {e}")
            raise

    @staticmethod
    def load_embeddings(save_path: str) -> Tuple[np.ndarray, List[str]]:
        """
        Load embeddings from disk.

        Args:
            save_path: Path to saved embeddings file

        Returns:
            (embeddings_array, assessment_ids)
        """

        try:
            embeddings = np.load(save_path)
            logger.info(f"Loaded {len(embeddings)} embeddings from {save_path}")

            # Load ID mapping
            id_map_path = str(save_path).replace(".npy", "_ids.txt")
            with open(id_map_path, "r") as f:
                assessment_ids = [line.strip() for line in f]

            if len(assessment_ids) != len(embeddings):
                logger.warning(
                    f"ID count ({len(assessment_ids)}) != embeddings count ({len(embeddings)})"
                )

            return embeddings, assessment_ids

        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            raise

    def get_embedding_dim(self) -> int:
        """Get embedding dimension."""
        if self.embedding_dim is None:
            self.load_model()
        return self.embedding_dim
