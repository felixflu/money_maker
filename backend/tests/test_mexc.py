"""
Tests for MEXC exchange integration.

TDD: Tests with mocked MEXC API responses.
Covers: sync holdings, transaction import, error handling, rate limits.
"""

import json
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.exchange_connection import ExchangeConnection
from app.services.mexc_client import (
    MEXCClient,
    MEXCConfig,
    MEXCHolding,
    MEXCTrade,
    MEXCError,
    MEXCAuthError,
    MEXCRateLimitError,
    MEXCAPIError,
)
from app.services.mexc_sync import MEXCSyncService, MEXCSyncError


# Test database URL (SQLite in-memory for fast tests)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine) -> Session:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mexc_config():
    """Create a test MEXC config."""
    return MEXCConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        base_url="https://api.mexc.com",
    )


@pytest.fixture
def mock_account_response():
    """Mock MEXC account response."""
    return {
        "makerCommission": 10,
        "takerCommission": 10,
        "buyerCommission": 0,
        "sellerCommission": 0,
        "canTrade": True,
        "canWithdraw": True,
        "canDeposit": True,
        "balances": [
            {"asset": "BTC", "free": "1.50000000", "locked": "0.00000000"},
            {"asset": "ETH", "free": "10.00000000", "locked": "2.00000000"},
            {"asset": "USDT", "free": "5000.00", "locked": "0.00"},
        ],
    }


@pytest.fixture
def mock_trades_response():
    """Mock MEXC trades response."""
    return [
        {
            "symbol": "BTCUSDT",
            "id": 28457,
            "orderId": 100234,
            "price": "45000.00",
            "qty": "0.5",
            "quoteQty": "22500.00",
            "commission": "22.50",
            "commissionAsset": "USDT",
            "time": 1609459200000,  # 2021-01-01 00:00:00 UTC
            "isBuyer": True,
            "isMaker": False,
            "isBestMatch": True,
        },
        {
            "symbol": "ETHUSDT",
            "id": 28458,
            "orderId": 100235,
            "price": "3000.00",
            "qty": "5.0",
            "quoteQty": "15000.00",
            "commission": "15.00",
            "commissionAsset": "USDT",
            "time": 1609545600000,  # 2021-01-02 00:00:00 UTC
            "isBuyer": False,
            "isMaker": True,
            "isBestMatch": True,
        },
    ]


class TestMEXCClient:
    """Tests for MEXC API client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, mexc_config):
        """Test MEXC client initialization."""
        client = MEXCClient(mexc_config)
        assert client.config == mexc_config
        assert client._client is None

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mexc_config):
        """Test async context manager."""
        async with MEXCClient(mexc_config) as client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_generate_signature(self, mexc_config):
        """Test signature generation."""
        client = MEXCClient(mexc_config)
        query_string = "timestamp=1234567890"
        signature = client._generate_signature(query_string)

        # Signature should be a valid hex string
        assert len(signature) == 64  # SHA256 produces 32 bytes = 64 hex chars
        assert all(c in "0123456789abcdef" for c in signature)

    @pytest.mark.asyncio
    async def test_build_signed_params(self, mexc_config):
        """Test building signed parameters."""
        client = MEXCClient(mexc_config)
        params = client._build_signed_params({"symbol": "BTCUSDT"})

        assert "timestamp" in params
        assert "recvWindow" in params
        assert "signature" in params
        assert params["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_get_account_success(
        self, mock_request, mexc_config, mock_account_response
    ):
        """Test successful account fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_account_response
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            account = await client.get_account()

        assert account["canTrade"] is True
        assert len(account["balances"]) == 3

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_get_holdings(self, mock_request, mexc_config, mock_account_response):
        """Test getting holdings."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_account_response
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            holdings = await client.get_holdings()

        assert len(holdings) == 3

        # Check BTC holding
        btc_holding = next(h for h in holdings if h.asset == "BTC")
        assert btc_holding.free == Decimal("1.5")
        assert btc_holding.locked == Decimal("0")
        assert btc_holding.total == Decimal("1.5")

        # Check ETH holding
        eth_holding = next(h for h in holdings if h.asset == "ETH")
        assert eth_holding.free == Decimal("10")
        assert eth_holding.locked == Decimal("2")
        assert eth_holding.total == Decimal("12")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_get_holdings_excludes_zero_balance(self, mock_request, mexc_config):
        """Test that zero-balance assets are excluded."""
        mock_response_data = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0"},
                {"asset": "EMPTY", "free": "0", "locked": "0"},
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            holdings = await client.get_holdings()

        assert len(holdings) == 1
        assert holdings[0].asset == "BTC"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_get_my_trades(self, mock_request, mexc_config, mock_trades_response):
        """Test getting trade history."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_trades_response
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            trades = await client.get_my_trades(symbol="BTCUSDT")

        assert len(trades) == 2

        # Check first trade
        trade1 = trades[0]
        assert trade1.symbol == "BTCUSDT"
        assert trade1.price == Decimal("45000.00")
        assert trade1.qty == Decimal("0.5")
        assert trade1.is_buyer is True
        assert trade1.side == "BUY"

        # Check second trade
        trade2 = trades[1]
        assert trade2.symbol == "ETHUSDT"
        assert trade2.is_buyer is False
        assert trade2.side == "SELL"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_auth_error(self, mock_request, mexc_config):
        """Test handling of authentication errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            with pytest.raises(MEXCAuthError):
                await client.get_account()

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_rate_limit_error(self, mock_request, mexc_config):
        """Test handling of rate limit errors."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            with pytest.raises(MEXCRateLimitError):
                await client.get_account()

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_api_error_response(self, mock_request, mexc_config):
        """Test handling of API error responses."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": -2015, "msg": "Invalid API-key"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            with pytest.raises(MEXCAuthError) as exc_info:
                await client.get_account()
            assert "Invalid API credentials" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_test_connection_success(self, mock_request, mexc_config):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"canTrade": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            result = await client.test_connection()

        assert result is True

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_test_connection_failure(self, mock_request, mexc_config):
        """Test failed connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
        mock_request.return_value = mock_response

        async with MEXCClient(mexc_config) as client:
            result = await client.test_connection()

        assert result is False


