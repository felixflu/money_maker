"""
Tests for holdings sync service and router.

TDD: Tests for syncing WealthAPI account/investment data
to our Portfolio/Asset model.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient

from app.models.user import User
from app.models.bank_connection import BankConnection
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.auth import get_current_user
from app.main import app
from tests.conftest import TestSession


def get_test_user():
    return User(id=1, email="test@example.com", hashed_password="hashed", is_active=True)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_user():
    db = TestSession()
    user = User(id=1, email="test@example.com", hashed_password="hashed", is_active=True)
    db.add(user)
    db.commit()
    db.close()


def _seed_bank_connection(wealthapi_id="conn-123"):
    _seed_user()
    db = TestSession()
    conn = BankConnection(
        user_id=1,
        wealthapi_connection_id=wealthapi_id,
        bank_name="Deutsche Bank",
        bank_id=277672,
        update_status="READY",
        is_active=True,
    )
    db.add(conn)
    db.commit()
    conn_id = conn.id
    db.close()
    return conn_id


MOCK_ACCOUNTS_RESPONSE = {
    "accounts": [
        {
            "id": "acc-1",
            "accountName": "Depot Deutsche Bank",
            "accountType": "DEPOT",
            "balance": 15234.56,
            "bankConnectionId": "conn-123",
        },
    ]
}

MOCK_ACCOUNT_DETAIL = {
    "id": "acc-1",
    "accountName": "Depot Deutsche Bank",
    "accountType": "DEPOT",
    "balance": 15234.56,
    "bankConnectionId": "conn-123",
    "investments": [
        {
            "id": "inv-1",
            "securityName": "iShares MSCI World ETF",
            "isin": "IE00B4L5Y983",
            "wkn": "A0RPWH",
            "quantity": 42.5,
            "currentValue": 3825.00,
            "entryQuote": 85.20,
            "currentQuote": 90.00,
            "profitOrLoss": 204.00,
        },
        {
            "id": "inv-2",
            "securityName": "Apple Inc.",
            "isin": "US0378331005",
            "wkn": "865985",
            "quantity": 10,
            "currentValue": 1750.00,
            "entryQuote": 150.00,
            "currentQuote": 175.00,
            "profitOrLoss": 250.00,
        },
    ],
}


class TestSyncHoldingsEndpoint:
    """Tests for POST /api/v1/bank-connections/{id}/sync-holdings."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_success(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = MOCK_ACCOUNT_DETAIL
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["holdings_synced"] == 2
        assert data["portfolio_id"] is not None

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_creates_portfolio(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = MOCK_ACCOUNT_DETAIL
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200

        # Verify portfolio was created
        db = TestSession()
        portfolio = db.query(Portfolio).filter(Portfolio.user_id == 1).first()
        assert portfolio is not None
        assert "Deutsche Bank" in portfolio.name
        assert len(portfolio.assets) == 2
        db.close()

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_maps_investments_to_assets(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = MOCK_ACCOUNT_DETAIL
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200

        db = TestSession()
        assets = db.query(Asset).all()
        assert len(assets) == 2

        # Check ETF mapping
        etf = db.query(Asset).filter(Asset.symbol == "IE00B4L5Y983").first()
        assert etf is not None
        assert etf.name == "iShares MSCI World ETF"
        assert etf.quantity == Decimal("42.5")
        assert etf.average_buy_price == Decimal("85.20")

        # Check stock mapping
        stock = db.query(Asset).filter(Asset.symbol == "US0378331005").first()
        assert stock is not None
        assert stock.name == "Apple Inc."
        assert stock.quantity == Decimal("10")
        assert stock.average_buy_price == Decimal("150.00")
        db.close()

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_updates_existing_assets(self, mock_get_client, client):
        conn_id = _seed_bank_connection()

        # Create existing portfolio and asset
        db = TestSession()
        portfolio = Portfolio(user_id=1, name="Deutsche Bank - Depot")
        db.add(portfolio)
        db.commit()
        asset = Asset(
            portfolio_id=portfolio.id,
            symbol="IE00B4L5Y983",
            name="iShares MSCI World ETF",
            asset_type="etf",
            quantity=Decimal("30.0"),
            average_buy_price=Decimal("80.00"),
        )
        db.add(asset)
        db.commit()
        db.close()

        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = MOCK_ACCOUNT_DETAIL
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200

        # Verify asset was updated, not duplicated
        db = TestSession()
        assets = db.query(Asset).filter(Asset.symbol == "IE00B4L5Y983").all()
        assert len(assets) == 1
        assert assets[0].quantity == Decimal("42.5")
        assert assets[0].average_buy_price == Decimal("85.20")
        db.close()

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_updates_last_synced(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = MOCK_ACCOUNT_DETAIL
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200

        db = TestSession()
        conn = db.query(BankConnection).filter(BankConnection.id == conn_id).first()
        assert conn.last_synced_at is not None
        db.close()

    def test_sync_not_found(self, client):
        _seed_user()
        response = client.post("/api/v1/bank-connections/999/sync-holdings")
        assert response.status_code == 404

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_inactive_connection(self, mock_get_client, client):
        _seed_user()
        db = TestSession()
        conn = BankConnection(
            user_id=1,
            wealthapi_connection_id="conn-inactive",
            bank_name="Inactive Bank",
            bank_id=99999,
            update_status="READY",
            is_active=False,
        )
        db.add(conn)
        db.commit()
        conn_id = conn.id
        db.close()

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 400

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_no_depot_accounts(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-2",
                    "accountName": "Girokonto",
                    "accountType": "CHECKING",
                    "balance": 2500.00,
                    "bankConnectionId": "conn-123",
                },
            ]
        }
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200
        data = response.json()
        assert data["holdings_synced"] == 0

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_wealthapi_error(self, mock_get_client, client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        from app.integrations.wealthapi import WealthApiError
        mock_client.list_accounts.side_effect = WealthApiError(
            "Server error", status_code=500
        )
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 502

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_sync_determines_asset_type(self, mock_get_client, client):
        """Test that asset_type is inferred from investment data."""
        conn_id = _seed_bank_connection()

        account_with_types = {
            "id": "acc-1",
            "accountName": "Depot",
            "accountType": "DEPOT",
            "balance": 5000.00,
            "bankConnectionId": "conn-123",
            "investments": [
                {
                    "id": "inv-1",
                    "securityName": "iShares Core MSCI World UCITS ETF",
                    "isin": "IE00B4L5Y983",
                    "quantity": 10,
                    "currentValue": 1000.00,
                    "entryQuote": 90.00,
                    "currentQuote": 100.00,
                    "profitOrLoss": 100.00,
                },
            ],
        }

        mock_client = Mock()
        mock_client.list_accounts.return_value = MOCK_ACCOUNTS_RESPONSE
        mock_client.get_account.return_value = account_with_types
        mock_get_client.return_value = mock_client

        response = client.post(f"/api/v1/bank-connections/{conn_id}/sync-holdings")
        assert response.status_code == 200

        db = TestSession()
        asset = db.query(Asset).first()
        assert asset is not None
        # asset_type should be set (etf, stock, or investment as fallback)
        assert asset.asset_type in ("etf", "stock", "bond", "fund", "investment")
        db.close()
