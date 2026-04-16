"""
Tests for bank connections router endpoints.

TDD: Tests for the bank connection flow API endpoints with mocked
WealthAPI client and in-memory SQLite database.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.user import User
from app.models.bank_connection import BankConnection
from app.database import get_db
from app.auth import get_current_user
from app.main import app


# Test database setup
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_test_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def get_test_user():
    return User(id=1, email="test@example.com", hashed_password="hashed", is_active=True)


app.dependency_overrides[get_db] = get_test_db
app.dependency_overrides[get_current_user] = get_test_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_user():
    """Seed a test user into the database."""
    db = TestSession()
    user = User(
        id=1,
        email="test@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.close()


def _seed_bank_connection(
    wealthapi_id="conn-123",
    bank_name="Deutsche Bank",
    bank_id=277672,
):
    """Seed a bank connection into the database."""
    _seed_user()
    db = TestSession()
    conn = BankConnection(
        user_id=1,
        wealthapi_connection_id=wealthapi_id,
        bank_name=bank_name,
        bank_id=bank_id,
        update_status="READY",
        is_active=True,
    )
    db.add(conn)
    db.commit()
    conn_id = conn.id
    db.close()
    return conn_id


class TestCreateBankConnection:
    """Tests for POST /api/v1/bank-connections."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_create_success(self, mock_get_client):
        _seed_user()
        mock_client = Mock()
        mock_client.create_bank_connection.return_value = {
            "id": "wapi-conn-1",
            "bankConnectionName": "Deutsche Bank",
            "bankId": 277672,
            "updateStatus": "IN_PROGRESS",
            "categorizationStatus": "PENDING",
            "interfaces": [],
        }
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/bank-connections",
            json={"bank_id": 277672},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["bank_connection"]["bank_name"] == "Deutsche Bank"
        assert data["bank_connection"]["wealthapi_connection_id"] == "wapi-conn-1"
        assert data["bank_connection"]["bank_id"] == 277672

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_create_with_web_form(self, mock_get_client):
        _seed_user()
        mock_client = Mock()
        mock_client.create_bank_connection.return_value = {
            "id": "wapi-conn-2",
            "bankConnectionName": "Sparkasse",
            "bankId": 12345,
            "updateStatus": "IN_PROGRESS",
            "interfaces": [
                {"interface": "WEB_SCRAPER", "webFormId": "wf-abc"}
            ],
        }
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/bank-connections",
            json={
                "bank_id": 12345,
                "redirect_url": "https://app.example.com/callback",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["web_form_flow_id"] == "wf-abc"

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_create_wealthapi_auth_error(self, mock_get_client):
        _seed_user()
        mock_client = Mock()
        from app.integrations.wealthapi import WealthApiAuthError
        mock_client.create_bank_connection.side_effect = WealthApiAuthError(
            "Invalid mandator credentials", status_code=401
        )
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/bank-connections",
            json={"bank_id": 277672},
        )

        assert response.status_code == 401

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_create_wealthapi_rate_limit(self, mock_get_client):
        _seed_user()
        mock_client = Mock()
        from app.integrations.wealthapi import WealthApiRateLimitError
        mock_client.create_bank_connection.side_effect = WealthApiRateLimitError(
            retry_after=120
        )
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/bank-connections",
            json={"bank_id": 277672},
        )

        assert response.status_code == 429


class TestListBankConnections:
    """Tests for GET /api/v1/bank-connections."""

    def test_list_empty(self):
        _seed_user()
        response = client.get("/api/v1/bank-connections")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_connections(self):
        conn_id = _seed_bank_connection()
        response = client.get("/api/v1/bank-connections")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["bank_name"] == "Deutsche Bank"
        assert data[0]["wealthapi_connection_id"] == "conn-123"