class TestMEXCSyncService:
    """Tests for MEXC sync service."""

    @pytest.fixture
    def user(self, db_session):
        """Create a test user."""
        user = User(
            email="mexc_test@example.com",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()
        return user

    @pytest.fixture
    def exchange_connection(self, db_session, user):
        """Create a test MEXC exchange connection."""
        connection = ExchangeConnection(
            user_id=user.id,
            exchange_name="MEXC",
            api_key_encrypted="test_key",
            api_secret_encrypted="test_secret",
            is_active=True,
        )
        db_session.add(connection)
        db_session.commit()
        return connection

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_sync_holdings_success(
        self, mock_client_class, db_session, user, exchange_connection
    ):
        """Test successful holdings sync."""
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = True
        mock_client.get_holdings.return_value = [
            MEXCHolding(
                asset="BTC",
                free=Decimal("1.0"),
                locked=Decimal("0"),
                total=Decimal("1.0"),
            ),
            MEXCHolding(
                asset="ETH",
                free=Decimal("10.0"),
                locked=Decimal("0"),
                total=Decimal("10.0"),
            ),
        ]
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        sync_service = MEXCSyncService(db_session)
        result = await sync_service.sync_holdings(exchange_connection)

        assert result["success"] is True
        assert result["synced_count"] == 2

        # Check portfolio was created
        portfolio = db_session.query(Portfolio).filter_by(user_id=user.id).first()
        assert portfolio is not None
        assert portfolio.name == "MEXC Portfolio"

        # Check assets were created
        assets = db_session.query(Asset).filter_by(portfolio_id=portfolio.id).all()
        assert len(assets) == 2

        # Check BTC asset
        btc_asset = next(a for a in assets if a.symbol == "BTC")
        assert btc_asset.quantity == Decimal("1.0")

        # Check last_synced_at was updated
        assert exchange_connection.last_synced_at is not None

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_sync_holdings_wrong_exchange(
        self, mock_client_class, db_session, user
    ):
        """Test sync with wrong exchange type."""
        connection = ExchangeConnection(
            user_id=user.id,
            exchange_name="Coinbase",  # Wrong exchange
            api_key_encrypted="test_key",
            api_secret_encrypted="test_secret",
            is_active=True,
        )
        db_session.add(connection)
        db_session.commit()

        sync_service = MEXCSyncService(db_session)

        with pytest.raises(MEXCSyncError) as exc_info:
            await sync_service.sync_holdings(connection)

        assert "Invalid exchange" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_sync_holdings_connection_failure(
        self, mock_client_class, db_session, user, exchange_connection
    ):
        """Test sync when connection test fails."""
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = False
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        sync_service = MEXCSyncService(db_session)

        with pytest.raises(MEXCSyncError) as exc_info:
            await sync_service.sync_holdings(exchange_connection)

        assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_sync_transactions_success(
        self, mock_client_class, db_session, user, exchange_connection
    ):
        """Test successful transaction sync."""
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = True
        mock_client.get_all_trades.return_value = [
            MEXCTrade(
                symbol="BTCUSDT",
                id="123",
                order_id="456",
                price=Decimal("45000"),
                qty=Decimal("0.5"),
                quote_qty=Decimal("22500"),
                commission=Decimal("22.5"),
                commission_asset="USDT",
                time=1609459200000,
                is_buyer=True,
                is_maker=False,
                side="BUY",
            ),
        ]
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        sync_service = MEXCSyncService(db_session)
        result = await sync_service.sync_transactions(exchange_connection)

        assert result["success"] is True
        assert result["synced_count"] == 1

        # Check portfolio was created
        portfolio = db_session.query(Portfolio).filter_by(user_id=user.id).first()
        assert portfolio is not None

        # Check asset was created
        btc_asset = (
            db_session.query(Asset)
            .filter_by(portfolio_id=portfolio.id, symbol="BTC")
            .first()
        )
        assert btc_asset is not None

        # Check transaction was created
        transaction = (
            db_session.query(Transaction).filter_by(asset_id=btc_asset.id).first()
        )
        assert transaction is not None
        assert transaction.transaction_type == "buy"
        assert transaction.quantity == Decimal("0.5")
        assert transaction.price == Decimal("45000")
        assert transaction.exchange == "MEXC"

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_sync_transactions_no_duplicates(
        self, mock_client_class, db_session, user, exchange_connection
    ):
        """Test that duplicate transactions are not created."""
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = True
        mock_client.get_all_trades.return_value = [
            MEXCTrade(
                symbol="BTCUSDT",
                id="123",
                order_id="456",
                price=Decimal("45000"),
                qty=Decimal("0.5"),
                quote_qty=Decimal("22500"),
                commission=Decimal("0"),
                commission_asset="USDT",
                time=1609459200000,
                is_buyer=True,
                is_maker=False,
                side="BUY",
            ),
        ]
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        sync_service = MEXCSyncService(db_session)

        # First sync
        await sync_service.sync_transactions(exchange_connection)

        # Second sync with same trades
        result = await sync_service.sync_transactions(exchange_connection)

        # Should not create new transactions
        assert result["synced_count"] == 0

        # Count total transactions
        transactions = db_session.query(Transaction).all()
        assert len(transactions) == 1

    @pytest.mark.asyncio
    @patch("app.services.mexc_client.MEXCClient")
    async def test_full_sync(
        self, mock_client_class, db_session, user, exchange_connection
    ):
        """Test full sync including holdings and transactions."""
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = True
        mock_client.get_holdings.return_value = [
            MEXCHolding(
                asset="BTC",
                free=Decimal("1.0"),
                locked=Decimal("0"),
                total=Decimal("1.0"),
            ),
        ]
        mock_client.get_all_trades.return_value = [
            MEXCTrade(
                symbol="BTCUSDT",
                id="123",
                order_id="456",
                price=Decimal("45000"),
                qty=Decimal("0.5"),
                quote_qty=Decimal("22500"),
                commission=Decimal("0"),
                commission_asset="USDT",
                time=1609459200000,
                is_buyer=True,
                is_maker=False,
                side="BUY",
            ),
        ]
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        sync_service = MEXCSyncService(db_session)
        result = await sync_service.full_sync(exchange_connection)

        assert result["holdings"]["success"] is True
        assert result["transactions"]["success"] is True
        assert len(result["errors"]) == 0


class TestMEXCHolding:
    """Tests for MEXCHolding model."""

    def test_holding_creation(self):
        """Test creating a holding."""
        holding = MEXCHolding(
            asset="BTC",
            free=Decimal("1.5"),
            locked=Decimal("0.5"),
            total=Decimal("2.0"),
        )

        assert holding.asset == "BTC"
        assert holding.free == Decimal("1.5")
        assert holding.locked == Decimal("0.5")
        assert holding.total == Decimal("2.0")


class TestMEXCTrade:
    """Tests for MEXCTrade model."""

    def test_trade_creation(self):
        """Test creating a trade."""
        trade = MEXCTrade(
            symbol="BTCUSDT",
            id="12345",
            order_id="67890",
            price=Decimal("45000.00"),
            qty=Decimal("0.5"),
            quote_qty=Decimal("22500.00"),
            commission=Decimal("22.50"),
            commission_asset="USDT",
            time=1609459200000,
            is_buyer=True,
            is_maker=False,
            side="BUY",
        )

        assert trade.symbol == "BTCUSDT"
        assert trade.id == "12345"
        assert trade.price == Decimal("45000.00")
        assert trade.is_buyer is True
        assert trade.side == "BUY"

    def test_trade_sell_side(self):
        """Test trade with SELL side."""
        trade = MEXCTrade(
            symbol="ETHUSDT",
            id="123",
            order_id="456",
            price=Decimal("3000"),
            qty=Decimal("5"),
            quote_qty=Decimal("15000"),
            commission=Decimal("15"),
            commission_asset="USDT",
            time=1609459200000,
            is_buyer=False,
            is_maker=True,
            side="SELL",
        )

        assert trade.is_buyer is False
        assert trade.side == "SELL"


class TestMEXCErrorHandling:
    """Tests for MEXC error handling."""

    def test_mex_error(self):
        """Test base MEXC error."""
        error = MEXCError("Test error", code=-1000)
        assert str(error) == "Test error"
        assert error.code == -1000

    def test_mex_auth_error(self):
        """Test MEXC auth error."""
        error = MEXCAuthError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, MEXCError)

    def test_mex_rate_limit_error(self):
        """Test MEXC rate limit error."""
        error = MEXCRateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert isinstance(error, MEXCError)

    def test_mex_api_error(self):
        """Test MEXC API error."""
        response = {"code": -1001, "msg": "Internal error"}
        error = MEXCAPIError("API error", code=-1001, response=response)
        assert error.code == -1001
        assert error.response == response
