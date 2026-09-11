"""Keeps a MarketDataSource's tracked ticker set in sync with watchlist ∪ open positions.

The tracked set for price streaming is always the union of watchlist tickers and
tickers with an open position, so a position is never left unpriced even if its
ticker is removed from the watchlist. This module owns that invariant in one place;
platform code (watchlist routes, trade routes, startup) calls these helpers instead
of calling `MarketDataSource.add_ticker` / `remove_ticker` directly.

These helpers are deliberately DB-agnostic: `db` is any object exposing the four
async methods used below (`get_watchlist_tickers`, `get_open_position_tickers`,
`get_position`, `is_on_watchlist`). The platform layer's database module supplies
the concrete implementation; tests use a lightweight fake.
"""

from __future__ import annotations

from typing import Protocol

from .interface import MarketDataSource


class Position(Protocol):
    quantity: float


class TrackedTickerStore(Protocol):
    """The subset of the database API this module depends on."""

    async def get_watchlist_tickers(self) -> list[str]: ...

    async def get_open_position_tickers(self) -> list[str]: ...

    async def get_position(self, ticker: str) -> Position | None: ...

    async def is_on_watchlist(self, ticker: str) -> bool: ...


async def get_tracked_tickers(db: TrackedTickerStore) -> list[str]:
    """The full tracked set: every watchlist ticker plus every ticker with an open
    position, deduplicated. Used at startup and anywhere the full set needs
    recomputing from scratch."""
    watchlist = await db.get_watchlist_tickers()
    positions = await db.get_open_position_tickers()
    return sorted(set(watchlist) | set(positions))


async def on_watchlist_add(source: MarketDataSource, ticker: str) -> None:
    """Call after inserting a new watchlist row. Idempotent — add_ticker() on both
    sources is already a no-op if the ticker is already tracked (e.g. via an open
    position)."""
    await source.add_ticker(ticker)


async def on_watchlist_remove(source: MarketDataSource, db: TrackedTickerStore, ticker: str) -> None:
    """Call after deleting a watchlist row. Only stops tracking if there is no open
    position for this ticker — an open position keeps it priced even off the
    watchlist."""
    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)


async def on_trade_executed(source: MarketDataSource, db: TrackedTickerStore, ticker: str) -> None:
    """Call after every trade commits (buy or sell). Covers two edge cases the
    watchlist-add/remove hooks alone don't handle:

    1. A buy opens a *new* ticker not on the watchlist -> it must start being tracked.
    2. A sell reduces a ticker's quantity to 0, and that ticker had already been
       removed from the watchlist earlier while the position was still open -> now
       that nothing references it, stop tracking it.
    """
    position = await db.get_position(ticker)
    on_watchlist = await db.is_on_watchlist(ticker)

    if position and position.quantity > 0:
        await source.add_ticker(ticker)  # covers case 1; no-op if already tracked
    elif not on_watchlist:
        await source.remove_ticker(ticker)  # covers case 2
