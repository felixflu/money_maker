"""
Tests for live price feed functionality.

TDD approach: Write tests first with mocked price API responses.
Tests: price fetch, caching, stale data handling, multiple asset types.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
import httpx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.pricing import PriceService, PriceCache
from app.schemas import PriceResponse, AssetType


@pytest.fixture
def mock_coingecko_response():
    """Mock CoinGecko API response for crypto assets."""
    return {
        "bitcoin": {
            "usd": 65000.50,
            "usd_24h_change": 2.5,
            "last_updated_at": int(datetime.now().timestamp()),
        },
        "ethereum": {
            "usd": 3500.75,
            "usd_24h_change": -1.2,
            "last_updated_at": int(datetime.now().timestamp()),
        },
    }


@pytest.fixture
def mock_yfinance_response():
    """Mock Yahoo Finance response for ETF/stock assets."""
    return {
        "SPY": {"price": 450.25, "change": 1.5, "change_percent": 0.33},
        "VTI": {"price": 280.50, "change": -0.75, "change_percent": -0.27},
    }


class TestPriceCache:
    """Tests for price caching functionality."""

    def test_cache_stores_and_retrieves_price(self):
        """Test that cache can store and retrieve price data."""
        cache = PriceCache(ttl_seconds=300)
        price_data = {
            "symbol": "BTC",
            "price": Decimal("65000.50"),
            "currency": "USD",
            "timestamp": datetime.now(),
            "source": "coingecko",
        }

        cache.set("BTC", price_data)
        result = cache.get("BTC")

        assert result is not None
        assert result["price"] == Decimal("65000.50")
        assert result["symbol"] == "BTC"

    def test_cache_returns_none_for_expired_entry(self):
        """Test that cache returns None for expired entries."""
        cache = PriceCache(ttl_seconds=1)
        price_data = {
            "symbol": "BTC",
            "price": Decimal("65000.50"),
            "currency": "USD",
            "timestamp": datetime.now() - timedelta(seconds=2),
            "source": "coingecko",
        }

        cache.set("BTC", price_data)
        result = cache.get("BTC")

        assert result is None

    def test_cache_returns_none_for_missing_key(self):
        """Test that cache returns None for non-existent keys."""
        cache = PriceCache(ttl_seconds=300)
        result = cache.get("NONEXISTENT")

        assert result is None

    def test_cache_clear_removes_all_entries(self):
        """Test that cache clear removes all entries."""
        cache = PriceCache(ttl_seconds=300)
        cache.set("BTC", {"price": Decimal("65000")})
        cache.set("ETH", {"price": Decimal("3500")})

        cache.clear()

        assert cache.get("BTC") is None
        assert cache.get("ETH") is None


class TestPriceServiceFetch:
    """Tests for price fetching from external APIs."""

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_fetch_crypto_price_from_coingecko(
        self, mock_get, mock_coingecko_response
    ):
        """Test fetching crypto price from CoinGecko."""
        mock_response = Mock()
        mock_response.json.return_value = {"bitcoin": {"usd": 65000.50}}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        result = await service.fetch_crypto_price("BTC", "bitcoin")

        assert result is not None
        assert result["price"] == Decimal("65000.50")
        assert result["currency"] == "USD"
        assert result["source"] == "coingecko"

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_fetch_crypto_price_handles_api_error(self, mock_get):
        """Test handling of CoinGecko API errors."""
        mock_get.side_effect = httpx.HTTPError("API Error")

        service = PriceService()
        result = await service.fetch_crypto_price("BTC", "bitcoin")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_fetch_etf_price_from_yahoo(self, mock_get, mock_yfinance_response):
        """Test fetching ETF price from Yahoo Finance."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chart": {"result": [{"meta": {"regularMarketPrice": 450.25}}]}
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        result = await service.fetch_etf_price("SPY")

        assert result is not None
        assert result["price"] == Decimal("450.25")
        assert result["currency"] == "USD"
        assert result["source"] == "yahoo"

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_fetch_etf_price_handles_api_error(self, mock_get):
        """Test handling of Yahoo Finance API errors."""
        mock_get.side_effect = httpx.HTTPError("API Error")

        service = PriceService()
        result = await service.fetch_etf_price("SPY")

        assert result is None


class TestPriceServiceCaching:
    """Tests for price service caching behavior."""

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_get_price_uses_cache_when_available(self, mock_get):
        """Test that cached prices are returned without API call."""
        mock_response = Mock()
        mock_response.json.return_value = {"bitcoin": {"usd": 65000.50}}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService(cache_ttl_seconds=300)

        # First call should hit API
        result1 = await service.get_price(
            "BTC", "cryptocurrency", coingecko_id="bitcoin"
        )
        assert result1 is not None
        assert mock_get.called

        # Reset mock to verify second call uses cache
        mock_get.reset_mock()

        # Second call should use cache
        result2 = await service.get_price(
            "BTC", "cryptocurrency", coingecko_id="bitcoin"
        )
        assert result2 is not None
        assert not mock_get.called

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_get_price_refreshes_expired_cache(self, mock_get):
        """Test that expired cache entries trigger fresh API calls."""
        mock_response = Mock()
        mock_response.json.return_value = {"bitcoin": {"usd": 65000.50}}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService(cache_ttl_seconds=0)  # Immediate expiry

        # First call
        await service.get_price("BTC", "cryptocurrency", coingecko_id="bitcoin")
        call_count = mock_get.call_count

        # Second call should hit API again due to expired cache
        await service.get_price("BTC", "cryptocurrency", coingecko_id="bitcoin")
        assert mock_get.call_count == call_count + 1


