"""
FastAPI backend application main entry point.
"""

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

# Create FastAPI application
app = FastAPI(
    title="Money Maker API",
    description="Backend API for the money_maker application",
    version="0.1.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV") != "production" else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint returning API info."""
    return {"name": "Money Maker API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker Compose."""
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"status": "healthy", "service": "api"}
    )


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint."""
    return {
        "api_version": "v1",
        "status": "operational",
        "environment": os.getenv("ENV", "development"),
    }
