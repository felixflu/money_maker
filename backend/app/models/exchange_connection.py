"""
ExchangeConnection model.

Represents a connection to an external exchange API.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExchangeConnection(Base):
    """
    ExchangeConnection model representing API credentials for an exchange.

    Attributes:
        id: Unique identifier for the connection.
        user_id: Foreign key to the user who owns this connection.
        exchange_name: Name of the exchange (e.g., Coinbase, Binance).
        api_key_encrypted: Encrypted API key for the exchange.
        api_secret_encrypted: Encrypted API secret for the exchange.
        additional_config: Optional JSON configuration for the exchange.
        is_active: Whether this connection is currently active.
        last_synced_at: When data was last synced from this exchange.
        created_at: Timestamp when connection was created.
        updated_at: Timestamp when connection was last updated.
    """

    __tablename__ = "exchange_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    exchange_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    additional_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        back_populates="exchange_connections",
    )

    def __repr__(self) -> str:
        return (
            f"<ExchangeConnection(id={self.id}, exchange={self.exchange_name}, "
            f"user_id={self.user_id}, active={self.is_active})>"
        )
