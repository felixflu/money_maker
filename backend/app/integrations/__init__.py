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
)
from app.integrations.coinbase import (
    CoinbaseClient,
    CoinbaseAPIError,
    CoinbaseAuthError,
    CoinbaseRateLimitError,
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
    "MexcClient",
    "MexcAPIError",
    "MexcAuthError",
    "MexcRateLimitError",
    "CoinbaseClient",
    "CoinbaseAPIError",
    "CoinbaseAuthError",
    "CoinbaseRateLimitError",
    "BitpandaClient",
    "BitpandaAPIError",
    "BitpandaAuthError",
    "BitpandaRateLimitError",
]
