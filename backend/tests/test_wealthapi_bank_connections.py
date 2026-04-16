"""
Tests for WealthAPI bank connection flow.

TDD: Tests for bank connection methods on WealthApiClient.
Tests cover: create connection, list connections, web form flow,
update/refresh, delete, poll sync process.
"""

import time

import pytest
from unittest.mock import Mock

from app.integrations.wealthapi import (
    WealthApiClient,
    WealthApiError,
    WealthApiAuthError,
)


def _make_authenticated_client():
    """Create a client with valid auth tokens."""
    client = WealthApiClient(client_id="id", client_secret="secret")
    client._access_token = "token"
    client._token_expires_at = time.time() + 3600
    return client


class TestCreateBankConnection:
    """Tests for POST v2/bankConnections."""

    def test_create_bank_connection_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "conn-123"}'
        mock_response.json.return_value = {
            "id": "conn-123",
            "bankConnectionName": "Deutsche Bank",
            "bankId": 277672,
            "type": "ONLINE_BANKING",
            "updateStatus": "IN_PROGRESS",
            "categorizationStatus": "PENDING",
            "interfaces": [
                {
                    "interface": "WEB_SCRAPER",
                    "status": "UPDATED",
                }
            ],
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.create_bank_connection(bank_id=277672)
        assert result["id"] == "conn-123"
        assert result["bankId"] == 277672

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "POST"
        assert "bankConnections" in call_args.kwargs["url"]
        assert call_args.kwargs["json"]["bankId"] == 277672

    def test_create_bank_connection_with_credentials(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "conn-456"}'
        mock_response.json.return_value = {"id": "conn-456"}
        client._session.request = Mock(return_value=mock_response)

        result = client.create_bank_connection(
            bank_id=277672,
            credentials={
                "loginName": "user123",
                "password": "pass456",
            },
        )
        assert result["id"] == "conn-456"

        call_args = client._session.request.call_args
        body = call_args.kwargs["json"]
        assert body["bankId"] == 277672
        assert body["credentials"]["loginName"] == "user123"

    def test_create_bank_connection_with_redirect(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "conn-789"}'
        mock_response.json.return_value = {
            "id": "conn-789",
            "bankId": 277672,
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.create_bank_connection(
            bank_id=277672,
            redirect_url="https://app.example.com/callback",
        )
        assert result["id"] == "conn-789"

        call_args = client._session.request.call_args
        body = call_args.kwargs["json"]
        assert body["redirectUrl"] == "https://app.example.com/callback"

    def test_create_bank_connection_auth_error(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiAuthError):
            client.create_bank_connection(bank_id=277672)


class TestListBankConnections:
    """Tests for GET v2/bankConnections."""

    def test_list_bank_connections_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"connections": []}'
        mock_response.json.return_value = {
            "connections": [
                {
                    "id": "conn-1",
                    "bankConnectionName": "Deutsche Bank",
                    "bankId": 277672,
                    "updateStatus": "READY",
                },
                {
                    "id": "conn-2",
                    "bankConnectionName": "Sparkasse",
                    "bankId": 12345,
                    "updateStatus": "READY",
                },
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.list_bank_connections()
        assert len(result["connections"]) == 2
        assert result["connections"][0]["id"] == "conn-1"

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "bankConnections" in call_args.kwargs["url"]

    def test_list_bank_connections_with_ids_filter(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"connections": []}'
        mock_response.json.return_value = {"connections": []}
        client._session.request = Mock(return_value=mock_response)

        client.list_bank_connections(ids=["conn-1", "conn-2"])

        call_args = client._session.request.call_args
        assert call_args.kwargs["params"]["ids"] == "conn-1,conn-2"

    def test_list_bank_connections_empty(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"connections": []}'
        mock_response.json.return_value = {"connections": []}
        client._session.request = Mock(return_value=mock_response)

        result = client.list_bank_connections()
        assert result["connections"] == []


class TestGetBankConnection:
    """Tests for GET v2/bankConnections/{id}."""

    def test_get_bank_connection_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "conn-1"}'
        mock_response.json.return_value = {
            "id": "conn-1",
            "bankConnectionName": "Deutsche Bank",
            "bankId": 277672,
            "updateStatus": "READY",
            "accounts": [
                {
                    "id": "acc-1",
                    "accountName": "Checking",
                    "balance": 1234.56,
                }
            ],
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_bank_connection("conn-1")
        assert result["id"] == "conn-1"
        assert result["bankConnectionName"] == "Deutsche Bank"

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "bankConnections/conn-1" in call_args.kwargs["url"]

    def test_get_bank_connection_not_found(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError) as exc_info:
            client.get_bank_connection("nonexistent")
        assert exc_info.value.status_code == 404


class TestWebFormFlow:
    """Tests for v2/bankConnections/webFormFlow/{id}."""

    def test_get_web_form_flow_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "wf-1"}'
        mock_response.json.return_value = {
            "id": "wf-1",
            "status": "NOT_YET_OPENED",
            "serviceUrl": "https://sandbox.wealthapi.eu/webForm/wf-1",
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_web_form_flow("wf-1")
        assert result["id"] == "wf-1"
        assert "serviceUrl" in result

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "bankConnections/webFormFlow/wf-1" in call_args.kwargs["url"]

    def test_get_web_form_flow_completed(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "wf-1"}'
        mock_response.json.return_value = {
            "id": "wf-1",
            "status": "COMPLETED",
            "serviceUrl": "https://sandbox.wealthapi.eu/webForm/wf-1",
            "bankConnectionId": "conn-123",
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_web_form_flow("wf-1")
        assert result["status"] == "COMPLETED"
        assert result["bankConnectionId"] == "conn-123"


class TestUpdateBankConnection:
    """Tests for PUT v2/bankConnections/{id}/update."""

    def test_update_bank_connection_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "conn-1"}'
        mock_response.json.return_value = {
            "id": "conn-1",
            "updateStatus": "IN_PROGRESS",
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.update_bank_connection("conn-1")
        assert result["updateStatus"] == "IN_PROGRESS"

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "PUT"
        assert "bankConnections/conn-1/update" in call_args.kwargs["url"]

    def test_update_bank_connection_with_redirect(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "conn-1"}'
        mock_response.json.return_value = {"id": "conn-1"}
        client._session.request = Mock(return_value=mock_response)

        client.update_bank_connection(
            "conn-1",
            redirect_url="https://app.example.com/callback",
        )

        call_args = client._session.request.call_args
        body = call_args.kwargs["json"]
        assert body["redirectUrl"] == "https://app.example.com/callback"


class TestDeleteBankConnection:
    """Tests for DELETE v2/bankConnections/{id}."""

    def test_delete_bank_connection_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.content = b""
        client._session.request = Mock(return_value=mock_response)

        result = client.delete_bank_connection("conn-1")
        assert result == {}

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "DELETE"
        assert "bankConnections/conn-1" in call_args.kwargs["url"]

    def test_delete_bank_connection_not_found(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError) as exc_info:
            client.delete_bank_connection("nonexistent")
        assert exc_info.value.status_code == 404


class TestPollUpdateProcess:
    """Tests for GET v2/bankConnections/updateProcess/{processId}."""

    def test_poll_update_process_in_progress(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "proc-1"}'
        mock_response.json.return_value = {
            "id": "proc-1",
            "status": "IN_PROGRESS",
            "progress": 50,
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.poll_update_process("proc-1")
        assert result["status"] == "IN_PROGRESS"
        assert result["progress"] == 50

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "bankConnections/updateProcess/proc-1" in call_args.kwargs["url"]

    def test_poll_update_process_completed(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "proc-1"}'
        mock_response.json.return_value = {
            "id": "proc-1",
            "status": "COMPLETED",
            "progress": 100,
            "bankConnectionId": "conn-1",
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.poll_update_process("proc-1")
        assert result["status"] == "COMPLETED"
        assert result["bankConnectionId"] == "conn-1"

    def test_poll_update_process_failed(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "proc-1"}'
        mock_response.json.return_value = {
            "id": "proc-1",
            "status": "FAILED",
            "error": "Bank server unavailable",
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.poll_update_process("proc-1")
        assert result["status"] == "FAILED"
        assert "error" in result
