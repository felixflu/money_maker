"""
Portfolio routes with live price enrichment.

Provides endpoints for:
- Fetching user portfolios with real-time asset prices
- Portfolio value calculation using live price feeds
"""

import logging
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Portfolio, Asset
from app.services.pricing import PriceService

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])
logger = logging.getLogger(__name__)

_price_service = PriceService()


@router.get(
    "",
    summary="Get portfolios with live prices",
    description="Get all portfolios for the current user, enriched with live asset prices.",
)
async def get_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = (
        db.query(Portfolio)
        .options(joinedload(Portfolio.assets))
        .filter(Portfolio.user_id == current_user.id)
        .all()
    )

    result = []
    for portfolio in portfolios:
        enriched = await _enrich_portfolio(portfolio)
        result.append(enriched)

    return result


@router.get(
    "/{portfolio_id}",
    summary="Get portfolio with live prices",
    description="Get a specific portfolio enriched with live asset prices.",
)
async def get_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = (
        db.query(Portfolio)
        .options(joinedload(Portfolio.assets).joinedload(Asset.transactions))
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id)
        .first()
    )

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    return await _enrich_portfolio(portfolio)


async def _enrich_portfolio(portfolio: Portfolio) -> dict:
    """Enrich a portfolio with live prices from external APIs."""
    assets = portfolio.assets or []

    # Build batch request for all assets
    batch_assets = []
    for asset in assets:
        coingecko_id = asset.symbol.lower() if asset.asset_type == "cryptocurrency" else None
        batch_assets.append((asset.symbol, asset.asset_type, coingecko_id))

    # Fetch all prices in one batch
    prices = {}
    if batch_assets:
        prices = await _price_service.get_prices_batch(batch_assets)

    holdings = []
    total_value = Decimal("0")

    for asset in assets:
        price_data = prices.get(asset.symbol)
        current_price = price_data["price"] if price_data else None
        is_stale = price_data.get("is_stale", False) if price_data else False
        source = price_data.get("source", "unknown") if price_data else None

        value = Decimal("0")
        if current_price is not None:
            value = asset.quantity * current_price
            total_value += value

        # Compute cost basis from average_buy_price
        cost_basis = Decimal("0")
        if asset.average_buy_price is not None:
            cost_basis = asset.quantity * asset.average_buy_price

        unrealized_pnl = value - cost_basis if current_price is not None else Decimal("0")

        holdings.append({
            "id": asset.id,
            "symbol": asset.symbol,
            "name": asset.name,
            "assetType": asset.asset_type,
            "quantity": str(asset.quantity),
            "currentPrice": str(current_price) if current_price is not None else None,
            "value": str(value),
            "costBasis": str(cost_basis),
            "averageBuyPrice": str(asset.average_buy_price) if asset.average_buy_price else None,
            "unrealizedPnL": str(unrealized_pnl),
            "priceSource": source,
            "isStale": is_stale,
        })

    total_cost_basis = sum(
        Decimal(h["costBasis"]) for h in holdings
    )
    total_unrealized = total_value - total_cost_basis
    pnl_percent = (
        float(total_unrealized / total_cost_basis * 100)
        if total_cost_basis > 0
        else 0.0
    )

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "description": portfolio.description,
        "totalValue": str(total_value),
        "totalCostBasis": str(total_cost_basis),
        "totalUnrealizedPnL": str(total_unrealized),
        "totalPnLPercent": pnl_percent,
        "holdings": holdings,
        "updatedAt": portfolio.updated_at.isoformat() if portfolio.updated_at else None,
    }
