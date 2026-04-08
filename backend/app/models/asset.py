"""
Asset model.

Represents an asset (stock, cryptocurrency, etc.) in a portfolio.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import String, ForeignKey, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Asset(Base):
    """
    Asset model representing a financial asset in a portfolio.

    Attributes:
        id: Unique identifier for the asset.
        symbol: Asset symbol/ticker (e.g., BTC, AAPL).
        name: Full name of the asset (e.g., Bitcoin, Apple Inc.).
        asset_type: Type of asset (cryptocurrency, stock, bond, etc.).
        portfolio_id: Foreign key to the portfolio containing this asset.
        quantity: Total quantity of the asset held.
        average_buy_price: Average price at which the asset was purchased.
        created_at: Timestamp when asset was created.
        updated_at: Timestamp when asset was last updated.
    """

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )
    average_buy_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 8),
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
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="assets")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    @property
    def total_value(self) -> Optional[Decimal]:
        """Calculate total value based on quantity and average buy price."""
        if self.average_buy_price is not None:
            return self.quantity * self.average_buy_price
        return None

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, symbol={self.symbol}, portfolio_id={self.portfolio_id})>"
