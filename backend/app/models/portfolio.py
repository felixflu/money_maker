"""
Portfolio model.

Represents a portfolio of assets owned by a user.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Portfolio(Base):
    """
    Portfolio model representing a collection of assets.

    Attributes:
        id: Unique identifier for the portfolio.
        name: Portfolio name (required).
        description: Optional portfolio description.
        user_id: Foreign key to the user who owns this portfolio.
        created_at: Timestamp when portfolio was created.
        updated_at: Timestamp when portfolio was last updated.
    """

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
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
    user: Mapped["User"] = relationship("User", back_populates="portfolios")
    assets: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, name={self.name}, user_id={self.user_id})>"
