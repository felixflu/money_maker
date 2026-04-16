"""
Tests for exchange router Trade Republic → WealthAPI refactoring.

TDD: Tests verify that Trade Republic endpoints use WealthApiClient
instead of TradeRepublicClient, while other exchanges remain unchanged.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.integrations.wealthapi import (
    WealthApiClient,
    WealthApiError,
    WealthApiAuthError,
    WealthApiRateLimitError,
)


class TestSyncTradeRepublicWithWealthAPI:
    """Tests for sync_trade_republic using WealthApiClient."""

    def _make_mock_connection(self, is_active=True):
        conn = Mock()
        conn.id = 1
        conn.user_id = 42
        conn.exchange_name = "trade_republic"
        conn.api_key_encrypted = "user@example.com"
        conn.api_secret_encrypted = "password123"
        conn.is_active = is_active
        conn.last_synced_at = None
        return conn

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_creates_wealthapi_client_with_settings_creds(
        self, mock_settings, mock_client_cls
    ):
        """Sync should create WealthApiClient using app-level mandator creds."""
        mock_settings.wealthapi_client_id = "mandator_id"
        mock_settings.wealthapi_client_secret = "mandator_secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.return_value = {"accounts": [], "holdings": []}

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        result = _sync_trade_republic_via_wealthapi(conn)

        mock_client_cls.assert_called_once_with(
            client_id="mandator_id",
            client_secret="mandator_secret",
            base_url="https://sandbox.wealthapi.eu",
        )

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_logs_in_with_connection_credentials(
        self, mock_settings, mock_client_cls
    ):
        """Sync should login to WealthAPI using the stored connection credentials."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.return_value = {"accounts": [], "holdings": []}

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        _sync_trade_republic_via_wealthapi(conn)

        mock_client.login.assert_called_once_with("user@example.com", "password123")

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_fetches_accounts_and_holdings(
        self, mock_settings, mock_client_cls
    ):
        """Sync should fetch bank connections and accounts from WealthAPI."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.side_effect = [
            # First call: GET connections
            {
                "connections": [
                    {"id": "conn-1", "provider": "trade_republic", "status": "active"}
                ]
            },
            # Second call: GET connections/{id}/accounts
            {
                "accounts": [
                    {
                        "id": "acc-1",
                        "name": "Portfolio",
                        "balance": {"amount": 1500.0, "currency": "EUR"},
                        "holdings": [
                            {
                                "isin": "IE00B4L5Y983",
                                "name": "iShares MSCI World",
                                "quantity": 10.0,
                                "current_price": 75.0,
                                "currency": "EUR",
                                "total_value": 750.0,
                            }
                        ],
                    }
                ]
            },
        ]

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        result = _sync_trade_republic_via_wealthapi(conn)

        assert result["success"] is True
        assert result["holdings_count"] == 1
        assert mock_client.get.call_count == 2

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_returns_failure_on_auth_error(
        self, mock_settings, mock_client_cls
    ):
        """Sync should return failure when WealthAPI auth fails."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.side_effect = WealthApiAuthError("Invalid credentials")

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        result = _sync_trade_republic_via_wealthapi(conn)

        assert result["success"] is False
        assert "Authentication failed" in result["error"]

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_returns_failure_on_rate_limit(
        self, mock_settings, mock_client_cls
    ):
        """Sync should return failure on rate limit."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.side_effect = WealthApiRateLimitError(retry_after=120)

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        result = _sync_trade_republic_via_wealthapi(conn)

        assert result["success"] is False
        assert "Rate limit" in result["error"]

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_sync_returns_failure_on_api_error(
        self, mock_settings, mock_client_cls
    ):
        """Sync should return failure on generic API error."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.side_effect = WealthApiError("Server error", status_code=500)

        from app.routers.exchanges import _sync_trade_republic_via_wealthapi

        conn = self._make_mock_connection()
        result = _sync_trade_republic_via_wealthapi(conn)

        assert result["success"] is False
        assert "API error" in result["error"]


class TestValidateTradeRepublicWithWealthAPI:
    """Tests for validate endpoint using WealthApiClient for Trade Republic."""

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_validate_creates_wealthapi_client(
        self, mock_settings, mock_client_cls
    ):
        """Validate should use WealthApiClient for trade_republic."""
        mock_settings.wealthapi_client_id = "mandator_id"
        mock_settings.wealthapi_client_secret = "mandator_secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.return_value = {
            "access_token": "jwt",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        mock_client.get.return_value = {"status": "ok", "user": {"id": "u1"}}

        from app.routers.exchanges import _validate_trade_republic_via_wealthapi

        is_valid, error, account_info = _validate_trade_republic_via_wealthapi(
            "user@test.com", "password123"
        )

        assert is_valid is True
        assert error is None
        assert account_info is not None
        mock_client_cls.assert_called_once_with(
            client_id="mandator_id",
            client_secret="mandator_secret",
            base_url="https://sandbox.wealthapi.eu",
        )
        mock_client.login.assert_called_once_with("user@test.com", "password123")

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_validate_returns_invalid_on_auth_error(
        self, mock_settings, mock_client_cls
    ):
        """Validate should return invalid on auth failure."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.side_effect = WealthApiAuthError("Bad creds")

        from app.routers.exchanges import _validate_trade_republic_via_wealthapi

        is_valid, error, account_info = _validate_trade_republic_via_wealthapi(
            "bad@test.com", "wrong"
        )

        assert is_valid is False
        assert "Authentication failed" in error
        assert account_info is None

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_validate_returns_invalid_on_rate_limit(
        self, mock_settings, mock_client_cls
    ):
        """Validate should return invalid on rate limit."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.login.side_effect = WealthApiRateLimitError(retry_after=60)

        from app.routers.exchanges import _validate_trade_republic_via_wealthapi

        is_valid, error, account_info = _validate_trade_republic_via_wealthapi(
            "user@test.com", "pass"
        )

        assert is_valid is False
        assert "Rate limit" in error


class TestGetConnectionDetailWithWealthAPI:
    """Tests for get_connection using WealthApiClient for Trade Republic."""

    @patch("app.routers.exchanges.WealthApiClient")
    @patch("app.routers.exchanges.settings")
    def test_uses_wealthapi_for_trade_republic_validation(
        self, mock_settings, mock_client_cls
    ):
        """get_connection should use WealthApiClient for TR connection validation."""
        mock_settings.wealthapi_client_id = "id"
        mock_settings.wealthapi_client_secret = "secret"
        mock_settings.wealthapi_base_url = "https://sandbox.wealthapi.eu"

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.validate_connection.return_value = (True, None)

        from app.routers.exchanges import _validate_connection_status

        is_valid, error = _validate_connection_status(
            "trade_republic", "api_key", "api_secret"
        )

        assert is_valid is True
        assert error is None
        mock_client_cls.assert_called_once()

    @patch("app.routers.exchanges.CoinbaseClient")
    def test_still_uses_coinbase_client_for_coinbase(self, mock_coinbase_cls):
        """get_connection should still use CoinbaseClient for coinbase."""
        mock_client = Mock()
        mock_coinbase_cls.return_value = mock_client
        mock_client.validate_connection.return_value = (True, None)

        from app.routers.exchanges import _validate_connection_status

        is_valid, error = _validate_connection_status(
            "coinbase", "api_key", "api_secret"
        )

        assert is_valid is True
        mock_coinbase_cls.assert_called_once_with(
            api_key="api_key", api_secret="api_secret"
        )
