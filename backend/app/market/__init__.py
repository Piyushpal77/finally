"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate         - Immutable price snapshot dataclass (includes day-change anchor)
    PriceCache          - Thread-safe in-memory price store
    MarketDataSource    - Abstract interface for data providers
    create_market_data_source - Factory that selects simulator or Massive
    create_stream_router - FastAPI router factory for SSE endpoint
    validate_ticker / InvalidTickerError - Ticker symbol format validation
    get_tracked_tickers / on_watchlist_add / on_watchlist_remove / on_trade_executed
        - Keep the market source's tracked set in sync with watchlist ∪ open positions
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .reconcile import (
    get_tracked_tickers,
    on_trade_executed,
    on_watchlist_add,
    on_watchlist_remove,
)
from .stream import create_stream_router
from .validation import InvalidTickerError, validate_ticker

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
    "get_tracked_tickers",
    "on_watchlist_add",
    "on_watchlist_remove",
    "on_trade_executed",
    "validate_ticker",
    "InvalidTickerError",
]
