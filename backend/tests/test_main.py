"""
Tests for the main FastAPI application.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client():
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_api_info(self, async_client):
        """Test that root endpoint returns API information."""
        async with async_client as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Money Maker API"
            assert data["version"] == "0.1.0"
            assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_root_content_type_is_json(self, async_client):
        """Test that root returns JSON content."""
        async with async_client as client:
            response = await client.get("/")
            assert response.headers["content-type"] == "application/json"


class TestHealthEndpoint:
    """Tests for the health check endpoint (used by Docker Compose)."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, async_client):
        """Test health check returns HTTP 200."""
        async with async_client as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_healthy_status(self, async_client):
        """Test health check returns healthy status."""
        async with async_client as client:
            response = await client.get("/health")
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "api"


class TestApiStatusEndpoint:
    """Tests for the API status endpoint."""

    @pytest.mark.asyncio
    async def test_api_status_returns_version(self, async_client):
        """Test API status returns version info."""
        async with async_client as client:
            response = await client.get("/api/v1/status")
            assert response.status_code == 200
            data = response.json()
            assert data["api_version"] == "v1"
            assert data["status"] == "operational"
            assert "environment" in data
