"""
Trade Republic API client.

Provides integration with Trade Republic for syncing ETF and crypto holdings,
importing transactions, and managing exchange connections.

Note: Trade Republic uses a web/mobile API. This client implements the common
API patterns used by Trade Republic's platform.
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class TradeRepublicAPIError(Exception):
    """Base exception for Trade Republic API errors."""

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


class TradeRepublicAuthError(TradeRepublicAPIError):
    """Exception for authentication errors."""

    pass


class TradeRepublicRateLimitError(TradeRepublicAPIError):
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


class TradeRepublicClient:
    """
    Client for Trade Republic API integration.

    Provides methods for:
    - Authentication
    - Portfolio/holdings synchronization
    - Transaction history import
    - Account information retrieval

    Args:
        api_key: Trade Republic API key
        api_secret: Trade Republic API secret
        timeout: Request timeout in seconds (default: 30)
    """

    BASE_URL = "https://api.traderepublic.com"
    API_VERSION = "v1"

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
        self._access_token: Optional[str] = None
        self._session = requests.Session()

    def _get_headers(self, auth: bool = True) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoneyMaker/1.0",
        }
        if auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                raise TradeRepublicAPIError(
                    f"Invalid JSON response: {e}",
                    status_code=response.status_code,
                )

        # Handle specific error codes
        if response.status_code == 401:
            raise TradeRepublicAuthError(
                "Authentication failed: Invalid credentials",
                status_code=401,
            )

        if response.status_code == 403:
            raise TradeRepublicAuthError(
                "Access forbidden: Check API permissions",
                status_code=403,
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise TradeRepublicRateLimitError(
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
            elif "message" in error_data:
                error_message = f"API error: {error_data['message']}"
        except ValueError:
            error_message = f"API error: {response.status_code} - {response.text}"

        raise TradeRepublicAPIError(
            error_message,
            status_code=response.status_code,
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API."""
        url = urljoin(self.base_url, f"/api/{self.API_VERSION}/{endpoint}")
        headers = self._get_headers(auth=auth)

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
                raise TradeRepublicAPIError(f"Unsupported HTTP method: {method}")

            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise TradeRepublicAPIError(
                f"Request timeout after {self.timeout} seconds",
                status_code=408,
            )
        except requests.exceptions.ConnectionError as e:
            raise TradeRepublicAPIError(
                f"Connection error: {e}",
                status_code=503,
            )
        except requests.exceptions.RequestException as e:
            raise TradeRepublicAPIError(
                f"Request failed: {e}",
                status_code=500,
            )

    def authenticate(self) -> str:
        """
        Authenticate with Trade Republic API.

        Returns:
            Access token string

        Raises:
            TradeRepublicAuthError: If authentication fails
            TradeRepublicRateLimitError: If rate limited
        """
        auth_data = {
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "grant_type": "client_credentials",
        }

        response = self._make_request(
            "POST",
            "auth/token",
            data=auth_data,
            auth=False,
        )

        self._access_token = response.get("access_token")
        if not self._access_token:
            raise TradeRepublicAuthError("No access token in authentication response")

        logger.info("Successfully authenticated with Trade Republic")
        return self._access_token

    def get_holdings(self) -> list[dict[str, Any]]:
        """
        Get current portfolio holdings.

        Returns:
            List of holdings with ETF and cryptocurrency data

        Raises:
            TradeRepublicAPIError: If the request fails
        """
        response = self._make_request("GET", "portfolio/holdings")
        holdings = response.get("holdings", [])
        logger.info(f"Retrieved {len(holdings)} holdings from Trade Republic")
        return holdings

    def get_transactions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get transaction history.

        Args:
            start_date: Filter transactions from this date
            end_date: Filter transactions until this date
            limit: Maximum number of transactions to retrieve
            cursor: Pagination cursor for fetching next page

        Returns:
            List of transactions

        Raises:
            TradeRepublicAPIError: If the request fails
        """
        params: dict[str, Any] = {"limit": limit}

        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if cursor:
            params["cursor"] = cursor

        response = self._make_request("GET", "transactions", params=params)
        transactions = response.get("transactions", [])
        logger.info(f"Retrieved {len(transactions)} transactions from Trade Republic")
        return transactions

    def get_account_info(self) -> dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details including ID, type, and status

        Raises:
            TradeRepublicAPIError: If the request fails
        """
        return self._make_request("GET", "account")

    def get_instrument_details(self, isin: str) -> dict[str, Any]:
        """
        Get details for a specific instrument by ISIN.

        Args:
            isin: International Securities Identification Number

        Returns:
            Instrument details

        Raises:
            TradeRepublicAPIError: If the request fails
        """
        return self._make_request("GET", f"instruments/{isin}")

    def _normalize_holding(self, raw_holding: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw holding data to standard format.

        Args:
            raw_holding: Raw holding data from API

        Returns:
            Normalized holding data
        """
        return {
            "symbol": raw_holding.get("isin", ""),
            "name": raw_holding.get("name", ""),
            "asset_type": raw_holding.get("type", ""),
            "quantity": Decimal(str(raw_holding.get("quantity", 0))),
            "current_price": Decimal(str(raw_holding.get("current_price", 0))),
            "currency": raw_holding.get("currency", "EUR"),
            "total_value": Decimal(str(raw_holding.get("total_value", 0))),
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
        timestamp_str = raw_tx.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()

        return {
            "external_id": raw_tx.get("id", ""),
            "transaction_type": raw_tx.get("type", ""),
            "symbol": raw_tx.get("isin", ""),
            "asset_name": raw_tx.get("name", ""),
            "quantity": Decimal(str(raw_tx.get("quantity", 0))),
            "price": Decimal(str(raw_tx.get("price", 0))),
            "total_amount": Decimal(str(raw_tx.get("total_amount", 0))),
            "fees": Decimal(str(raw_tx.get("fees", 0))),
            "currency": raw_tx.get("currency", "EUR"),
            "timestamp": timestamp,
            "status": raw_tx.get("status", ""),
        }

    def sync_portfolio(self) -> dict[str, Any]:
        """
        Perform full portfolio sync including holdings and transactions.

        This is a convenience method that authenticates, fetches holdings,
        and retrieves recent transactions.

        Returns:
            Dictionary with success status, holdings, and transactions
        """
        try:
            # Ensure authenticated
            if not self._access_token:
                self.authenticate()

            # Get holdings
            raw_holdings = self.get_holdings()
            holdings = [self._normalize_holding(h) for h in raw_holdings]

            # Get recent transactions (last 90 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            raw_transactions = self.get_transactions(
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

        except TradeRepublicAuthError as e:
            logger.error(f"Authentication failed during sync: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {e.message}",
                "holdings": [],
                "transactions": [],
            }
        except TradeRepublicRateLimitError as e:
            logger.error(f"Rate limited during sync: {e}")
            return {
                "success": False,
                "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                "holdings": [],
                "transactions": [],
            }
        except TradeRepublicAPIError as e:
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
            # Try to authenticate
            self.authenticate()

            # Try to fetch account info
            account_info = self.get_account_info()

            # Check account status
            account_status = account_info.get("status", "").lower()
            if account_status != "active":
                return (
                    False,
                    f"Account is not active (status: {account_status})",
                )

            return True, None

        except TradeRepublicAuthError as e:
            return False, f"Authentication failed: {e.message}"
        except TradeRepublicRateLimitError as e:
            return False, f"Rate limit exceeded. Retry after {e.retry_after} seconds"
        except TradeRepublicAPIError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self._session.close()
