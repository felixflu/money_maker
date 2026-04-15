"""
Tests for WealthAPI integration.

TDD: Tests for WealthAPI client with mocked responses.
Tests cover: initialization, mandator auth, user login, token refresh,
HTTP methods, error handling, rate limits.
"""

import time

import pytest
from unittest.mock import Mock, patch

from app.integrations.wealthapi import (
    WealthApiClient,
    WealthApiError,
    WealthApiAuthError,
    WealthApiRateLimitError,
)


class TestWealthApiClientInit:
    """Tests for WealthApiClient initialization."""

    def test_client_initialization(self):
        client = WealthApiClient(
            client_id="test_id",
            client_secret="test_secret",
        )
        assert client.client_id == "test_id"
        assert client.client_secret == "test_secret"
        assert client.base_url == "https://sandbox.wealthapi.eu"
        assert client.timeout == 30

    def test_client_initialization_custom_url(self):
        client = WealthApiClient(
            client_id="test_id",
            client_secret="test_secret",
            base_url="https://wealthapi.eu",
            timeout=60,
        )
        assert client.base_url == "https://wealthapi.eu"
        assert client.timeout == 60

    def test_client_strips_trailing_slash(self):
        client = WealthApiClient(
            client_id="test_id",
            client_secret="test_secret",
            base_url="https://sandbox.wealthapi.eu/",
        )
        assert client.base_url == "https://sandbox.wealthapi.eu"

    def test_initial_token_state(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        assert client._access_token is None
        assert client._refresh_token is None
        assert client._token_expires_at == 0.0


class TestMandatorHeaders:
    """Tests for mandator-level authentication headers."""

    def test_mandator_headers(self):
        client = WealthApiClient(client_id="my_id", client_secret="my_secret")
        headers = client._get_mandator_headers()
        assert headers["X-Mandator-Client-Id"] == "my_id"
        assert headers["X-Mandator-Client-Secret"] == "my_secret"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert headers["User-Agent"] == "MoneyMaker/1.0"

    def test_auth_headers_without_token(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        headers = client._get_auth_headers()
        assert "Authorization" not in headers
        assert headers["X-Mandator-Client-Id"] == "id"

    def test_auth_headers_with_token(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "jwt_token_123"
        headers = client._get_auth_headers()
        assert headers["Authorization"] == "Bearer jwt_token_123"
        assert headers["X-Mandator-Client-Id"] == "id"


class TestUrlBuilding:
    """Tests for URL construction."""

    def test_build_url(self):
        client = WealthApiClient(
            client_id="id",
            client_secret="secret",
            base_url="https://sandbox.wealthapi.eu",
        )
        url = client._build_url("accounts")
        assert url == "https://sandbox.wealthapi.eu/api/v2/accounts"

    def test_build_url_strips_leading_slash(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        url = client._build_url("/accounts")
        assert url == "https://sandbox.wealthapi.eu/api/v2/accounts"

    def test_build_url_nested_path(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        url = client._build_url("connections/123/accounts")
        assert url == "https://sandbox.wealthapi.eu/api/v2/connections/123/accounts"


class TestTokenManagement:
    """Tests for JWT token lifecycle."""

    def test_token_expired_when_none(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        assert client._is_token_expired() is True

    def test_token_not_expired(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        client._token_expires_at = time.time() + 3600
        assert client._is_token_expired() is False

    def test_token_expired_within_buffer(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        # Expires in 4 minutes (within 5-minute buffer)
        client._token_expires_at = time.time() + 240
        assert client._is_token_expired() is True

    def test_set_tokens(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client.set_tokens("access_123", "refresh_456", expires_in=7200)
        assert client._access_token == "access_123"
        assert client._refresh_token == "refresh_456"
        assert client._is_token_expired() is False


class TestLogin:
    """Tests for user login flow."""

    def test_login_success(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"access_token":"jwt","refresh_token":"ref","expires_in":3600}'
        mock_response.json.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.login("user@test.com", "password123")
        assert result["access_token"] == "jwt"
        assert client._access_token == "jwt"
        assert client._refresh_token == "ref"

    def test_login_failure_401(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiAuthError):
            client.login("bad@test.com", "wrong")

    def test_login_missing_access_token(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"refresh_token":"ref"}'
        mock_response.json.return_value = {"refresh_token": "ref"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiAuthError, match="No access_token"):
            client.login("user@test.com", "password123")


class TestTokenRefresh:
    """Tests for JWT token refresh flow."""

    def test_refresh_success(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._refresh_token = "old_refresh"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"access_token":"new_jwt","refresh_token":"new_ref","expires_in":3600}'
        mock_response.json.return_value = {
            "access_token": "new_jwt",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        client._session.request = Mock(return_value=mock_response)

        client.refresh_access_token()
        assert client._access_token == "new_jwt"
        assert client._refresh_token == "new_ref"

    def test_refresh_no_refresh_token(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        with pytest.raises(WealthApiAuthError, match="No refresh token"):
            client.refresh_access_token()

    def test_refresh_failure_clears_tokens(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "old_jwt"
        client._refresh_token = "old_refresh"

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Token expired"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiAuthError):
            client.refresh_access_token()

        assert client._access_token is None
        assert client._refresh_token is None


class TestEnsureAuthenticated:
    """Tests for automatic token management."""

    def test_raises_when_not_logged_in(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        with pytest.raises(WealthApiAuthError, match="Not authenticated"):
            client._ensure_authenticated()

    def test_no_op_when_token_valid(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "valid_token"
        client._token_expires_at = time.time() + 3600
        # Should not raise
        client._ensure_authenticated()

    def test_auto_refresh_when_expired(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "expired"
        client._refresh_token = "refresh"
        client._token_expires_at = time.time() - 10  # Already expired

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"access_token":"new","refresh_token":"new_ref","expires_in":3600}'
        mock_response.json.return_value = {
            "access_token": "new",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        client._session.request = Mock(return_value=mock_response)

        client._ensure_authenticated()
        assert client._access_token == "new"


class TestHttpMethods:
    """Tests for convenience HTTP methods."""

    def _make_client(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        client._token_expires_at = time.time() + 3600
        return client

    def test_get(self):
        client = self._make_client()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": []}'
        mock_response.json.return_value = {"data": []}
        client._session.request = Mock(return_value=mock_response)

        result = client.get("accounts", params={"limit": 10})
        assert result == {"data": []}
        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"

    def test_post(self):
        client = self._make_client()
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "123"}'
        mock_response.json.return_value = {"id": "123"}
        client._session.request = Mock(return_value=mock_response)

        result = client.post("connections", data={"bank": "test"})
        assert result == {"id": "123"}
        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "POST"

    def test_put(self):
        client = self._make_client()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"updated": true}'
        mock_response.json.return_value = {"updated": True}
        client._session.request = Mock(return_value=mock_response)

        result = client.put("connections/1", data={"active": True})
        assert result == {"updated": True}
        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "PUT"

    def test_delete(self):
        client = self._make_client()
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.content = b""
        client._session.request = Mock(return_value=mock_response)

        result = client.delete("connections/1")
        assert result == {}
        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "DELETE"


class TestErrorHandling:
    """Tests for error handling and rate limits."""

    def test_rate_limit_429(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}
        mock_response.json.return_value = {"error": "Rate limited"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiRateLimitError) as exc_info:
            client._make_request("GET", "test", authenticated=False)

        assert exc_info.value.retry_after == 120

    def test_timeout_error(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        import requests

        client._session.request = Mock(side_effect=requests.exceptions.Timeout())

        with pytest.raises(WealthApiError, match="timeout"):
            client._make_request("GET", "test", authenticated=False)

    def test_connection_error(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        import requests

        client._session.request = Mock(
            side_effect=requests.exceptions.ConnectionError("refused")
        )

        with pytest.raises(WealthApiError, match="Connection error"):
            client._make_request("GET", "test", authenticated=False)

    def test_generic_api_error(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError) as exc_info:
            client._make_request("GET", "test", authenticated=False)

        assert exc_info.value.status_code == 500

    def test_invalid_json_response(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"not json"
        mock_response.json.side_effect = ValueError("Invalid JSON")
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError, match="Invalid JSON"):
            client._make_request("GET", "test", authenticated=False)

    def test_204_no_content(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 204
        client._session.request = Mock(return_value=mock_response)

        result = client._make_request("DELETE", "test", authenticated=False)
        assert result == {}


class TestValidateConnection:
    """Tests for connection validation."""

    def test_validate_success(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}
        client._session.request = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()
        assert is_valid is True
        assert error is None

    def test_validate_auth_failure(self):
        client = WealthApiClient(client_id="bad", client_secret="bad")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.request = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()
        assert is_valid is False
        assert "Authentication failed" in error

    def test_validate_rate_limited(self):
        client = WealthApiClient(client_id="id", client_secret="secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {}
        client._session.request = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()
        assert is_valid is False
        assert "Rate limit" in error


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager(self):
        with WealthApiClient(client_id="id", client_secret="secret") as client:
            assert client is not None
        # Session should be closed after exit


class TestExceptionFormatting:
    """Tests for exception string representation."""

    def test_error_with_status_code(self):
        err = WealthApiError("fail", status_code=404)
        assert str(err) == "[404] fail"

    def test_error_without_status_code(self):
        err = WealthApiError("fail")
        assert str(err) == "fail"

    def test_rate_limit_error_defaults(self):
        err = WealthApiRateLimitError()
        assert err.retry_after == 60
        assert err.status_code == 429
