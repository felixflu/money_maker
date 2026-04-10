"""
Pydantic schemas for authentication and user management.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(
        ..., min_length=8, description="User password (min 8 characters)"
    )


class UserResponse(UserBase):
    """Schema for user response (excludes sensitive data)."""

    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""

    sub: int | None = None
    type: str | None = None


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(
        ..., min_length=8, description="New password (min 8 characters)"
    )


class PasswordResetResponse(BaseModel):
    """Schema for password reset response."""

    message: str


# ============================================================================
# Exchange Connection Schemas
# ============================================================================


class ExchangeConnectionBase(BaseModel):
    """Base schema for exchange connections."""

    exchange_name: str = Field(
        ..., min_length=1, max_length=100, description="Name of the exchange"
    )
    is_active: bool = Field(
        default=True, description="Whether the connection is active"
    )
    additional_config: Optional[str] = Field(
        default=None, description="Additional JSON configuration"
    )


class ExchangeConnectionCreate(ExchangeConnectionBase):
    """Schema for creating a new exchange connection."""

    api_key: str = Field(..., min_length=1, description="API key for the exchange")
    api_secret: str = Field(
        ..., min_length=1, description="API secret for the exchange"
    )


class ExchangeConnectionUpdate(BaseModel):
    """Schema for updating an exchange connection."""

    api_key: Optional[str] = Field(default=None, description="New API key")
    api_secret: Optional[str] = Field(default=None, description="New API secret")
    is_active: Optional[bool] = Field(default=None, description="Active status")
    additional_config: Optional[str] = Field(
        default=None, description="Additional config"
    )


class ExchangeConnectionResponse(ExchangeConnectionBase):
    """Schema for exchange connection response (excludes sensitive data)."""

    id: int
    user_id: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    api_key_masked: Optional[str] = Field(
        default=None, description="Masked API key for display"
    )

    class Config:
        from_attributes = True


class ExchangeConnectionDetailResponse(ExchangeConnectionResponse):
    """Detailed response including connection status."""

    connection_valid: bool = Field(
        default=False, description="Whether the connection credentials are valid"
    )
    connection_error: Optional[str] = Field(
        default=None, description="Error message if connection is invalid"
    )


# ============================================================================
# Trade Republic Specific Schemas
# ============================================================================


class TradeRepublicCredentials(BaseModel):
    """Schema for Trade Republic API credentials."""

    api_key: str = Field(..., min_length=1, description="Trade Republic API key")
    api_secret: str = Field(..., min_length=1, description="Trade Republic API secret")


class TradeRepublicHolding(BaseModel):
    """Schema for a Trade Republic holding."""

    symbol: str = Field(..., description="ISIN or ticker symbol")
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(..., description="Asset type (etf, cryptocurrency, etc.)")
    quantity: float = Field(..., ge=0, description="Quantity held")
    current_price: float = Field(..., ge=0, description="Current price")
    currency: str = Field(default="EUR", description="Currency code")
    total_value: float = Field(..., ge=0, description="Total value of holding")


class TradeRepublicTransaction(BaseModel):
    """Schema for a Trade Republic transaction."""

    external_id: str = Field(..., description="Transaction ID from Trade Republic")
    transaction_type: str = Field(..., description="Type: buy, sell, dividend, etc.")
    symbol: str = Field(..., description="ISIN or ticker symbol")
    asset_name: Optional[str] = Field(default=None, description="Asset name")
    quantity: float = Field(..., description="Quantity")
    price: float = Field(..., description="Price per unit")
    total_amount: float = Field(..., description="Total transaction amount")
    fees: float = Field(default=0.0, description="Transaction fees")
    currency: str = Field(default="EUR", description="Currency code")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    status: str = Field(..., description="Transaction status")


class TradeRepublicSyncRequest(BaseModel):
    """Schema for requesting a Trade Republic sync."""

    sync_transactions: bool = Field(
        default=True, description="Whether to sync transaction history"
    )
    transaction_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Number of days of transaction history to sync",
    )


class TradeRepublicSyncResponse(BaseModel):
    """Schema for Trade Republic sync response."""

    success: bool
    message: str
    holdings_synced: int = Field(default=0, description="Number of holdings synced")
    transactions_synced: int = Field(
        default=0, description="Number of transactions synced"
    )
    synced_at: Optional[datetime] = Field(default=None, description="Sync timestamp")
    error: Optional[str] = Field(
        default=None, description="Error message if sync failed"
    )


# ============================================================================
# MEXC Specific Schemas
# ============================================================================


class MexcHolding(BaseModel):
    """Schema for a MEXC holding."""

    symbol: str = Field(..., description="Asset symbol (e.g., BTC)")
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(default="cryptocurrency", description="Asset type")
    quantity: float = Field(..., ge=0, description="Total quantity held")
    available: float = Field(..., ge=0, description="Available quantity")
    locked: float = Field(..., ge=0, description="Locked quantity")
    currency: str = Field(..., description="Currency code")


class MexcTransaction(BaseModel):
    """Schema for a MEXC transaction."""

    external_id: str = Field(..., description="Transaction ID from MEXC")
    transaction_type: str = Field(..., description="Type: buy, sell")
    symbol: str = Field(..., description="Base asset symbol")
    base_asset: str = Field(..., description="Base asset (e.g., BTC)")
    quote_asset: str = Field(..., description="Quote asset (e.g., USDT)")
    full_symbol: str = Field(..., description="Full trading pair (e.g., BTCUSDT)")
# Bitpanda Specific Schemas
# ============================================================================


class BitpandaCredentials(BaseModel):
    """Schema for Bitpanda API credentials."""

    api_key: str = Field(..., min_length=1, description="Bitpanda API key")
    api_secret: Optional[str] = Field(
        default=None, description="Not used for Bitpanda (API key only)"
    )


class BitpandaHolding(BaseModel):
    """Schema for a Bitpanda cryptocurrency holding."""

    symbol: str = Field(..., description="Cryptocurrency symbol (e.g., BTC, ETH)")
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(default="cryptocurrency", description="Asset type")
    quantity: float = Field(..., ge=0, description="Quantity held")
    available_quantity: float = Field(..., ge=0, description="Available quantity")
    current_price: Optional[float] = Field(
        default=None, description="Current price if available"
    )
    currency: str = Field(default="EUR", description="Currency code")
    total_value: Optional[float] = Field(
        default=None, description="Total value if price available"
    )
    wallet_id: str = Field(..., description="Bitpanda wallet ID")


class BitpandaTransaction(BaseModel):
    """Schema for a Bitpanda trade/transaction."""

    external_id: str = Field(..., description="Transaction ID from Bitpanda")
    transaction_type: str = Field(..., description="Type: buy, sell, etc.")
    symbol: str = Field(..., description="Cryptocurrency symbol")
    asset_name: Optional[str] = Field(default=None, description="Asset name")
    quantity: float = Field(..., description="Quantity")
    price: float = Field(..., description="Price per unit")
    total_amount: float = Field(..., description="Total transaction amount")
    fees: float = Field(default=0.0, description="Transaction fees")
    fee_asset: str = Field(default="", description="Asset used for fees")
    currency: str = Field(..., description="Quote currency")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    order_type: str = Field(default="", description="Order type (MARKET, LIMIT)")
    is_maker: bool = Field(default=False, description="Whether trade was maker")


class MexcSyncRequest(BaseModel):
    """Schema for requesting a MEXC sync."""

    sync_transactions: bool = Field(
        default=True, description="Whether to sync transaction history"
    currency: str = Field(default="EUR", description="Currency code")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    status: str = Field(..., description="Transaction status")


class BitpandaSyncRequest(BaseModel):
    """Schema for requesting a Bitpanda sync."""

    sync_transactions: bool = Field(
        default=True, description="Whether to sync trade history"
    )
    transaction_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Number of days of transaction history to sync",
    )


class MexcSyncResponse(BaseModel):
    """Schema for MEXC sync response."""
class BitpandaSyncResponse(BaseModel):
    """Schema for Bitpanda sync response."""

    success: bool
    message: str
    holdings_synced: int = Field(default=0, description="Number of holdings synced")
    transactions_synced: int = Field(
        default=0, description="Number of transactions synced"
    )
    synced_at: Optional[datetime] = Field(default=None, description="Sync timestamp")
    error: Optional[str] = Field(
        default=None, description="Error message if sync failed"
    )


# ============================================================================
# Exchange Validation Schemas
# ============================================================================


class ExchangeValidationRequest(BaseModel):
    """Schema for validating exchange credentials."""

    exchange_name: str = Field(..., description="Name of the exchange")
    api_key: str = Field(..., description="API key")
    api_secret: str = Field(..., description="API secret")


class ExchangeValidationResponse(BaseModel):
    """Schema for exchange validation response."""

    valid: bool
    message: str
    account_info: Optional[dict] = Field(
        default=None, description="Account information if validation succeeded"
    )


# ============================================================================
# Exchange List Schemas
# ============================================================================


class SupportedExchange(BaseModel):
    """Schema for supported exchange information."""

    name: str = Field(..., description="Exchange identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Exchange description")
    supported_features: list[str] = Field(
        default_factory=list, description="List of supported features"
    )
    requires_api_secret: bool = Field(
        default=True, description="Whether API secret is required"
    )
    website_url: Optional[str] = Field(default=None, description="Exchange website URL")
    docs_url: Optional[str] = Field(default=None, description="API documentation URL")


class SupportedExchangesResponse(BaseModel):
    """Schema for list of supported exchanges."""

    exchanges: list[SupportedExchange]
