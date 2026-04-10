"""
Tests for Bitpanda integration.

TDD: Tests for Bitpanda API client with mocked responses.
Tests cover: sync holdings, transaction import, error handling, rate limits.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from app.integrations.bitpanda import (
    BitpandaClient,
    BitpandaAPIError,
    BitpandaRateLimitError,
    BitpandaAuthError,
)


class TestBitpandaClient:
    """Tests for the Bitpanda API client."""

    def test_client_initialization(self):
        """Test client initializes with API key."""
        client = BitpandaClient(
            api_key="test_key_12345",
        )
        assert client.api_key == "test_key_12345"
        assert client.api_secret is None
        assert client.base_url == "https://api.bitpanda.com"
        assert client.timeout == 30

    def test_client_initialization_with_secret(self):
        """Test client accepts secret for interface compatibility."""
        client = BitpandaClient(
            api_key="test_key",
            api_secret="ignored_secret",
            timeout=60,
        )
        assert client.api_key == "test_key"
        assert client.api_secret == "ignored_secret"
        assert client.timeout == 60

    def test_headers_contain_api_key(self):
        """Test that headers include X-Api-Key header."""
        client = BitpandaClient(api_key="my_api_key")
        headers = client._get_headers()
        assert headers["X-Api-Key"] == "my_api_key"
        assert headers["Content-Type"] == "application/json"


class TestBitpandaAuthentication:
    """Tests for Bitpanda authentication."""

    def test_successful_account_info(self):
        """Test successful authentication via account info endpoint."""
        client = BitpandaClient(api_key="valid_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "user_123",
                "type": "user",
                "attributes": {
                    "email": "user@example.com",
                    "status": "active",
                },
            }
        }
        client._session.get = Mock(return_value=mock_response)

        account_info = client.get_account_info()

        assert account_info["data"]["id"] == "user_123"
        assert account_info["data"]["attributes"]["email"] == "user@example.com"
        client._session.get.assert_called_once()

    def test_authentication_failure_invalid_key(self):
        """Test authentication failure with invalid API key."""
        client = BitpandaClient(api_key="invalid_key")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"detail": "Invalid API key"}]}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaAuthError):
            client.get_account_info()

    def test_authentication_rate_limit(self):
        """Test rate limit raises BitpandaRateLimitError."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaRateLimitError) as exc_info:
            client.get_account_info()

        assert exc_info.value.retry_after == 60


class TestBitpandaPortfolioSync:
    """Tests for portfolio/holdings synchronization."""

    def test_get_wallets_success(self):
        """Test successful retrieval of cryptocurrency wallets."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "wallet_btc",
                    "type": "wallet",
                    "attributes": {
                        "name": "Bitcoin",
                        "cryptocoin_symbol": "BTC",
                        "balance": 0.5,
                        "available": 0.4,
                    },
                },
                {
                    "id": "wallet_eth",
                    "type": "wallet",
                    "attributes": {
                        "name": "Ethereum",
                        "cryptocoin_symbol": "ETH",
                        "balance": 2.5,
                        "available": 2.0,
                    },
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        wallets = client.get_wallets()

        assert len(wallets) == 2
        assert wallets[0]["attributes"]["cryptocoin_symbol"] == "BTC"
        assert wallets[0]["attributes"]["balance"] == 0.5
        assert wallets[1]["attributes"]["cryptocoin_symbol"] == "ETH"

    def test_get_wallets_empty_portfolio(self):
        """Test handling empty wallet list."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        wallets = client.get_wallets()

        assert wallets == []

    def test_get_wallets_unauthorized(self):
        """Test handling unauthorized access to wallets."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"errors": [{"detail": "Forbidden"}]}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaAPIError):
            client.get_wallets()

    def test_get_wallets_rate_limit(self):
        """Test rate limiting on wallets endpoint."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"errors": [{"detail": "Rate limit exceeded"}]}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaRateLimitError) as exc_info:
            client.get_wallets()

        assert exc_info.value.retry_after == 30

    def test_normalize_holding(self):
        """Test normalization of wallet data."""
        client = BitpandaClient(api_key="test_key")

        raw_wallet = {
            "id": "wallet_btc",
            "type": "wallet",
            "attributes": {
                "name": "Bitcoin",
                "cryptocoin_symbol": "BTC",
                "balance": "1.5",
                "available": "1.0",
            },
        }

        normalized = client._normalize_holding(raw_wallet)

        assert normalized["symbol"] == "BTC"
        assert normalized["name"] == "Bitcoin"
        assert normalized["asset_type"] == "cryptocurrency"
        assert normalized["quantity"] == 1.5
        assert normalized["available_quantity"] == 1.0
        assert normalized["wallet_id"] == "wallet_btc"
        assert normalized["currency"] == "EUR"


