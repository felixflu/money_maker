"""
Bank connection routes for WealthAPI v2 bank connection management.

Provides endpoints for:
- Creating bank connections (initiating web form auth)
- Listing bank connections
- Getting web form flow status
- Refreshing/updating connections
- Deleting connections
- Polling sync process status
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.config import settings
from app.models import User
from app.models.bank_connection import BankConnection
from app.integrations.wealthapi import (
    WealthApiClient,
    WealthApiError,
    WealthApiAuthError,
    WealthApiRateLimitError,
)
from app.schemas import (
    BankConnectionCreate,
    BankConnectionResponse,
    BankConnectionInitResponse,
    BankConnectionUpdateResponse,
    WebFormFlowResponse,
    UpdateProcessResponse,
)

router = APIRouter(prefix="/api/v1/bank-connections", tags=["bank-connections"])
logger = logging.getLogger(__name__)


def _get_wealthapi_client() -> WealthApiClient:
    """Create a WealthAPI client with mandator credentials."""
    return WealthApiClient(
        client_id=settings.wealthapi_client_id,
        client_secret=settings.wealthapi_client_secret,
        base_url=settings.wealthapi_base_url,
    )


@router.post(
    "",
    response_model=BankConnectionInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bank connection",
)
async def create_bank_connection(
    connection_data: BankConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initiate a new bank connection via WealthAPI.

    Returns connection details and web form URL for bank authentication.
    The user should be redirected to the web form URL to complete setup.
    """
    client = _get_wealthapi_client()

    try:
        # Login as the WealthAPI user (using stored credentials or creating one)
        # For now, use mandator-level access with user token set externally
        result = client.create_bank_connection(
            bank_id=connection_data.bank_id,
            redirect_url=connection_data.redirect_url,
        )
    except WealthApiAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"WealthAPI authentication failed: {e.message}",
        )
    except WealthApiRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {e.retry_after} seconds",
        )
    except WealthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WealthAPI error: {e.message}",
        )

    wealthapi_id = str(result.get("id", ""))
    bank_name = result.get("bankConnectionName", f"Bank {connection_data.bank_id}")

    # Persist to local DB
    bank_conn = BankConnection(
        user_id=current_user.id,
        wealthapi_connection_id=wealthapi_id,
        bank_name=bank_name,
        bank_id=connection_data.bank_id,
        update_status=result.get("updateStatus", "IN_PROGRESS"),
        categorization_status=result.get("categorizationStatus"),
        is_active=True,
    )
    db.add(bank_conn)
    db.commit()
    db.refresh(bank_conn)

    logger.info(
        f"Created bank connection: {bank_name} (wealthapi={wealthapi_id}) "
        f"for user {current_user.id}"
    )

    # Extract web form info if present
    web_form_url = None
    web_form_flow_id = None
    interfaces = result.get("interfaces", [])
    for iface in interfaces:
        if "webFormId" in iface:
            web_form_flow_id = iface["webFormId"]
            break

    process_id = result.get("processId")

    return BankConnectionInitResponse(
        bank_connection=BankConnectionResponse.model_validate(bank_conn),
        web_form_url=web_form_url,
        web_form_flow_id=web_form_flow_id,
        process_id=process_id,
    )


@router.get(
    "",
    response_model=list[BankConnectionResponse],
    summary="List bank connections",
)
async def list_bank_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all bank connections for the current user."""
    connections = (
        db.query(BankConnection)
        .filter(BankConnection.user_id == current_user.id)
        .all()
    )
    return [BankConnectionResponse.model_validate(c) for c in connections]


@router.get(
    "/{connection_id}",
    response_model=BankConnectionResponse,
    summary="Get bank connection details",
)
async def get_bank_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of a specific bank connection."""
    conn = (
        db.query(BankConnection)
        .filter(
            BankConnection.id == connection_id,
            BankConnection.user_id == current_user.id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank connection not found",
        )
    return BankConnectionResponse.model_validate(conn)


@router.get(
    "/web-form/{flow_id}",
    response_model=WebFormFlowResponse,
    summary="Get web form flow status",
)
async def get_web_form_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check the status of a bank authentication web form flow.

    Use this to poll whether the user has completed bank authentication.
    """
    client = _get_wealthapi_client()

    try:
        result = client.get_web_form_flow(flow_id)
    except WealthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WealthAPI error: {e.message}",
        )

    return WebFormFlowResponse(
        id=result.get("id", flow_id),
        status=result.get("status", "UNKNOWN"),
        service_url=result.get("serviceUrl"),
        bank_connection_id=result.get("bankConnectionId"),
    )


@router.put(
    "/{connection_id}/update",
    response_model=BankConnectionUpdateResponse,
    summary="Refresh bank connection",
)
async def update_bank_connection(
    connection_id: int,
    redirect_url: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a refresh/sync for a bank connection.

    If re-authentication is needed, returns a web form URL.
    """
    conn = (
        db.query(BankConnection)
        .filter(
            BankConnection.id == connection_id,
            BankConnection.user_id == current_user.id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank connection not found",
        )

    if not conn.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank connection is not active",
        )

    client = _get_wealthapi_client()

    try:
        result = client.update_bank_connection(
            conn.wealthapi_connection_id,
            redirect_url=redirect_url,
        )
    except WealthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WealthAPI error: {e.message}",
        )

    conn.update_status = result.get("updateStatus", conn.update_status)
    db.commit()
    db.refresh(conn)

    return BankConnectionUpdateResponse(
        bank_connection=BankConnectionResponse.model_validate(conn),
        process_id=result.get("processId"),
        web_form_url=result.get("webFormUrl"),
        web_form_flow_id=result.get("webFormId"),
    )


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bank connection",
)
async def delete_bank_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a bank connection from both WealthAPI and local DB."""
    conn = (
        db.query(BankConnection)
        .filter(
            BankConnection.id == connection_id,
            BankConnection.user_id == current_user.id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank connection not found",
        )

    client = _get_wealthapi_client()

    try:
        client.delete_bank_connection(conn.wealthapi_connection_id)
    except WealthApiError as e:
        logger.warning(
            f"WealthAPI delete failed for {conn.wealthapi_connection_id}: {e.message}. "
            "Removing local record anyway."
        )

    db.delete(conn)
    db.commit()
    logger.info(f"Deleted bank connection: {connection_id}")


@router.get(
    "/process/{process_id}",
    response_model=UpdateProcessResponse,
    summary="Poll sync process status",
)
async def poll_update_process(
    process_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Poll the status of an async bank sync process.

    Returns progress info; poll until status is COMPLETED or FAILED.
    """
    client = _get_wealthapi_client()

    try:
        result = client.poll_update_process(process_id)
    except WealthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WealthAPI error: {e.message}",
        )

    return UpdateProcessResponse(
        id=result.get("id", process_id),
        status=result.get("status", "UNKNOWN"),
        progress=result.get("progress"),
        bank_connection_id=result.get("bankConnectionId"),
        error=result.get("error"),
    )
