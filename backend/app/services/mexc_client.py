"""
MEXC Exchange API Client.

Handles authentication, rate limiting, and API interactions with MEXC exchange.
API Documentation: https://mexcdevelop.github.io/apidocs/spot_v3_en/
"""

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field


class MEXCConfig(BaseModel):
    """Configuration for MEXC API client."""

    api_key: str = Field(..., description="MEXC API key")
    api_secret: str = Field(..., description="MEXC API secret")
    base_url: str = Field(
        default="https://api.mexc.com", description="MEXC API base URL"
    )
    recv_window: int = Field(default=5000, description="Receive window in milliseconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


class MEXCHolding(BaseModel):
    """Represents a holding/asset in MEXC account."""

    asset: str = Field(..., description="Asset symbol (e.g., BTC, ETH)")
    free: Decimal = Field(..., description="Available/free balance")
    locked: Decimal = Field(..., description="Locked/locked balance")
    total: Decimal = Field(..., description="Total balance (free + locked)")


class MEXCTrade(BaseModel):
    """Represents a trade from MEXC transaction history."""

    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    id: str = Field(..., description="Trade ID")
    order_id: str = Field(..., description="Order ID")
    price: Decimal = Field(..., description="Trade price")
    qty: Decimal = Field(..., description="Trade quantity")
    quote_qty: Decimal = Field(..., description="Quote asset quantity")
    commission: Decimal = Field(..., description="Commission/fee")
    commission_asset: str = Field(..., description="Commission asset")
    time: int = Field(..., description="Trade timestamp in milliseconds")
    is_buyer: bool = Field(..., description="True if user was buyer")
    is_maker: bool = Field(..., description="True if user was maker")
    side: str = Field(..., description="Trade side (BUY or SELL)")


class MEXCError(Exception):
    """Base exception for MEXC API errors."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        response: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.response = response


class MEXCAuthError(MEXCError):
    """Raised when authentication fails."""

    pass


class MEXCRateLimitError(MEXCError):
    """Raised when rate limit is exceeded."""

    pass


class MEXCAPIError(MEXCError):
    """Raised when API returns an error."""

    pass


class MEXCClient:
    """
    Client for MEXC Exchange API.

    Supports:
    - Account balance/holdings sync
    - Transaction history import
    - Rate limiting and retry logic
    - HMAC-SHA256 signature authentication
    """

    def __init__(self, config: MEXCConfig):
        """Initialize MEXC client with configuration."""
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.1  # 100ms between requests

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={"X-MEXC-APIKEY": self.config.api_key},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _generate_signature(self, query_string: str) -> str:
        """Generate HMAC-SHA256 signature for request."""
        return hmac.new(
            self.config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _build_signed_params(self, params: Optional[dict] = None) -> dict:
        """Build parameters with timestamp and signature."""
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.config.recv_window

        query_string = urlencode(params)
        params["signature"] = self._generate_signature(query_string)
        return params

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            await self._sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()

    async def _sleep(self, duration: float):
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(duration)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        signed: bool = False,
        retry_count: int = 0,
    ) -> Any:
        """
        Make authenticated request to MEXC API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            signed: Whether to sign the request
            retry_count: Current retry attempt

        Returns:
            Parsed JSON response

        Raises:
            MEXCAuthError: If authentication fails
            MEXCRateLimitError: If rate limit exceeded
            MEXCAPIError: For other API errors
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        await self._rate_limit()

        if signed:
            params = self._build_signed_params(params)

        try:
            response = await self._client.request(method, endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for API-level errors
            if isinstance(data, dict) and "code" in data and data["code"] != 200:
                error_code = data.get("code")
                error_msg = data.get("msg", "Unknown error")

                if error_code == -2015 or error_code == -2014:  # Invalid API key
                    raise MEXCAuthError(f"Invalid API credentials: {error_msg}")
                elif error_code == -1003:  # Rate limit exceeded
                    raise MEXCRateLimitError(f"Rate limit exceeded: {error_msg}")
                else:
                    raise MEXCAPIError(
                        f"API error {error_code}: {error_msg}", code=error_code
                    )

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise MEXCAuthError("Invalid API credentials")
            elif e.response.status_code == 429:
                if retry_count < self.config.max_retries:
                    await self._sleep(2**retry_count)  # Exponential backoff
                    return await self._make_request(
                        method, endpoint, params, signed, retry_count + 1
                    )
                raise MEXCRateLimitError("Rate limit exceeded, max retries reached")
            elif e.response.status_code >= 500:
                if retry_count < self.config.max_retries:
                    await self._sleep(2**retry_count)
                    return await self._make_request(
                        method, endpoint, params, signed, retry_count + 1
                    )
                raise MEXCAPIError(f"Server error: {e.response.status_code}")
            raise MEXCAPIError(f"HTTP error: {e.response.status_code}")

        except httpx.TimeoutException:
            if retry_count < self.config.max_retries:
                await self._sleep(2**retry_count)
                return await self._make_request(
                    method, endpoint, params, signed, retry_count + 1
                )
            raise MEXCAPIError("Request timeout, max retries reached")

        except httpx.RequestError as e:
            if retry_count < self.config.max_retries:
                await self._sleep(2**retry_count)
                return await self._make_request(
                    method, endpoint, params, signed, retry_count + 1
                )
            raise MEXCAPIError(f"Request failed: {str(e)}")

    async def get_account(self) -> dict:
        """
        Get account information including permissions.

        Returns:
            Account information dictionary
        """
        return await self._make_request("GET", "/api/v3/account", signed=True)

    async def get_holdings(self) -> list[MEXCHolding]:
        """
        Get all account holdings/balances.

        Returns:
            List of MEXCHolding objects
        """
        data = await self._make_request("GET", "/api/v3/account", signed=True)
        balances = data.get("balances", [])

        holdings = []
        for balance in balances:
            free = Decimal(balance.get("free", "0"))
            locked = Decimal(balance.get("locked", "0"))
            total = free + locked

            # Only include assets with non-zero balance
            if total > 0:
                holdings.append(
                    MEXCHolding(
                        asset=balance["asset"],
                        free=free,
                        locked=locked,
                        total=total,
                    )
                )

        return holdings

    async def get_my_trades(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> list[MEXCTrade]:
        """
        Get trade history for the account.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Maximum number of trades to fetch (default 500, max 1000)

        Returns:
            List of MEXCTrade objects
        """
        params = {"limit": min(limit, 1000)}

        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = await self._make_request(
            "GET", "/api/v3/myTrades", params=params, signed=True
        )

        trades = []
        for trade_data in data:
            trades.append(
                MEXCTrade(
                    symbol=trade_data["symbol"],
                    id=str(trade_data["id"]),
                    order_id=str(trade_data["orderId"]),
                    price=Decimal(trade_data["price"]),
                    qty=Decimal(trade_data["qty"]),
                    quote_qty=Decimal(trade_data["quoteQty"]),
                    commission=Decimal(trade_data["commission"]),
                    commission_asset=trade_data["commissionAsset"],
                    time=trade_data["time"],
                    is_buyer=trade_data["isBuyer"],
                    is_maker=trade_data["isMaker"],
                    side="BUY" if trade_data["isBuyer"] else "SELL",
                )
            )

        return trades

    async def get_all_trades(
        self,
        symbols: Optional[list[str]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[MEXCTrade]:
        """
        Get all trades across multiple symbols.

        Args:
            symbols: List of trading pair symbols (fetches all if None)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds

        Returns:
            List of MEXCTrade objects
        """
        all_trades = []

        if symbols:
            for symbol in symbols:
                trades = await self.get_my_trades(
                    symbol=symbol, start_time=start_time, end_time=end_time
                )
                all_trades.extend(trades)
        else:
            # Fetch all trades without symbol filter
            trades = await self.get_my_trades(start_time=start_time, end_time=end_time)
            all_trades.extend(trades)

        # Sort by time
        all_trades.sort(key=lambda x: x.time)
        return all_trades

    async def test_connection(self) -> bool:
        """
        Test API connection and credentials.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await self.get_account()
            return True
        except MEXCError:
            return False
