"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.api.routes import scoring, graph, investigation, consortium
from src.api import dependencies

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: Initialize connections
    logger.info("Starting up Fraud Detection API...")

    # Pre-initialize connections (optional - they're lazy by default)
    try:
        dependencies.get_redis_client()
        dependencies.get_neo4j_driver()
    except Exception as e:
        logger.warning(f"Failed to initialize some connections: {e}")

    yield

    # Shutdown: Cleanup connections
    logger.info("Shutting down Fraud Detection API...")
    dependencies.cleanup()


app = FastAPI(
    title="Synthetic Identity Fraud Detection API",
    description="API for detecting synthetic identities and bust-out fraud",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scoring.router, prefix="/api/v1/score", tags=["scoring"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(investigation.router, prefix="/api/v1/investigation", tags=["investigation"])
app.include_router(consortium.router, prefix="/api/v1/consortium", tags=["consortium"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "fraud-detection"}


@app.get("/health")
async def health():
    """Detailed health check."""
    redis_status = await dependencies.check_redis_health()
    neo4j_status = await dependencies.check_neo4j_health()

    # Determine overall status
    all_up = redis_status["status"] == "up" and neo4j_status["status"] == "up"
    overall = "healthy" if all_up else "degraded"

    return {
        "status": overall,
        "components": {
            "api": "up",
            "redis": redis_status["status"],
            "neo4j": neo4j_status["status"],
        },
        "details": {
            "redis": redis_status,
            "neo4j": neo4j_status,
        },
    }
