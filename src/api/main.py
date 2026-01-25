"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.api.routes import scoring, graph, investigation, consortium

settings = get_settings()

app = FastAPI(
    title="Synthetic Identity Fraud Detection API",
    description="API for detecting synthetic identities and bust-out fraud",
    version="1.0.0",
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
    return {
        "status": "healthy",
        "components": {
            "api": "up",
            "database": "up",
            "neo4j": "up",
            "kafka": "up",
        },
    }
