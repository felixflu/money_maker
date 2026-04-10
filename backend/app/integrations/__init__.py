"""
Exchange integrations module.

Provides API clients for external exchange integrations.
"""

from app.integrations.trade_republic import (
    TradeRepublicClient,
    TradeRepublicAPIError,
    TradeRepublicAuthError,
    TradeRepublicRateLimitError,
)
from app.integrations.bitpanda import (
    BitpandaClient,
    BitpandaAPIError,
    BitpandaAuthError,
    BitpandaRateLimitError,
)

__all__ = [
    "TradeRepublicClient",
    "TradeRepublicAPIError",
    "TradeRepublicAuthError",
    "TradeRepublicRateLimitError",
    "BitpandaClient",
    "BitpandaAPIError",
    "BitpandaAuthError",
    "BitpandaRateLimitError",
]