class TestBitpandaTransactionImport:
    """Tests for trade history import."""

    def test_get_trades_success(self):
        """Test successful retrieval of trade history."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "trade_001",
                    "type": "trade",
                    "attributes": {
                        "type": "buy",
                        "cryptocoin_symbol": "BTC",
                        "cryptocoin_id": "Bitcoin",
                        "amount": 0.05,
                        "price": 50000.00,
                        "bfx_fee": 2.50,
                        "fiat_id": "EUR",
                        "status": "finished",
                        "time": {
                            "date_iso8601": "2024-01-15T10:30:00Z",
                        },
                    },
                },
                {
                    "id": "trade_002",
                    "type": "trade",
                    "attributes": {
                        "type": "sell",
                        "cryptocoin_symbol": "ETH",
                        "cryptocoin_id": "Ethereum",
                        "amount": 1.0,
                        "price": 3000.00,
                        "bfx_fee": 1.50,
                        "fiat_id": "EUR",
                        "status": "finished",
                        "time": {
                            "date_iso8601": "2024-01-20T14:45:00Z",
                        },
                    },
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        trades = client.get_trades()

        assert len(trades) == 2
        assert trades[0]["attributes"]["type"] == "buy"
        assert trades[0]["attributes"]["cryptocoin_symbol"] == "BTC"
        assert trades[1]["attributes"]["type"] == "sell"
        assert trades[1]["attributes"]["cryptocoin_symbol"] == "ETH"

    def test_get_trades_with_date_range(self):
        """Test trade retrieval with date filter."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        client.get_trades(start_date=start_date, end_date=end_date)

        # Verify the request was made with date parameters
        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs
        assert "from" in call_args.kwargs["params"]
        assert "to" in call_args.kwargs["params"]

    def test_get_trades_pagination(self):
        """Test pagination parameters."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        client.get_trades(page=2, page_size=50)

        call_args = client._session.get.call_args
        assert call_args.kwargs["params"]["page"] == 2
        assert call_args.kwargs["params"]["page_size"] == 50

    def test_normalize_trade(self):
        """Test normalization of trade data."""
        client = BitpandaClient(api_key="test_key")

        raw_trade = {
            "id": "trade_001",
            "type": "trade",
            "attributes": {
                "type": "buy",
                "cryptocoin_symbol": "BTC",
                "cryptocoin_id": "Bitcoin",
                "amount": "0.1",
                "price": "45000.00",
                "bfx_fee": "1.00",
                "fiat_id": "EUR",
                "status": "finished",
                "time": {
                    "date_iso8601": "2024-02-15T10:30:00Z",
                },
            },
        }

        normalized = client._normalize_trade(raw_trade)

        assert normalized["external_id"] == "trade_001"
        assert normalized["transaction_type"] == "buy"
        assert normalized["symbol"] == "BTC"
        assert normalized["quantity"] == 0.1
        assert normalized["price"] == 45000.00
        assert normalized["fees"] == 1.00
        assert normalized["currency"] == "EUR"
        assert normalized["status"] == "finished"

    def test_normalize_trade_sell(self):
        """Test normalization of sell trade."""
        client = BitpandaClient(api_key="test_key")

        raw_trade = {
            "id": "trade_002",
            "type": "trade",
            "attributes": {
                "type": "sell",
                "cryptocoin_symbol": "ETH",
                "cryptocoin_id": "Ethereum",
                "amount": "2.0",
                "price": "3000.00",
                "bfx_fee": "0.50",
                "fiat_id": "EUR",
                "status": "finished",
                "time": {
                    "date_iso8601": "2024-02-16T14:00:00Z",
                },
            },
        }

        normalized = client._normalize_trade(raw_trade)

        assert normalized["transaction_type"] == "sell"
        assert normalized["symbol"] == "ETH"
        assert normalized["quantity"] == 2.0


class TestBitpandaFiatWallets:
    """Tests for fiat wallet operations."""

    def test_get_fiat_wallets_success(self):
        """Test successful retrieval of fiat wallets."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "fiat_eur",
                    "type": "fiat_wallet",
                    "attributes": {
                        "fiat_symbol": "EUR",
                        "balance": 1000.00,
                        "name": "Euro Wallet",
                    },
                },
                {
                    "id": "fiat_chf",
                    "type": "fiat_wallet",
                    "attributes": {
                        "fiat_symbol": "CHF",
                        "balance": 500.00,
                        "name": "Swiss Franc Wallet",
                    },
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        wallets = client.get_fiat_wallets()

        assert len(wallets) == 2
        assert wallets[0]["attributes"]["fiat_symbol"] == "EUR"
        assert wallets[1]["attributes"]["fiat_symbol"] == "CHF"


class TestBitpandaSyncPortfolio:
    """Tests for full portfolio sync."""

    def test_sync_portfolio_success(self):
        """Test successful full portfolio sync."""
        client = BitpandaClient(api_key="test_key")

        # Mock wallets response
        wallets_response = Mock()
        wallets_response.status_code = 200
        wallets_response.json.return_value = {
            "data": [
                {
                    "id": "wallet_btc",
                    "type": "wallet",
                    "attributes": {
                        "name": "Bitcoin",
                        "cryptocoin_symbol": "BTC",
                        "balance": 0.5,
                        "available": 0.5,
                    },
                }
            ]
        }

        # Mock trades response
        trades_response = Mock()
        trades_response.status_code = 200
        trades_response.json.return_value = {
            "data": [
                {
                    "id": "trade_001",
                    "type": "trade",
                    "attributes": {
                        "type": "buy",
                        "cryptocoin_symbol": "BTC",
                        "cryptocoin_id": "Bitcoin",
                        "amount": 0.5,
                        "price": 45000.00,
                        "bfx_fee": 2.0,
                        "fiat_id": "EUR",
                        "status": "finished",
                        "time": {"date_iso8601": "2024-01-15T10:00:00Z"},
                    },
                }
            ]
        }

        def mock_get(*args, **kwargs):
            url = args[0] if args else ""
            if "wallets" in url:
                return wallets_response
            elif "trades" in url:
                return trades_response
            return Mock(status_code=404)

        client._session.get = Mock(side_effect=mock_get)

        result = client.sync_portfolio()

        assert result["success"] is True
        assert len(result["holdings"]) == 1
        assert len(result["transactions"]) == 1
        assert result["holdings"][0]["symbol"] == "BTC"
        assert result["transactions"][0]["symbol"] == "BTC"

    def test_sync_portfolio_auth_error(self):
        """Test sync with authentication failure."""
        client = BitpandaClient(api_key="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"detail": "Invalid API key"}]}
        client._session.get = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "Authentication failed" in result["error"]
        assert result["holdings"] == []
        assert result["transactions"] == []

    def test_sync_portfolio_rate_limit(self):
        """Test sync with rate limit error."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"errors": [{"detail": "Rate limit"}]}
        client._session.get = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        assert "60" in result["error"]


class TestBitpandaValidateConnection:
    """Tests for connection validation."""

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        client = BitpandaClient(api_key="valid_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "user_123",
                "type": "user",
                "attributes": {
                    "email": "user@example.com",
                    "status": "active",
                },
            }
        }
        client._session.get = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()

        assert is_valid is True
        assert error is None

    def test_validate_connection_invalid_key(self):
        """Test validation with invalid API key."""
        client = BitpandaClient(api_key="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"detail": "Invalid key"}]}
        client._session.get = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()

        assert is_valid is False
        assert "Authentication failed" in error

    def test_validate_connection_empty_response(self):
        """Test validation with empty response data."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": None}
        client._session.get = Mock(return_value=mock_response)

        is_valid, error = client.validate_connection()

        assert is_valid is False
        assert "Invalid response" in error


class TestBitpandaErrorHandling:
    """Tests for error handling scenarios."""

    def test_connection_error(self):
        """Test handling of connection errors."""
        client = BitpandaClient(api_key="test_key")
        client._session.get = Mock(
            side_effect=Exception("Connection refused")
        )

        with pytest.raises(BitpandaAPIError):
            client.get_account_info()

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        import requests

        client = BitpandaClient(api_key="test_key")
        client._session.get = Mock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        with pytest.raises(BitpandaAPIError) as exc_info:
            client.get_account_info()

        assert "timeout" in str(exc_info.value).lower()

    def test_malformed_json_response(self):
        """Test handling of invalid JSON response."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaAPIError) as exc_info:
            client.get_account_info()

        assert "Invalid JSON" in str(exc_info.value)

    def test_server_error_500(self):
        """Test handling of 500 server error."""
        client = BitpandaClient(api_key="test_key")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"errors": [{"detail": "Internal server error"}]}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(BitpandaAPIError) as exc_info:
            client.get_account_info()

        assert exc_info.value.status_code == 500


class TestBitpandaContextManager:
    """Tests for context manager usage."""

    def test_context_manager(self):
        """Test client works as context manager."""
        with BitpandaClient(api_key="test_key") as client:
            assert client.api_key == "test_key"
            # Context manager should not raise

    def test_context_manager_closes_session(self):
        """Test that context manager closes session on exit."""
        client = BitpandaClient(api_key="test_key")
        client._session.close = Mock()

        with client:
            pass

        client._session.close.assert_called_once()
