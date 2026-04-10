"""
Exchange routes for managing exchange connections and syncing data.

Provides endpoints for:
- CRUD operations on exchange connections
- Trade Republic integration
- Coinbase integration
- Syncing portfolio data and transactions
- Validating connection credentials
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.models.exchange_connection import ExchangeConnection
from app.schemas import (
    ExchangeConnectionCreate,
    ExchangeConnectionUpdate,
    ExchangeConnectionResponse,
    ExchangeConnectionDetailResponse,
    TradeRepublicSyncRequest,
    TradeRepublicSyncResponse,
    ExchangeValidationRequest,
    ExchangeValidationResponse,
    SupportedExchange,
    SupportedExchangesResponse,
)
from app.integrations.trade_republic import (
    TradeRepublicClient,
    TradeRepublicAPIError,
    TradeRepublicAuthError,
    TradeRepublicRateLimitError,
)
from app.integrations.coinbase import (
    CoinbaseClient,
    CoinbaseAPIError,
    CoinbaseAuthError,
    CoinbaseRateLimitError,
)

router = APIRouter(prefix="/api/v1/exchanges", tags=["exchanges"])
logger = logging.getLogger(__name__)

# ============================================================================
# Supported Exchanges
# ============================================================================

SUPPORTED_EXCHANGES = [
    SupportedExchange(
        name="trade_republic",
        display_name="Trade Republic",
        description="German neobroker for ETFs, stocks, and crypto",
        supported_features=[
            "portfolio_sync",
            "transaction_import",
            "etf_holdings",
            "crypto_holdings",
        ],
        requires_api_secret=True,
        website_url="https://traderepublic.com",
        docs_url="https://docs.exchanges/traderepublic.md",
    ),
    SupportedExchange(
        name="coinbase",
        display_name="Coinbase",
        description="Popular cryptocurrency exchange for buying, selling, and storing crypto",
        supported_features=[
            "portfolio_sync",
            "transaction_import",
            "crypto_holdings",
            "price_lookup",
        ],
        requires_api_secret=True,
        website_url="https://coinbase.com",
        docs_url="https://docs.exchanges/coinbase.md",
    ),
]


@router.get(
    "/supported",
    response_model=SupportedExchangesResponse,
    summary="List supported exchanges",
    description="Get a list of all supported exchanges and their capabilities.",
)
async def list_supported_exchanges():
    """
    List all supported exchanges.

    Returns information about each supported exchange including
    features, requirements, and documentation links.
    """
    return SupportedExchangesResponse(exchanges=SUPPORTED_EXCHANGES)


# ============================================================================
# Exchange Connection CRUD
# ============================================================================


def _mask_api_key(api_key: str) -> str:
    """Mask API key for display, showing only first 4 and last 4 characters."""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


@router.get(
    "/connections",
    response_model=list[ExchangeConnectionResponse],
    summary="List exchange connections",
    description="Get all exchange connections for the current user.",
)
async def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all exchange connections for the current user.

    Returns a list of exchange connections (sensitive data is masked).
    """
    connections = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == current_user.id)
        .all()
    )

    # Add masked API key to each connection
    result = []
    for conn in connections:
        conn_dict = {
            "id": conn.id,
            "user_id": conn.user_id,
            "exchange_name": conn.exchange_name,
            "is_active": conn.is_active,
            "additional_config": conn.additional_config,
            "last_synced_at": conn.last_synced_at,
            "created_at": conn.created_at,
            "updated_at": conn.updated_at,
            "api_key_masked": _mask_api_key(conn.api_key_encrypted),
        }
        result.append(conn_dict)

    return result


