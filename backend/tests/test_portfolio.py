"""
Tests for portfolio endpoint with live price enrichment.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, Mock, AsyncMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.pricing import PriceService


@pytest.fixture
def mock_price_batch():
    """Mock batch price response."""
    return {
        "BTC": {
            "symbol": "BTC",
            "price": Decimal("65000.50"),
            "currency": "USD",
            "timestamp": datetime.now(),
            "source": "coingecko",
        },
        "SPY": {
            "symbol": "SPY",
            "price": Decimal("450.25"),
            "currency": "USD",
            "timestamp": datetime.now(),
            "source": "yahoo",
        },
    }


class TestEnrichPortfolio:
    """Tests for portfolio enrichment logic."""

    @pytest.mark.asyncio
    @patch("app.routers.portfolio._price_service")
    async def test_enrich_portfolio_calculates_values(self, mock_service, mock_price_batch):
        """Test that enrichment computes value and PnL correctly."""
        mock_service.get_prices_batch = AsyncMock(return_value=mock_price_batch)

        from app.routers.portfolio import _enrich_portfolio

        # Create mock portfolio with assets
        mock_asset_btc = Mock()
        mock_asset_btc.id = 1
        mock_asset_btc.symbol = "BTC"
        mock_asset_btc.name = "Bitcoin"
        mock_asset_btc.asset_type = "cryptocurrency"
        mock_asset_btc.quantity = Decimal("0.5")
        mock_asset_btc.average_buy_price = Decimal("50000")

        mock_asset_spy = Mock()
        mock_asset_spy.id = 2
        mock_asset_spy.symbol = "SPY"
        mock_asset_spy.name = "S&P 500 ETF"
        mock_asset_spy.asset_type = "etf"
        mock_asset_spy.quantity = Decimal("10")
        mock_asset_spy.average_buy_price = Decimal("400")

        mock_portfolio = Mock()
        mock_portfolio.id = 1
        mock_portfolio.name = "Main"
        mock_portfolio.description = None
        mock_portfolio.assets = [mock_asset_btc, mock_asset_spy]
        mock_portfolio.updated_at = datetime.now()

        result = await _enrich_portfolio(mock_portfolio)

        assert result["name"] == "Main"
        assert len(result["holdings"]) == 2

        # BTC: 0.5 * 65000.50 = 32500.250
        btc_holding = next(h for h in result["holdings"] if h["symbol"] == "BTC")
        assert Decimal(btc_holding["value"]) == Decimal("32500.250")
        assert btc_holding["currentPrice"] == "65000.50"

        # SPY: 10 * 450.25 = 4502.50
        spy_holding = next(h for h in result["holdings"] if h["symbol"] == "SPY")
        assert Decimal(spy_holding["value"]) == Decimal("4502.50")

        # Total: 32500.25 + 4502.50 = 37002.75
        assert Decimal(result["totalValue"]) == Decimal("37002.750")

    @pytest.mark.asyncio
    @patch("app.routers.portfolio._price_service")
    async def test_enrich_portfolio_handles_missing_prices(self, mock_service):
        """Test enrichment handles assets with no price data."""
        mock_service.get_prices_batch = AsyncMock(return_value={})

        from app.routers.portfolio import _enrich_portfolio

        mock_asset = Mock()
        mock_asset.id = 1
        mock_asset.symbol = "UNKNOWN"
        mock_asset.name = "Unknown Asset"
        mock_asset.asset_type = "cryptocurrency"
        mock_asset.quantity = Decimal("100")
        mock_asset.average_buy_price = Decimal("10")

        mock_portfolio = Mock()
        mock_portfolio.id = 1
        mock_portfolio.name = "Test"
        mock_portfolio.description = None
        mock_portfolio.assets = [mock_asset]
        mock_portfolio.updated_at = datetime.now()

        result = await _enrich_portfolio(mock_portfolio)

        holding = result["holdings"][0]
        assert holding["currentPrice"] is None
        assert holding["value"] == "0"

    @pytest.mark.asyncio
    @patch("app.routers.portfolio._price_service")
    async def test_enrich_empty_portfolio(self, mock_service):
        """Test enrichment of empty portfolio."""
        mock_service.get_prices_batch = AsyncMock(return_value={})

        from app.routers.portfolio import _enrich_portfolio

        mock_portfolio = Mock()
        mock_portfolio.id = 1
        mock_portfolio.name = "Empty"
        mock_portfolio.description = None
        mock_portfolio.assets = []
        mock_portfolio.updated_at = datetime.now()

        result = await _enrich_portfolio(mock_portfolio)

        assert result["totalValue"] == "0"
        assert result["holdings"] == []
        assert result["totalPnLPercent"] == 0.0


class TestPortfolioEndpoints:
    """Tests for portfolio API endpoints."""

    @pytest.fixture
    async def async_client(self):
        """Create an async test client."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_get_portfolios_requires_auth(self, async_client):
        """Test that portfolio endpoint requires authentication."""
        response = await async_client.get("/api/v1/portfolio")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_portfolio_by_id_requires_auth(self, async_client):
        """Test that single portfolio endpoint requires authentication."""
        response = await async_client.get("/api/v1/portfolio/1")
        assert response.status_code == 401
