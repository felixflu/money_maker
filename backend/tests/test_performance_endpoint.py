"""
Tests for bank connection performance endpoint.

TDD: Tests for GET /api/v1/bank-connections/{id}/performance
that fetches historic valuations from WealthAPI and maps to PnLDataPoint format.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.models.user import User
from app.models.bank_connection import BankConnection

# Import shared test fixtures
from tests.conftest import TestSession


client = TestClient(app)


def _create_test_user(db) -> User:
    user = User(
        email="perf@test.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_bank_connection(db, user_id: int) -> BankConnection:
    conn = BankConnection(
        user_id=user_id,
        wealthapi_connection_id="wapi-conn-123",
        bank_name="Test Bank",
        bank_id=1,
        update_status="READY",
        is_active=True,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


class TestAggregatedPerformance:
    """Tests for GET /api/v1/bank-connections/performance (all connections)."""

    def setup_method(self):
        self.db = TestSession()
        self.user = _create_test_user(self.db)
        self.conn = _create_bank_connection(self.db, self.user.id)

        async def override_user():
            return self.user

        app.dependency_overrides[get_current_user] = override_user

    def teardown_method(self):
        app.dependency_overrides.pop(get_current_user, None)
        self.db.close()

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_aggregated_performance_returns_data(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "bankConnectionId": "wapi-conn-123",
                    "accountType": "DEPOT",
                },
            ]
        }
        mock_client.get_historic_valuations.return_value = {
            "valuations": [
                {"date": "2026-01-01", "totalValue": 10000.0},
                {"date": "2026-02-01", "totalValue": 10500.0},
            ]
        }
        mock_client.get_absolute_return.return_value = {"returns": []}
        mock_client.get_cash_flows.return_value = {"cashFlows": []}

        response = client.get("/api/v1/bank-connections/performance")

        assert response.status_code == 200
        data = response.json()
        assert len(data["pnlHistory"]) == 2
        assert data["pnlHistory"][0]["date"] == "2026-01-01"

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_aggregated_performance_no_connections(self, mock_get_client):
        # Delete the connection so user has none
        self.db.delete(self.conn)
        self.db.commit()

        response = client.get("/api/v1/bank-connections/performance")

        assert response.status_code == 200
        data = response.json()
        assert data["pnlHistory"] == []

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_aggregated_performance_with_interval(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "bankConnectionId": "wapi-conn-123",
                    "accountType": "DEPOT",
                },
            ]
        }
        mock_client.get_historic_valuations.return_value = {"valuations": []}
        mock_client.get_absolute_return.return_value = {"returns": []}
        mock_client.get_cash_flows.return_value = {"cashFlows": []}

        response = client.get(
            "/api/v1/bank-connections/performance",
            params={"interval_type": "month"},
        )

        assert response.status_code == 200
        mock_client.get_historic_valuations.assert_called_once_with(
            account_ids=["acc-1"],
            interval_type="month",
            start_date=None,
            include_cash=True,
        )


class TestPerformanceEndpoint:
    """Tests for GET /api/v1/bank-connections/{id}/performance."""

    def setup_method(self):
        self.db = TestSession()
        self.user = _create_test_user(self.db)
        self.conn = _create_bank_connection(self.db, self.user.id)

        async def override_user():
            return self.user

        app.dependency_overrides[get_current_user] = override_user

    def teardown_method(self):
        app.dependency_overrides.pop(get_current_user, None)
        self.db.close()

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_returns_pnl_data(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock list_accounts to return depot accounts for this connection
        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "bankConnectionId": "wapi-conn-123",
                    "accountType": "DEPOT",
                },
            ]
        }

        # Mock historic valuations response
        mock_client.get_historic_valuations.return_value = {
            "valuations": [
                {"date": "2026-01-01", "totalValue": 10000.0},
                {"date": "2026-01-15", "totalValue": 10500.0},
                {"date": "2026-02-01", "totalValue": 10200.0},
            ]
        }

        response = client.get(f"/api/v1/bank-connections/{self.conn.id}/performance")

        assert response.status_code == 200
        data = response.json()
        assert "pnlHistory" in data
        assert len(data["pnlHistory"]) == 3
        assert data["pnlHistory"][0]["date"] == "2026-01-01"
        assert data["pnlHistory"][0]["value"] == 10000.0
        assert data["pnlHistory"][2]["value"] == 10200.0

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_with_interval_param(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "bankConnectionId": "wapi-conn-123",
                    "accountType": "DEPOT",
                },
            ]
        }
        mock_client.get_historic_valuations.return_value = {"valuations": []}

        response = client.get(
            f"/api/v1/bank-connections/{self.conn.id}/performance",
            params={"interval_type": "month", "start_date": "2025-01-01"},
        )

        assert response.status_code == 200
        mock_client.get_historic_valuations.assert_called_once_with(
            account_ids=["acc-1"],
            interval_type="month",
            start_date="2025-01-01",
            include_cash=True,
        )

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_includes_absolute_return(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "bankConnectionId": "wapi-conn-123",
                    "accountType": "DEPOT",
                },
            ]
        }
        mock_client.get_historic_valuations.return_value = {
            "valuations": [
                {"date": "2026-01-01", "totalValue": 10000.0},
            ]
        }
        mock_client.get_absolute_return.return_value = {
            "returns": [
                {
                    "date": "2026-01-01",
                    "absoluteReturn": 500.0,
                    "dividends": 50.0,
                    "expenses": 10.0,
                }
            ]
        }
        mock_client.get_cash_flows.return_value = {
            "cashFlows": [
                {"date": "2026-01-10", "amount": 5000.0, "type": "DEPOSIT"},
            ]
        }

        response = client.get(
            f"/api/v1/bank-connections/{self.conn.id}/performance"
        )

        assert response.status_code == 200
        data = response.json()
        assert "absoluteReturn" in data
        assert data["absoluteReturn"]["totalReturn"] == 500.0
        assert data["absoluteReturn"]["dividends"] == 50.0
        assert data["absoluteReturn"]["expenses"] == 10.0
        assert "cashFlows" in data
        assert len(data["cashFlows"]) == 1

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_not_found(self, mock_get_client):
        response = client.get("/api/v1/bank-connections/9999/performance")
        assert response.status_code == 404

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_inactive_connection(self, mock_get_client):
        self.conn.is_active = False
        self.db.commit()

        response = client.get(
            f"/api/v1/bank-connections/{self.conn.id}/performance"
        )
        assert response.status_code == 400

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_no_depot_accounts(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_accounts.return_value = {"accounts": []}

        response = client.get(
            f"/api/v1/bank-connections/{self.conn.id}/performance"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pnlHistory"] == []

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_performance_wealthapi_error(self, mock_get_client):
        from app.integrations.wealthapi import WealthApiError

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_accounts.side_effect = WealthApiError(
            "API down", status_code=502
        )

        response = client.get(
            f"/api/v1/bank-connections/{self.conn.id}/performance"
        )
        assert response.status_code == 502
