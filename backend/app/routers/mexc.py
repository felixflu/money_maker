"""
MEXC Exchange integration routes.

Provides endpoints for:
- Connecting MEXC exchange
- Syncing holdings
- Syncing transaction history
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exchange_connection import ExchangeConnection
from app.models.user import User
from app.auth import get_current_user
from app.services.mexc_client import MEXCClient, MEXCConfig, MEXCError
from app.services.mexc_sync import MEXCSyncService, MEXCSyncError

router = APIRouter(prefix="/api/v1/exchanges/mexc", tags=["mexc"])


class MEXCConnectionCreate(BaseModel):
    """Schema for creating a MEXC connection."""

    api_key: str = Field(..., description="MEXC API key")
    api_secret: str = Field(..., description="MEXC API secret")
    is_active: bool = Field(default=True, description="Whether connection is active")


class MEXCConnectionResponse(BaseModel):
    """Schema for MEXC connection response."""

    id: int
    exchange_name: str
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class MEXCConnectionTest(BaseModel):
    """Schema for testing MEXC connection."""

    api_key: str = Field(..., description="MEXC API key")
    api_secret: str = Field(..., description="MEXC API secret")


class MEXCConnectionTestResponse(BaseModel):
    """Schema for MEXC connection test response."""

    success: bool
    message: str


class MEXCSyncRequest(BaseModel):
    """Schema for MEXC sync request."""

    sync_transactions: bool = Field(
        default=True, description="Whether to sync transaction history"
    )
    transaction_start_date: Optional[datetime] = Field(
        default=None, description="Start date for transaction sync"
    )


class MEXCSyncResponse(BaseModel):
    """Schema for MEXC sync response."""

    success: bool
    message: str
    holdings_synced: Optional[int] = None
    transactions_synced: Optional[int] = None
    errors: list[str] = []


class MEXCHoldingResponse(BaseModel):
    """Schema for MEXC holding in response."""

    asset: str
    free: str
    locked: str
    total: str


class MEXCHoldingsResponse(BaseModel):
    """Schema for MEXC holdings response."""

    success: bool
    holdings: list[MEXCHoldingResponse]


def _encrypt_credentials(api_key: str, api_secret: str) -> tuple[str, str]:
    """
    Encrypt API credentials for storage.

    In production, this should use proper encryption.
    For now, we store as-is but mark as needing encryption.
    """
    # TODO: Implement proper encryption using app's encryption system
    return api_key, api_secret


def _decrypt_credentials(encrypted_key: str, encrypted_secret: str) -> tuple[str, str]:
    """
    Decrypt API credentials for use.

    In production, this should use proper decryption.
    """
    # TODO: Implement proper decryption
    return encrypted_key, encrypted_secret


@router.post(
    "/connect",
    response_model=MEXCConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect MEXC exchange",
    description="Create a new MEXC exchange connection with API credentials.",
)
async def connect_mexc(
    connection_data: MEXCConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Connect MEXC exchange account.

    - **api_key**: Your MEXC API key
    - **api_secret**: Your MEXC API secret
    - **is_active**: Whether the connection should be active (default: true)

    Returns the created connection details.
    """
    # Test credentials first
    config = MEXCConfig(
        api_key=connection_data.api_key,
        api_secret=connection_data.api_secret,
    )

    try:
        async with MEXCClient(config) as client:
            if not await client.test_connection():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid MEXC API credentials",
                )
    except MEXCError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to MEXC: {str(e)}",
        )

    # Check if connection already exists
    existing = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MEXC connection already exists. Use PUT to update.",
        )

    # Encrypt credentials
    encrypted_key, encrypted_secret = _encrypt_credentials(
        connection_data.api_key, connection_data.api_secret
    )

    # Create connection
    connection = ExchangeConnection(
        user_id=current_user.id,
        exchange_name="MEXC",
        api_key_encrypted=encrypted_key,
        api_secret_encrypted=encrypted_secret,
        is_active=connection_data.is_active,
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)

    return connection


@router.post(
    "/test-connection",
    response_model=MEXCConnectionTestResponse,
    summary="Test MEXC connection",
    description="Test MEXC API credentials without saving them.",
)
async def test_mexc_connection(
    test_data: MEXCConnectionTest,
):
    """
    Test MEXC API credentials.

    - **api_key**: Your MEXC API key
    - **api_secret**: Your MEXC API secret

    Returns success status and message.
    """
    config = MEXCConfig(
        api_key=test_data.api_key,
        api_secret=test_data.api_secret,
    )

    try:
        async with MEXCClient(config) as client:
            if await client.test_connection():
                return MEXCConnectionTestResponse(
                    success=True, message="Successfully connected to MEXC"
                )
            else:
                return MEXCConnectionTestResponse(
                    success=False, message="Failed to connect to MEXC"
                )
    except MEXCError as e:
        return MEXCConnectionTestResponse(
            success=False, message=f"Connection failed: {str(e)}"
        )


