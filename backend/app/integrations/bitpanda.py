"""
Bitpanda API client.

Provides integration with Bitpanda for syncing cryptocurrency holdings,
importing trades, and managing exchange connections.

Bitpanda API Documentation: https://developers.bitpanda.com/
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class BitpandaAPIError(Exception):
    """Base exception for Bitpanda API errors."""

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


class BitpandaAuthError(BitpandaAPIError):
    """Exception for authentication errors."""

    pass


class BitpandaRateLimitError(BitpandaAPIError):
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


class BitpandaClient:
    """
    Client for Bitpanda API integration.

    Provides methods for:
    - Authentication (via API key)
    - Wallet/holdings synchronization
    - Trade history import
    - Account information retrieval

    Args:
        api_key: Bitpanda API key
        api_secret: Not used for Bitpanda (API key only), but kept for interface consistency
        timeout: Request timeout in seconds (default: 30)
    """

    BASE_URL = "https://api.bitpanda.com"
    API_VERSION = "v1"

    def __init__(
        self,
        api_key: str,
        api_secret: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.api_secret = (
            api_secret  # Not used by Bitpanda, but kept for interface consistency
        )
        self.timeout = timeout
        self.base_url = self.BASE_URL
        self._session = requests.Session()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with API key authentication."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": "MoneyMaker/1.0",
        }

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                raise BitpandaAPIError(
                    f"Invalid JSON response: {e}",
                    status_code=response.status_code,
                )

        # Handle specific error codes
        if response.status_code == 401:
            raise BitpandaAuthError(
                "Authentication failed: Invalid API key",
                status_code=401,
            )

        if response.status_code == 403:
            raise BitpandaAuthError(
                "Access forbidden: Check API permissions",
                status_code=403,
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise BitpandaRateLimitError(
                "Rate limit exceeded. Please try again later.",
                retry_after=retry_after,
                status_code=429,
            )

        # Try to parse error message from response
        error_message = f"API error: {response.status_code}"
        try:
            error_data = response.json()
            if "errors" in error_data and len(error_data["errors"]) > 0:
                error_message = f"API error: {error_data['errors'][0].get('detail', 'Unknown error')}"
            elif "error" in error_data:
                error_message = f"API error: {error_data['error']}"
            elif "message" in error_data:
                error_message = f"API error: {error_data['message']}"
        except ValueError:
            error_message = f"API error: {response.status_code} - {response.text}"

        raise BitpandaAPIError(
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
                raise BitpandaAPIError(f"Unsupported HTTP method: {method}")

            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise BitpandaAPIError(
                f"Request timeout after {self.timeout} seconds",
                status_code=408,
            )
        except requests.exceptions.ConnectionError as e:
            raise BitpandaAPIError(
                f"Connection error: {e}",
                status_code=503,
            )
        except requests.exceptions.RequestException as e:
            raise BitpandaAPIError(
                f"Request failed: {e}",
                status_code=500,
            )

    def get_account_info(self) -> dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details including ID, email, and status

        Raises:
            BitpandaAPIError: If the request fails
        """
        return self._make_request("GET", "account")

    def get_wallets(self) -> list[dict[str, Any]]:
        """
        Get cryptocurrency wallets (holdings).

        Returns:
            List of wallets with cryptocurrency balances

        Raises:
            BitpandaAPIError: If the request fails
        """
        response = self._make_request("GET", "wallets")
        wallets = response.get("data", [])
        logger.info(f"Retrieved {len(wallets)} wallets from Bitpanda")
        return wallets

    def get_trades(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get trade history.

        Args:
            start_date: Filter trades from this date
            end_date: Filter trades until this date
            page: Page number for pagination
            page_size: Number of trades per page (max 100)

        Returns:
            List of trades

        Raises:
            BitpandaAPIError: If the request fails
        """
        params: dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),  # API max is 100
        }

        if start_date:
            params["from"] = start_date.isoformat()
        if end_date:
            params["to"] = end_date.isoformat()

        response = self._make_request("GET", "trades", params=params)
        trades = response.get("data", [])
        logger.info(f"Retrieved {len(trades)} trades from Bitpanda")
        return trades

    def get_fiat_wallets(self) -> list[dict[str, Any]]:
        """
        Get fiat currency wallets.

        Returns:
            List of fiat wallets with balances

        Raises:
            BitpandaAPIError: If the request fails
        """
        response = self._make_request("GET", "fiatwallets")
        wallets = response.get("data", [])
        logger.info(f"Retrieved {len(wallets)} fiat wallets from Bitpanda")
        return wallets

    def _normalize_holding(self, raw_wallet: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw wallet data to standard format.

        Args:
            raw_wallet: Raw wallet data from API

        Returns:
            Normalized holding data
        """
        attributes = raw_wallet.get("attributes", {})
        cryptocurrency = attributes.get("cryptocoin_symbol", "")
        if not cryptocurrency:
            cryptocurrency = raw_wallet.get("type", "").replace("wallet", "").upper()

        balance = Decimal(str(attributes.get("balance", 0)))
        # Calculate approximate value if available, otherwise use balance
        available = Decimal(str(attributes.get("available", 0)))

        return {
            "symbol": cryptocurrency,
            "name": attributes.get("name", ""),
            "asset_type": "cryptocurrency",
            "quantity": float(balance),
            "available_quantity": float(available),
            "current_price": None,  # Price requires separate API call
            "currency": "EUR",  # Bitpanda primarily uses EUR
            "total_value": None,  # Calculated externally if price available
            "wallet_id": raw_wallet.get("id", ""),
        }

    def _normalize_trade(self, raw_trade: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw trade data to standard format.

        Args:
            raw_trade: Raw trade data from API

        Returns:
            Normalized transaction data
        """
        attributes = raw_trade.get("attributes", {})

        # Parse timestamp
        timestamp_str = attributes.get("time", {}).get("date_iso8601", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()

        # Determine transaction type
        trade_type = attributes.get("type", "").lower()
        if trade_type == "buy":
            tx_type = "buy"
        elif trade_type == "sell":
            tx_type = "sell"
        else:
            tx_type = trade_type

        # Get cryptocurrency symbol
        cryptocurrency = attributes.get("cryptocoin_symbol", "")
        if not cryptocurrency:
            cryptocurrency = attributes.get("cryptocoin_id", "")

        # Parse amounts
        amount = Decimal(str(attributes.get("amount", 0)))
        price = Decimal(str(attributes.get("price", 0)))
        bfx_fee = Decimal(str(attributes.get("bfx_fee", 0)))

        return {
            "external_id": raw_trade.get("id", ""),
            "transaction_type": tx_type,
            "symbol": cryptocurrency,
            "asset_name": attributes.get("cryptocoin_id", ""),
            "quantity": float(amount),
            "price": float(price),
            "total_amount": float(amount * price),
            "fees": float(bfx_fee),
            "currency": attributes.get("fiat_id", "EUR"),
            "timestamp": timestamp,
            "status": attributes.get("status", ""),
        }

    def sync_portfolio(self) -> dict[str, Any]:
        """
        Perform full portfolio sync including holdings and trades.

        This is a convenience method that fetches wallet balances
        and retrieves recent trades.

        Returns:
            Dictionary with success status, holdings, and transactions
        """
        try:
            # Get wallet holdings
            raw_wallets = self.get_wallets()
            holdings = [self._normalize_holding(w) for w in raw_wallets]

            # Get recent trades (last 90 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            raw_trades = self.get_trades(
                start_date=start_date,
                end_date=end_date,
                page=1,
                page_size=100,
            )
            transactions = [self._normalize_trade(t) for t in raw_trades]

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

        except BitpandaAuthError as e:
            logger.error(f"Authentication failed during sync: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {e.message}",
                "holdings": [],
                "transactions": [],
            }
        except BitpandaRateLimitError as e:
            logger.error(f"Rate limited during sync: {e}")
            return {
                "success": False,
                "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                "holdings": [],
                "transactions": [],
            }
        except BitpandaAPIError as e:
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
            # Try to fetch account info - this validates the API key
            account_info = self.get_account_info()

            # Check account data exists
            account_data = account_info.get("data", {})
            if not account_data:
                return False, "Invalid response from Bitpanda API"

            return True, None

        except BitpandaAuthError as e:
            return False, f"Authentication failed: {e.message}"
        except BitpandaRateLimitError as e:
            return False, f"Rate limit exceeded. Retry after {e.retry_after} seconds"
        except BitpandaAPIError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self._session.close()
