# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `anchor`, `timestamp`, plus properties `change`/`change_percent`/`direction` ("up"/"down"/"flat", tick-to-tick) and `day_change`/`day_change_percent` (vs. `anchor` — this is the "% change" shown in the watchlist), and `to_dict()` for JSON serialization.

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None, anchor=None) -> PriceUpdate` — `anchor` is captured only on a ticker's first write and stays sticky after that
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_anchor(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `remove(ticker)` — also drops the ticker's anchor
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

- **`validate_ticker(raw) -> str`** / **`InvalidTickerError`** — normalizes and enforces the `^[A-Z]{1,5}$` ticker format. Call this at every write path that accepts a ticker (watchlist add, trade, LLM-issued actions) before touching the DB or the market source.

- **`get_tracked_tickers(db)`**, **`on_watchlist_add(source, ticker)`**, **`on_watchlist_remove(source, db, ticker)`**, **`on_trade_executed(source, db, ticker)`** — keep the market source's tracked ticker set equal to `watchlist ∪ open positions`. `db` is duck-typed (see `reconcile.py`'s `TrackedTickerStore` protocol) since this module has no DB dependency of its own; call these after each DB write commits.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
# Emits a ": keepalive" comment every ~15s when no price has changed.
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
