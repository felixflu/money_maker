"""
Transaction model.

Represents a buy/sell transaction of an asset.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, ForeignKey, Numeric, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Transaction(Base):
    """
    Transaction model representing a buy/sell transaction.

    Attributes:
        id: Unique identifier for the transaction.
        asset_id: Foreign key to the asset being transacted.
        transaction_type: Type of transaction (buy, sell, deposit, withdraw, dividend).
        quantity: Quantity of the asset transacted.
        price: Price per unit at time of transaction.
        total_amount: Total transaction amount (quantity * price).
        fees: Transaction fees paid.
        exchange: Exchange where transaction occurred.
        notes: Optional notes about the transaction.
        timestamp: When the transaction occurred.
        created_at: Timestamp when transaction record was created.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fees: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="transactions")

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, type={self.transaction_type}, "
            f"asset_id={self.asset_id}, quantity={self.quantity})>"
        )
