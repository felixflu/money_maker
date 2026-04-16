"""
Tests for WealthAPI account/holdings methods.

TDD: Tests for fetching accounts, holdings, valuations, and balance data
from WealthAPI and mapping to portfolio model.
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


class TestListAccounts:
    """Tests for GET v2/accounts."""

    def test_list_accounts_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"accounts": []}'
        mock_response.json.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "accountName": "Depot Deutsche Bank",
                    "accountTypeId": 8,
                    "accountType": "DEPOT",
                    "balance": 15234.56,
                    "bankConnectionId": "conn-1",
                },
                {
                    "id": "acc-2",
                    "accountName": "Girokonto",
                    "accountTypeId": 1,
                    "accountType": "CHECKING",
                    "balance": 2500.00,
                    "bankConnectionId": "conn-1",
                },
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.list_accounts()
        assert len(result["accounts"]) == 2
        assert result["accounts"][0]["accountType"] == "DEPOT"

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "accounts" in call_args.kwargs["url"]

    def test_list_accounts_filter_depot(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"accounts": []}'
        mock_response.json.return_value = {
            "accounts": [
                {
                    "id": "acc-1",
                    "accountName": "Depot",
                    "accountType": "DEPOT",
                    "balance": 15234.56,
                },
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.list_accounts(account_type="DEPOT")
        call_args = client._session.request.call_args
        assert call_args.kwargs["params"]["accountType"] == "DEPOT"

    def test_list_accounts_empty(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"accounts": []}'
        mock_response.json.return_value = {"accounts": []}
        client._session.request = Mock(return_value=mock_response)

        result = client.list_accounts()
        assert result["accounts"] == []


class TestGetAccount:
    """Tests for GET v2/accounts/{id}."""

    def test_get_account_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "acc-1"}'
        mock_response.json.return_value = {
            "id": "acc-1",
            "accountName": "Depot Deutsche Bank",
            "accountType": "DEPOT",
            "balance": 15234.56,
            "bankConnectionId": "conn-1",
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
        client._session.request = Mock(return_value=mock_response)

        result = client.get_account("acc-1")
        assert result["id"] == "acc-1"
        assert len(result["investments"]) == 2
        assert result["investments"][0]["isin"] == "IE00B4L5Y983"

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "accounts/acc-1" in call_args.kwargs["url"]

    def test_get_account_not_found(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        client._session.request = Mock(return_value=mock_response)

        with pytest.raises(WealthApiError) as exc_info:
            client.get_account("nonexistent")
        assert exc_info.value.status_code == 404


class TestGetAccountValuation:
    """Tests for GET v2/accounts/valuation."""

    def test_get_valuation_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {
            "totalValue": 25000.00,
            "currency": "EUR",
            "valuationDate": "2026-04-15",
            "accounts": [
                {
                    "accountId": "acc-1",
                    "value": 15234.56,
                },
                {
                    "accountId": "acc-2",
                    "value": 9765.44,
                },
            ],
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_account_valuation()
        assert result["totalValue"] == 25000.00

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "accounts/valuation" in call_args.kwargs["url"]

    def test_get_valuation_with_account_ids(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {"totalValue": 15234.56}
        client._session.request = Mock(return_value=mock_response)

        client.get_account_valuation(account_ids=["acc-1"])
        call_args = client._session.request.call_args
        assert call_args.kwargs["params"]["accountIds"] == "acc-1"


class TestGetAccountBalances:
    """Tests for GET v2/accounts/balances."""

    def test_get_balances_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {
            "balances": [
                {
                    "accountId": "acc-1",
                    "balance": 15234.56,
                    "date": "2026-04-15",
                },
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_account_balances(account_ids=["acc-1"])
        assert len(result["balances"]) == 1

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "accounts/balances" in call_args.kwargs["url"]


class TestGetAccountCategorization:
    """Tests for GET v2/accounts/categorize."""

    def test_get_categorization_success(self):
        client = _make_authenticated_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{}'
        mock_response.json.return_value = {
            "categories": [
                {
                    "name": "ETF",
                    "value": 10000.00,
                    "percentage": 65.7,
                },
                {
                    "name": "Stocks",
                    "value": 5234.56,
                    "percentage": 34.3,
                },
            ]
        }
        client._session.request = Mock(return_value=mock_response)

        result = client.get_account_categorization()
        assert len(result["categories"]) == 2

        call_args = client._session.request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert "accounts/categorize" in call_args.kwargs["url"]