class TestPriceServiceStaleData:
    """Tests for stale data handling."""

    @pytest.mark.asyncio
    async def test_get_price_returns_stale_data_with_warning(self):
        """Test that stale data is returned with a warning flag when API fails."""
        service = PriceService()

        # Pre-populate cache with stale data
        stale_data = {
            "symbol": "BTC",
            "price": Decimal("65000.50"),
            "currency": "USD",
            "timestamp": datetime.now() - timedelta(minutes=10),
            "source": "coingecko",
        }
        service.cache.set("BTC", stale_data)

        # Mock API failure
        with patch(
            "app.services.pricing.httpx.AsyncClient.get",
            side_effect=httpx.HTTPError("API Down"),
        ):
            result = await service.get_price(
                "BTC", "cryptocurrency", coingecko_id="bitcoin"
            )

        assert result is not None
        assert result.get("is_stale") is True
        assert result["price"] == Decimal("65000.50")

    @pytest.mark.asyncio
    async def test_get_price_returns_none_when_no_data_and_api_fails(self):
        """Test that None is returned when no cache and API fails."""
        service = PriceService()

        with patch(
            "app.services.pricing.httpx.AsyncClient.get",
            side_effect=httpx.HTTPError("API Down"),
        ):
            result = await service.get_price("UNKNOWN", "cryptocurrency")

        assert result is None


class TestPriceServiceMultipleAssetTypes:
    """Tests for handling multiple asset types."""

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_get_price_routes_to_correct_provider_for_crypto(self, mock_get):
        """Test that crypto assets are routed to CoinGecko."""
        mock_response = Mock()
        mock_response.json.return_value = {"bitcoin": {"usd": 65000.50}}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        result = await service.get_price(
            "BTC", "cryptocurrency", coingecko_id="bitcoin"
        )

        assert result is not None
        assert result["source"] == "coingecko"

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_get_price_routes_to_correct_provider_for_etf(self, mock_get):
        """Test that ETF assets are routed to Yahoo Finance."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chart": {"result": [{"meta": {"regularMarketPrice": 450.25}}]}
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        result = await service.get_price("SPY", "etf")

        assert result is not None
        assert result["source"] == "yahoo"

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_get_price_routes_to_correct_provider_for_stock(self, mock_get):
        """Test that stock assets are routed to Yahoo Finance."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chart": {"result": [{"meta": {"regularMarketPrice": 175.50}}]}
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        result = await service.get_price("AAPL", "stock")

        assert result is not None
        assert result["source"] == "yahoo"


class TestPriceBatchFetch:
    """Tests for batch price fetching."""

    @pytest.mark.asyncio
    @patch("app.services.pricing.httpx.AsyncClient.get")
    async def test_fetch_multiple_prices_concurrently(self, mock_get):
        """Test fetching multiple prices concurrently."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "bitcoin": {"usd": 65000.50},
            "ethereum": {"usd": 3500.75},
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = PriceService()
        assets = [
            ("BTC", "cryptocurrency", "bitcoin"),
            ("ETH", "cryptocurrency", "ethereum"),
        ]
        results = await service.get_prices_batch(assets)

        assert len(results) == 2
        assert results["BTC"]["price"] == Decimal("65000.50")
        assert results["ETH"]["price"] == Decimal("3500.75")


class TestPriceEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    async def async_client(self):
        """Create an async test client."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    @patch("app.services.pricing.PriceService.get_price")
    async def test_get_price_endpoint_success(self, mock_get_price, async_client):
        """Test price endpoint returns price data."""
        mock_get_price.return_value = {
            "symbol": "BTC",
            "price": Decimal("65000.50"),
            "currency": "USD",
            "timestamp": datetime.now(),
            "source": "coingecko",
            "is_stale": False,
        }

        async with async_client as client:
            response = await client.get("/api/v1/prices/BTC?asset_type=cryptocurrency")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        assert data["price"] == "65000.50"
        assert data["currency"] == "USD"

    @pytest.mark.asyncio
    @patch("app.services.pricing.PriceService.get_price")
    async def test_get_price_endpoint_not_found(self, mock_get_price, async_client):
        """Test price endpoint returns 404 when price not available."""
        mock_get_price.return_value = None

        async with async_client as client:
            response = await client.get(
                "/api/v1/prices/UNKNOWN?asset_type=cryptocurrency"
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.pricing.PriceService.get_prices_batch")
    async def test_post_prices_batch_endpoint(self, mock_get_prices, async_client):
        """Test batch price endpoint returns multiple prices."""
        mock_get_prices.return_value = {
            "BTC": {"symbol": "BTC", "price": Decimal("65000.50"), "currency": "USD"},
            "ETH": {"symbol": "ETH", "price": Decimal("3500.75"), "currency": "USD"},
        }

        async with async_client as client:
            response = await client.post(
                "/api/v1/prices/batch",
                json={
                    "assets": [
                        {"symbol": "BTC", "asset_type": "cryptocurrency"},
                        {"symbol": "ETH", "asset_type": "cryptocurrency"},
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["prices"]) == 2
