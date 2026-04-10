"""
Tests for Trade Republic integration.

TDD: Tests for Trade Republic API client with mocked responses.
Tests cover: sync holdings, transaction import, error handling, rate limits.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from app.integrations.trade_republic import (
    TradeRepublicClient,
    TradeRepublicAPIError,
    TradeRepublicRateLimitError,
    TradeRepublicAuthError,
)


class TestTradeRepublicClient:
    """Tests for the Trade Republic API client."""

    def test_client_initialization(self):
        """Test client initializes with credentials."""
        client = TradeRepublicClient(
            api_key="test_key",
            api_secret="test_secret",
        )
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api.traderepublic.com"
        assert client.timeout == 30

    def test_client_initialization_with_custom_timeout(self):
        """Test client initializes with custom timeout."""
        client = TradeRepublicClient(
            api_key="test_key",
            api_secret="test_secret",
            timeout=60,
        )
        assert client.timeout == 60


class TestTradeRepublicAuthentication:
    """Tests for Trade Republic authentication."""

    def test_successful_authentication(self):
        """Test successful authentication returns token."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        # Mock the session.post method
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token_123",
            "refresh_token": "refresh_token_456",
            "expires_in": 3600,
        }
        client._session.post = Mock(return_value=mock_response)

        token = client.authenticate()

        assert token == "test_token_123"
        assert client._access_token == "test_token_123"
        client._session.post.assert_called_once()

    def test_authentication_failure(self):
        """Test authentication failure raises error."""
        client = TradeRepublicClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.post = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicAuthError):
            client.authenticate()

    def test_authentication_rate_limit(self):
        """Test rate limit during authentication raises error."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        client._session.post = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicRateLimitError) as exc_info:
            client.authenticate()

        assert exc_info.value.retry_after == 60


class TestTradeRepublicPortfolioSync:
    """Tests for portfolio/holdings synchronization."""

    def test_get_holdings_success(self):
        """Test successful retrieval of ETF and crypto holdings."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "holdings": [
                {
                    "isin": "IE00B4L5Y983",
                    "name": "iShares Core MSCI World UCITS ETF",
                    "type": "etf",
                    "quantity": 10.5,
                    "current_price": 98.50,
                    "currency": "EUR",
                    "total_value": 1034.25,
                },
                {
                    "isin": "BTC",
                    "name": "Bitcoin",
                    "type": "cryptocurrency",
                    "quantity": 0.05,
                    "current_price": 52000.00,
                    "currency": "EUR",
                    "total_value": 2600.00,
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        assert len(holdings) == 2
        assert holdings[0]["type"] == "etf"
        assert holdings[0]["isin"] == "IE00B4L5Y983"
        assert holdings[1]["type"] == "cryptocurrency"
        assert holdings[1]["isin"] == "BTC"

    def test_get_holdings_empty_portfolio(self):
        """Test handling empty portfolio."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"holdings": []}
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        assert holdings == []

    def test_get_holdings_unauthorized(self):
        """Test handling unauthorized access to holdings."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Forbidden"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicAPIError):
            client.get_holdings()

    def test_get_holdings_rate_limit(self):
        """Test rate limiting on holdings endpoint."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicRateLimitError) as exc_info:
            client.get_holdings()

        assert exc_info.value.retry_after == 30


class TestTradeRepublicTransactionImport:
    """Tests for transaction history import."""

    def test_get_transactions_success(self):
        """Test successful retrieval of transaction history."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "id": "tx_001",
                    "type": "buy",
                    "isin": "IE00B4L5Y983",
                    "name": "iShares Core MSCI World UCITS ETF",
                    "quantity": 5.0,
                    "price": 95.20,
                    "total_amount": 476.00,
                    "fees": 1.00,
                    "currency": "EUR",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "status": "executed",
                },
                {
                    "id": "tx_002",
                    "type": "sell",
                    "isin": "BTC",
                    "name": "Bitcoin",
                    "quantity": 0.01,
                    "price": 48000.00,
                    "total_amount": 480.00,
                    "fees": 0.50,
                    "currency": "EUR",
                    "timestamp": "2024-01-20T14:45:00Z",
                    "status": "executed",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions()

        assert len(transactions) == 2
        assert transactions[0]["type"] == "buy"
        assert transactions[0]["isin"] == "IE00B4L5Y983"
        assert transactions[1]["type"] == "sell"
        assert transactions[1]["isin"] == "BTC"

    def test_get_transactions_with_date_range(self):
        """Test transaction retrieval with date filter."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transactions": []}
        client._session.get = Mock(return_value=mock_response)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        client.get_transactions(start_date=start_date, end_date=end_date)

        # Verify the request was made with date parameters
        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs

    def test_get_transactions_pagination(self):
        """Test transaction retrieval with pagination."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {"id": "tx_001", "type": "buy", "isin": "ETF1"},
            ],
            "next_cursor": "cursor_123",
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions(limit=1)

        assert len(transactions) == 1


