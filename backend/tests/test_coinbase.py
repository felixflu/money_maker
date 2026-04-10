"""
Tests for Coinbase integration.

TDD: Tests for Coinbase API client with mocked responses.
Tests cover: sync holdings, transaction import, error handling, rate limits.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from app.integrations.coinbase import (
    CoinbaseClient,
    CoinbaseAPIError,
    CoinbaseRateLimitError,
    CoinbaseAuthError,
)


class TestCoinbaseClient:
    """Tests for the Coinbase API client."""

    def test_client_initialization(self):
        """Test client initializes with credentials."""
        client = CoinbaseClient(
            api_key="test_key",
            api_secret="test_secret",
        )
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api.coinbase.com"
        assert client.timeout == 30

    def test_client_initialization_with_custom_timeout(self):
        """Test client initializes with custom timeout."""
        client = CoinbaseClient(
            api_key="test_key",
            api_secret="test_secret",
            timeout=60,
        )
        assert client.timeout == 60

    def test_client_headers(self):
        """Test client generates correct headers."""
        client = CoinbaseClient(
            api_key="test_key",
            api_secret="test_secret",
        )
        headers = client._get_headers()
        assert headers["CB-ACCESS-KEY"] == "test_key"
        assert headers["CB-VERSION"] == "2024-01-01"
        assert headers["Content-Type"] == "application/json"


class TestCoinbaseAuthentication:
    """Tests for Coinbase authentication."""

    def test_authentication_failure_401(self):
        """Test authentication failure raises error."""
        client = CoinbaseClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAuthError):
            client.get_account_info()

    def test_authentication_forbidden_403(self):
        """Test forbidden access raises error."""
        client = CoinbaseClient(api_key="valid", api_secret="valid")

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Forbidden"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAuthError):
            client.get_account_info()

    def test_authentication_rate_limit(self):
        """Test rate limit during authentication raises error."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseRateLimitError) as exc_info:
            client.get_account_info()

        assert exc_info.value.retry_after == 60


class TestCoinbaseAccounts:
    """Tests for account retrieval."""

    def test_get_accounts_success(self):
        """Test successful retrieval of accounts."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "acc_001",
                    "name": "BTC Wallet",
                    "currency": {"code": "BTC", "name": "Bitcoin"},
                    "balance": {"amount": "1.5", "currency": "BTC"},
                    "type": "wallet",
                },
                {
                    "id": "acc_002",
                    "name": "ETH Wallet",
                    "currency": {"code": "ETH", "name": "Ethereum"},
                    "balance": {"amount": "10.0", "currency": "ETH"},
                    "type": "wallet",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        accounts = client.get_accounts()

        assert len(accounts) == 2
        assert accounts[0]["currency"]["code"] == "BTC"
        assert accounts[1]["currency"]["code"] == "ETH"

    def test_get_accounts_empty(self):
        """Test handling empty accounts list."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        accounts = client.get_accounts()

        assert accounts == []


class TestCoinbaseHoldingsSync:
    """Tests for portfolio/holdings synchronization."""

    def test_get_holdings_success(self):
        """Test successful retrieval of crypto holdings."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "btc_wallet",
                    "name": "BTC Wallet",
                    "currency": {"code": "BTC", "name": "Bitcoin"},
                    "balance": {"amount": "1.5", "currency": "BTC"},
                    "type": "wallet",
                },
                {
                    "id": "eth_wallet",
                    "name": "ETH Wallet",
                    "currency": {"code": "ETH", "name": "Ethereum"},
                    "balance": {"amount": "10.0", "currency": "ETH"},
                    "type": "wallet",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        assert len(holdings) == 2
        assert holdings[0]["currency"] == "BTC"
        assert holdings[0]["quantity"] == Decimal("1.5")
        assert holdings[1]["currency"] == "ETH"
        assert holdings[1]["quantity"] == Decimal("10.0")

    def test_get_holdings_empty_portfolio(self):
        """Test handling empty portfolio."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "btc_wallet",
                    "name": "BTC Wallet",
                    "currency": {"code": "BTC"},
                    "balance": {"amount": "0.0", "currency": "BTC"},
                    "type": "wallet",
                }
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        holdings = client.get_holdings()

        # Zero balance accounts are filtered out
        assert holdings == []

    def test_get_holdings_unauthorized(self):
        """Test handling unauthorized access to holdings."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Forbidden"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAPIError):
            client.get_accounts()

    def test_get_holdings_rate_limit(self):
        """Test rate limiting on holdings endpoint."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseRateLimitError) as exc_info:
            client.get_accounts()

        assert exc_info.value.retry_after == 30


