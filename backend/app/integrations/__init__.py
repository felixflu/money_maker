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
from app.integrations.mexc import (
    MexcClient,
    MexcAPIError,
    MexcAuthError,
    MexcRateLimitError,
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
    "MexcClient",
    "MexcAPIError",
    "MexcAuthError",
    "MexcRateLimitError",
    "BitpandaClient",
    "BitpandaAPIError",
    "BitpandaAuthError",
    "BitpandaRateLimitError",
]