class TestTradeRepublicErrorHandling:
    """Tests for error handling scenarios."""

    def test_network_error(self):
        """Test handling of network errors."""
        import requests

        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"
        client._session.get = Mock(
            side_effect=requests.exceptions.ConnectionError("Network error")
        )

        with pytest.raises(TradeRepublicAPIError) as exc_info:
            client.get_holdings()

        assert "Network error" in str(exc_info.value)

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        import requests

        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"
        client._session.get = Mock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        with pytest.raises(TradeRepublicAPIError) as exc_info:
            client.get_holdings()

        assert "timeout" in str(exc_info.value).lower()

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicAPIError):
            client.get_holdings()

    def test_server_error(self):
        """Test handling of 5xx server errors."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"error": "Service unavailable"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(TradeRepublicAPIError) as exc_info:
            client.get_holdings()

        assert exc_info.value.status_code == 503


class TestTradeRepublicSyncService:
    """Tests for the high-level sync service."""

    def test_full_sync_success(self):
        """Test successful full sync of holdings and transactions."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        # Mock authenticate
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "token_123",
            "expires_in": 3600,
        }

        # Mock holdings
        mock_holdings_response = Mock()
        mock_holdings_response.status_code = 200
        mock_holdings_response.json.return_value = {
            "holdings": [
                {
                    "isin": "IE00B4L5Y983",
                    "name": "iShares Core MSCI World UCITS ETF",
                    "type": "etf",
                    "quantity": 10.5,
                    "current_price": 98.50,
                    "currency": "EUR",
                    "total_value": 1034.25,
                }
            ]
        }

        # Mock transactions
        mock_tx_response = Mock()
        mock_tx_response.status_code = 200
        mock_tx_response.json.return_value = {
            "transactions": [
                {
                    "id": "tx_001",
                    "type": "buy",
                    "isin": "IE00B4L5Y983",
                    "quantity": 5.0,
                    "price": 95.20,
                    "total_amount": 476.00,
                    "timestamp": "2024-01-15T10:30:00Z",
                }
            ]
        }

        # Set up mock to return different responses for different calls
        client._session.post = Mock(return_value=mock_auth_response)
        client._session.get = Mock(
            side_effect=[mock_holdings_response, mock_tx_response]
        )

        result = client.sync_portfolio()

        assert result["success"] is True
        assert len(result["holdings"]) == 1
        assert len(result["transactions"]) == 1
        assert result["holdings"][0]["asset_type"] == "etf"

    def test_sync_authentication_failure(self):
        """Test sync fails gracefully when authentication fails."""
        client = TradeRepublicClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.post = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "error" in result
        assert "authentication" in result["error"].lower()


