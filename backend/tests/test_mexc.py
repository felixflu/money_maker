"""
Tests for MEXC integration.

TDD: Tests for MEXC API client with mocked responses.
Tests cover: sync holdings, transaction import, error handling, rate limits.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from app.integrations.mexc import (
    MexcClient,
    MexcAPIError,
    MexcRateLimitError,
    MexcAuthError,
)


class TestMexcClient:
    """Tests for the MEXC API client."""

    def test_client_initialization(self):
        """Test client initializes with credentials."""
        client = MexcClient(
            api_key="test_key",
            api_secret="test_secret",
        )
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api.mexc.com"
        assert client.timeout == 30

    def test_client_initialization_with_custom_timeout(self):
        """Test client initializes with custom timeout."""
        client = MexcClient(
            api_key="test_key",
            api_secret="test_secret",
            timeout=60,
        )
        assert client.timeout == 60


class TestMexcAuthentication:
    """Tests for MEXC authentication."""

    def test_successful_authentication(self):
        """Test successful authentication returns token."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        # Mock the session.get method for test connectivity
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        client._session.get = Mock(return_value=mock_response)

        # MEXC uses signature-based auth, authenticate validates credentials
        result = client.authenticate()

        assert result is True
        client._session.get.assert_called_once()

    def test_authentication_failure_invalid_key(self):
        """Test authentication failure raises error."""
        client = MexcClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"msg": "Invalid API key", "code": -2015}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcAuthError):
            client.authenticate()

    def test_authentication_rate_limit(self):
        """Test rate limit during authentication raises error."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"msg": "Rate limit exceeded"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcRateLimitError) as exc_info:
            client.authenticate()

        assert exc_info.value.retry_after == 60


class TestMexcPortfolioSync:
    """Tests for portfolio/holdings synchronization."""

    def test_get_holdings_success(self):
        """Test successful retrieval of crypto holdings."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.5",
                    "locked": "0.1",
                },
                {
                    "asset": "ETH",
                    "free": "2.5",
                    "locked": "0.5",
                },
                {
                    "asset": "USDT",
                    "free": "1000.0",
                    "locked": "0.0",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        assert len(holdings) == 3
        assert holdings[0]["asset"] == "BTC"
        assert holdings[0]["free"] == "0.5"
        assert holdings[0]["locked"] == "0.1"
        assert holdings[1]["asset"] == "ETH"

    def test_get_holdings_empty_portfolio(self):
        """Test handling empty portfolio."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balances": []}
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        assert holdings == []

    def test_get_holdings_with_zero_balances(self):
        """Test filtering out zero balance assets."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.5",
                    "locked": "0.0",
                },
                {
                    "asset": "EMPTY",
                    "free": "0.0",
                    "locked": "0.0",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        # Zero balance assets should be filtered out
        assert len(holdings) == 1
        assert holdings[0]["asset"] == "BTC"

    def test_get_holdings_unauthorized(self):
        """Test handling unauthorized access to holdings."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"msg": "Invalid API key"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcAuthError):
            client.get_holdings()

    def test_get_holdings_rate_limit(self):
        """Test rate limiting on holdings endpoint."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"msg": "Rate limit exceeded"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcRateLimitError) as exc_info:
            client.get_holdings()

        assert exc_info.value.retry_after == 30


class TestMexcTransactionImport:
    """Tests for transaction history import."""

    def test_get_transactions_success(self):
        """Test successful retrieval of transaction history."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "id": "tx_001",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "type": "MARKET",
                    "price": "45000.00",
                    "qty": "0.01",
                    "quoteQty": "450.00",
                    "commission": "0.45",
                    "commissionAsset": "USDT",
                    "time": 1705312800000,  # 2024-01-15 10:00:00 UTC
                    "isBuyer": True,
                },
                {
                    "id": "tx_002",
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                    "type": "LIMIT",
                    "price": "2800.00",
                    "qty": "0.5",
                    "quoteQty": "1400.00",
                    "commission": "1.40",
                    "commissionAsset": "USDT",
                    "time": 1705399200000,  # 2024-01-16 10:00:00 UTC
                    "isBuyer": False,
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions()

        assert len(transactions) == 2
        assert transactions[0]["symbol"] == "BTCUSDT"
        assert transactions[0]["side"] == "BUY"
        assert transactions[1]["symbol"] == "ETHUSDT"
        assert transactions[1]["side"] == "SELL"

    def test_get_transactions_with_date_range(self):
        """Test transaction retrieval with date filter."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"list": []}
        client._session.get = Mock(return_value=mock_response)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        client.get_transactions(start_date=start_date, end_date=end_date)

        # Verify the request was made with timestamp parameters
        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs

    def test_get_transactions_pagination(self):
        """Test transaction retrieval with pagination."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {"id": "tx_001", "symbol": "BTCUSDT", "side": "BUY"},
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions(limit=1)

        assert len(transactions) == 1


class TestMexcErrorHandling:
    """Tests for error handling scenarios."""

    def test_network_error(self):
        """Test handling of network errors."""
        import requests

        client = MexcClient(api_key="test_key", api_secret="test_secret")
        client._session.get = Mock(
            side_effect=requests.exceptions.ConnectionError("Network error")
        )

        with pytest.raises(MexcAPIError) as exc_info:
            client.get_holdings()

        assert "Connection error" in str(exc_info.value)

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        import requests

        client = MexcClient(api_key="test_key", api_secret="test_secret")
        client._session.get = Mock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        with pytest.raises(MexcAPIError) as exc_info:
            client.get_holdings()

        assert "timeout" in str(exc_info.value).lower()

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcAPIError):
            client.get_holdings()

    def test_server_error(self):
        """Test handling of 5xx server errors."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"msg": "Service unavailable"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcAPIError) as exc_info:
            client.get_holdings()

        assert exc_info.value.status_code == 503

    def test_ip_ban_error(self):
        """Test handling of IP ban (418)."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 418
        mock_response.json.return_value = {"msg": "IP auto banned"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(MexcRateLimitError) as exc_info:
            client.get_holdings()

        assert "IP banned" in str(exc_info.value).lower()


class TestMexcSyncService:
    """Tests for the high-level sync service."""

    def test_full_sync_success(self):
        """Test successful full sync of holdings and transactions."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        # Mock account response (for authenticate)
        mock_account_response = Mock()
        mock_account_response.status_code = 200
        mock_account_response.json.return_value = {"balances": []}

        # Mock holdings
        mock_holdings_response = Mock()
        mock_holdings_response.status_code = 200
        mock_holdings_response.json.return_value = {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.5",
                    "locked": "0.1",
                }
            ]
        }

        # Mock transactions
        mock_tx_response = Mock()
        mock_tx_response.status_code = 200
        mock_tx_response.json.return_value = {
            "list": [
                {
                    "id": "tx_001",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "type": "MARKET",
                    "price": "45000.00",
                    "qty": "0.01",
                    "quoteQty": "450.00",
                    "commission": "0.45",
                    "commissionAsset": "USDT",
                    "time": 1705312800000,
                    "isBuyer": True,
                }
            ]
        }

        # Set up mock to return different responses for different calls
        client._session.get = Mock(
            side_effect=[
                mock_account_response,
                mock_holdings_response,
                mock_tx_response,
            ]
        )

        result = client.sync_portfolio()

        assert result["success"] is True
        assert len(result["holdings"]) == 1
        assert len(result["transactions"]) == 1
        assert result["holdings"][0]["symbol"] == "BTC"

    def test_sync_authentication_failure(self):
        """Test sync fails gracefully when authentication fails."""
        client = MexcClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"msg": "Invalid API key"}
        client._session.get = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "error" in result
        assert "authentication" in result["error"].lower()

    def test_sync_rate_limit_failure(self):
        """Test sync fails gracefully with rate limit error."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"msg": "Rate limit exceeded"}
        client._session.get = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "rate limit" in result["error"].lower()


class TestMexcRateLimiting:
    """Tests for rate limit handling."""

    def test_rate_limit_error_attributes(self):
        """Test rate limit error has correct attributes."""
        error = MexcRateLimitError(
            message="Rate limit exceeded",
            retry_after=60,
            status_code=429,
        )

        assert error.retry_after == 60
        assert error.status_code == 429
        assert "Rate limit exceeded" in str(error)

    def test_weight_header_extraction(self):
        """Test extraction of rate limit weight headers."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balances": []}
        mock_response.headers = {
            "X-MBX-USED-WEIGHT-1M": "100",
        }
        client._session.get = Mock(return_value=mock_response)

        # Should not raise
        client.get_holdings()


