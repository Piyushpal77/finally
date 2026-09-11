# Market Data Backend — Summary

**Status:** Complete, tested, reviewed, all issues resolved. Updated to also cover the four
follow-up items `planning/MARKET_DATA_DESIGN.md` and `planning/REVIEW.md` flagged as
not-yet-built: the day-change **anchor**, ticker-format **validation**, SSE **keepalive**, and
the watchlist ∪ open-positions **reconciliation** helper. See "Follow-Up Additions" below.

## What Was Built

A complete market data subsystem in `backend/app/market/` (10 modules, ~700 lines) providing live price simulation and real market data via a unified interface.

### Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, in-memory)
        │
        ├──→ SSE stream endpoint (/api/stream/prices)
        ├──→ Portfolio valuation
        └──→ Trade execution
```

### Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` — immutable frozen dataclass (ticker, price, previous_price, timestamp, change, direction) |
| `interface.py` | `MarketDataSource` — abstract base class defining `start/stop/add_ticker/remove_ticker/get_tickers` |
| `cache.py` | `PriceCache` — thread-safe price store with version counter for SSE change detection |
| `seed_prices.py` | Realistic seed prices, per-ticker GBM params (drift/volatility), correlation groups |
| `simulator.py` | `GBMSimulator` (Geometric Brownian Motion with Cholesky-correlated moves) + `SimulatorDataSource` |
| `massive_client.py` | `MassiveDataSource` — REST polling client for Polygon.io via the `massive` package |
| `factory.py` | `create_market_data_source()` — selects simulator or Massive based on `MASSIVE_API_KEY` env var |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint factory using version-based change detection, plus a ~15s `: keepalive` comment when the cache is idle |
| `validation.py` | `validate_ticker()` / `InvalidTickerError` — normalizes and enforces the 1-5 uppercase letter ticker format at every write path |
| `reconcile.py` | `get_tracked_tickers()` / `on_watchlist_add()` / `on_watchlist_remove()` / `on_trade_executed()` — keeps the market source's tracked set in sync with watchlist ∪ open positions; DB-agnostic (duck-typed), for the platform layer to call |

### Key Design Decisions

- **Strategy pattern** — both data sources implement the same ABC; downstream code is source-agnostic
- **PriceCache as single point of truth** — producers write, consumers read; no direct coupling
- **GBM with correlated moves** — Cholesky decomposition of sector-based correlation matrix; tech stocks correlate at 0.6, finance at 0.5, cross-sector at 0.3
- **Random shock events** — ~0.1% chance per tick per ticker of a 2-5% move for visual drama
- **SSE over WebSockets** — simpler, one-way push, universal browser support

## Test Suite

9 test modules in `backend/tests/market/` (originally 73 tests across 6 modules; extended with
anchor/validation/keepalive/reconcile coverage below — run `uv run --extra dev pytest -v` to get
the current count and coverage in your environment).

| Module | Covers |
|--------|--------|
| test_models.py | `PriceUpdate`, including day-change (`anchor`, `day_change`, `day_change_percent`) |
| test_cache.py | `PriceCache`, including anchor capture/stickiness/eviction (`TestPriceCacheAnchor`) |
| test_simulator.py | `GBMSimulator` math, correlation, unknown-ticker synthesis |
| test_simulator_source.py | `SimulatorDataSource` integration |
| test_factory.py | `create_market_data_source()` selection logic |
| test_massive.py | `MassiveDataSource`, including previous-close → anchor plumbing |
| test_validation.py | `validate_ticker()` / `InvalidTickerError` — new |
| test_stream.py | `_generate_events()` SSE loop, including the keepalive timer — new |
| test_reconcile.py | tracked-ticker reconciliation helpers against a fake DB/source — new |

## Code Review & Fixes Applied

A comprehensive code review identified 7 issues. All were resolved:

1. **pyproject.toml build config** — added `[tool.hatch.build.targets.wheel] packages = ["app"]`
2. **Lazy imports removed** — `massive` is a core dependency; imports moved to top level
3. **SSE return type fixed** — `_generate_events` annotated as `AsyncGenerator[str, None]`
4. **Public `get_tickers()`** — added to `GBMSimulator` to avoid private attribute access
5. **Correlation constants cleaned up** — removed unused `DEFAULT_CORR`, consolidated into `CROSS_GROUP_CORR`
6. **Unused test imports removed** — `pytest`, `math`, `asyncio` cleaned from 4 test files
7. **Massive test mocks fixed** — `source._client` set in tests, patches target correct names

