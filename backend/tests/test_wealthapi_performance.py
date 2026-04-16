"""
Tests for WealthAPI historic valuations and performance endpoints.

TDD: Tests written first for v1 performance endpoints:
- GET v1/accounts/historicValuations
- GET v1/performance/absoluteReturn
- GET v1/accounts/cashFlows
"""

import time

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.integrations.wealthapi import (
    WealthApiClient,
    WealthApiError,
    WealthApiAuthError,
)


class TestHistoricValuations:
    """Tests for GET v1/accounts/historicValuations."""

    def _make_client(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        client._token_expires_at = time.time() + 3600
        return client

    def test_get_historic_valuations_basic(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"valuations": []}'
        mock_response.json.return_value = {
            "valuations": [
                {"date": "2026-01-01", "totalValue": 10000.0},
                {"date": "2026-01-02", "totalValue": 10150.0},
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_historic_valuations()
        assert "valuations" in result
        assert len(result["valuations"]) == 2

        # Verify v1 URL used
        call_args = client._session.request.call_args
        url = call_args.kwargs["url"]
        assert "/api/v1/accounts/historicValuations" in url

    def test_get_historic_valuations_with_params(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"valuations": []}'
        mock_response.json.return_value = {"valuations": []}
        client._session.request = Mock(return_value=mock_response)

        result = client.get_historic_valuations(
            account_ids=["acc1", "acc2"],
            interval_type="month",
            start_date="2025-01-01",
            include_cash=True,
        )

        call_args = client._session.request.call_args
        params = call_args.kwargs["params"]
        assert params["accountIds"] == "acc1,acc2"
        assert params["intervalType"] == "month"
        assert params["startDate"] == "2025-01-01"
        assert params["includeCash"] == "true"

    def test_get_historic_valuations_default_no_params(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"valuations": []}'
        mock_response.json.return_value = {"valuations": []}
        client._session.request = Mock(return_value=mock_response)

        client.get_historic_valuations()

        call_args = client._session.request.call_args
        params = call_args.kwargs["params"]
        assert params is None

    def test_get_historic_valuations_api_error(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal error"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError):
            client.get_historic_valuations()


class TestAbsoluteReturn:
    """Tests for GET v1/performance/absoluteReturn."""

    def _make_client(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        client._token_expires_at = time.time() + 3600
        return client

    def test_get_absolute_return_basic(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"returns": []}'
        mock_response.json.return_value = {
            "returns": [
                {
                    "date": "2026-01-01",
                    "absoluteReturn": 500.0,
                    "dividends": 50.0,
                    "expenses": 10.0,
                }
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_absolute_return()
        assert "returns" in result

        call_args = client._session.request.call_args
        url = call_args.kwargs["url"]
        assert "/api/v1/performance/absoluteReturn" in url

    def test_get_absolute_return_with_params(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"returns": []}'
        mock_response.json.return_value = {"returns": []}
        client._session.request = Mock(return_value=mock_response)

        client.get_absolute_return(
            account_ids=["acc1"],
            interval_type="week",
            start_date="2025-06-01",
        )

        call_args = client._session.request.call_args
        params = call_args.kwargs["params"]
        assert params["accountIds"] == "acc1"
        assert params["intervalType"] == "week"
        assert params["startDate"] == "2025-06-01"


class TestCashFlows:
    """Tests for GET v1/accounts/cashFlows."""

    def _make_client(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        client._access_token = "token"
        client._token_expires_at = time.time() + 3600
        return client

    def test_get_cash_flows_basic(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"cashFlows": []}'
        mock_response.json.return_value = {
            "cashFlows": [
                {"date": "2026-01-15", "amount": -5000.0, "type": "DEPOSIT"},
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_cash_flows()
        assert "cashFlows" in result

        call_args = client._session.request.call_args
        url = call_args.kwargs["url"]
        assert "/api/v1/accounts/cashFlows" in url

    def test_get_cash_flows_with_params(self):
        client = self._make_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"cashFlows": []}'
        mock_response.json.return_value = {"cashFlows": []}
        client._session.request = Mock(return_value=mock_response)

        client.get_cash_flows(
            account_ids=["acc1", "acc2"],
            start_date="2025-01-01",
        )

        call_args = client._session.request.call_args
        params = call_args.kwargs["params"]
        assert params["accountIds"] == "acc1,acc2"
        assert params["startDate"] == "2025-01-01"


class TestV1UrlBuilding:
    """Test that v1 endpoints use correct URL pattern."""

    def test_build_v1_url(self):
        client = WealthApiClient(
            client_id="id",
            client_secret="secret",
            base_url="https://sandbox.wealthapi.eu",
        )
        url = client._build_url("accounts/historicValuations", api_version="v1")
        assert url == "https://sandbox.wealthapi.eu/api/v1/accounts/historicValuations"

    def test_build_v2_url_default(self):
        client = WealthApiClient(client_id="id", client_secret="secret")
        url = client._build_url("accounts")
        assert url == "https://sandbox.wealthapi.eu/api/v2/accounts"
