"""Ticker symbol validation shared by every write path that accepts a ticker."""

from __future__ import annotations

import re

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


class InvalidTickerError(ValueError):
    """Raised when a ticker does not match the 1-5 uppercase letter format."""


def validate_ticker(raw: str) -> str:
    """Normalize and validate a ticker symbol.

    Uppercases and strips whitespace, then requires 1-5 letters A-Z.
    Returns the normalized ticker on success; raises InvalidTickerError otherwise.

    Callers (every write path that accepts a ticker):
        - POST /api/watchlist              (manual watchlist add)
        - POST /api/portfolio/trade         (manual trade)
        - LLM `trades[].ticker`             (chat-initiated trade)
        - LLM `watchlist_changes[].ticker`  (chat-initiated watchlist change)
    """
    ticker = raw.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise InvalidTickerError(f"Invalid ticker '{raw}': must be 1-5 letters (A-Z).")
    return ticker
