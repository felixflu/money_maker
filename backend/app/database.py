"""
Database configuration and session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Use SQLite for testing, PostgreSQL for production/development
if os.getenv("TESTING"):
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
