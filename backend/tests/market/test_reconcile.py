"""Tests for the watchlist <-> open-position tracked-ticker reconciliation helpers."""

from dataclasses import dataclass

import pytest

from app.market.reconcile import (
    get_tracked_tickers,
    on_trade_executed,
    on_watchlist_add,
    on_watchlist_remove,
)


@dataclass
class FakePosition:
    quantity: float


class FakeDB:
    """In-memory stand-in for the database, exposing only what reconcile.py needs."""

    def __init__(self, watchlist=None, positions=None):
        self._watchlist: set[str] = set(watchlist or [])
        self._positions: dict[str, FakePosition] = dict(positions or {})

    def set_position(self, ticker: str, quantity: float) -> None:
        self._positions[ticker] = FakePosition(quantity=quantity)

    def set_on_watchlist(self, ticker: str, on: bool) -> None:
        if on:
            self._watchlist.add(ticker)
        else:
            self._watchlist.discard(ticker)

    async def get_watchlist_tickers(self) -> list[str]:
        return sorted(self._watchlist)

    async def get_open_position_tickers(self) -> list[str]:
        return sorted(t for t, p in self._positions.items() if p.quantity > 0)

    async def get_position(self, ticker: str) -> FakePosition | None:
        return self._positions.get(ticker)

    async def is_on_watchlist(self, ticker: str) -> bool:
        return ticker in self._watchlist


class FakeSource:
    """Records add_ticker/remove_ticker calls without touching a real cache."""

    def __init__(self):
        self.added: list[str] = []
        self.removed: list[str] = []

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)

    @property
    def add_called(self) -> bool:
        return bool(self.added)

    @property
    def remove_called(self) -> bool:
        return bool(self.removed)


@pytest.mark.asyncio
class TestGetTrackedTickers:
    async def test_union_of_watchlist_and_positions(self):
        db = FakeDB(watchlist=["AAPL", "GOOGL"], positions={"TSLA": FakePosition(5)})
        tracked = await get_tracked_tickers(db)
        assert tracked == ["AAPL", "GOOGL", "TSLA"]

    async def test_deduplicates_overlap(self):
        db = FakeDB(watchlist=["AAPL"], positions={"AAPL": FakePosition(5)})
        tracked = await get_tracked_tickers(db)
        assert tracked == ["AAPL"]

    async def test_excludes_zero_quantity_positions(self):
        db = FakeDB(watchlist=[], positions={"AAPL": FakePosition(0)})
        tracked = await get_tracked_tickers(db)
        assert tracked == []

    async def test_empty_everything(self):
        db = FakeDB()
        assert await get_tracked_tickers(db) == []


@pytest.mark.asyncio
class TestOnWatchlistAdd:
    async def test_adds_to_source(self):
        source = FakeSource()
        await on_watchlist_add(source, "AAPL")
        assert source.added == ["AAPL"]


@pytest.mark.asyncio
class TestOnWatchlistRemove:
    async def test_remove_watchlist_keeps_open_position(self):
        db = FakeDB()
        db.set_position("AAPL", quantity=10)
        source = FakeSource()
        await on_watchlist_remove(source, db, "AAPL")
        assert not source.remove_called

    async def test_remove_watchlist_no_position_removes(self):
        db = FakeDB()
        db.set_position("AAPL", quantity=0)
        source = FakeSource()
        await on_watchlist_remove(source, db, "AAPL")
        assert source.remove_called

    async def test_remove_watchlist_unknown_ticker_removes(self):
        db = FakeDB()
        source = FakeSource()
        await on_watchlist_remove(source, db, "NOPE")
        assert source.remove_called


@pytest.mark.asyncio
class TestOnTradeExecuted:
    async def test_trade_opens_new_ticker_not_on_watchlist(self):
        db = FakeDB()
        db.set_position("PYPL", quantity=5)
        db.set_on_watchlist("PYPL", False)
        source = FakeSource()
        await on_trade_executed(source, db, "PYPL")
        assert source.added == ["PYPL"]

    async def test_sell_to_zero_off_watchlist_removes(self):
        db = FakeDB()
        db.set_position("PYPL", quantity=0)
        db.set_on_watchlist("PYPL", False)
        source = FakeSource()
        await on_trade_executed(source, db, "PYPL")
        assert source.removed == ["PYPL"]

    async def test_sell_to_zero_still_on_watchlist_keeps_tracked(self):
        db = FakeDB()
        db.set_position("AAPL", quantity=0)
        db.set_on_watchlist("AAPL", True)
        source = FakeSource()
        await on_trade_executed(source, db, "AAPL")
        assert not source.remove_called
        assert not source.add_called

    async def test_buy_more_of_existing_open_position(self):
        db = FakeDB()
        db.set_position("AAPL", quantity=15)
        db.set_on_watchlist("AAPL", True)
        source = FakeSource()
        await on_trade_executed(source, db, "AAPL")
        assert source.added == ["AAPL"]
