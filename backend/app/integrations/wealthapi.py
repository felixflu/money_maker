"""
WealthAPI client.

Provides integration with WealthAPI for bank connection management,
portfolio synchronization, and transaction import.

WealthAPI uses two-tier authentication:
1. Mandator-level: X-Mandator-Client-Id / X-Mandator-Client-Secret headers
2. User-level: JWT Bearer token from login endpoint (1h TTL, refresh flow)

Base URL pattern: https://{env}/api/{version}/{resource}
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Token refresh buffer: refresh 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300
# Default token TTL if not provided by server
DEFAULT_TOKEN_TTL_SECONDS = 3600


class WealthApiError(Exception):
    """Base exception for WealthAPI errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class WealthApiAuthError(WealthApiError):
    """Exception for authentication errors."""

    pass


class WealthApiRateLimitError(WealthApiError):
    """Exception for rate limit errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        status_code: int = 429,
        response_data: Optional[dict] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.retry_after = retry_after


class WealthApiClient:
    """
    Client for WealthAPI integration.

    Provides methods for:
    - Mandator-level authentication (app credentials)
    - User-level authentication (login, JWT management, refresh)
    - Base HTTP methods (GET/POST/PUT/DELETE)
    - Rate limit handling
    - Sandbox/production URL switching

    Args:
        client_id: Mandator client ID (X-Mandator-Client-Id)
        client_secret: Mandator client secret (X-Mandator-Client-Secret)
        base_url: API base URL (sandbox or production)
        timeout: Request timeout in seconds (default: 30)
    """

    API_VERSION = "v2"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "https://sandbox.wealthapi.eu",
        timeout: int = 30,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

        # User-level JWT token state
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_mandator_headers(self) -> dict[str, str]:
        """Get mandator-level authentication headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoneyMaker/1.0",
            "X-Mandator-Client-Id": self.client_id,
            "X-Mandator-Client-Secret": self.client_secret,
        }

    def _get_auth_headers(self) -> dict[str, str]:
        """Get full headers with mandator + user Bearer token."""
        headers = self._get_mandator_headers()
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _is_token_expired(self) -> bool:
        """Check if the access token is expired or about to expire."""
        if not self._access_token:
            return True
        return time.time() >= (self._token_expires_at - TOKEN_REFRESH_BUFFER_SECONDS)

    def _build_url(self, endpoint: str, api_version: Optional[str] = None) -> str:
        """Build full API URL from endpoint."""
        endpoint = endpoint.lstrip("/")
        version = api_version or self.API_VERSION
        return f"{self.base_url}/api/{version}/{endpoint}"

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code in (200, 201):
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError as e:
                raise WealthApiError(
                    f"Invalid JSON response: {e}",
                    status_code=response.status_code,
                )

        if response.status_code == 204:
            return {}

        if response.status_code == 401:
            raise WealthApiAuthError(
                "Authentication failed: Invalid credentials",
                status_code=401,
            )

        if response.status_code == 403:
            raise WealthApiAuthError(
                "Access forbidden: Check API permissions",
                status_code=403,
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise WealthApiRateLimitError(
                "Rate limit exceeded. Please try again later.",
                retry_after=retry_after,
                status_code=429,
            )

        # Parse error from response body
        error_message = f"API error: {response.status_code}"
        try:
            error_data = response.json()
            if "error" in error_data:
                error_message = f"API error: {error_data['error']}"
            elif "message" in error_data:
                error_message = f"API error: {error_data['message']}"
            elif "errors" in error_data:
                errors = error_data["errors"]
                if isinstance(errors, list) and len(errors) > 0:
                    error_message = (
                        f"API error: {errors[0].get('message', response.status_code)}"
                    )
                else:
                    error_message = f"API error: {errors}"
        except ValueError:
            error_message = f"API error: {response.status_code} - {response.text}"

        raise WealthApiError(
            error_message,
            status_code=response.status_code,
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        authenticated: bool = True,
        api_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the WealthAPI.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body for POST/PUT
            params: Query parameters
            authenticated: Whether to include user Bearer token
            api_version: Override API version (e.g. "v1" for legacy endpoints)

        Returns:
            Parsed JSON response

        Raises:
            WealthApiError: On request failure
        """
        url = self._build_url(endpoint, api_version=api_version)

        if authenticated:
            self._ensure_authenticated()
            headers = self._get_auth_headers()
        else:
            headers = self._get_mandator_headers()

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params,
                timeout=self.timeout,
            )
            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise WealthApiError(
                f"Request timeout after {self.timeout} seconds",
                status_code=408,
            )
        except requests.exceptions.ConnectionError as e:
            raise WealthApiError(
                f"Connection error: {e}",
                status_code=503,
            )
        except requests.exceptions.RequestException as e:
            raise WealthApiError(
                f"Request failed: {e}",
                status_code=500,
            )

    def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Authenticate a user and obtain JWT tokens.

        Args:
            username: User's login email/username
            password: User's password

        Returns:
            Token response with access_token, refresh_token, expires_in

        Raises:
            WealthApiAuthError: If login fails
        """
        try:
            response = self._make_request(
                "POST",
                "auth/login",
                data={"username": username, "password": password},
                authenticated=False,
            )
        except WealthApiAuthError:
            raise
        except WealthApiError as e:
            raise WealthApiAuthError(
                f"Login failed: {e.message}",
                status_code=e.status_code,
                response_data=e.response_data,
            )

        self._store_tokens(response)
        logger.info("WealthAPI user login successful")
        return response

    def _store_tokens(self, token_response: dict[str, Any]) -> None:
        """Store access and refresh tokens from a token response."""
        self._access_token = token_response.get("access_token")
        self._refresh_token = token_response.get("refresh_token")

        expires_in = token_response.get("expires_in", DEFAULT_TOKEN_TTL_SECONDS)
        self._token_expires_at = time.time() + expires_in

        if not self._access_token:
            raise WealthApiAuthError(
                "No access_token in login response",
                status_code=None,
                response_data=token_response,
            )

    def refresh_access_token(self) -> dict[str, Any]:
        """
        Refresh the JWT access token using the refresh token.

        Returns:
            New token response

        Raises:
            WealthApiAuthError: If refresh fails or no refresh token available
        """
        if not self._refresh_token:
            raise WealthApiAuthError(
                "No refresh token available. Login required.",
            )

        try:
            response = self._make_request(
                "POST",
                "auth/refresh",
                data={"refresh_token": self._refresh_token},
                authenticated=False,
            )
        except WealthApiAuthError:
            # Refresh token is invalid/expired — clear tokens
            self._access_token = None
            self._refresh_token = None
            self._token_expires_at = 0.0
            raise
        except WealthApiError as e:
            raise WealthApiAuthError(
                f"Token refresh failed: {e.message}",
                status_code=e.status_code,
                response_data=e.response_data,
            )

        self._store_tokens(response)
        logger.info("WealthAPI token refreshed successfully")
        return response

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._is_token_expired():
            return

        if self._refresh_token:
            logger.debug("Access token expired, attempting refresh")
            self.refresh_access_token()
        elif not self._access_token:
            raise WealthApiAuthError(
                "Not authenticated. Call login() first.",
            )

    def set_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: int = DEFAULT_TOKEN_TTL_SECONDS,
    ) -> None:
        """
        Set tokens directly (e.g. from stored credentials).

        Args:
            access_token: JWT access token
            refresh_token: JWT refresh token
            expires_in: Token TTL in seconds
        """
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = time.time() + expires_in

    def get(
        self, endpoint: str, params: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make an authenticated GET request."""
        return self._make_request("GET", endpoint, params=params)

    def post(
        self, endpoint: str, data: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make an authenticated POST request."""
        return self._make_request("POST", endpoint, data=data)

    def put(
        self, endpoint: str, data: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make an authenticated PUT request."""
        return self._make_request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> dict[str, Any]:
        """Make an authenticated DELETE request."""
        return self._make_request("DELETE", endpoint)

    # =========================================================================
    # Bank Connection Management (v2/bankConnections)
    # =========================================================================

    def create_bank_connection(
        self,
        bank_id: int,
        credentials: Optional[dict] = None,
        redirect_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Initiate a new bank connection.

        Args:
            bank_id: WealthAPI bank identifier
            credentials: Optional login credentials (loginName, password)
            redirect_url: Optional redirect URL for web form auth flow

        Returns:
            BankSynchronizationProcess response with connection details
        """
        data: dict[str, Any] = {"bankId": bank_id}
        if credentials:
            data["credentials"] = credentials
        if redirect_url:
            data["redirectUrl"] = redirect_url
        return self.post("bankConnections", data=data)

    def list_bank_connections(
        self,
        ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        List existing bank connections.

        Args:
            ids: Optional list of connection IDs to filter by

        Returns:
            Dict with 'connections' list
        """
        params = {}
        if ids:
            params["ids"] = ",".join(ids)
        return self.get("bankConnections", params=params if params else None)

    def get_bank_connection(self, connection_id: str) -> dict[str, Any]:
        """
        Get details of a specific bank connection.

        Args:
            connection_id: Bank connection ID

        Returns:
            Bank connection details including accounts
        """
        return self.get(f"bankConnections/{connection_id}")

    def get_web_form_flow(self, flow_id: str) -> dict[str, Any]:
        """
        Get web form flow status for bank authentication.

        Args:
            flow_id: Web form flow ID

        Returns:
            Web form flow status including serviceUrl for redirect
        """
        return self.get(f"bankConnections/webFormFlow/{flow_id}")

    def update_bank_connection(
        self,
        connection_id: str,
        redirect_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Refresh/sync an existing bank connection.

        Args:
            connection_id: Bank connection ID
            redirect_url: Optional redirect URL for re-authentication

        Returns:
            Update process status
        """
        data: dict[str, Any] = {}
        if redirect_url:
            data["redirectUrl"] = redirect_url
        return self.put(
            f"bankConnections/{connection_id}/update",
            data=data if data else None,
        )

    def delete_bank_connection(self, connection_id: str) -> dict[str, Any]:
        """
        Delete a bank connection.

        Args:
            connection_id: Bank connection ID

        Returns:
            Empty dict on success (204)
        """
        return self.delete(f"bankConnections/{connection_id}")

    def poll_update_process(self, process_id: str) -> dict[str, Any]:
        """
        Poll for async bank sync process status.

        Args:
            process_id: Update process ID

        Returns:
            Process status with progress info
        """
        return self.get(f"bankConnections/updateProcess/{process_id}")

    # =========================================================================
    # Account & Holdings Management (v2/accounts)
    # =========================================================================

    def list_accounts(
        self,
        account_type: Optional[str] = None,
        account_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        List accounts, optionally filtered by type.

        Args:
            account_type: Filter by account type (e.g. DEPOT, CHECKING)
            account_ids: Filter by specific account IDs

        Returns:
            Dict with 'accounts' list
        """
        params: dict[str, str] = {}
        if account_type:
            params["accountType"] = account_type
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        return self.get("accounts", params=params if params else None)

    def get_account(self, account_id: str) -> dict[str, Any]:
        """
        Get details of a specific account including investments.

        Args:
            account_id: Account ID

        Returns:
            Account details with investments list
        """
        return self.get(f"accounts/{account_id}")

    def get_account_valuation(
        self,
        account_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get total valuation across accounts.

        Args:
            account_ids: Optional list of account IDs to include

        Returns:
            Valuation data with totalValue
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        return self.get("accounts/valuation", params=params if params else None)

    def get_account_balances(
        self,
        account_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get balance history for accounts.

        Args:
            account_ids: Optional list of account IDs

        Returns:
            Balance history data
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        return self.get("accounts/balances", params=params if params else None)

    def get_account_categorization(
        self,
        account_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get asset categorization breakdown.

        Args:
            account_ids: Optional list of account IDs

        Returns:
            Categorization data with category breakdown
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        return self.get("accounts/categorize", params=params if params else None)

    # =========================================================================
    # Historic Valuations & Performance (v1 endpoints)
    # =========================================================================

    def get_historic_valuations(
        self,
        account_ids: Optional[list[str]] = None,
        interval_type: Optional[str] = None,
        start_date: Optional[str] = None,
        include_cash: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Get historic valuations time series for accounts.

        Args:
            account_ids: Optional list of account IDs
            interval_type: Interval granularity (day/week/month/year)
            start_date: Start date (YYYY-MM-DD)
            include_cash: Whether to include cash positions

        Returns:
            Dict with 'valuations' list of {date, totalValue} entries
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        if interval_type:
            params["intervalType"] = interval_type
        if start_date:
            params["startDate"] = start_date
        if include_cash is not None:
            params["includeCash"] = str(include_cash).lower()
        return self._make_request(
            "GET",
            "accounts/historicValuations",
            params=params if params else None,
            api_version="v1",
        )

    def get_absolute_return(
        self,
        account_ids: Optional[list[str]] = None,
        interval_type: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get absolute return performance data with dividends and expenses.

        Args:
            account_ids: Optional list of account IDs
            interval_type: Interval granularity (day/week/month/year)
            start_date: Start date (YYYY-MM-DD)

        Returns:
            Dict with 'returns' list of {date, absoluteReturn, dividends, expenses}
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        if interval_type:
            params["intervalType"] = interval_type
        if start_date:
            params["startDate"] = start_date
        return self._make_request(
            "GET",
            "performance/absoluteReturn",
            params=params if params else None,
            api_version="v1",
        )

    def get_cash_flows(
        self,
        account_ids: Optional[list[str]] = None,
        start_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get cash flow analysis for accounts.

        Args:
            account_ids: Optional list of account IDs
            start_date: Start date (YYYY-MM-DD)

        Returns:
            Dict with 'cashFlows' list of {date, amount, type}
        """
        params: dict[str, str] = {}
        if account_ids:
            params["accountIds"] = ",".join(account_ids)
        if start_date:
            params["startDate"] = start_date
        return self._make_request(
            "GET",
            "accounts/cashFlows",
            params=params if params else None,
            api_version="v1",
        )

    def validate_connection(self) -> tuple[bool, Optional[str]]:
        """
        Validate the mandator credentials are working.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Attempt an unauthenticated mandator-level call
            self._make_request("GET", "mandator/status", authenticated=False)
            return True, None
        except WealthApiAuthError as e:
            return False, f"Authentication failed: {e.message}"
        except WealthApiRateLimitError as e:
            return False, f"Rate limit exceeded. Retry after {e.retry_after} seconds"
        except WealthApiError as e:
            return False, f"API error: {e.message}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self._session.close()