@router.post(
    "/connections",
    response_model=ExchangeConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exchange connection",
    description="Create a new exchange connection for the current user.",
)
async def create_connection(
    connection_data: ExchangeConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new exchange connection.

    - **exchange_name**: Name of the exchange (e.g., "trade_republic")
    - **api_key**: API key for the exchange
    - **api_secret**: API secret for the exchange
    - **is_active**: Whether the connection is active (default: true)
    - **additional_config**: Optional JSON configuration

    Returns the created connection.
    """
    # Validate exchange is supported
    supported_names = {e.name for e in SUPPORTED_EXCHANGES}
    if connection_data.exchange_name not in supported_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange '{connection_data.exchange_name}' is not supported",
        )

    # Check if connection already exists for this user and exchange
    existing = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == connection_data.exchange_name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection to '{connection_data.exchange_name}' already exists",
        )

    # Create new connection (store API key/secret encrypted in production)
    # For now, we store them directly (encryption should be added)
    new_connection = ExchangeConnection(
        user_id=current_user.id,
        exchange_name=connection_data.exchange_name,
        api_key_encrypted=connection_data.api_key,
        api_secret_encrypted=connection_data.api_secret,
        is_active=connection_data.is_active,
        additional_config=connection_data.additional_config,
    )

    db.add(new_connection)
    db.commit()
    db.refresh(new_connection)

    logger.info(
        f"Created exchange connection: {new_connection.exchange_name} "
        f"for user {current_user.id}"
    )

    return {
        "id": new_connection.id,
        "user_id": new_connection.user_id,
        "exchange_name": new_connection.exchange_name,
        "is_active": new_connection.is_active,
        "additional_config": new_connection.additional_config,
        "last_synced_at": new_connection.last_synced_at,
        "created_at": new_connection.created_at,
        "updated_at": new_connection.updated_at,
        "api_key_masked": _mask_api_key(new_connection.api_key_encrypted),
    }


@router.get(
    "/connections/{connection_id}",
    response_model=ExchangeConnectionDetailResponse,
    summary="Get connection details",
    description="Get details for a specific exchange connection.",
)
async def get_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details for a specific exchange connection.

    - **connection_id**: ID of the exchange connection

    Returns connection details including validation status.
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange connection not found",
        )

    # Validate connection if it's active
    connection_valid = False
    connection_error = None

    if connection.is_active:
        try:
            if connection.exchange_name == "trade_republic":
                client = TradeRepublicClient(
                    api_key=connection.api_key_encrypted,
                    api_secret=connection.api_secret_encrypted,
                )
                connection_valid, connection_error = client.validate_connection()
            elif connection.exchange_name == "coinbase":
                client = CoinbaseClient(
                    api_key=connection.api_key_encrypted,
                    api_secret=connection.api_secret_encrypted,
                )
                connection_valid, connection_error = client.validate_connection()
        except Exception as e:
            connection_error = str(e)
            logger.error(f"Error validating connection {connection_id}: {e}")

    return {
        "id": connection.id,
        "user_id": connection.user_id,
        "exchange_name": connection.exchange_name,
        "is_active": connection.is_active,
        "additional_config": connection.additional_config,
        "last_synced_at": connection.last_synced_at,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
        "api_key_masked": _mask_api_key(connection.api_key_encrypted),
        "connection_valid": connection_valid,
        "connection_error": connection_error,
    }


@router.patch(
    "/connections/{connection_id}",
    response_model=ExchangeConnectionResponse,
    summary="Update exchange connection",
    description="Update an existing exchange connection.",
)
async def update_connection(
    connection_id: int,
    connection_data: ExchangeConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an exchange connection.

    - **connection_id**: ID of the connection to update
    - **api_key**: New API key (optional)
    - **api_secret**: New API secret (optional)
    - **is_active**: New active status (optional)
    - **additional_config**: New additional config (optional)

    Returns the updated connection.
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange connection not found",
        )

    # Update fields
    if connection_data.api_key is not None:
        connection.api_key_encrypted = connection_data.api_key
    if connection_data.api_secret is not None:
        connection.api_secret_encrypted = connection_data.api_secret
    if connection_data.is_active is not None:
        connection.is_active = connection_data.is_active
    if connection_data.additional_config is not None:
        connection.additional_config = connection_data.additional_config

    db.commit()
    db.refresh(connection)

    logger.info(f"Updated exchange connection: {connection_id}")

    return {
        "id": connection.id,
        "user_id": connection.user_id,
        "exchange_name": connection.exchange_name,
        "is_active": connection.is_active,
        "additional_config": connection.additional_config,
        "last_synced_at": connection.last_synced_at,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
        "api_key_masked": _mask_api_key(connection.api_key_encrypted),
    }


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete exchange connection",
    description="Delete an exchange connection.",
)
async def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an exchange connection.

    - **connection_id**: ID of the connection to delete
    """
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange connection not found",
        )

    db.delete(connection)
    db.commit()

    logger.info(f"Deleted exchange connection: {connection_id}")


# ============================================================================
# Connection Validation
# ============================================================================


@router.post(
    "/validate",
    response_model=ExchangeValidationResponse,
    summary="Validate exchange credentials",
    description="Validate exchange API credentials without creating a connection.",
)
async def validate_connection(
    validation_data: ExchangeValidationRequest,
):
    """
    Validate exchange API credentials.

    - **exchange_name**: Name of the exchange
    - **api_key**: API key to validate
    - **api_secret**: API secret to validate

    Returns validation result and account information if valid.
    """
    # Validate exchange is supported
    supported_names = {e.name for e in SUPPORTED_EXCHANGES}
    if validation_data.exchange_name not in supported_names:
        return ExchangeValidationResponse(
            valid=False,
            message=f"Exchange '{validation_data.exchange_name}' is not supported",
        )

    try:
        if validation_data.exchange_name == "trade_republic":
            client = TradeRepublicClient(
                api_key=validation_data.api_key,
                api_secret=validation_data.api_secret,
            )
            is_valid, error_message = client.validate_connection()

            if is_valid:
                account_info = client.get_account_info()
                return ExchangeValidationResponse(
                    valid=True,
                    message="Connection successful",
                    account_info=account_info,
                )
            else:
                return ExchangeValidationResponse(
                    valid=False,
                    message=error_message or "Connection failed",
                )

        elif validation_data.exchange_name == "coinbase":
            client = CoinbaseClient(
                api_key=validation_data.api_key,
                api_secret=validation_data.api_secret,
            )
            is_valid, error_message = client.validate_connection()

            if is_valid:
                account_info = client.get_account_info()
                return ExchangeValidationResponse(
                    valid=True,
                    message="Connection successful",
                    account_info=account_info,
                )
            else:
                return ExchangeValidationResponse(
                    valid=False,
                    message=error_message or "Connection failed",
                )

    except TradeRepublicAuthError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"Authentication failed: {e.message}",
        )
    except TradeRepublicRateLimitError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"Rate limit exceeded. Retry after {e.retry_after} seconds",
        )
    except TradeRepublicAPIError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"API error: {e.message}",
        )
    except CoinbaseAuthError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"Authentication failed: {e.message}",
        )
    except CoinbaseRateLimitError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"Rate limit exceeded. Retry after {e.retry_after} seconds",
        )
    except CoinbaseAPIError as e:
        return ExchangeValidationResponse(
            valid=False,
            message=f"API error: {e.message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error validating connection: {e}")
        return ExchangeValidationResponse(
            valid=False,
            message=f"Unexpected error: {str(e)}",
        )


