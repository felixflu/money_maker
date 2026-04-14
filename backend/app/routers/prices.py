"""
Price routes for fetching live asset prices.

Provides endpoints for:
- Single asset price lookup
- Batch price fetching
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import AssetType, PriceResponse, BatchPriceRequest, BatchPriceResponse
from app.services.pricing import PriceService

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])
logger = logging.getLogger(__name__)

_price_service = PriceService()


@router.get(
    "/{symbol}",
    response_model=PriceResponse,
    summary="Get asset price",
    description="Get the current price for a single asset.",
)
async def get_price(
    symbol: str,
    asset_type: AssetType = Query(..., description="Type of asset"),
    coingecko_id: Optional[str] = Query(None, description="CoinGecko ID for crypto"),
):
    result = await _price_service.get_price(
        symbol, asset_type.value, coingecko_id=coingecko_id
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price not available for {symbol}",
        )

    return PriceResponse(
        symbol=result["symbol"],
        price=str(result["price"]),
        currency=result.get("currency", "USD"),
        source=result["source"],
        timestamp=result.get("timestamp"),
        is_stale=result.get("is_stale", False),
    )


@router.post(
    "/batch",
    response_model=BatchPriceResponse,
    summary="Get batch prices",
    description="Get prices for multiple assets in a single request.",
)
async def get_prices_batch(request: BatchPriceRequest):
    assets = []
    for item in request.assets:
        symbol = item.get("symbol", "")
        asset_type = item.get("asset_type", "cryptocurrency")
        coingecko_id = item.get("coingecko_id")
        assets.append((symbol, asset_type, coingecko_id))

    results = await _price_service.get_prices_batch(assets)

    prices = []
    for symbol, data in results.items():
        prices.append(
            PriceResponse(
                symbol=data["symbol"],
                price=str(data["price"]),
                currency=data.get("currency", "USD"),
                source=data.get("source", "unknown"),
                timestamp=data.get("timestamp"),
                is_stale=data.get("is_stale", False),
            )
        )

    return BatchPriceResponse(prices=prices)
