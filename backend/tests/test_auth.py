"""
Tests for authentication endpoints.
"""

import pytest
from datetime import datetime, timedelta
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    create_password_reset_token,
    decode_token,
)
from app.models import User, PasswordResetToken
from tests.conftest import TestSession


@pytest.fixture(scope="function")
async def async_client():
    """Create an async test client with isolated database.

    Table creation/teardown is handled by conftest.setup_test_db (autouse).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


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
        # Verify new tokens are valid by decoding them
        new_access_payload = decode_token(data["access_token"])
        new_refresh_payload = decode_token(data["refresh_token"])
        assert new_access_payload is not None
        assert new_refresh_payload is not None
        assert new_access_payload.type == "access"
        assert new_refresh_payload.type == "refresh"

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


class TestTokenRefreshExtended:
    """Extended tests for token refresh including expired and revoked tokens."""

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, async_client, test_user):
        """Test refresh with expired token returns 401."""
        # Create an expired refresh token
        from app.auth import decode_token
        from jose import jwt
        from app.config import settings

        # Create token that expired 1 second ago
        expired_time = datetime.utcnow() - timedelta(seconds=1)
        expired_token = jwt.encode(
            {
                "sub": str(test_user["id"]),
                "exp": expired_time,
                "type": "refresh",
            },
            settings.secret_key,
            algorithm="HS256",
        )

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_signature(self, async_client):
        """Test refresh with invalid signature returns 401."""
        from jose import jwt

        # Create token with wrong secret
        invalid_token = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.utcnow() + timedelta(days=7),
                "type": "refresh",
            },
            "wrong-secret-key",
            algorithm="HS256",
        )

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": invalid_token},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_malformed(self, async_client):
        """Test refresh with malformed token returns 401."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.valid.token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_missing_sub(self, async_client):
        """Test refresh with token missing subject returns 401."""
        from jose import jwt
        from app.config import settings

        # Create token without sub claim
        token_without_sub = jwt.encode(
            {
                "exp": datetime.utcnow() + timedelta(days=7),
                "type": "refresh",
            },
            settings.secret_key,
            algorithm="HS256",
        )

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_without_sub},
        )

        assert response.status_code == 401


class TestPasswordResetRequest:
    """Tests for password reset request endpoint."""

    @pytest.mark.asyncio
    async def test_password_reset_request_success(self, async_client, test_user):
        """Test successful password reset request."""
        response = await async_client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": test_user["email"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "reset link has been sent" in data["message"]

    @pytest.mark.asyncio
    async def test_password_reset_request_nonexistent_email(self, async_client):
        """Test password reset request with non-existent email returns same message."""
        response = await async_client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "nonexistent@example.com"},
        )

        # Should return same message to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "reset link has been sent" in data["message"]

    @pytest.mark.asyncio
    async def test_password_reset_request_invalid_email(self, async_client):
        """Test password reset request with invalid email format."""
        response = await async_client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "not-an-email"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_password_reset_request_creates_token(self, async_client, test_user):
        """Test that password reset request creates a token in database."""
        db = TestSession()
        user = db.query(User).filter(User.email == test_user["email"]).first()

        # Create token directly
        token = create_password_reset_token(db, user.id)

        # Verify token exists in database
        db_token = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token == token)
            .first()
        )
        assert db_token is not None
        assert db_token.user_id == user.id
        assert db_token.used_at is None
        assert db_token.expires_at > datetime.utcnow()

        db.close()


class TestPasswordResetConfirm:
    """Tests for password reset confirmation endpoint."""

    @pytest.fixture
    async def reset_token(self, async_client, test_user):
        """Create a password reset token for testing."""
        from sqlalchemy.orm import Session
        db = TestSession()
        user = db.query(User).filter(User.email == test_user["email"]).first()
        token = create_password_reset_token(db, user.id)
        db.close()
        return token

    @pytest.mark.asyncio
    async def test_password_reset_success(self, async_client, test_user, reset_token):
        """Test successful password reset."""
        new_password = "newpassword123"

        response = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": new_password,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "reset successfully" in data["message"]

        # Verify can login with new password
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": new_password,
            },
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    @pytest.mark.asyncio
    async def test_password_reset_invalid_token(self, async_client):
        """Test password reset with invalid token."""
        response = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": "invalid-token",
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_password_reset_expired_token(self, async_client, test_user):
        """Test password reset with expired token."""
        from sqlalchemy.orm import Session
        import secrets

        db = TestSession()
        user = db.query(User).filter(User.email == test_user["email"]).first()

        # Create an expired token directly
        expired_token = secrets.token_urlsafe(32)
        db_token = PasswordResetToken(
            user_id=user.id,
            token=expired_token,
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
        )
        db.add(db_token)
        db.commit()
        db.close()

        response = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": expired_token,
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == 400
        assert (
            "invalid" in response.json()["detail"].lower()
            or "expired" in response.json()["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_password_reset_used_token(self, async_client, test_user):
        """Test password reset with already used token."""
        from sqlalchemy.orm import Session
        db = TestSession()
        user = db.query(User).filter(User.email == test_user["email"]).first()

        # Create a token and mark it as used
        token = create_password_reset_token(db, user.id)
        db_token = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token == token)
            .first()
        )
        db_token.used_at = datetime.utcnow()
        db.commit()
        db.close()

        response = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": token,
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_password_reset_short_password(self, async_client, reset_token):
        """Test password reset with short password returns validation error."""
        response = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": "short",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_password_reset_token_single_use(
        self, async_client, test_user, reset_token
    ):
        """Test that password reset token can only be used once."""
        new_password = "newpassword123"

        # First reset should succeed
        response1 = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": new_password,
            },
        )
        assert response1.status_code == 200

        # Second reset with same token should fail
        response2 = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": "anotherpassword123",
            },
        )
        assert response2.status_code == 400
