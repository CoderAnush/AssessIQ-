"""
FastAPI application entry point.
Initializes app, loads data, and mounts routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import psutil
import time
import os

from app.config import settings, validate_config
from app.logger_config.logger import setup_logging
from app.models.response import HealthResponse
from app.routes import chat

# Setup logging first
logger = setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""

    # STARTUP
    logger.info("Starting AssessIQ AI...")
    logger.info("BACKEND STARTUP INITIATED")
    logger.debug(f"Memory Usage: {psutil.virtual_memory()}")
    
    start_time = time.time()
    app.state.start_time = start_time
    
    try:
        validate_config()
        logger.info("Configuration validated")

        # 1. Load Catalog
        logger.info("STARTUP: Loading Catalog...")
        from app.services.catalog_loader import CatalogLoader
        catalog_path = getattr(settings, "catalog_path", "data/processed/catalog_enriched_v2.json")
        app.state.catalog_loader = CatalogLoader(catalog_path)
        logger.info(f"STARTUP: Catalog loaded in {time.time() - start_time:.2f}s")

        # 2. Initialize LLM only when credentials are available.
        gemini_key = getattr(settings, "gemini_api_key", "")
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            logger.info("STARTUP: Initializing LLM Service...")
            from app.services.llm_service import LLMService
            app.state.llm_service = LLMService()
            logger.info(f"STARTUP: LLM Service ready in {time.time() - start_time:.2f}s")
        else:
            app.state.llm_service = None
            logger.info("STARTUP: LLM Service skipped (no API key configured)")

        # 3. Initialize Retriever (Lightweight version already in retriever.py)
        logger.info("STARTUP: Initializing LIGHTWEIGHT Retriever...")
        from app.services.retriever import HybridRetriever
        app.state.retriever = HybridRetriever(app.state.catalog_loader)
        logger.info(f"STARTUP: Retriever ready in {time.time() - start_time:.2f}s")

        # 4. Initialize Ranker & Embedding Service
        logger.info("STARTUP: Initializing Ranker & Embedding Service...")
        from app.services.embedding_service import EmbeddingService
        # 4. Initialize Decision & Ranking Engine
        from app.services.ranker_v2 import EnterpriseRanker
        from app.services.competency_taxonomy_v2 import CompetencyTaxonomyV2
        from app.services.adaptive_orchestrator import AdaptiveOrchestrator
        from app.services.orchestration_analytics import OrchestrationAnalytics
        
        app.state.taxonomy = CompetencyTaxonomyV2()
        app.state.orchestration_analytics = OrchestrationAnalytics()
        app.state.adaptive_orchestrator = AdaptiveOrchestrator(app.state.taxonomy)
        app.state.ranker = EnterpriseRanker(embedding_service=EmbeddingService(), skill_graph=None)
        logger.info("STARTUP: Initializing Comparison Engine...")

        # 4b. Initialize Comparison Engine
        from app.services.comparison_engine import ComparisonEngine
        app.state.comparison_engine = ComparisonEngine()

        # 5. Initialize Decision Engine
        logger.info("STARTUP: Initializing Decision Engine...")
        from app.agents.decision_engine import DecisionEngine
        app.state.decision_engine = DecisionEngine()

        # 6. Initialize Hallucination Checker
        logger.info("STARTUP: Initializing Hallucination Checker...")
        from app.utils.hallucination_checker import HallucinationChecker
        app.state.hallucination_checker = HallucinationChecker(app.state.catalog_loader)

        logger.info("BACKEND STARTUP COMPLETE")
        logger.info(f"Startup time: {time.time() - start_time:.2f}s")
        logger.debug(f"Final Memory Usage: {psutil.virtual_memory()}")
        logger.info("AssessIQ AI startup complete")
    except Exception as e:
        logger.exception(f"CRITICAL STARTUP FAILURE: {e}")
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
        uptime_seconds = time.time() - getattr(app.state, "start_time", time.time())
        memory_mb = psutil.virtual_memory().used / (1024 * 1024)
        return {
            "status": "ok",
            "version": "1.0.0",
            "uptime_seconds": uptime_seconds,
            "memory_usage_mb": memory_mb,
        }

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
        return JSONResponse(status_code=400, content={
            "detail": str(exc),
            "error_type": "validation_error"
        })

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "detail": "Internal server error",
            "error_type": "internal_error"
        })

    return app


# Create app instance
app = create_app()


@app.post("/feedback")
async def post_feedback(request: Request):
    """
    POST /feedback endpoint for recruiter actions (Phase 7).
    """
    data = await request.json()
    assessment_id = data.get("id")
    action = data.get("action") # select, reject
    
    if assessment_id and action:
        # In a real app, this would be per session in a DB.
        # Here we update the stateful ranker in app.state.
        from app.services.ranker_v2 import EnterpriseRanker
        if isinstance(app.state.ranker, EnterpriseRanker):
            app.state.ranker.update_feedback(assessment_id, action)
            return {"status": "success", "message": f"Feedback {action} recorded for {assessment_id}"}
    
    return {"status": "error", "message": "Invalid feedback data"}

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
