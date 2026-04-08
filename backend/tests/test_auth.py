"""
Tests for authentication endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.auth import create_access_token, create_refresh_token, get_password_hash
from app.database import Base, engine
from app.models import User


@pytest.fixture(scope="function")
async def async_client():
    """Create an async test client with isolated database."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Drop tables after test
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def test_user(async_client):
    """Create a test user and return user data."""
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
    }
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201
    return {**user_data, "id": response.json()["id"]}


class TestRegister:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, async_client):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
        }
        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert "id" in data
        assert "is_active" in data
        assert data["is_active"] is True
        assert "created_at" in data
        assert "hashed_password" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client, test_user):
        """Test registration with duplicate email returns error."""
        user_data = {
            "email": test_user["email"],
            "password": "anotherpassword123",
        }
        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, async_client):
        """Test registration with invalid email returns validation error."""
        user_data = {
            "email": "not-an-email",
            "password": "password123",
        }
        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client):
        """Test registration with short password returns validation error."""
        user_data = {
            "email": "user@example.com",
            "password": "short",
        }
        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422


class TestLogin:
    """Tests for user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, test_user):
        """Test successful login returns tokens."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }
        response = await async_client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, async_client):
        """Test login with non-existent email returns 401."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123",
        }
        response = await async_client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, async_client, test_user):
        """Test login with wrong password returns 401."""
        login_data = {
            "email": test_user["email"],
            "password": "wrongpassword",
        }
        response = await async_client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, async_client):
        """Test login with missing fields returns validation error."""
        response = await async_client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422


class TestLoginForm:
    """Tests for OAuth2 form-based login."""

    @pytest.mark.asyncio
    async def test_login_form_success(self, async_client, test_user):
        """Test successful OAuth2 form login."""
        response = await async_client.post(
            "/api/v1/auth/login/form",
            data={
                "username": test_user["email"],
                "password": test_user["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_form_invalid_credentials(self, async_client):
        """Test OAuth2 form login with invalid credentials."""
        response = await async_client.post(
            "/api/v1/auth/login/form",
            data={
                "username": "wrong@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, async_client, test_user):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # New tokens should be different
        assert data["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, async_client):
        """Test refresh with invalid token returns 401."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_access_token_rejected(self, async_client, test_user):
        """Test using access token as refresh token fails."""
        # Login to get access token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        # Try to use access token as refresh token
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401


class TestTokenValidation:
    """Tests for token validation and security."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(self, async_client, test_user):
        """Test accessing protected endpoint with valid token."""
        # Login to get token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        # Access protected endpoint (we'll use it to verify token works)
        # For now, just verify the token structure
        from app.auth import decode_token

        payload = decode_token(access_token)
        assert payload is not None
        assert payload.sub == test_user["id"]
        assert payload.type == "access"

    @pytest.mark.asyncio
    async def test_token_contains_user_id(self, async_client, test_user):
        """Test that token contains correct user ID."""
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        from app.auth import decode_token

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload.sub == test_user["id"]
        assert refresh_payload.sub == test_user["id"]
        assert access_payload.type == "access"
        assert refresh_payload.type == "refresh"
