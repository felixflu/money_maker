"""
FastAPI backend application main entry point.
"""

from fastapi import FastAPI, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os

from app.routers import auth, mexc
from app.models import init_db, get_db

# Create FastAPI application
app = FastAPI(
    title="Money Maker API",
    description="Backend API for the money_maker application",
    version="0.1.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV") != "production" else None,
)

# Include routers
app.include_router(auth.router)
app.include_router(mexc.router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/api/v1/health/db")
async def health_check_db(db: Session = Depends(get_db)):
    """Health check endpoint that verifies database connectivity."""
    try:
        # Execute a simple query to verify connection
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": str(e)},
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
