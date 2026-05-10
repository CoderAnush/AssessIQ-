"""
BM25 keyword search service for assessments.
Enables fast keyword-based retrieval grounded in catalog.
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path
import json
import pickle

logger = logging.getLogger(__name__)


class BM25Retriever:
    """
    BM25 keyword retriever for assessments.
    Fast, grounded keyword-based search.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 retriever.

        Args:
            k1: BM25 parameter (controls term saturation)
            b: BM25 parameter (controls length normalization)
        """
        try:
            from rank_bm25 import BM25Okapi
            self.BM25Okapi = BM25Okapi
        except ImportError:
            logger.error("rank_bm25 not installed. Install with: pip install rank_bm25")
            raise

        self.k1 = k1
        self.b = b
        self.bm25 = None
        self.documents = []
        self.doc_to_assessment = {}

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization for BM25.
        Lowercase, split by whitespace, remove common words.
        """
        if not text:
            return []

        text = text.lower()

        # Common stopwords
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
        }

        tokens = []
        for word in text.split():
            # Remove punctuation
            word = word.strip(".,!?;:()[]{}\"'")
            # Keep if not stopword and not too short
            if word and len(word) > 2 and word not in stopwords:
                tokens.append(word)

        return tokens

    def build_index(self, assessments: List[Dict]) -> None:
        """
        Build BM25 index from assessments.

        Args:
            assessments: List of assessment dicts
        """

        logger.info(f"Building BM25 index for {len(assessments)} assessments")

        documents = []
        self.doc_to_assessment = {}

        for idx, assessment in enumerate(assessments):
            # Combine all text fields
            text = " ".join(
                [
                    assessment.get("name", ""),
                    assessment.get("description", ""),
                    " ".join(assessment.get("skills", [])),
                    " ".join(assessment.get("inferred_roles", [])),
                ]
            )

            # Tokenize
            tokens = self._tokenize(text)
            documents.append(tokens)
            self.doc_to_assessment[idx] = assessment

            if (idx + 1) % 100 == 0:
                logger.debug(f"Indexed {idx + 1} assessments")

        # Build BM25
        self.documents = documents
        self.bm25 = self.BM25Okapi(documents, k1=self.k1, b=self.b)

        logger.info(f"BM25 index built with {len(documents)} documents")

    def search(self, query: str, k: int = 10) -> List[Dict]:
        """
        Search using BM25.

        Args:
            query: Search query string
            k: Number of results

        Returns:
            List of {
                'name': assessment_name,
                'score': bm25_score,
                'assessment': full_assessment
            }
        """

        if self.bm25 is None or len(self.documents) == 0:
            logger.warning("BM25 index is empty")
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)

        if not query_tokens:
            logger.warning(f"Query produced no tokens: {query}")
            return []

        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)

        # Get top k indices
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include positive scores
                assessment = self.doc_to_assessment.get(idx)
                if assessment:
                    results.append(
                        {
                            "name": assessment.get("name", ""),
                            "url": assessment.get("url", ""),
                            "score": float(scores[idx]),
                            "assessment": assessment,
                        }
                    )

        return results

    def search_batch(self, queries: List[str], k: int = 10) -> List[List[Dict]]:
        """
        Search multiple queries at once.

        Args:
            queries: List of query strings
            k: Results per query

        Returns:
            List of result lists
        """

        return [self.search(q, k) for q in queries]

    def save(self, index_path: str) -> None:
        """
        Save BM25 index to disk.

        Args:
            index_path: Path to save index
        """

        try:
            Path(index_path).parent.mkdir(parents=True, exist_ok=True)

            with open(index_path, "wb") as f:
                pickle.dump(
                    {
                        "documents": self.documents,
                        "doc_to_assessment": self.doc_to_assessment,
                        "k1": self.k1,
                        "b": self.b,
                    },
                    f,
                )

            logger.info(f"Saved BM25 index to {index_path}")

        except Exception as e:
            logger.error(f"Error saving BM25 index: {e}")
            raise

    @staticmethod
    def load(index_path: str) -> "BM25Retriever":
        """
        Load BM25 index from disk.

        Args:
            index_path: Path to saved index

        Returns:
            Loaded BM25Retriever instance
        """

        try:
            with open(index_path, "rb") as f:
                data = pickle.load(f)

            retriever = BM25Retriever(k1=data["k1"], b=data["b"])
            retriever.documents = data["documents"]
            retriever.doc_to_assessment = data["doc_to_assessment"]

            # Rebuild BM25
            retriever.bm25 = retriever.BM25Okapi(
                retriever.documents, k1=retriever.k1, b=retriever.b
            )

            logger.info(
                f"Loaded BM25 index with {len(retriever.documents)} documents"
            )
            return retriever

        except Exception as e:
            logger.error(f"Error loading BM25 index: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "total_documents": len(self.documents),
            "k1": self.k1,
            "b": self.b,
            "index_ready": self.bm25 is not None,
        }