## Follow-Up Additions (day-change anchor, validation, keepalive, reconciliation)

`planning/MARKET_DATA_DESIGN.md` and `planning/REVIEW.md` identified four pieces PLAN.md §6 and
the Design Decisions Log call for that were not in the original build. All four are now
implemented, per the design doc's specification:

1. **Day-change anchor** — `PriceUpdate` gained a required `anchor` field plus `day_change` /
   `day_change_percent` properties (distinct from the tick-to-tick `change` / `change_percent`).
   `PriceCache` captures the anchor on a ticker's first write (previous close if Massive supplies
   one via `snap.day.previous_close`, otherwise the first observed price) and keeps it sticky
   across later updates; `remove()` drops it so re-tracking re-anchors fresh. `to_dict()` — and so
   the SSE payload — now includes `anchor`, `day_change`, `day_change_percent`.
2. **Ticker validation** — new `validation.py` with `validate_ticker()` / `InvalidTickerError`,
   enforcing the `^[A-Z]{1,5}$` format. Scoped to the API boundary per the design doc: the
   simulator's unknown-ticker synthesis (`SEED_PRICES.get(ticker, random.uniform(50, 300))`)
   stays permissive internally and was already correct.
3. **SSE keepalive** — `stream.py`'s `_generate_events()` now tracks the wall-clock time since
   the last byte sent and emits a `: keepalive\n\n` comment after `KEEPALIVE_INTERVAL` (15s,
   configurable) of no price changes, so the frontend's connection-status indicator can tell an
   idle stream from a dropped one.
4. **Watchlist ∪ open-positions reconciliation** — new `reconcile.py` with `get_tracked_tickers()`,
   `on_watchlist_add()`, `on_watchlist_remove()`, `on_trade_executed()`. These are intentionally
   DB-agnostic (a `TrackedTickerStore` `Protocol` with `get_watchlist_tickers` /
   `get_open_position_tickers` / `get_position` / `is_on_watchlist`) since no database module
   exists yet — the backend platform agent wires in the real DB implementation and calls these
   helpers from the watchlist/trade routes and at startup, per §13 of `MARKET_DATA_DESIGN.md`.

All four are additive (new optional kwargs, new modules) — no existing call site outside the
market package needed to change.

## Demo

A Rich terminal demo is available at `backend/market_data_demo.py`:

```bash
cd backend
uv run market_data_demo.py
```

Displays a live-updating dashboard with all 10 tickers, sparklines, color-coded direction arrows, and an event log for notable price moves. Runs 60 seconds or until Ctrl+C.

## Usage for Downstream Code

```python
from app.market import PriceCache, create_market_data_source

# Startup
cache = PriceCache()
source = create_market_data_source(cache)  # Reads MASSIVE_API_KEY
await source.start(["AAPL", "GOOGL", "MSFT", ...])

# Read prices
update = cache.get("AAPL")          # PriceUpdate or None
price = cache.get_price("AAPL")     # float or None
all_prices = cache.get_all()        # dict[str, PriceUpdate]

# Dynamic watchlist
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```

```python
from app.market import InvalidTickerError, validate_ticker

# At every write path that accepts a ticker (watchlist add, trade, LLM actions)
try:
    ticker = validate_ticker(raw_ticker)
except InvalidTickerError as e:
    ...  # 400 for manual API calls; folded into the per-action chat result for LLM actions
```

```python
from app.market import get_tracked_tickers, on_trade_executed, on_watchlist_add, on_watchlist_remove

# `db` is anything exposing get_watchlist_tickers / get_open_position_tickers /
# get_position / is_on_watchlist (see reconcile.py) — supplied by the platform's DB module.
initial_tickers = await get_tracked_tickers(db)
await source.start(initial_tickers)

# After the DB transaction commits in each write path:
await on_watchlist_add(source, ticker)
await on_watchlist_remove(source, db, ticker)
await on_trade_executed(source, db, ticker)
```
