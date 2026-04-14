"""
Price service for fetching live prices from external APIs.

Supports CoinGecko for crypto and Yahoo Finance for ETFs/stocks.
Includes caching with TTL and stale data fallback.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
YAHOO_FINANCE_URL = "https://query1.finance.yahoo.com/v8/finance"


class PriceCache:
    """In-memory price cache with TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if key not in self._cache:
            return None
        entry = self._cache[key]
        timestamp = entry.get("timestamp")
        if timestamp and (datetime.now() - timestamp).total_seconds() > self.ttl_seconds:
            return None
        return entry

    def set(self, key: str, data: Dict[str, Any]) -> None:
        if "timestamp" not in data:
            data["timestamp"] = datetime.now()
        self._cache[key] = data

    def clear(self) -> None:
        self._cache.clear()


class PriceService:
    """Service for fetching and caching asset prices."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache = PriceCache(ttl_seconds=cache_ttl_seconds)

    async def fetch_crypto_price(
        self, symbol: str, coingecko_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        cg_id = coingecko_id or symbol.lower()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{COINGECKO_API_URL}/simple/price",
                    params={"ids": cg_id, "vs_currencies": "usd"},
                )
                response.raise_for_status()
                data = response.json()
                if cg_id in data and "usd" in data[cg_id]:
                    return {
                        "symbol": symbol,
                        "price": Decimal(str(data[cg_id]["usd"])),
                        "currency": "USD",
                        "timestamp": datetime.now(),
                        "source": "coingecko",
                    }
        except (httpx.HTTPError, Exception) as e:
            logger.error(f"Error fetching crypto price for {symbol}: {e}")
        return None

    async def fetch_etf_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{YAHOO_FINANCE_URL}/chart/{symbol}",
                )
                response.raise_for_status()
                data = response.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                price = result.get("meta", {}).get("regularMarketPrice")
                if price is not None:
                    return {
                        "symbol": symbol,
                        "price": Decimal(str(price)),
                        "currency": "USD",
                        "timestamp": datetime.now(),
                        "source": "yahoo",
                    }
        except (httpx.HTTPError, Exception) as e:
            logger.error(f"Error fetching ETF price for {symbol}: {e}")
        return None

    async def get_price(
        self,
        symbol: str,
        asset_type: str,
        coingecko_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        cached = self.cache.get(symbol)
        if cached is not None:
            return cached

        result = None
        if asset_type == "cryptocurrency":
            result = await self.fetch_crypto_price(symbol, coingecko_id)
        elif asset_type in ("etf", "stock"):
            result = await self.fetch_etf_price(symbol)

        if result is not None:
            self.cache.set(symbol, result)
            return result

        # Return stale data if available
        stale = self.cache._cache.get(symbol)
        if stale is not None:
            stale["is_stale"] = True
            return stale

        return None

    async def get_prices_batch(
        self, assets: List[Tuple[str, str, Optional[str]]]
    ) -> Dict[str, Dict[str, Any]]:
        # For crypto, try batch CoinGecko call
        crypto_assets = [a for a in assets if a[1] == "cryptocurrency"]
        other_assets = [a for a in assets if a[1] != "cryptocurrency"]
        results = {}

        if crypto_assets:
            ids = [a[2] or a[0].lower() for a in crypto_assets]
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{COINGECKO_API_URL}/simple/price",
                        params={"ids": ",".join(ids), "vs_currencies": "usd"},
                    )
                    response.raise_for_status()
                    data = response.json()
                    for asset in crypto_assets:
                        symbol, _, cg_id = asset
                        cg_id = cg_id or symbol.lower()
                        if cg_id in data and "usd" in data[cg_id]:
                            price_data = {
                                "symbol": symbol,
                                "price": Decimal(str(data[cg_id]["usd"])),
                                "currency": "USD",
                                "timestamp": datetime.now(),
                                "source": "coingecko",
                            }
                            results[symbol] = price_data
                            self.cache.set(symbol, price_data)
            except (httpx.HTTPError, Exception) as e:
                logger.error(f"Error fetching batch crypto prices: {e}")

        for symbol, asset_type, _ in other_assets:
            result = await self.fetch_etf_price(symbol)
            if result:
                results[symbol] = result
                self.cache.set(symbol, result)

        return results