class TestMexcDataTransformation:
    """Tests for data transformation and normalization."""

    def test_normalize_holding(self):
        """Test holding data normalization."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        raw_holding = {
            "asset": "BTC",
            "free": "0.5",
            "locked": "0.1",
        }

        normalized = client._normalize_holding(raw_holding)

        assert normalized["symbol"] == "BTC"
        assert normalized["asset_type"] == "cryptocurrency"
        assert normalized["quantity"] == Decimal("0.6")  # free + locked
        assert normalized["available"] == Decimal("0.5")
        assert normalized["locked"] == Decimal("0.1")

    def test_normalize_transaction_buy(self):
        """Test buy transaction data normalization."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        raw_transaction = {
            "id": "tx_001",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "price": "45000.00",
            "qty": "0.01",
            "quoteQty": "450.00",
            "commission": "0.45",
            "commissionAsset": "USDT",
            "time": 1705312800000,
            "isBuyer": True,
        }

        normalized = client._normalize_transaction(raw_transaction)

        assert normalized["external_id"] == "tx_001"
        assert normalized["transaction_type"] == "buy"
        assert normalized["symbol"] == "BTC"
        assert normalized["base_asset"] == "BTC"
        assert normalized["quote_asset"] == "USDT"
        assert normalized["quantity"] == Decimal("0.01")
        assert normalized["price"] == Decimal("45000.00")
        assert normalized["total_amount"] == Decimal("450.00")
        assert normalized["fees"] == Decimal("0.45")
        assert normalized["fee_asset"] == "USDT"

    def test_normalize_transaction_sell(self):
        """Test sell transaction data normalization."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        raw_transaction = {
            "id": "tx_002",
            "symbol": "ETHUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "price": "2800.00",
            "qty": "0.5",
            "quoteQty": "1400.00",
            "commission": "1.40",
            "commissionAsset": "USDT",
            "time": 1705399200000,
            "isBuyer": False,
        }

        normalized = client._normalize_transaction(raw_transaction)

        assert normalized["external_id"] == "tx_002"
        assert normalized["transaction_type"] == "sell"
        assert normalized["symbol"] == "ETH"

    def test_normalize_transaction_timestamp(self):
        """Test transaction timestamp conversion."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        # MEXC uses milliseconds timestamp
        raw_transaction = {
            "id": "tx_001",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "price": "45000.00",
            "qty": "0.01",
            "quoteQty": "450.00",
            "commission": "0.45",
            "commissionAsset": "USDT",
            "time": 1705312800000,  # 2024-01-15 10:00:00 UTC
            "isBuyer": True,
        }

        normalized = client._normalize_transaction(raw_transaction)

        # Verify timestamp is converted from milliseconds
        assert normalized["timestamp"] == datetime(2024, 1, 15, 10, 0, 0)


