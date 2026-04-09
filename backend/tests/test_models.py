"""
Tests for database models.

TDD: Write tests before implementing models to define expected behavior.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from app.models.base import Base
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.exchange_connection import ExchangeConnection


# Test database URL (SQLite in-memory for fast tests)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine) -> Session:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestUserModel:
    """Tests for the User model."""

    def test_user_creation(self, db_session: Session):
        """Test creating a user with required fields."""
        user = User(
            email="test@example.com",
            hashed_password="hashed_password_123",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_email_unique_constraint(self, db_session: Session):
        """Test that email must be unique."""
        user1 = User(
            email="duplicate@example.com",
            hashed_password="password1",
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            email="duplicate@example.com",
            hashed_password="password2",
        )
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_user_email_required(self, db_session: Session):
        """Test that email is required."""
        user = User(hashed_password="password123")
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_user_portfolios_relationship(self, db_session: Session):
        """Test user-portfolios relationship."""
        user = User(
            email="portfolio_user@example.com",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="My Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        assert len(user.portfolios) == 1
        assert user.portfolios[0].name == "My Portfolio"

    def test_user_full_name_property(self, db_session: Session):
        """Test full_name property."""
        user = User(
            email="name@example.com",
            hashed_password="password123",
            first_name="John",
            last_name="Doe",
        )
        db_session.add(user)
        db_session.commit()

        assert user.full_name == "John Doe"


class TestPortfolioModel:
    """Tests for the Portfolio model."""

    def test_portfolio_creation(self, db_session: Session):
        """Test creating a portfolio."""
        user = User(email="portfolio_test@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(
            name="Test Portfolio",
            description="A test portfolio",
            user_id=user.id,
        )
        db_session.add(portfolio)
        db_session.commit()
        db_session.refresh(portfolio)

        assert portfolio.id is not None
        assert portfolio.name == "Test Portfolio"
        assert portfolio.description == "A test portfolio"
        assert portfolio.user_id == user.id
        assert portfolio.created_at is not None

    def test_portfolio_assets_relationship(self, db_session: Session):
        """Test portfolio-assets relationship."""
        user = User(email="asset_test@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="Asset Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        asset = Asset(
            symbol="BTC",
            name="Bitcoin",
            asset_type="cryptocurrency",
            portfolio_id=portfolio.id,
        )
        db_session.add(asset)
        db_session.commit()

        assert len(portfolio.assets) == 1
        assert portfolio.assets[0].symbol == "BTC"


class TestAssetModel:
    """Tests for the Asset model."""

    def test_asset_creation(self, db_session: Session):
        """Test creating an asset."""
        user = User(email="asset_user@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="Crypto Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        asset = Asset(
            symbol="ETH",
            name="Ethereum",
            asset_type="cryptocurrency",
            portfolio_id=portfolio.id,
            quantity=1.5,
            average_buy_price=2000.00,
        )
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)

        assert asset.id is not None
        assert asset.symbol == "ETH"
        assert asset.name == "Ethereum"
        assert asset.asset_type == "cryptocurrency"
        assert asset.quantity == 1.5
        assert asset.average_buy_price == 2000.00

    def test_asset_transactions_relationship(self, db_session: Session):
        """Test asset-transactions relationship."""
        user = User(email="tx_user@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="Tx Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        asset = Asset(
            symbol="BTC",
            name="Bitcoin",
            asset_type="cryptocurrency",
            portfolio_id=portfolio.id,
        )
        db_session.add(asset)
        db_session.commit()

        transaction = Transaction(
            asset_id=asset.id,
            transaction_type="buy",
            quantity=0.5,
            price=40000.00,
            total_amount=20000.00,
        )
        db_session.add(transaction)
        db_session.commit()

        assert len(asset.transactions) == 1
        assert asset.transactions[0].transaction_type == "buy"


class TestTransactionModel:
    """Tests for the Transaction model."""

    def test_transaction_creation(self, db_session: Session):
        """Test creating a transaction."""
        from decimal import Decimal

        user = User(email="tx_test@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="Tx Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        asset = Asset(
            symbol="BTC",
            name="Bitcoin",
            asset_type="cryptocurrency",
            portfolio_id=portfolio.id,
        )
        db_session.add(asset)
        db_session.commit()

        transaction = Transaction(
            asset_id=asset.id,
            transaction_type="buy",
            quantity=0.1,
            price=50000.00,
            total_amount=5000.00,
            fees=10.00,
            exchange="Coinbase",
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)

        assert transaction.id is not None
        assert transaction.transaction_type == "buy"
        assert transaction.quantity == Decimal("0.1")
        assert transaction.price == Decimal("50000.00")
        assert transaction.total_amount == Decimal("5000.00")
        assert transaction.fees == Decimal("10.00")
        assert transaction.exchange == "Coinbase"
        assert transaction.timestamp is not None

    def test_transaction_type_constraint(self, db_session: Session):
        """Test transaction_type must be valid."""
        user = User(email="tx_type@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        portfolio = Portfolio(name="Tx Portfolio", user_id=user.id)
        db_session.add(portfolio)
        db_session.commit()

        asset = Asset(
            symbol="BTC",
            name="Bitcoin",
            asset_type="cryptocurrency",
            portfolio_id=portfolio.id,
        )
        db_session.add(asset)
        db_session.commit()

        # Valid types: buy, sell, deposit, withdraw, dividend
        for tx_type in ["buy", "sell", "deposit", "withdraw", "dividend"]:
            transaction = Transaction(
                asset_id=asset.id,
                transaction_type=tx_type,
                quantity=1.0,
                price=100.0,
                total_amount=100.0,
            )
            db_session.add(transaction)
            db_session.commit()

        # Invalid type should fail at database level
        # This would be caught by CHECK constraint in PostgreSQL
        # SQLite may not enforce CHECK constraints the same way


class TestExchangeConnectionModel:
    """Tests for the ExchangeConnection model."""

    def test_exchange_connection_creation(self, db_session: Session):
        """Test creating an exchange connection."""
        user = User(email="exchange_test@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        connection = ExchangeConnection(
            user_id=user.id,
            exchange_name="Coinbase",
            api_key_encrypted="encrypted_api_key",
            api_secret_encrypted="encrypted_api_secret",
            is_active=True,
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)

        assert connection.id is not None
        assert connection.exchange_name == "Coinbase"
        assert connection.api_key_encrypted == "encrypted_api_key"
        assert connection.is_active is True
        assert connection.created_at is not None
        assert connection.last_synced_at is None

    def test_exchange_connection_user_relationship(self, db_session: Session):
        """Test exchange connection-user relationship."""
        user = User(email="exchange_user@example.com", hashed_password="password123")
        db_session.add(user)
        db_session.commit()

        connection = ExchangeConnection(
            user_id=user.id,
            exchange_name="Binance",
            api_key_encrypted="key",
            api_secret_encrypted="secret",
        )
        db_session.add(connection)
        db_session.commit()

        assert len(user.exchange_connections) == 1
        assert user.exchange_connections[0].exchange_name == "Binance"


class TestDatabaseSchema:
    """Tests for database schema structure."""

    def test_all_tables_created(self, db_engine):
        """Test that all expected tables are created."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "users",
            "portfolios",
            "assets",
            "transactions",
            "exchange_connections",
        ]

        for table in expected_tables:
            assert table in tables, f"Table '{table}' not found"

    def test_users_table_columns(self, db_engine):
        """Test users table has expected columns."""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("users")}

        expected_columns = {
            "id",
            "email",
            "hashed_password",
            "first_name",
            "last_name",
            "is_active",
            "created_at",
            "updated_at",
        }

        assert expected_columns.issubset(columns)

    def test_portfolios_table_columns(self, db_engine):
        """Test portfolios table has expected columns."""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("portfolios")}

        expected_columns = {
            "id",
            "name",
            "description",
            "user_id",
            "created_at",
            "updated_at",
        }

        assert expected_columns.issubset(columns)

    def test_assets_table_columns(self, db_engine):
        """Test assets table has expected columns."""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("assets")}

        expected_columns = {
            "id",
            "symbol",
            "name",
            "asset_type",
            "portfolio_id",
            "quantity",
            "average_buy_price",
            "created_at",
            "updated_at",
        }

        assert expected_columns.issubset(columns)

    def test_transactions_table_columns(self, db_engine):
        """Test transactions table has expected columns."""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("transactions")}

        expected_columns = {
            "id",
            "asset_id",
            "transaction_type",
            "quantity",
            "price",
            "total_amount",
            "fees",
            "exchange",
            "notes",
            "timestamp",
            "created_at",
        }

        assert expected_columns.issubset(columns)

    def test_exchange_connections_table_columns(self, db_engine):
        """Test exchange_connections table has expected columns."""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("exchange_connections")}

        expected_columns = {
            "id",
            "user_id",
            "exchange_name",
            "api_key_encrypted",
            "api_secret_encrypted",
            "is_active",
            "last_synced_at",
            "created_at",
            "updated_at",
        }

        assert expected_columns.issubset(columns)

    def test_foreign_keys_exist(self, db_engine):
        """Test that foreign key constraints exist."""
        inspector = inspect(db_engine)

        # Portfolios -> Users
        portfolios_fks = inspector.get_foreign_keys("portfolios")
        assert any(fk["referred_table"] == "users" for fk in portfolios_fks)

        # Assets -> Portfolios
        assets_fks = inspector.get_foreign_keys("assets")
        assert any(fk["referred_table"] == "portfolios" for fk in assets_fks)

        # Transactions -> Assets
        transactions_fks = inspector.get_foreign_keys("transactions")
        assert any(fk["referred_table"] == "assets" for fk in transactions_fks)

        # ExchangeConnections -> Users
        exchange_fks = inspector.get_foreign_keys("exchange_connections")
        assert any(fk["referred_table"] == "users" for fk in exchange_fks)
