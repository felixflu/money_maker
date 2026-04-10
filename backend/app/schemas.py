"""
Pydantic schemas for authentication, user management, and pricing.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
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
# Pricing Schemas
# ============================================================================


class AssetType(str, Enum):
    """Enumeration of supported asset types."""

    CRYPTOCURRENCY = "cryptocurrency"
    STOCK = "stock"
    ETF = "etf"
    BOND = "bond"
    COMMODITY = "commodity"


class PriceResponse(BaseModel):
    """Schema for price data response."""

    symbol: str = Field(..., description="Asset symbol/ticker")
    price: Decimal = Field(..., description="Current price")
    currency: str = Field(default="USD", description="Price currency")
    timestamp: datetime = Field(..., description="When price was fetched")
    source: str = Field(..., description="Price source (coingecko, yahoo, etc.)")
    is_stale: bool = Field(
        default=False, description="Whether price is from stale cache"
    )
    change_24h: Optional[Decimal] = Field(default=None, description="24h price change")
    change_24h_percent: Optional[Decimal] = Field(
        default=None, description="24h price change percentage"
    )

    class Config:
        from_attributes = True


class PriceRequest(BaseModel):
    """Schema for price request."""

    symbol: str = Field(..., description="Asset symbol/ticker")
    asset_type: AssetType = Field(..., description="Type of asset")
    coingecko_id: Optional[str] = Field(
        default=None, description="CoinGecko ID for crypto assets"
    )


class BatchPriceRequest(BaseModel):
    """Schema for batch price request."""

    assets: list[PriceRequest] = Field(..., min_length=1, max_length=100)


class BatchPriceResponse(BaseModel):
    """Schema for batch price response."""

    prices: list[PriceResponse]
    failed_symbols: list[str] = Field(
        default=[], description="Symbols that failed to fetch"
    )
