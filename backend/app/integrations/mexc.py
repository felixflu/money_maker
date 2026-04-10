"""
MEXC API client.

Provides integration with MEXC cryptocurrency exchange for syncing crypto holdings,
importing transactions, and managing exchange connections.

Note: MEXC uses a REST API with HMAC SHA256 signature authentication.
This client implements the standard MEXC API patterns.

API Documentation: https://mexcdevelop.github.io/apidocs/spot_v3_en/
"""

import hashlib
import hmac
import logging
import urllib.parse
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class MexcAPIError(Exception):
    """Base exception for MEXC API errors."""

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


class MexcAuthError(MexcAPIError):
    """Exception for authentication errors."""

    pass


class MexcRateLimitError(MexcAPIError):
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


class MexcClient:
    """
    Client for MEXC API integration.

    Provides methods for:
    - Authentication with HMAC SHA256 signature
    - Portfolio/holdings synchronization
    - Transaction history import
    - Account information retrieval
    - Symbol price retrieval

    Args:
        api_key: MEXC API key
        api_secret: MEXC API secret
        timeout: Request timeout in seconds (default: 30)
    """

    BASE_URL = "https://api.mexc.com"

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
        """Get request headers with API key."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoneyMaker/1.0",
            "X-MEXC-APIKEY": self.api_key,
        }

    def _generate_signature(self, params: dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for request.

        Args:
            params: Query parameters to sign

        Returns:
            Hex-encoded signature string
        """
        # Sort parameters alphabetically and create query string
        query_string = urllib.parse.urlencode(sorted(params.items()))

        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return signature

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                raise MexcAPIError(
                    f"Invalid JSON response: {e}",
                    status_code=response.status_code,
                )

        # Handle specific error codes
        error_msg = "Unknown error"
        error_code = None
        try:
            error_data = response.json()
            error_msg = error_data.get("msg", error_msg)
            error_code = error_data.get("code")
        except ValueError:
            error_msg = response.text or f"HTTP {response.status_code}"

        # MEXC specific error codes
        if response.status_code == 401 or error_code == -2015:
            raise MexcAuthError(
                f"Authentication failed: {error_msg}",
                status_code=response.status_code,
            )

        if response.status_code == 403:
            raise MexcAuthError(
                f"Access forbidden: {error_msg}. Check IP whitelist settings.",
                status_code=response.status_code,
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise MexcRateLimitError(
                f"Rate limit exceeded: {error_msg}",
                retry_after=retry_after,
                status_code=response.status_code,
            )

        # MEXC IP auto-ban (418)
        if response.status_code == 418:
            raise MexcRateLimitError(
                f"IP banned due to rate limits: {error_msg}",
                retry_after=3600,  # Usually 1 hour ban
                status_code=response.status_code,
            )

        # Server errors
        if response.status_code >= 500:
            raise MexcAPIError(
                f"Server error: {error_msg}",
                status_code=response.status_code,
            )

        raise MexcAPIError(
            f"API error: {error_msg}",
            status_code=response.status_code,
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        signed: bool = True,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            signed: Whether to sign the request (default: True)

        Returns:
            Parsed JSON response
        """
        url = urljoin(self.base_url, f"/api/v3/{endpoint}")
        headers = self._get_headers()

        # Prepare parameters
        request_params = params.copy() if params else {}

        if signed:
            # Add timestamp for signed requests
            request_params["timestamp"] = int(datetime.utcnow().timestamp() * 1000)
            # Generate and add signature
            request_params["signature"] = self._generate_signature(request_params)

        try:
            if method == "GET":
                response = self._session.get(
                    url,
                    headers=headers,
                    params=request_params,
                    timeout=self.timeout,
                )
            elif method == "POST":
                response = self._session.post(
                    url,
                    headers=headers,
                    params=request_params,
                    timeout=self.timeout,
                )
            elif method == "DELETE":
                response = self._session.delete(
                    url,
                    headers=headers,
                    params=request_params,
                    timeout=self.timeout,
                )
            else:
                raise MexcAPIError(f"Unsupported HTTP method: {method}")

            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise MexcAPIError(
                f"Request timeout after {self.timeout} seconds",
                status_code=408,
            )
        except requests.exceptions.ConnectionError as e:
            raise MexcAPIError(
                f"Connection error: {e}",
                status_code=503,
            )
        except requests.exceptions.RequestException as e:
            raise MexcAPIError(
                f"Request failed: {e}",
                status_code=500,
            )

    def authenticate(self) -> bool:
        """
        Authenticate with MEXC API by validating credentials.

        MEXC uses signature-based authentication. This method validates
        the API key and secret by making a test request.

        Returns:
            True if authentication successful

        Raises:
            MexcAuthError: If authentication fails
            MexcRateLimitError: If rate limited
        """
        try:
            # Test authentication by fetching account info
            self.get_account_info()
            logger.info("Successfully authenticated with MEXC")
            return True
        except MexcAuthError:
            raise
        except MexcRateLimitError:
            raise
        except MexcAPIError as e:
            raise MexcAuthError(f"Authentication failed: {e.message}")

    def get_account_info(self) -> dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details including commissions, permissions, and balances

        Raises:
            MexcAPIError: If the request fails
        """
        return self._make_request("GET", "account")

    def get_holdings(self) -> list[dict[str, Any]]:
        """
        Get current portfolio holdings.

        Returns:
            List of cryptocurrency holdings with balance information

        Raises:
            MexcAPIError: If the request fails
        """
        response = self._make_request("GET", "account")
        balances = response.get("balances", [])

        # Filter out zero balance assets
        non_zero_balances = [
            balance
            for balance in balances
            if Decimal(balance.get("free", 0)) > 0
            or Decimal(balance.get("locked", 0)) > 0
        ]

        logger.info(f"Retrieved {len(non_zero_balances)} holdings from MEXC")
        return non_zero_balances

    def get_transactions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Get transaction history (my trades).

        Args:
            start_date: Filter transactions from this date
            end_date: Filter transactions until this date
            symbol: Filter by trading pair (e.g., "BTCUSDT")
            limit: Maximum number of transactions to retrieve (max 1000)

        Returns:
            List of trades/transactions

        Raises:
            MexcAPIError: If the request fails
        """
        params: dict[str, Any] = {"limit": min(limit, 1000)}

        if start_date:
            params["startTime"] = int(start_date.timestamp() * 1000)
        if end_date:
            params["endTime"] = int(end_date.timestamp() * 1000)
        if symbol:
            params["symbol"] = symbol

        response = self._make_request("GET", "myTrades", params=params)
        transactions = response.get("list", [])
        logger.info(f"Retrieved {len(transactions)} transactions from MEXC")
        return transactions

    def get_symbol_price(self, symbol: str) -> Decimal:
        """
        Get current price for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Current price as Decimal

        Raises:
            MexcAPIError: If the request fails
        """
        params = {"symbol": symbol}
        response = self._make_request(
            "GET", "ticker/price", params=params, signed=False
        )
        return Decimal(str(response.get("price", 0)))

    def get_symbol_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Get 24h price ticker statistics for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Ticker data including price change, volume, etc.

        Raises:
            MexcAPIError: If the request fails
        """
        params = {"symbol": symbol}
        return self._make_request("GET", "ticker/24hr", params=params, signed=False)

    def _normalize_holding(self, raw_holding: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw holding data to standard format.

        Args:
            raw_holding: Raw holding data from API

        Returns:
            Normalized holding data
        """
        free = Decimal(str(raw_holding.get("free", 0)))
        locked = Decimal(str(raw_holding.get("locked", 0)))
        total = free + locked

        return {
            "symbol": raw_holding.get("asset", ""),
            "name": raw_holding.get("asset", ""),  # MEXC doesn't provide full names
            "asset_type": "cryptocurrency",
            "quantity": total,
            "available": free,
            "locked": locked,
            "currency": raw_holding.get("asset", ""),
        }

    def _normalize_transaction(self, raw_tx: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize raw transaction data to standard format.

        Args:
            raw_tx: Raw transaction data from API

        Returns:
            Normalized transaction data
        """
        # Parse timestamp (MEXC uses milliseconds)
        timestamp_ms = raw_tx.get("time", 0)
        timestamp = datetime.utcfromtimestamp(timestamp_ms / 1000)

        # Parse symbol (e.g., "BTCUSDT" -> base: "BTC", quote: "USDT")
        symbol = raw_tx.get("symbol", "")
        base_asset = ""
        quote_asset = ""
        if symbol and len(symbol) >= 6:
            # Common quote assets
            for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH"]:
                if symbol.endswith(quote):
                    base_asset = symbol[: -len(quote)]
                    quote_asset = quote
                    break

        # Determine transaction type
        side = raw_tx.get("side", "")
        transaction_type = "buy" if side.upper() == "BUY" else "sell"

        # Check if buyer (MEXC specific flag)
        if raw_tx.get("isBuyer", False):
            transaction_type = "buy"
        elif "isBuyer" in raw_tx and not raw_tx["isBuyer"]:
            transaction_type = "sell"

        return {
            "external_id": str(raw_tx.get("id", "")),
            "transaction_type": transaction_type,
            "symbol": base_asset,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "full_symbol": symbol,
            "quantity": Decimal(str(raw_tx.get("qty", 0))),
            "price": Decimal(str(raw_tx.get("price", 0))),
            "total_amount": Decimal(str(raw_tx.get("quoteQty", 0))),
            "fees": Decimal(str(raw_tx.get("commission", 0))),
            "fee_asset": raw_tx.get("commissionAsset", ""),
            "currency": quote_asset,
            "timestamp": timestamp,
            "order_type": raw_tx.get("type", ""),
            "is_maker": raw_tx.get("isMaker", False),
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
            # Get holdings
            raw_holdings = self.get_holdings()
            holdings = [self._normalize_holding(h) for h in raw_holdings]

            # Get recent transactions (last 90 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            raw_transactions = self.get_transactions(
                start_date=start_date,
                end_date=end_date,
                limit=500,
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

        except MexcAuthError as e:
            logger.error(f"Authentication failed during sync: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {e.message}",
                "holdings": [],
                "transactions": [],
            }
        except MexcRateLimitError as e:
            logger.error(f"Rate limited during sync: {e}")
            return {
                "success": False,
                "error": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                "holdings": [],
                "transactions": [],
            }
        except MexcAPIError as e:
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
            # Try to fetch account info
            account_info = self.get_account_info()

            # Check if trading is enabled (optional check)
            can_trade = account_info.get("canTrade", True)
            if not can_trade:
                return (
                    True,  # Connection is still valid
                    "Warning: Trading is disabled for this account",
                )

            return True, None

        except MexcAuthError as e:
            return False, f"Authentication failed: {e.message}"
        except MexcRateLimitError as e:
            return False, f"Rate limit exceeded. Retry after {e.retry_after} seconds"
        except MexcAPIError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self._session.close()
