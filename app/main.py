"""
FastAPI application entry point.
Initializes app, loads data, and mounts routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import psutil
import time
import os

from app.config import settings, validate_config
from app.logging.logger import setup_logging
from app.models.response import HealthResponse
from app.routes import chat

# Setup logging first
logger = setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""

    # STARTUP
    logger.info("Starting AssessIQ AI...")
    print("="*60)
    print("BACKEND STARTUP INITIATED")
    print(f"Memory Usage: {psutil.virtual_memory()}")
    print("="*60)
    
    start_time = time.time()
    
    try:
        validate_config()
        logger.info("Configuration validated")

        # 1. Load Catalog
        print("STARTUP: Loading Catalog...")
        from app.services.catalog_loader import CatalogLoader
        catalog_path = getattr(settings, "catalog_path", "data/processed/catalog_processed.json")
        app.state.catalog_loader = CatalogLoader(catalog_path)
        print(f"STARTUP: Catalog loaded in {time.time() - start_time:.2f}s")

        # 2. Initialize LLM
        print("STARTUP: Initializing LLM Service...")
        from app.services.llm_service import LLMService
        app.state.llm_service = LLMService()
        print(f"STARTUP: LLM Service ready in {time.time() - start_time:.2f}s")

        # 3. Initialize Retriever (Lightweight version already in retriever.py)
        print("STARTUP: Initializing LIGHTWEIGHT Retriever...")
        from app.services.retriever import HybridRetriever
        app.state.retriever = HybridRetriever(app.state.catalog_loader)
        print(f"STARTUP: Retriever ready in {time.time() - start_time:.2f}s")

        # 4. Initialize Ranker
        print("STARTUP: Initializing Ranker...")
        from app.services.ranker import RecommendationRanker
        app.state.ranker = RecommendationRanker()

        # 5. Initialize Decision Engine
        print("STARTUP: Initializing Decision Engine...")
        from app.agents.decision_engine import DecisionEngine
        app.state.decision_engine = DecisionEngine()

        # 6. Initialize Hallucination Checker
        print("STARTUP: Initializing Hallucination Checker...")
        from app.utils.hallucination_checker import HallucinationChecker
        app.state.hallucination_checker = HallucinationChecker(app.state.catalog_loader)

        print("="*60)
        print(f"BACKEND STARTUP COMPLETE in {time.time() - start_time:.2f}s")
        print(f"Final Memory Usage: {psutil.virtual_memory()}")
        print("="*60)
        
        logger.info("AssessIQ AI startup complete")
    except Exception as e:
        print(f"CRITICAL STARTUP FAILURE: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # SHUTDOWN
    logger.info("Shutting down AssessIQ AI...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="AssessIQ AI",
        description="Conversational SHL Assessment Recommender",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint for readiness probes."""
        return {"status": "ok"}

    # Middleware for request/response logging
    @app.middleware("http")
    async def log_requests(request, call_next):
        logger.info(f"INCOMING REQUEST: {request.method} {request.url}")
        try:
            response = await call_next(request)
            logger.info(f"RESPONSE STATUS: {response.status_code}")
            return response
        except Exception as e:
            logger.exception(f"MIDDLEWARE ERROR: {e}")
            raise

    # Mount chat routes
    app.include_router(chat.router)

    # Error handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        logger.error(f"Validation error: {exc}")
        return {
            "detail": str(exc),
            "error_type": "validation_error"
        }

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return {
            "detail": "Internal server error",
            "error_type": "internal_error"
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    import os
    port = int(os.environ.get("PORT", settings.api_port))
    host = os.environ.get("HOST", settings.api_host)
    
    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
