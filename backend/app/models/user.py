"""
User model.

Represents a user account in the application.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """
    User model representing a user account.

    Attributes:
        id: Unique identifier for the user.
        email: User's email address (unique, required).
        hashed_password: Bcrypt-hashed password.
        first_name: User's first name.
        last_name: User's last name.
        is_active: Whether the user account is active.
        created_at: Timestamp when user was created.
        updated_at: Timestamp when user was last updated.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    portfolios: Mapped[List["Portfolio"]] = relationship(
        "Portfolio",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    exchange_connections: Mapped[List["ExchangeConnection"]] = relationship(
        "ExchangeConnection",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