class TestGetBankConnection:
    """Tests for GET /api/v1/bank-connections/{id}."""

    def test_get_success(self):
        conn_id = _seed_bank_connection()
        response = client.get(f"/api/v1/bank-connections/{conn_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["bank_name"] == "Deutsche Bank"
        assert data["bank_id"] == 277672

    def test_get_not_found(self):
        _seed_user()
        response = client.get("/api/v1/bank-connections/999")
        assert response.status_code == 404


class TestWebFormFlow:
    """Tests for GET /api/v1/bank-connections/web-form/{flow_id}."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_get_web_form_status(self, mock_get_client):
        mock_client = Mock()
        mock_client.get_web_form_flow.return_value = {
            "id": "wf-1",
            "status": "NOT_YET_OPENED",
            "serviceUrl": "https://sandbox.wealthapi.eu/webForm/wf-1",
        }
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/bank-connections/web-form/wf-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "NOT_YET_OPENED"
        assert data["service_url"] == "https://sandbox.wealthapi.eu/webForm/wf-1"

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_get_web_form_completed(self, mock_get_client):
        mock_client = Mock()
        mock_client.get_web_form_flow.return_value = {
            "id": "wf-1",
            "status": "COMPLETED",
            "bankConnectionId": "conn-123",
        }
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/bank-connections/web-form/wf-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["bank_connection_id"] == "conn-123"


class TestUpdateBankConnection:
    """Tests for PUT /api/v1/bank-connections/{id}/update."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_update_success(self, mock_get_client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.update_bank_connection.return_value = {
            "id": "conn-123",
            "updateStatus": "IN_PROGRESS",
            "processId": "proc-1",
        }
        mock_get_client.return_value = mock_client

        response = client.put(f"/api/v1/bank-connections/{conn_id}/update")
        assert response.status_code == 200
        data = response.json()
        assert data["process_id"] == "proc-1"
        assert data["bank_connection"]["update_status"] == "IN_PROGRESS"

    def test_update_not_found(self):
        _seed_user()
        response = client.put("/api/v1/bank-connections/999/update")
        assert response.status_code == 404

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_update_inactive_connection(self, mock_get_client):
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

        response = client.put(f"/api/v1/bank-connections/{conn_id}/update")
        assert response.status_code == 400


class TestDeleteBankConnection:
    """Tests for DELETE /api/v1/bank-connections/{id}."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_delete_success(self, mock_get_client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        mock_client.delete_bank_connection.return_value = {}
        mock_get_client.return_value = mock_client

        response = client.delete(f"/api/v1/bank-connections/{conn_id}")
        assert response.status_code == 204

        # Verify deleted from DB
        get_response = client.get(f"/api/v1/bank-connections/{conn_id}")
        assert get_response.status_code == 404

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_delete_wealthapi_fails_still_removes_local(self, mock_get_client):
        conn_id = _seed_bank_connection()
        mock_client = Mock()
        from app.integrations.wealthapi import WealthApiError
        mock_client.delete_bank_connection.side_effect = WealthApiError(
            "Not found", status_code=404
        )
        mock_get_client.return_value = mock_client

        response = client.delete(f"/api/v1/bank-connections/{conn_id}")
        assert response.status_code == 204

    def test_delete_not_found(self):
        _seed_user()
        response = client.delete("/api/v1/bank-connections/999")
        assert response.status_code == 404


class TestPollUpdateProcess:
    """Tests for GET /api/v1/bank-connections/process/{process_id}."""

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_poll_in_progress(self, mock_get_client):
        mock_client = Mock()
        mock_client.poll_update_process.return_value = {
            "id": "proc-1",
            "status": "IN_PROGRESS",
            "progress": 50,
        }
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/bank-connections/process/proc-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert data["progress"] == 50

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_poll_completed(self, mock_get_client):
        mock_client = Mock()
        mock_client.poll_update_process.return_value = {
            "id": "proc-1",
            "status": "COMPLETED",
            "progress": 100,
            "bankConnectionId": "conn-123",
        }
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/bank-connections/process/proc-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["bank_connection_id"] == "conn-123"

    @patch("app.routers.bank_connections._get_wealthapi_client")
    def test_poll_failed(self, mock_get_client):
        mock_client = Mock()
        mock_client.poll_update_process.return_value = {
            "id": "proc-1",
            "status": "FAILED",
            "error": "Bank server unavailable",
        }
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/bank-connections/process/proc-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert data["error"] == "Bank server unavailable"