# ============================================================================
# Trade Republic Sync
# ============================================================================


@router.post(
    "/trade-republic/sync/{connection_id}",
    response_model=TradeRepublicSyncResponse,
    summary="Sync Trade Republic data",
    description="Sync portfolio holdings and transactions from Trade Republic.",
)
async def sync_trade_republic(
    connection_id: int,
    sync_request: TradeRepublicSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync data from Trade Republic.

    - **connection_id**: ID of the Trade Republic connection
    - **sync_transactions**: Whether to sync transaction history (default: true)
    - **transaction_days**: Number of days of history to sync (default: 90)

    Returns sync results including counts of synced data.
    """
    # Get connection
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "trade_republic",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade Republic connection not found",
        )

    if not connection.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is not active",
        )

    try:
        # Create client and sync
        client = TradeRepublicClient(
            api_key=connection.api_key_encrypted,
            api_secret=connection.api_secret_encrypted,
        )

        result = client.sync_portfolio()

        if result["success"]:
            # Update last synced timestamp
            from datetime import datetime

            connection.last_synced_at = datetime.utcnow()
            db.commit()

            return TradeRepublicSyncResponse(
                success=True,
                message="Sync completed successfully",
                holdings_synced=len(result.get("holdings", [])),
                transactions_synced=len(result.get("transactions", [])),
                synced_at=connection.last_synced_at,
            )
        else:
            return TradeRepublicSyncResponse(
                success=False,
                message="Sync failed",
                error=result.get("error", "Unknown error"),
            )

    except TradeRepublicAuthError as e:
        logger.error(f"Trade Republic auth error during sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Authentication failed",
            error=f"Invalid credentials: {e.message}",
        )
    except TradeRepublicRateLimitError as e:
        logger.error(f"Trade Republic rate limit during sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Rate limit exceeded",
            error=f"Retry after {e.retry_after} seconds",
        )
    except Exception as e:
        logger.error(f"Unexpected error during Trade Republic sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Sync failed",
            error=f"Unexpected error: {str(e)}",
        )


# ============================================================================
# Coinbase Sync
# ============================================================================


@router.post(
    "/coinbase/sync/{connection_id}",
    response_model=TradeRepublicSyncResponse,
    summary="Sync Coinbase data",
    description="Sync portfolio holdings and transactions from Coinbase.",
)
async def sync_coinbase(
    connection_id: int,
    sync_request: TradeRepublicSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync data from Coinbase.

    - **connection_id**: ID of the Coinbase connection
    - **sync_transactions**: Whether to sync transaction history (default: true)
    - **transaction_days**: Number of days of history to sync (default: 90)

    Returns sync results including counts of synced data.
    """
    # Get connection
    connection = (
        db.query(ExchangeConnection)
        .filter(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.exchange_name == "coinbase",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coinbase connection not found",
        )

    if not connection.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is not active",
        )

    try:
        # Create client and sync
        client = CoinbaseClient(
            api_key=connection.api_key_encrypted,
            api_secret=connection.api_secret_encrypted,
        )

        result = client.sync_portfolio()

        if result["success"]:
            # Update last synced timestamp
            from datetime import datetime

            connection.last_synced_at = datetime.utcnow()
            db.commit()

            return TradeRepublicSyncResponse(
                success=True,
                message="Sync completed successfully",
                holdings_synced=len(result.get("holdings", [])),
                transactions_synced=len(result.get("transactions", [])),
                synced_at=connection.last_synced_at,
            )
        else:
            return TradeRepublicSyncResponse(
                success=False,
                message="Sync failed",
                error=result.get("error", "Unknown error"),
            )

    except CoinbaseAuthError as e:
        logger.error(f"Coinbase auth error during sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Authentication failed",
            error=f"Invalid credentials: {e.message}",
        )
    except CoinbaseRateLimitError as e:
        logger.error(f"Coinbase rate limit during sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Rate limit exceeded",
            error=f"Retry after {e.retry_after} seconds",
        )
    except Exception as e:
        logger.error(f"Unexpected error during Coinbase sync: {e}")
        return TradeRepublicSyncResponse(
            success=False,
            message="Sync failed",
            error=f"Unexpected error: {str(e)}",
        )
