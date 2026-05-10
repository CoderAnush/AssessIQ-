"""
Pipeline testing and validation utilities.
Validates that the RAG pipeline produces high-quality indexes.
"""

import json
import logging
from typing import Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class PipelineValidator:
    """Validates pipeline outputs."""

    @staticmethod
    def validate_catalog(catalog_path: str) -> Dict:
        """
        Validate processed catalog.

        Checks:
        - All required fields present
        - No duplicate URLs
        - Valid test types
        - URLs are SHL domain only
        """

        logger.info(f"Validating catalog: {catalog_path}")

        with open(catalog_path, "r") as f:
            data = json.load(f)

        assessments = data.get("assessments", [])
        errors = []
        warnings = []

        seen_urls = set()
        seen_ids = set()

        for idx, assessment in enumerate(assessments):
            # Check required fields
            for field in ["name", "url", "description"]:
                if not assessment.get(field):
                    errors.append(
                        f"[{idx}] Missing field '{field}' for {assessment.get('name', 'Unknown')}"
                    )

            # Check URL
            url = assessment.get("url", "")
            if url:
                if url in seen_urls:
                    errors.append(f"[{idx}] Duplicate URL: {url}")
                else:
                    seen_urls.add(url)

                if "shl.com" not in url and "talentlens.com" not in url:
                    errors.append(
                        f"[{idx}] Non-SHL URL: {url} for {assessment.get('name')}"
                    )

            # Check ID
            assessment_id = assessment.get("id", assessment.get("name", "").lower())
            if assessment_id in seen_ids:
                warnings.append(f"[{idx}] Duplicate ID: {assessment_id}")
            seen_ids.add(assessment_id)

            # Check test type
            test_type = assessment.get("test_type", "")
            if test_type and test_type not in ["K", "A", "P"]:
                warnings.append(
                    f"[{idx}] Invalid test type '{test_type}' for {assessment.get('name')}"
                )

        return {
            "valid": len(errors) == 0,
            "total_assessments": len(assessments),
            "unique_urls": len(seen_urls),
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }

    @staticmethod
    def validate_embeddings(embeddings_path: str, ids_path: str) -> Dict:
        """
        Validate embeddings file.

        Checks:
        - File exists and is readable
        - Correct shape
        - ID mapping matches
        - No NaN or inf values
        """

        logger.info(f"Validating embeddings: {embeddings_path}")

        import numpy as np

        try:
            embeddings = np.load(embeddings_path)

            with open(ids_path, "r") as f:
                ids = [line.strip() for line in f]

            errors = []

            # Check shape
            if len(embeddings.shape) != 2:
                errors.append(
                    f"Invalid shape {embeddings.shape}, expected 2D array"
                )

            # Check ID count
            if len(ids) != len(embeddings):
                errors.append(
                    f"ID count ({len(ids)}) != embedding count ({len(embeddings)})"
                )

            # Check for NaN/inf
            if np.any(np.isnan(embeddings)):
                errors.append("Embeddings contain NaN values")

            if np.any(np.isinf(embeddings)):
                errors.append("Embeddings contain inf values")

            # Check normalization
            norms = np.linalg.norm(embeddings, axis=1)
            norm_mean = np.mean(norms)
            if not (0.9 < norm_mean < 1.1):
                logger.warning(
                    f"Embeddings may not be normalized (mean norm: {norm_mean:.2f})"
                )

            return {
                "valid": len(errors) == 0,
                "shape": embeddings.shape,
                "embedding_dim": embeddings.shape[1],
                "total_embeddings": len(embeddings),
                "id_count": len(ids),
                "norm_mean": float(np.mean(norms)),
                "errors": errors,
            }

        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    @staticmethod
    def validate_faiss_index(index_path: str, metadata_path: str) -> Dict:
        """Validate FAISS index."""

        logger.info(f"Validating FAISS index: {index_path}")

        try:
            import faiss

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            index = faiss.read_index(index_path)

            errors = []

            # Check vector count
            expected_count = metadata.get("total_vectors", 0)
            actual_count = index.ntotal

            if expected_count != actual_count:
                errors.append(
                    f"Vector count mismatch: expected {expected_count}, got {actual_count}"
                )

            # Check embedding dimension
            embedding_dim = metadata.get("embedding_dim", 0)
            if embedding_dim != index.d:
                errors.append(
                    f"Dimension mismatch: expected {embedding_dim}, got {index.d}"
                )

            return {
                "valid": len(errors) == 0,
                "total_vectors": index.ntotal,
                "embedding_dim": index.d,
                "index_type": str(type(index)),
                "errors": errors,
            }

        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    @staticmethod
    def validate_bm25_index(index_path: str) -> Dict:
        """Validate BM25 index."""

        logger.info(f"Validating BM25 index: {index_path}")

        try:
            import pickle

            with open(index_path, "rb") as f:
                data = pickle.load(f)

            errors = []

            # Check required fields
            for field in ["documents", "doc_to_assessment"]:
                if field not in data:
                    errors.append(f"Missing field: {field}")

            doc_count = len(data.get("documents", []))
            assessment_count = len(data.get("doc_to_assessment", {}))

            if doc_count != assessment_count:
                errors.append(
                    f"Document count ({doc_count}) != assessment count ({assessment_count})"
                )

            return {
                "valid": len(errors) == 0,
                "total_documents": doc_count,
                "total_assessments": assessment_count,
                "k1": data.get("k1"),
                "b": data.get("b"),
                "errors": errors,
            }

        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    @staticmethod
    def validate_all(output_dir: str) -> Dict:
        """
        Validate entire pipeline output.

        Checks all generated files.
        """

        output_path = Path(output_dir)

        logger.info("=" * 80)
        logger.info("VALIDATING PIPELINE OUTPUTS")
        logger.info("=" * 80)

        results = {
            "timestamp": None,
            "output_dir": output_dir,
            "validations": {},
            "overall_valid": True,
        }

        from datetime import datetime

        results["timestamp"] = datetime.now().isoformat()

        # Validate catalog
        catalog_file = output_path / "catalog_processed.json"
        if catalog_file.exists():
            results["validations"]["catalog"] = PipelineValidator.validate_catalog(
                str(catalog_file)
            )
        else:
            results["validations"]["catalog"] = {"valid": False, "error": "Not found"}

        # Validate embeddings
        embeddings_file = output_path / "embeddings.npy"
        ids_file = output_path / "embeddings_ids.txt"
        if embeddings_file.exists() and ids_file.exists():
            results["validations"]["embeddings"] = (
                PipelineValidator.validate_embeddings(
                    str(embeddings_file), str(ids_file)
                )
            )
        else:
            results["validations"]["embeddings"] = {"valid": False, "error": "Not found"}

        # Validate FAISS
        faiss_file = output_path / "faiss_index.bin"
        faiss_meta = output_path / "faiss_metadata.json"
        if faiss_file.exists() and faiss_meta.exists():
            results["validations"]["faiss"] = PipelineValidator.validate_faiss_index(
                str(faiss_file), str(faiss_meta)
            )
        else:
            results["validations"]["faiss"] = {"valid": False, "error": "Not found"}

        # Validate BM25
        bm25_file = output_path / "bm25_index.pkl"
        if bm25_file.exists():
            results["validations"]["bm25"] = PipelineValidator.validate_bm25_index(
                str(bm25_file)
            )
        else:
            results["validations"]["bm25"] = {"valid": False, "error": "Not found"}

        # Check overall validity
        results["overall_valid"] = all(
            v.get("valid", False) for v in results["validations"].values()
        )

        logger.info("=" * 80)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 80)

        # Print summary
        for component, validation in results["validations"].items():
            status = "✓" if validation.get("valid") else "✗"
            logger.info(f"{status} {component}: {validation}")

        return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    output_dir = "data/processed"

    result = PipelineValidator.validate_all(output_dir)

    print("\n" + json.dumps(result, indent=2))

    sys.exit(0 if result["overall_valid"] else 1)
