"""
MEXC Exchange Sync Service.

Handles syncing holdings and transactions from MEXC to the local database.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.exchange_connection import ExchangeConnection
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction
from app.services.mexc_client import MEXCClient, MEXCConfig, MEXCError

logger = logging.getLogger(__name__)


class MEXCSyncError(Exception):
    """Raised when MEXC sync fails."""

    pass


class MEXCSyncService:
    """
    Service for syncing data from MEXC exchange.

    Handles:
    - Holdings/assets sync
    - Transaction history import
    - Portfolio updates
    """

    EXCHANGE_NAME = "MEXC"
    ASSET_TYPE_CRYPTO = "cryptocurrency"

    def __init__(self, db: Session):
        """Initialize sync service with database session."""
        self.db = db

    def _get_or_create_portfolio(self, user_id: int) -> Portfolio:
        """Get or create a portfolio for MEXC holdings."""
        portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.user_id == user_id, Portfolio.name == "MEXC Portfolio")
            .first()
        )

        if not portfolio:
            portfolio = Portfolio(
                name="MEXC Portfolio",
                description="Portfolio synced from MEXC exchange",
                user_id=user_id,
            )
            self.db.add(portfolio)
            self.db.commit()
            self.db.refresh(portfolio)
            logger.info(f"Created new portfolio for user {user_id}")

        return portfolio

    def _get_or_create_asset(
        self, portfolio_id: int, symbol: str, name: Optional[str] = None
    ) -> Asset:
        """Get or create an asset in the portfolio."""
        asset = (
            self.db.query(Asset)
            .filter(Asset.portfolio_id == portfolio_id, Asset.symbol == symbol)
            .first()
        )

        if not asset:
            asset = Asset(
                symbol=symbol,
                name=name or symbol,
                asset_type=self.ASSET_TYPE_CRYPTO,
                portfolio_id=portfolio_id,
                quantity=Decimal("0"),
            )
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)
            logger.info(f"Created new asset {symbol} in portfolio {portfolio_id}")

        return asset

    async def sync_holdings(
        self,
        connection: ExchangeConnection,
    ) -> dict:
        """
        Sync holdings from MEXC to local database.

        Args:
            connection: ExchangeConnection with MEXC credentials

        Returns:
            Dictionary with sync results

        Raises:
            MEXCSyncError: If sync fails
        """
        if connection.exchange_name != self.EXCHANGE_NAME:
            raise MEXCSyncError(
                f"Invalid exchange: {connection.exchange_name}. Expected {self.EXCHANGE_NAME}"
            )

        # Parse additional config if present
        additional_config = {}
        if connection.additional_config:
            import json

            try:
                additional_config = json.loads(connection.additional_config)
            except json.JSONDecodeError:
                pass

        config = MEXCConfig(
            api_key=connection.api_key_encrypted,  # Assume already decrypted or use decryption
            api_secret=connection.api_secret_encrypted,  # Assume already decrypted or use decryption
        )

        try:
            async with MEXCClient(config) as client:
                # Test connection first
                if not await client.test_connection():
                    raise MEXCSyncError("Failed to connect to MEXC API")

                # Get holdings from MEXC
                holdings = await client.get_holdings()

                # Get or create portfolio
                portfolio = self._get_or_create_portfolio(connection.user_id)

                synced_assets = []
                for holding in holdings:
                    # Get or create asset
                    asset = self._get_or_create_asset(
                        portfolio_id=portfolio.id,
                        symbol=holding.asset,
                        name=holding.asset,
                    )

                    # Update asset quantity
                    old_quantity = asset.quantity
                    asset.quantity = holding.total

                    # Calculate average buy price if not set
                    if asset.average_buy_price is None:
                        # Default to current value if no historical data
                        asset.average_buy_price = Decimal("0")

                    synced_assets.append(
                        {
                            "symbol": holding.asset,
                            "old_quantity": str(old_quantity),
                            "new_quantity": str(holding.total),
                            "free": str(holding.free),
                            "locked": str(holding.locked),
                        }
                    )

                self.db.commit()

                # Update last synced timestamp
                connection.last_synced_at = datetime.now(timezone.utc)
                self.db.commit()

                logger.info(
                    f"Synced {len(synced_assets)} holdings for user {connection.user_id}"
                )

                return {
                    "success": True,
                    "synced_count": len(synced_assets),
                    "assets": synced_assets,
                }

        except MEXCError as e:
            logger.error(f"MEXC API error during holdings sync: {e}")
            raise MEXCSyncError(f"MEXC API error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during holdings sync: {e}")
            raise MEXCSyncError(f"Sync failed: {e}") from e

    async def sync_transactions(
        self,
        connection: ExchangeConnection,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """
        Sync transaction history from MEXC to local database.

        Args:
            connection: ExchangeConnection with MEXC credentials
            start_time: Optional start time for transaction fetch
            end_time: Optional end time for transaction fetch

        Returns:
            Dictionary with sync results

        Raises:
            MEXCSyncError: If sync fails
        """
        if connection.exchange_name != self.EXCHANGE_NAME:
            raise MEXCSyncError(
                f"Invalid exchange: {connection.exchange_name}. Expected {self.EXCHANGE_NAME}"
            )

        config = MEXCConfig(
            api_key=connection.api_key_encrypted,
            api_secret=connection.api_secret_encrypted,
        )

        try:
            async with MEXCClient(config) as client:
                # Test connection first
                if not await client.test_connection():
                    raise MEXCSyncError("Failed to connect to MEXC API")

                # Convert datetime to milliseconds timestamp
                start_ms = int(start_time.timestamp() * 1000) if start_time else None
                end_ms = int(end_time.timestamp() * 1000) if end_time else None

                # Get trades from MEXC
                trades = await client.get_all_trades(
                    start_time=start_ms, end_time=end_ms
                )

                # Get or create portfolio
                portfolio = self._get_or_create_portfolio(connection.user_id)

                synced_transactions = []
                for trade in trades:
                    # Extract base asset from symbol (e.g., "BTC" from "BTCUSDT")
                    # MEXC symbols are typically BASEQUOTE format
                    symbol = trade.symbol
                    base_asset = symbol[:3] if len(symbol) >= 6 else symbol
                    if symbol.endswith("USDT"):
                        base_asset = symbol[:-4]
                    elif symbol.endswith("USDC"):
                        base_asset = symbol[:-4]
                    elif symbol.endswith("BTC"):
                        base_asset = symbol[:-3]
                    elif symbol.endswith("ETH"):
                        base_asset = symbol[:-3]

                    # Get or create asset
                    asset = self._get_or_create_asset(
                        portfolio_id=portfolio.id,
                        symbol=base_asset,
                        name=base_asset,
                    )

                    # Check if transaction already exists
                    existing_tx = (
                        self.db.query(Transaction)
                        .filter(
                            Transaction.asset_id == asset.id,
                            Transaction.exchange == self.EXCHANGE_NAME,
                        )
                        .filter(Transaction.notes.contains(f"Trade ID: {trade.id}"))
                        .first()
                    )

                    if existing_tx:
                        continue

                    # Create transaction
                    transaction = Transaction(
                        asset_id=asset.id,
                        transaction_type="buy" if trade.is_buyer else "sell",
                        quantity=trade.qty,
                        price=trade.price,
                        total_amount=trade.quote_qty,
                        fees=trade.commission if trade.commission > 0 else None,
                        exchange=self.EXCHANGE_NAME,
                        notes=f"Trade ID: {trade.id}, Order ID: {trade.order_id}, Symbol: {trade.symbol}",
                        timestamp=datetime.fromtimestamp(
                            trade.time / 1000, tz=timezone.utc
                        ),
                    )
                    self.db.add(transaction)

                    synced_transactions.append(
                        {
                            "trade_id": trade.id,
                            "symbol": trade.symbol,
                            "side": trade.side,
                            "quantity": str(trade.qty),
                            "price": str(trade.price),
                        }
                    )

                self.db.commit()

                # Update last synced timestamp
                connection.last_synced_at = datetime.now(timezone.utc)
                self.db.commit()

                logger.info(
                    f"Synced {len(synced_transactions)} transactions for user {connection.user_id}"
                )

                return {
                    "success": True,
                    "synced_count": len(synced_transactions),
                    "transactions": synced_transactions,
                }

        except MEXCError as e:
            logger.error(f"MEXC API error during transaction sync: {e}")
            raise MEXCSyncError(f"MEXC API error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during transaction sync: {e}")
            raise MEXCSyncError(f"Sync failed: {e}") from e

    async def full_sync(
        self,
        connection: ExchangeConnection,
        sync_transactions: bool = True,
        transaction_start_time: Optional[datetime] = None,
    ) -> dict:
        """
        Perform full sync of holdings and optionally transactions.

        Args:
            connection: ExchangeConnection with MEXC credentials
            sync_transactions: Whether to sync transaction history
            transaction_start_time: Optional start time for transactions

        Returns:
            Dictionary with full sync results
        """
        results = {
            "holdings": None,
            "transactions": None,
            "errors": [],
        }

        # Sync holdings
        try:
            results["holdings"] = await self.sync_holdings(connection)
        except MEXCSyncError as e:
            results["errors"].append(f"Holdings sync failed: {e}")

        # Sync transactions if requested
        if sync_transactions:
            try:
                results["transactions"] = await self.sync_transactions(
                    connection, start_time=transaction_start_time
                )
            except MEXCSyncError as e:
                results["errors"].append(f"Transaction sync failed: {e}")

        return results