class TestCoinbaseTransactionImport:
    """Tests for transaction history import."""

    def test_get_transactions_success(self):
        """Test successful retrieval of transaction history."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "tx_001",
                    "type": "buy",
                    "status": "completed",
                    "amount": {"amount": "0.5", "currency": "BTC"},
                    "native_amount": {"amount": "25000.00", "currency": "USD"},
                    "created_at": "2024-01-15T10:30:00Z",
                },
                {
                    "id": "tx_002",
                    "type": "sell",
                    "status": "completed",
                    "amount": {"amount": "0.1", "currency": "BTC"},
                    "native_amount": {"amount": "5000.00", "currency": "USD"},
                    "created_at": "2024-01-20T14:45:00Z",
                },
            ]
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions("account_123")

        assert len(transactions) == 2
        assert transactions[0]["type"] == "buy"
        assert transactions[1]["type"] == "sell"

    def test_get_transactions_with_date_range(self):
        """Test transaction retrieval with date filter."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        client.get_transactions(
            "account_123",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify the request was made with date parameters
        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs

    def test_get_transactions_pagination(self):
        """Test transaction retrieval with pagination."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "tx_001", "type": "buy"},
            ],
            "pagination": {"next_cursor": "cursor_123"},
        }
        client._session.get = Mock(return_value=mock_response)

        transactions = client.get_transactions("account_123", limit=1)

        assert len(transactions) == 1

    def test_get_all_transactions(self):
        """Test retrieving transactions from all accounts."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        # Mock accounts response
        mock_accounts_response = Mock()
        mock_accounts_response.status_code = 200
        mock_accounts_response.json.return_value = {
            "data": [
                {
                    "id": "acc_001",
                    "name": "BTC Wallet",
                    "currency": {"code": "BTC"},
                },
                {
                    "id": "acc_002",
                    "name": "ETH Wallet",
                    "currency": {"code": "ETH"},
                },
            ]
        }

        # Mock transactions response
        mock_tx_response = Mock()
        mock_tx_response.status_code = 200
        mock_tx_response.json.return_value = {
            "data": [
                {"id": "tx_001", "type": "buy", "created_at": "2024-01-15T10:30:00Z"},
            ]
        }

        client._session.get = Mock(
            side_effect=[mock_accounts_response, mock_tx_response, mock_tx_response]
        )

        transactions = client.get_all_transactions()

        assert len(transactions) == 2
        assert transactions[0]["account_currency"] == "BTC"
        assert transactions[1]["account_currency"] == "ETH"


class TestCoinbaseErrorHandling:
    """Tests for error handling scenarios."""

    def test_network_error(self):
        """Test handling of network errors."""
        import requests

        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")
        client._session.get = Mock(
            side_effect=requests.exceptions.ConnectionError("Network error")
        )

        with pytest.raises(CoinbaseAPIError) as exc_info:
            client.get_accounts()

        assert "Connection error" in str(exc_info.value)

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        import requests

        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")
        client._session.get = Mock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        with pytest.raises(CoinbaseAPIError) as exc_info:
            client.get_accounts()

        assert "timeout" in str(exc_info.value).lower()

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAPIError):
            client.get_accounts()

    def test_server_error(self):
        """Test handling of 5xx server errors."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"error": "Service unavailable"}
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAPIError) as exc_info:
            client.get_accounts()

        assert exc_info.value.status_code == 503

    def test_error_with_errors_array(self):
        """Test handling errors in array format."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid parameter", "code": "invalid"}]
        }
        client._session.get = Mock(return_value=mock_response)

        with pytest.raises(CoinbaseAPIError) as exc_info:
            client.get_accounts()

        assert "Invalid parameter" in str(exc_info.value)


