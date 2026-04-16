"""
Shared test fixtures for the test suite.

Provides a properly isolated test database that all test files share,
preventing cross-test pollution from module-level dependency overrides.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import ALL models to ensure they're registered on Base.metadata
from app.models import (
    Base,
    User,
    Portfolio,
    Asset,
    Transaction,
    ExchangeConnection,
    BankConnection,
    PasswordResetToken,
)
from app.database import get_db
from app.main import app


# Shared test engine — in-memory SQLite with StaticPool so all connections
# see the same database within a test
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    """Yield a test database session."""
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables before each test, drop after.

    Also overrides the app's get_db dependency to use the test engine,
    and cleans up the override after each test so other test files
    aren't affected.
    """
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
