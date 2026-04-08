"""
SQLAlchemy base model and database utilities.

Provides the declarative base for all models and database session management.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, DateTime
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
    MappedAsDataclass,
)
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

from app.config import settings


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


# Create engine
engine = create_engine(settings.database_url)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_db() -> Session:
    """Get a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=engine)
