"""
Coinbase API client.

Provides integration with Coinbase for syncing cryptocurrency holdings,
importing transactions, and managing exchange connections.

Note: Coinbase uses the Coinbase API (v2) for account access.
This client implements the standard API patterns used by Coinbase.
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class CoinbaseAPIError(Exception):
    """Base exception for Coinbase API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class CoinbaseAuthError(CoinbaseAPIError):
    """Exception for authentication errors."""

    pass


class CoinbaseRateLimitError(CoinbaseAPIError):
    """Exception for rate limit errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        status_code: int = 429,
        response_data: Optional[dict] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.retry_after = retry_after


class CoinbaseClient:
    """
    Client for Coinbase API integration.

    Provides methods for:
    - Authentication
    - Portfolio/holdings synchronization
    - Transaction history import
    - Account information retrieval

    Args:
        api_key: Coinbase API key
        api_secret: Coinbase API secret
        timeout: Request timeout in seconds (default: 30)
    """

    BASE_URL = "https://api.coinbase.com"
    API_VERSION = "v2"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.base_url = self.BASE_URL
        self._session = requests.Session()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoneyMaker/1.0",
            "CB-ACCESS-KEY": self.api_key,
            "CB-VERSION": "2024-01-01",
        }

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                raise CoinbaseAPIError(
                    f"Invalid JSON response: {e}",
                    status_code=response.status_code,
                )

        # Handle specific error codes
        if response.status_code == 401:
            raise CoinbaseAuthError(
                "Authentication failed: Invalid credentials",
                status_code=401,
            )

        if response.status_code == 403:
            raise CoinbaseAuthError(
                "Access forbidden: Check API permissions",
                status_code=403,
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise CoinbaseRateLimitError(
                "Rate limit exceeded. Please try again later.",
                retry_after=retry_after,
                status_code=429,
            )

        # Try to parse error message from response
        error_message = f"API error: {response.status_code}"
        try:
            error_data = response.json()
            if "error" in error_data:
                error_message = f"API error: {error_data['error']}"
            elif "errors" in error_data:
                errors = error_data["errors"]
                if isinstance(errors, list) and len(errors) > 0:
                    error_message = (
                        f"API error: {errors[0].get('message', response.status_code)}"
                    )
                else:
                    error_message = f"API error: {errors}"
            elif "message" in error_data:
                error_message = f"API error: {error_data['message']}"
        except ValueError:
            error_message = f"API error: {response.status_code} - {response.text}"

        raise CoinbaseAPIError(
            error_message,
            status_code=response.status_code,
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API."""
        url = urljoin(self.base_url, f"/{self.API_VERSION}/{endpoint}")
        headers = self._get_headers()

        try:
            if method == "GET":
                response = self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
            elif method == "POST":
                response = self._session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout,
                )
            else:
                raise CoinbaseAPIError(f"Unsupported HTTP method: {method}")

            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise CoinbaseAPIError(
                f"Request timeout after {self.timeout} seconds",
                status_code=408,
            )
        except requests.exceptions.ConnectionError as e:
            raise CoinbaseAPIError(
                f"Connection error: {e}",
                status_code=503,
            )
        except requests.exceptions.RequestException as e:
            raise CoinbaseAPIError(
                f"Request failed: {e}",
                status_code=500,
            )

    def get_accounts(self) -> list[dict[str, Any]]:
        """
        Get all accounts (wallets) for the user.

        Returns:
            List of accounts with cryptocurrency balances

        Raises:
            CoinbaseAPIError: If the request fails
        """
        response = self._make_request("GET", "accounts")
        accounts = response.get("data", [])
        logger.info(f"Retrieved {len(accounts)} accounts from Coinbase")
        return accounts

    def get_holdings(self) -> list[dict[str, Any]]:
        """
        Get current portfolio holdings with non-zero balances.

        Returns:
            List of holdings with cryptocurrency data

        Raises:
            CoinbaseAPIError: If the request fails
        """
        accounts = self.get_accounts()
        holdings = []

        for account in accounts:
            balance = account.get("balance", {})
            amount = Decimal(str(balance.get("amount", "0")))

            # Only include accounts with non-zero balance
            if amount > 0:
                holding = {
                    "id": account.get("id"),
                    "currency": account.get("currency", {}).get("code"),
                    "name": account.get("name"),
                    "quantity": amount,
                    "balance": amount,
                    "type": account.get("type"),
                }
                holdings.append(holding)

        logger.info(f"Retrieved {len(holdings)} holdings from Coinbase")
        return holdings

    def get_transactions(
        self,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get transaction history for a specific account.

        Args:
            account_id: The account ID (wallet ID)
            start_date: Filter transactions from this date
            end_date: Filter transactions until this date
            limit: Maximum number of transactions to retrieve
            cursor: Pagination cursor for fetching next page

        Returns:
            List of transactions

        Raises:
            CoinbaseAPIError: If the request fails
        """
        params: dict[str, Any] = {"limit": limit}

        if start_date:
            params["since"] = start_date.isoformat()
        if end_date:
            params["until"] = end_date.isoformat()
        if cursor:
            params["starting_after"] = cursor

        response = self._make_request(
            "GET", f"accounts/{account_id}/transactions", params=params
        )
        transactions = response.get("data", [])
        logger.info(
            f"Retrieved {len(transactions)} transactions from Coinbase for account {account_id}"
        )
        return transactions

    def get_all_transactions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get transaction history for all accounts.

        Args:
            start_date: Filter transactions from this date
            end_date: Filter transactions until this date
            limit: Maximum number of transactions per account

        Returns:
            List of transactions from all accounts

        Raises:
            CoinbaseAPIError: If the request fails
        """
        accounts = self.get_accounts()
        all_transactions = []

        for account in accounts:
            account_id = account.get("id")
            if not account_id:
                continue

            try:
                transactions = self.get_transactions(
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )

                # Add account info to each transaction
                for tx in transactions:
                    tx["account_currency"] = account.get("currency", {}).get("code")
                    tx["account_name"] = account.get("name")

                all_transactions.extend(transactions)
            except CoinbaseAPIError as e:
                logger.warning(
                    f"Failed to get transactions for account {account_id}: {e}"
                )
                continue

        logger.info(
            f"Retrieved {len(all_transactions)} total transactions from Coinbase"
        )
        return all_transactions

    def get_account_info(self) -> dict[str, Any]:
        """
        Get user account information.

        Returns:
            User details including ID, name, and email

        Raises:
            CoinbaseAPIError: If the request fails
        """
        response = self._make_request("GET", "user")
        return response.get("data", {})

    def get_exchange_rates(self, currency: str = "USD") -> dict[str, Any]:
        """
        Get current exchange rates for a currency.

        Args:
            currency: Base currency code (default: USD)

        Returns:
            Exchange rates data

        Raises:
            CoinbaseAPIError: If the request fails
        """
        return self._make_request("GET", f"exchange-rates?currency={currency}")

    def get_buy_price(self, currency_pair: str) -> dict[str, Any]:
        """
        Get the current buy price for a currency pair.

        Args:
            currency_pair: Currency pair (e.g., "BTC-USD")

        Returns:
            Buy price data

        Raises:
            CoinbaseAPIError: If the request fails
        """
        return self._make_request("GET", f"prices/{currency_pair}/buy")

    def get_sell_price(self, currency_pair: str) -> dict[str, Any]:
        """
        Get the current sell price for a currency pair.

        Args:
            currency_pair: Currency pair (e.g., "BTC-USD")

        Returns:
            Sell price data

        Raises:
            CoinbaseAPIError: If the request fails
        """
        return self._make_request("GET", f"prices/{currency_pair}/sell")

    def _normalize_holding(self, raw_holding: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw holding data to standard format.

        Args:
            raw_holding: Raw holding data from API

        Returns:
            Normalized holding data
        """
        return {
            "symbol": raw_holding.get("currency", ""),
            "name": raw_holding.get("name", ""),
            "asset_type": "cryptocurrency",
            "quantity": raw_holding.get("balance", Decimal("0")),
            "current_price": None,  # Will be populated separately
            "currency": raw_holding.get("currency", "USD"),
            "total_value": None,  # Will be calculated
        }

    def _normalize_transaction(self, raw_tx: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw transaction data to standard format.

        Args:
            raw_tx: Raw transaction data from API

        Returns:
            Normalized transaction data
        """
        # Parse timestamp
        timestamp_str = raw_tx.get("created_at", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()

        # Determine transaction type
        tx_type = raw_tx.get("type", "unknown")
        resource_type = raw_tx.get("resource", "")

        # Map Coinbase types to standard types
        type_mapping = {
            "send": "transfer",
            "receive": "receive",
            "buy": "buy",
            "sell": "sell",
            "fiat_deposit": "deposit",
            "fiat_withdrawal": "withdrawal",
            "exchange_deposit": "deposit",
            "exchange_withdrawal": "withdrawal",
            "pro_deposit": "deposit",
            "pro_withdrawal": "withdrawal",
            "earn_payout": "reward",
            "staking_reward": "reward",
        }
        transaction_type = type_mapping.get(tx_type, tx_type)

        # Get amounts
        amount_data = raw_tx.get("amount", {})
        amount = Decimal(str(amount_data.get("amount", "0")))

        # Get native amount (in user's currency)
        native_amount_data = raw_tx.get("native_amount", {})
        native_amount = Decimal(str(native_amount_data.get("amount", "0")))
        native_currency = native_amount_data.get("currency", "USD")

        return {
            "external_id": raw_tx.get("id", ""),
            "transaction_type": transaction_type,
            "symbol": raw_tx.get("account_currency", ""),
            "asset_name": raw_tx.get("account_name", ""),
            "quantity": amount,
            "price": (native_amount / amount if amount != 0 else Decimal("0")),
            "total_amount": native_amount,
            "fees": Decimal("0"),  # Coinbase includes fees in the amount
            "currency": native_currency,
            "timestamp": timestamp,
            "status": raw_tx.get("status", ""),
        }

    def sync_portfolio(self) -> dict[str, Any]:
        """
        Perform full portfolio sync including holdings and transactions.

        This is a convenience method that fetches holdings
        and retrieves recent transactions.

        Returns:
            Dictionary with success status, holdings, and transactions
        """
        try:
            # Get holdings
            raw_holdings = self.get_holdings()
            holdings = [self._normalize_holding(h) for h in raw_holdings]

            # Enrich holdings with current prices
            for holding in holdings:
                currency = holding["symbol"]
                if currency:
                    try:
                        price_data = self.get_buy_price(f"{currency}-USD")
                        price_info = price_data.get("data", {})
                        holding["current_price"] = Decimal(
                            str(price_info.get("amount", "0"))
                        )
                        if holding["quantity"] and holding["current_price"]:
                            holding["total_value"] = (
                                holding["quantity"] * holding["current_price"]
                            )
                    except CoinbaseAPIError:
                        # Price lookup failed, continue without it
                        pass

            # Get recent transactions (last 90 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            raw_transactions = self.get_all_transactions(
                start_date=start_date,
                end_date=end_date,
                limit=100,
            )
            transactions = [self._normalize_transaction(t) for t in raw_transactions]

            logger.info(
                f"Portfolio sync completed: {len(holdings)} holdings, "
                f"{len(transactions)} transactions"
            )

            return {
                "success": True,
                "holdings": holdings,
                "transactions": transactions,
                "synced_at": datetime.utcnow().isoformat(),
            }

        except CoinbaseAuthError as e:
            logger.error(f"Authentication failed during sync: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {e.message}",
                "holdings": [],
                "transactions": [],
            }
        except CoinbaseRateLimitError as e:
            logger.error(f"Rate limited during sync: {e}")
            return {
                "success": False,
                "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                "holdings": [],
                "transactions": [],
            }
        except CoinbaseAPIError as e:
            logger.error(f"API error during sync: {e}")
            return {
                "success": False,
                "error": f"API error: {e.message}",
                "holdings": [],
                "transactions": [],
            }

    def validate_connection(self) -> tuple[bool, Optional[str]]:
        """
        Validate the API connection credentials.

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if connection is valid
            - error_message: None if valid, error description if invalid
        """
        try:
            # Try to fetch user info
            user_info = self.get_account_info()

            # Check if we got valid user data
            if not user_info or "id" not in user_info:
                return False, "Invalid response from Coinbase API"

            # Check user status if available
            if user_info.get("state") == "closed":
                return False, "Coinbase account is closed"

            return True, None

        except CoinbaseAuthError as e:
            return False, f"Authentication failed: {e.message}"
        except CoinbaseRateLimitError as e:
            return False, f"Rate limit exceeded. Retry after {e.retry_after} seconds"
        except CoinbaseAPIError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self._session.close()
