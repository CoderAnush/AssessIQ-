"""
Complete end-to-end RAG pipeline orchestration.
Transforms raw SHL catalog into production-ready vector + keyword indexes.

Pipeline steps:
1. Load raw catalog data
2. Clean and normalize
3. Enrich metadata
4. Generate embeddings
5. Build FAISS vector index
6. Build BM25 keyword index
7. Validate and persist

This is the FOUNDATION of the retrieval system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    End-to-end RAG pipeline.
    Builds production-ready retrieval indexes.
    """

    def __init__(
        self,
        raw_catalog_path: str,
        output_dir: str = "data/processed",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        """
        Initialize pipeline.

        Args:
            raw_catalog_path: Path to raw catalog JSON
            output_dir: Directory for processed outputs
            embedding_model: Sentence-transformers model name
        """
        self.raw_catalog_path = raw_catalog_path
        self.output_dir = Path(output_dir)
        self.embedding_model = embedding_model

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup pipeline logging."""
        log_path = self.output_dir / "pipeline.log"

        handler = logging.FileHandler(log_path)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("=" * 80)
        logger.info("RAG PIPELINE STARTED")
        logger.info("=" * 80)

    def load_raw_catalog(self) -> List[Dict]:
        """Load raw catalog from JSON."""
        logger.info(f"Loading raw catalog from {self.raw_catalog_path}")

        try:
            with open(self.raw_catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both direct list and dict with 'assessments' key
            assessments = data if isinstance(data, list) else data.get("assessments", [])

            logger.info(f"Loaded {len(assessments)} assessments")
            return assessments

        except Exception as e:
            logger.error(f"Error loading catalog: {e}")
            raise

    def clean_catalog(self, assessments: List[Dict]) -> List[Dict]:
        """Step 1: Clean and normalize data."""
        logger.info("=" * 80)
        logger.info("STEP 1: CLEANING CATALOG")
        logger.info("=" * 80)

        from app.utils.data_cleaner import DataCleaner

        result = DataCleaner.clean_catalog(assessments)

        logger.info(f"Cleaning stats: {result['stats']}")

        if result["invalid"]:
            logger.warning(f"Invalid assessments: {result['invalid'][:5]}")

        return result["cleaned"]

    def enrich_catalog(self, assessments: List[Dict]) -> List[Dict]:
        """Step 2: Enrich metadata."""
        logger.info("=" * 80)
        logger.info("STEP 2: ENRICHING METADATA")
        logger.info("=" * 80)

        from app.utils.metadata_enricher import MetadataEnricher

        result = MetadataEnricher.enrich_catalog(assessments)

        logger.info(f"Enrichment stats: {result['stats']}")

        return result["enriched"]

    def validate_urls(self, assessments: List[Dict]) -> List[Dict]:
        """Step 3: Validate URLs."""
        logger.info("=" * 80)
        logger.info("STEP 3: VALIDATING URLs")
        logger.info("=" * 80)

        from app.utils.url_validator import URLValidator

        valid_assessments = []

        for assessment in assessments:
            url = assessment.get("url", "")
            is_valid, reason = URLValidator.is_valid_shl_url(url)

            if is_valid:
                assessment["url"] = URLValidator.normalize_url(url)
                assessment["assessment_id"] = URLValidator.extract_assessment_id(url)
                valid_assessments.append(assessment)
            else:
                logger.warning(
                    f"Invalid URL for {assessment.get('name')}: {reason} ({url})"
                )

        logger.info(
            f"URL validation: {len(valid_assessments)}/{len(assessments)} valid"
        )

        return valid_assessments

    def generate_embeddings(
        self, assessments: List[Dict]
    ) -> tuple[np.ndarray, List[str]]:
        """Step 4: Generate embeddings."""
        logger.info("=" * 80)
        logger.info("STEP 4: GENERATING EMBEDDINGS")
        logger.info("=" * 80)

        from scripts.build_embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(
            model_name=self.embedding_model, batch_size=32
        )

        embeddings, ids = generator.generate_embeddings(assessments)

        # Save
        embeddings_path = self.output_dir / "embeddings.npy"
        generator.save_embeddings(embeddings, ids, str(embeddings_path))

        logger.info(f"Embeddings saved to {embeddings_path}")
        logger.info(f"Embedding dimension: {embeddings.shape[1]}")

        return embeddings, ids

    def build_faiss_index(
        self, assessments: List[Dict], embeddings: np.ndarray
    ) -> None:
        """Step 5: Build FAISS vector index."""
        logger.info("=" * 80)
        logger.info("STEP 5: BUILDING FAISS INDEX")
        logger.info("=" * 80)

        from app.services.vector_store import VectorStore

        store = VectorStore(embedding_dim=embeddings.shape[1])
        store.create_index()
        store.add_embeddings(embeddings, assessments)

        # Save
        index_path = str(self.output_dir / "faiss_index.bin")
        metadata_path = str(self.output_dir / "faiss_metadata.json")

        store.save(index_path, metadata_path)

        logger.info(f"FAISS index saved to {index_path}")
        logger.info(f"Metadata saved to {metadata_path}")
        logger.info(f"Stats: {store.get_stats()}")

    def build_bm25_index(self, assessments: List[Dict]) -> None:
        """Step 6: Build BM25 keyword index."""
        logger.info("=" * 80)
        logger.info("STEP 6: BUILDING BM25 INDEX")
        logger.info("=" * 80)

        from app.services.bm25_retriever import BM25Retriever

        retriever = BM25Retriever(k1=1.5, b=0.75)
        retriever.build_index(assessments)

        # Save
        index_path = str(self.output_dir / "bm25_index.pkl")
        retriever.save(index_path)

        logger.info(f"BM25 index saved to {index_path}")
        logger.info(f"Stats: {retriever.get_stats()}")

    def save_processed_catalog(self, assessments: List[Dict]) -> None:
        """Save processed catalog as JSON."""
        logger.info("Saving processed catalog...")

        catalog_path = self.output_dir / "catalog_processed.json"

        # Final ID check and collision resolution
        import re
        import hashlib
        seen_ids = {}
        for i, ass in enumerate(assessments):
            # 1. Generate base ID
            if not ass.get("id"):
                id_name = ass.get("name", f"unnamed-{i}").lower()
                id_name = id_name.replace("c#", "c-sharp").replace("c++", "c-plus-plus")
                ass["id"] = re.sub(r'[^a-z0-9]+', '-', id_name).strip('-')
            
            # 2. Collision detection
            current_id = ass["id"]
            if current_id in seen_ids:
                # Collision! Append hash of URL
                url_hash = hashlib.md5(ass.get("url", "").encode()).hexdigest()[:4]
                ass["id"] = f"{current_id}-{url_hash}"
                logger.warning(f"ID Collision resolved: {current_id} -> {ass['id']}")
            
            seen_ids[ass["id"]] = i

            if ass.get("duration_minutes") is None:
                ass["duration_minutes"] = 30
                ass["duration_minutes"] = 30

        with open(catalog_path, "w") as f:
            json.dump(
                {
                    "assessments": assessments,
                    "count": len(assessments),
                    "version": "1.1.0-expanded"
                },
                f,
                indent=2,
            )

        logger.info(f"Processed catalog saved to {catalog_path}")

    def run(self) -> Dict:
        """
        Run complete pipeline with robust normalization.
        """

        try:
            # 1. Load
            assessments = self.load_raw_catalog()
            initial_count = len(assessments)
            
            # Robust normalization layer
            import re
            normalized = []
            for i, ass in enumerate(assessments):
                # Map keys from official catalog
                if "link" in ass and not ass.get("url"):
                    ass["url"] = ass["link"]
                
                # Normalize duration from string
                if ass.get("duration") and ass.get("duration_minutes") is None:
                    m = re.search(r"(\d+)", str(ass["duration"]))
                    if m:
                        ass["duration_minutes"] = int(m.group(1))
                    else:
                        ass["duration_minutes"] = 30
                
                if not ass.get("name") or not ass.get("url"):
                    logger.warning(f"Skipping assessment {i}: missing name or url ({ass.get('name')})")
                    continue
                
                # Repair missing ID
                if not ass.get("id"):
                    id_name = ass["name"].lower()
                    id_name = id_name.replace("c#", "c-sharp").replace("c++", "c-plus-plus")
                    ass["id"] = re.sub(r'[^a-z0-9]+', '-', id_name).strip('-')
                
                # Repair missing duration
                if ass.get("duration_minutes") is None:
                    ass["duration_minutes"] = 30
                
                normalized.append(ass)
            
            normalized_count = len(normalized)
            logger.info(f"Normalized {normalized_count}/{initial_count} assessments")

            # 2. Clean
            assessments = self.clean_catalog(normalized)

            # 3. Enrich
            assessments = self.enrich_catalog(assessments)

            # 4. Validate URLs
            assessments = self.validate_urls(assessments)

            # 5. Generate embeddings
            embeddings, ids = self.generate_embeddings(assessments)

            # 6. Build FAISS
            self.build_faiss_index(assessments, embeddings)

            # 7. Build BM25
            self.build_bm25_index(assessments)

            # 8. Save processed catalog
            self.save_processed_catalog(assessments)

            # Summary
            summary = {
                "status": "success",
                "input_count": initial_count,
                "normalized_count": normalized_count,
                "output_count": len(assessments),
                "skipped_count": initial_count - len(assessments),
                "embeddings_dim": embeddings.shape[1],
                "output_dir": str(self.output_dir),
                "files_created": [
                    "embeddings.npy",
                    "embeddings_ids.txt",
                    "faiss_index.bin",
                    "faiss_metadata.json",
                    "bm25_index.pkl",
                    "catalog_processed.json",
                    "pipeline.log",
                ],
            }

            logger.info("=" * 80)
            logger.info("RAG PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            print("\nPIPELINE VALIDATION REPORT:")
            print(f"- Total Scraped: {initial_count}")
            print(f"- Total Normalized: {normalized_count}")
            print(f"- Total Skipped: {initial_count - len(assessments)}")
            print(f"- Final Catalog Count: {len(assessments)}")
            print("=" * 80)

            return summary

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    import sys

    # Configure paths
    raw_catalog = "data/raw/catalog.json"
    output_dir = "data/processed"

    # Run pipeline
    pipeline = RAGPipeline(raw_catalog, output_dir)

    try:
        result = pipeline.run()
        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"\nPIPELINE FAILED: {e}")
        sys.exit(1)
