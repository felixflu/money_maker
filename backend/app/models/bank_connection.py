"""
BankConnection model.

Represents a bank connection managed via WealthAPI v2.
Replaces direct exchange API credentials with WealthAPI's
bank connection + web form authentication flow.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BankConnection(Base):
    """
    BankConnection model representing a WealthAPI bank connection.

    Unlike ExchangeConnection (API key/secret), bank connections use
    WealthAPI's web form flow for user authentication with their bank.
    """

    __tablename__ = "bank_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    wealthapi_connection_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_id: Mapped[int] = mapped_column(nullable=False)
    update_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="READY"
    )
    categorization_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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
    user: Mapped["User"] = relationship(
        "User",
        back_populates="bank_connections",
    )

    def __repr__(self) -> str:
        return (
            f"<BankConnection(id={self.id}, bank={self.bank_name}, "
            f"wealthapi_id={self.wealthapi_connection_id}, user_id={self.user_id})>"
        )
