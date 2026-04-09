"""
Pydantic schemas for authentication and user management.
"""

from datetime import datetime
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