class TestTradeRepublicRateLimiting:
    """Tests for rate limit handling."""

    def test_rate_limit_error_attributes(self):
        """Test rate limit error has correct attributes."""
        error = TradeRepublicRateLimitError(
            message="Rate limit exceeded",
            retry_after=60,
            status_code=429,
        )

        assert error.retry_after == 60
        assert error.status_code == 429
        assert "Rate limit exceeded" in str(error)

    def test_rate_limit_backoff_strategy(self):
        """Test client respects rate limit headers."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        # First call hits rate limit
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        client._session.get = Mock(return_value=mock_response_429)

        # First call should raise rate limit error
        with pytest.raises(TradeRepublicRateLimitError):
            client.get_holdings()


class TestTradeRepublicDataTransformation:
    """Tests for data transformation and normalization."""

    def test_normalize_etf_holding(self):
        """Test ETF holding data normalization."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        raw_holding = {
            "isin": "IE00B4L5Y983",
            "name": "iShares Core MSCI World UCITS ETF",
            "type": "etf",
            "quantity": 10.5,
            "current_price": 98.50,
            "currency": "EUR",
            "total_value": 1034.25,
        }

        normalized = client._normalize_holding(raw_holding)

        assert normalized["symbol"] == "IE00B4L5Y983"
        assert normalized["name"] == "iShares Core MSCI World UCITS ETF"
        assert normalized["asset_type"] == "etf"
        assert normalized["quantity"] == Decimal("10.5")
        assert normalized["current_price"] == Decimal("98.50")

    def test_normalize_crypto_holding(self):
        """Test cryptocurrency holding data normalization."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        raw_holding = {
            "isin": "BTC",
            "name": "Bitcoin",
            "type": "cryptocurrency",
            "quantity": 0.05,
            "current_price": 52000.00,
            "currency": "EUR",
            "total_value": 2600.00,
        }

        normalized = client._normalize_holding(raw_holding)

        assert normalized["symbol"] == "BTC"
        assert normalized["asset_type"] == "cryptocurrency"
        assert normalized["quantity"] == Decimal("0.05")

    def test_normalize_transaction(self):
        """Test transaction data normalization."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        raw_transaction = {
            "id": "tx_001",
            "type": "buy",
            "isin": "IE00B4L5Y983",
            "name": "iShares Core MSCI World UCITS ETF",
            "quantity": 5.0,
            "price": 95.20,
            "total_amount": 476.00,
            "fees": 1.00,
            "currency": "EUR",
            "timestamp": "2024-01-15T10:30:00Z",
            "status": "executed",
        }

        normalized = client._normalize_transaction(raw_transaction)

        assert normalized["external_id"] == "tx_001"
        assert normalized["transaction_type"] == "buy"
        assert normalized["symbol"] == "IE00B4L5Y983"
        assert normalized["quantity"] == Decimal("5.0")
        assert normalized["price"] == Decimal("95.20")
        assert normalized["fees"] == Decimal("1.00")


class TestTradeRepublicAPIEndpoints:
    """Tests for specific Trade Republic API endpoint behaviors."""

    def test_get_account_info(self):
        """Test retrieving account information."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "account_id": "acc_123",
            "account_type": "individual",
            "currency": "EUR",
            "status": "active",
            "created_at": "2020-01-01T00:00:00Z",
        }
        client._session.get = Mock(return_value=mock_response)

        account_info = client.get_account_info()

        assert account_info["account_id"] == "acc_123"
        assert account_info["currency"] == "EUR"
        assert account_info["status"] == "active"

    def test_get_instrument_details(self):
        """Test retrieving instrument details by ISIN."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")
        client._access_token = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "isin": "IE00B4L5Y983",
            "name": "iShares Core MSCI World UCITS ETF",
            "type": "etf",
            "exchange": "XETRA",
            "currency": "EUR",
        }
        client._session.get = Mock(return_value=mock_response)

        instrument = client.get_instrument_details("IE00B4L5Y983")

        assert instrument["isin"] == "IE00B4L5Y983"
        assert instrument["type"] == "etf"


class TestTradeRepublicConnectionValidation:
    """Tests for connection validation and health checks."""

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        # Mock authenticate
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "token_123",
            "expires_in": 3600,
        }

        # Mock account info
        mock_account_response = Mock()
        mock_account_response.status_code = 200
        mock_account_response.json.return_value = {
            "account_id": "acc_123",
            "status": "active",
        }

        client._session.post = Mock(return_value=mock_auth_response)
        client._session.get = Mock(return_value=mock_account_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is True
        assert error_message is None

    def test_validate_connection_auth_failure(self):
        """Test connection validation fails with bad credentials."""
        client = TradeRepublicClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.post = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert error_message is not None
        assert "authentication" in error_message.lower()

    def test_validate_connection_inactive_account(self):
        """Test connection validation fails with inactive account."""
        client = TradeRepublicClient(api_key="test_key", api_secret="test_secret")

        # Mock authenticate
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "token_123",
            "expires_in": 3600,
        }

        # Mock inactive account
        mock_account_response = Mock()
        mock_account_response.status_code = 200
        mock_account_response.json.return_value = {
            "account_id": "acc_123",
            "status": "inactive",
        }

        client._session.post = Mock(return_value=mock_auth_response)
        client._session.get = Mock(return_value=mock_account_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert "inactive" in error_message.lower()