class TestMexcAPIEndpoints:
    """Tests for specific MEXC API endpoint behaviors."""

    def test_get_account_info(self):
        """Test retrieving account information."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "makerCommission": 10,
            "takerCommission": 10,
            "buyerCommission": 0,
            "sellerCommission": 0,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "updateTime": 1705312800000,
            "accountType": "SPOT",
            "balances": [],
        }
        client._session.get = Mock(return_value=mock_response)

        account_info = client.get_account_info()

        assert account_info["canTrade"] is True
        assert account_info["accountType"] == "SPOT"

    def test_get_symbol_price(self):
        """Test retrieving current symbol price."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "symbol": "BTCUSDT",
            "price": "45000.00",
        }
        client._session.get = Mock(return_value=mock_response)

        price = client.get_symbol_price("BTCUSDT")

        assert price == Decimal("45000.00")

    def test_get_symbol_price_ticker(self):
        """Test retrieving price ticker for symbol."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "symbol": "BTCUSDT",
            "priceChange": "1000.00",
            "priceChangePercent": "2.5",
            "weightedAvgPrice": "44500.00",
            "lastPrice": "45000.00",
            "volume": "1000.5",
        }
        client._session.get = Mock(return_value=mock_response)

        ticker = client.get_symbol_ticker("BTCUSDT")

        assert ticker["symbol"] == "BTCUSDT"
        assert ticker["lastPrice"] == "45000.00"


class TestMexcConnectionValidation:
    """Tests for connection validation and health checks."""

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "makerCommission": 10,
            "takerCommission": 10,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "accountType": "SPOT",
            "balances": [],
        }

        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is True
        assert error_message is None

    def test_validate_connection_auth_failure(self):
        """Test connection validation fails with bad credentials."""
        client = MexcClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"msg": "Invalid API key"}
        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert error_message is not None
        assert "authentication" in error_message.lower()

    def test_validate_connection_trading_disabled(self):
        """Test connection validation when trading is disabled."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "makerCommission": 10,
            "takerCommission": 10,
            "canTrade": False,
            "canWithdraw": True,
            "canDeposit": True,
            "accountType": "SPOT",
            "balances": [],
        }

        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is True  # Connection is valid even if trading disabled

    def test_validate_connection_ip_restriction(self):
        """Test connection validation with IP restriction."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"msg": "Unauthorized IP address"}
        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert "ip" in error_message.lower()


class TestMexcSignatureGeneration:
    """Tests for API signature generation."""

    def test_signature_generation(self):
        """Test HMAC signature is generated correctly."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        params = {"timestamp": "1705312800000"}
        signature = client._generate_signature(params)

        # Signature should be a hex string
        assert len(signature) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in signature)

    def test_request_includes_signature(self):
        """Test requests include signature parameter."""
        client = MexcClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balances": []}
        client._session.get = Mock(return_value=mock_response)

        client.get_holdings()

        # Verify the call included signature
        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs
        params = call_args.kwargs["params"]
        assert "signature" in params
        assert "timestamp" in params
