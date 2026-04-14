"""
SQLAlchemy base model and database utilities.

Re-exports Base, engine, SessionLocal, and get_db from app.database
so all models register on a single declarative base.
"""

from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

from app.database import Base, engine, SessionLocal, get_db


class UTCDateTime(TypeDecorator):
    """Type decorator for timezone-aware datetime storage."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """Process value before storing in database."""
        if value is not None:
            return value
        return None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Process value when loading from database."""
        return value


def init_db() -> None:
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=engine)
