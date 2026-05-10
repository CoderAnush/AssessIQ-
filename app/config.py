"""
Configuration management for AssessIQ AI.
Loads environment variables and provides config objects.
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # LLM Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 15
    gemini_max_tokens: int = 1024
    gemini_temperature: float = 0.7
    gemini_top_p: float = 0.95

    # Paths - Data Pipeline Outputs
    catalog_path: str = "data/processed/catalog_processed.json"
    faiss_index_path: str = "data/processed/faiss_index.bin"
    faiss_metadata_path: str = "data/processed/faiss_metadata.json"
    bm25_index_path: str = "data/processed/bm25_index.pkl"
    embeddings_path: str = "data/processed/embeddings.npy"
    embeddings_ids_path: str = "data/processed/embeddings_ids.txt"
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # API Configuration
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    environment: str = "development"

    # Retrieval Parameters
    semantic_search_weight: float = 0.7
    bm25_search_weight: float = 0.3
    top_k_retrieval: int = 20
    max_recommendations: int = 10

    # Conversation Parameters
    max_conversation_turns: int = 8
    request_timeout_seconds: int = 30

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "logs/assessiq.log"

    # Monitoring
    sentry_dsn: Optional[str] = None
    enable_metrics: bool = True

    # Development Flags
    debug: bool = False
    enable_test_routes: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False


# Global config instance
settings = Settings()  # type: ignore


def validate_config() -> bool:
    """Validate critical configuration before startup."""

    errors = []
    warnings = []

    # Check API key
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        errors.append("GEMINI_API_KEY not configured")

    # Check Gemini model is set
    if not settings.gemini_model:
        errors.append("GEMINI_MODEL not configured")

    # Check timeout values are reasonable
    if settings.gemini_timeout_seconds < 5:
        warnings.append(f"GEMINI_TIMEOUT_SECONDS is very low ({settings.gemini_timeout_seconds}s)")

    if settings.gemini_timeout_seconds > 60:
        warnings.append(f"GEMINI_TIMEOUT_SECONDS is very high ({settings.gemini_timeout_seconds}s)")

    # Check temperature is in valid range
    if not (0 <= settings.gemini_temperature <= 2):
        errors.append(f"GEMINI_TEMPERATURE must be 0-2, got {settings.gemini_temperature}")

    # Check top_p is in valid range
    if not (0 <= settings.gemini_top_p <= 1):
        errors.append(f"GEMINI_TOP_P must be 0-1, got {settings.gemini_top_p}")

    # Check max tokens
    if settings.gemini_max_tokens < 100:
        warnings.append(f"GEMINI_MAX_TOKENS is very low ({settings.gemini_max_tokens})")

    if settings.gemini_max_tokens > 4096:
        warnings.append(f"GEMINI_MAX_TOKENS is very high ({settings.gemini_max_tokens}), may cause cost/latency issues")

    # Check paths exist
    catalog_path = Path(settings.catalog_path)
    if not catalog_path.exists():
        warnings.append(f"Catalog not found at {settings.catalog_path} - run pipeline first: python scripts/build_pipeline.py")

    faiss_path = Path(settings.faiss_index_path)
    if not faiss_path.exists():
        warnings.append(f"FAISS index not found at {settings.faiss_index_path} - run pipeline first")

    bm25_path = Path(settings.bm25_index_path)
    if not bm25_path.exists():
        warnings.append(f"BM25 index not found at {settings.bm25_index_path} - run pipeline first")

    # Check weights sum to 1.0
    weight_sum = settings.semantic_search_weight + settings.bm25_search_weight
    if not (0.99 <= weight_sum <= 1.01):
        errors.append(f"Retrieval weights must sum to 1.0, got {weight_sum}")

    if errors:
        raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"⚠ {warning}")

    return True