class TestCoinbaseSyncService:
    """Tests for the high-level sync service."""

    def test_full_sync_success(self):
        """Test successful full sync of holdings and transactions."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        # Mock accounts
        mock_accounts_response = Mock()
        mock_accounts_response.status_code = 200
        mock_accounts_response.json.return_value = {
            "data": [
                {
                    "id": "btc_wallet",
                    "name": "BTC Wallet",
                    "currency": {"code": "BTC", "name": "Bitcoin"},
                    "balance": {"amount": "1.5", "currency": "BTC"},
                    "type": "wallet",
                }
            ]
        }

        # Mock price
        mock_price_response = Mock()
        mock_price_response.status_code = 200
        mock_price_response.json.return_value = {
            "data": {"amount": "50000.00", "currency": "USD"}
        }

        # Mock transactions
        mock_tx_response = Mock()
        mock_tx_response.status_code = 200
        mock_tx_response.json.return_value = {
            "data": [
                {
                    "id": "tx_001",
                    "type": "buy",
                    "status": "completed",
                    "amount": {"amount": "0.5", "currency": "BTC"},
                    "native_amount": {"amount": "25000.00", "currency": "USD"},
                    "created_at": "2024-01-15T10:30:00Z",
                    "account_currency": "BTC",
                    "account_name": "BTC Wallet",
                }
            ]
        }

        client._session.get = Mock(
            side_effect=[
                mock_accounts_response,
                mock_price_response,
                mock_accounts_response,
                mock_tx_response,
            ]
        )

        result = client.sync_portfolio()

        assert result["success"] is True
        assert len(result["holdings"]) == 1
        assert len(result["transactions"]) == 1
        assert result["holdings"][0]["asset_type"] == "cryptocurrency"

    def test_sync_authentication_failure(self):
        """Test sync fails gracefully when authentication fails."""
        client = CoinbaseClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.get = Mock(return_value=mock_response)

        result = client.sync_portfolio()

        assert result["success"] is False
        assert "error" in result
        assert "authentication" in result["error"].lower()


class TestCoinbaseRateLimiting:
    """Tests for rate limit handling."""

    def test_rate_limit_error_attributes(self):
        """Test rate limit error has correct attributes."""
        error = CoinbaseRateLimitError(
            message="Rate limit exceeded",
            retry_after=60,
            status_code=429,
        )

        assert error.retry_after == 60
        assert error.status_code == 429
        assert "Rate limit exceeded" in str(error)

    def test_rate_limit_backoff_strategy(self):
        """Test client respects rate limit headers."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        # First call hits rate limit
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}
        mock_response_429.json.return_value = {"error": "Rate limit"}

        client._session.get = Mock(return_value=mock_response_429)

        # First call should raise rate limit error
        with pytest.raises(CoinbaseRateLimitError):
            client.get_accounts()