@router.get(
    "/connection",
    response_model=MEXCConnectionResponse,
    summary="Get MEXC connection",
    description="Get the current user's MEXC connection details.",
)
async def get_mexc_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get MEXC connection details for the current user.

    Returns connection details (without sensitive credentials).
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MEXC connection not found",
        )

    return connection


@router.put(
    "/connection",
    response_model=MEXCConnectionResponse,
    summary="Update MEXC connection",
    description="Update MEXC API credentials or active status.",
)
async def update_mexc_connection(
    connection_data: MEXCConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update MEXC connection.

    - **api_key**: Your MEXC API key
    - **api_secret**: Your MEXC API secret
    - **is_active**: Whether the connection should be active

    Returns updated connection details.
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MEXC connection not found",
        )

    # Test new credentials
    config = MEXCConfig(
        api_key=connection_data.api_key,
        api_secret=connection_data.api_secret,
    )

    try:
        async with MEXCClient(config) as client:
            if not await client.test_connection():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid MEXC API credentials",
                )
    except MEXCError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to MEXC: {str(e)}",
        )

    # Encrypt and update credentials
    encrypted_key, encrypted_secret = _encrypt_credentials(
        connection_data.api_key, connection_data.api_secret
    )

    connection.api_key_encrypted = encrypted_key
    connection.api_secret_encrypted = encrypted_secret
    connection.is_active = connection_data.is_active

    db.commit()
    db.refresh(connection)

    return connection


@router.delete(
    "/connection",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete MEXC connection",
    description="Remove the MEXC exchange connection.",
)
async def delete_mexc_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete MEXC connection.

    Removes the connection and all associated sync data.
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MEXC connection not found",
        )

    db.delete(connection)
    db.commit()


@router.post(
    "/sync",
    response_model=MEXCSyncResponse,
    summary="Sync MEXC data",
    description="Sync holdings and optionally transactions from MEXC.",
)
async def sync_mexc(
    sync_request: MEXCSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sync data from MEXC exchange.

    - **sync_transactions**: Whether to sync transaction history (default: true)
    - **transaction_start_date**: Optional start date for transactions

    Returns sync results with counts of synced items.
    """
    # Get connection
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
            ExchangeConnection.is_active == True,
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active MEXC connection not found",
        )

    # Decrypt credentials
    api_key, api_secret = _decrypt_credentials(
        connection.api_key_encrypted, connection.api_secret_encrypted
    )

    # Update connection with decrypted credentials for sync service
    connection.api_key_encrypted = api_key
    connection.api_secret_encrypted = api_secret

    # Perform sync
    sync_service = MEXCSyncService(db)

    try:
        results = await sync_service.full_sync(
            connection,
            sync_transactions=sync_request.sync_transactions,
            transaction_start_time=sync_request.transaction_start_date,
        )

        holdings_count = (
            results["holdings"]["synced_count"]
            if results["holdings"] and results["holdings"].get("success")
            else 0
        )
        transactions_count = (
            results["transactions"]["synced_count"]
            if results["transactions"] and results["transactions"].get("success")
            else 0
        )

        return MEXCSyncResponse(
            success=len(results["errors"]) == 0,
            message="Sync completed"
            if not results["errors"]
            else "Sync completed with errors",
            holdings_synced=holdings_count,
            transactions_synced=transactions_count,
            errors=results["errors"],
        )

    except MEXCSyncError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sync failed: {str(e)}",
        )


@router.get(
    "/holdings",
    response_model=MEXCHoldingsResponse,
    summary="Get MEXC holdings",
    description="Fetch current holdings directly from MEXC API.",
)
async def get_mexc_holdings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current holdings from MEXC.

    Returns real-time holdings from MEXC API (not cached).
    """
    # Get connection
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "MEXC",
            ExchangeConnection.is_active == True,
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active MEXC connection not found",
        )

    # Decrypt credentials
    api_key, api_secret = _decrypt_credentials(
        connection.api_key_encrypted, connection.api_secret_encrypted
    )

    config = MEXCConfig(api_key=api_key, api_secret=api_secret)

    try:
        async with MEXCClient(config) as client:
            holdings = await client.get_holdings()

            return MEXCHoldingsResponse(
                success=True,
                holdings=[
                    MEXCHoldingResponse(
                        asset=h.asset,
                        free=str(h.free),
                        locked=str(h.locked),
                        total=str(h.total),
                    )
                    for h in holdings
                ],
            )

    except MEXCError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch holdings: {str(e)}",
        )
