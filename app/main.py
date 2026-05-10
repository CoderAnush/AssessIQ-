"""
FastAPI application entry point.
Initializes app, loads data, and mounts routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

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
    try:
        validate_config()
        logger.info("Configuration validated")

        # Load catalog (happens in routes lazily or here)
        logger.info(f"Catalog will be loaded from {settings.catalog_path}")
        logger.info(f"FAISS index will be loaded from {settings.faiss_index_path}")

        logger.info("AssessIQ AI startup complete")
    except Exception as e:
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

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