class TestCoinbaseDataTransformation:
    """Tests for data transformation and normalization."""

    def test_normalize_holding(self):
        """Test holding data normalization."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        raw_holding = {
            "id": "btc_wallet",
            "currency": "BTC",
            "name": "BTC Wallet",
            "balance": Decimal("1.5"),
            "type": "wallet",
        }

        normalized = client._normalize_holding(raw_holding)

        assert normalized["symbol"] == "BTC"
        assert normalized["name"] == "BTC Wallet"
        assert normalized["asset_type"] == "cryptocurrency"
        assert normalized["quantity"] == Decimal("1.5")
        assert normalized["currency"] == "BTC"

    def test_normalize_transaction(self):
        """Test transaction data normalization."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        raw_transaction = {
            "id": "tx_001",
            "type": "buy",
            "status": "completed",
            "amount": {"amount": "0.5", "currency": "BTC"},
            "native_amount": {"amount": "25000.00", "currency": "USD"},
            "created_at": "2024-01-15T10:30:00Z",
            "account_currency": "BTC",
            "account_name": "BTC Wallet",
        }

        normalized = client._normalize_transaction(raw_transaction)

        assert normalized["external_id"] == "tx_001"
        assert normalized["transaction_type"] == "buy"
        assert normalized["symbol"] == "BTC"
        assert normalized["quantity"] == Decimal("0.5")
        assert normalized["total_amount"] == Decimal("25000.00")
        assert normalized["currency"] == "USD"

    def test_normalize_transfer_transaction(self):
        """Test transfer transaction normalization."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        raw_transaction = {
            "id": "tx_002",
            "type": "send",
            "status": "completed",
            "amount": {"amount": "0.1", "currency": "BTC"},
            "native_amount": {"amount": "5000.00", "currency": "USD"},
            "created_at": "2024-01-20T14:45:00Z",
            "account_currency": "BTC",
            "account_name": "BTC Wallet",
        }

        normalized = client._normalize_transaction(raw_transaction)

        assert normalized["external_id"] == "tx_002"
        assert normalized["transaction_type"] == "transfer"


class TestCoinbaseAPIEndpoints:
    """Tests for specific Coinbase API endpoint behaviors."""

    def test_get_account_info(self):
        """Test retrieving account information."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "user_123",
                "name": "Test User",
                "email": "test@example.com",
                "state": "active",
                "created_at": "2020-01-01T00:00:00Z",
            }
        }
        client._session.get = Mock(return_value=mock_response)

        account_info = client.get_account_info()

        assert account_info["id"] == "user_123"
        assert account_info["email"] == "test@example.com"
        assert account_info["state"] == "active"

    def test_get_exchange_rates(self):
        """Test retrieving exchange rates."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "currency": "USD",
                "rates": {"BTC": "0.00002", "ETH": "0.0004"},
            }
        }
        client._session.get = Mock(return_value=mock_response)

        rates = client.get_exchange_rates("USD")

        assert rates["data"]["currency"] == "USD"
        assert "BTC" in rates["data"]["rates"]

    def test_get_buy_price(self):
        """Test retrieving buy price."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"amount": "50000.00", "currency": "USD"}
        }
        client._session.get = Mock(return_value=mock_response)

        price = client.get_buy_price("BTC-USD")

        assert price["data"]["amount"] == "50000.00"

    def test_get_sell_price(self):
        """Test retrieving sell price."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"amount": "49500.00", "currency": "USD"}
        }
        client._session.get = Mock(return_value=mock_response)

        price = client.get_sell_price("BTC-USD")

        assert price["data"]["amount"] == "49500.00"


class TestCoinbaseConnectionValidation:
    """Tests for connection validation and health checks."""

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        # Mock user info
        mock_user_response = Mock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "data": {
                "id": "user_123",
                "email": "test@example.com",
                "state": "active",
            }
        }

        client._session.get = Mock(return_value=mock_user_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is True
        assert error_message is None

    def test_validate_connection_auth_failure(self):
        """Test connection validation fails with bad credentials."""
        client = CoinbaseClient(api_key="invalid", api_secret="invalid")

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert error_message is not None
        assert "authentication" in error_message.lower()

    def test_validate_connection_closed_account(self):
        """Test connection validation fails with closed account."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "user_123",
                "email": "test@example.com",
                "state": "closed",
            }
        }

        client._session.get = Mock(return_value=mock_response)

        is_valid, error_message = client.validate_connection()

        assert is_valid is False
        assert "closed" in error_message.lower()


class TestCoinbaseContextManager:
    """Tests for context manager usage."""

    def test_context_manager_enter(self):
        """Test context manager entry."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        with client as c:
            assert c is client
            assert c._session is not None

    def test_context_manager_exit(self):
        """Test context manager exit closes session."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        with patch.object(client._session, "close") as mock_close:
            with client as c:
                pass
            mock_close.assert_called_once()


class TestCoinbaseTransactionTypes:
    """Tests for transaction type mappings."""

    def test_transaction_type_mappings(self):
        """Test all Coinbase transaction type mappings."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        test_cases = [
            ("send", "transfer"),
            ("receive", "receive"),
            ("buy", "buy"),
            ("sell", "sell"),
            ("fiat_deposit", "deposit"),
            ("fiat_withdrawal", "withdrawal"),
            ("earn_payout", "reward"),
            ("staking_reward", "reward"),
            ("unknown_type", "unknown_type"),
        ]

        for coinbase_type, expected_type in test_cases:
            raw_tx = {
                "id": "tx_test",
                "type": coinbase_type,
                "status": "completed",
                "amount": {"amount": "1.0", "currency": "BTC"},
                "native_amount": {"amount": "50000.00", "currency": "USD"},
                "created_at": "2024-01-15T10:30:00Z",
                "account_currency": "BTC",
                "account_name": "BTC Wallet",
            }

            normalized = client._normalize_transaction(raw_tx)
            assert normalized["transaction_type"] == expected_type


class TestCoinbasePagination:
    """Tests for pagination handling."""

    def test_pagination_with_cursor(self):
        """Test pagination with starting_after cursor."""
        client = CoinbaseClient(api_key="test_key", api_secret="test_secret")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._session.get = Mock(return_value=mock_response)

        client.get_transactions("account_123", cursor="cursor_abc", limit=10)

        call_args = client._session.get.call_args
        assert "params" in call_args.kwargs
        assert call_args.kwargs["params"]["starting_after"] == "cursor_abc"
        assert call_args.kwargs["params"]["limit"] == 10
