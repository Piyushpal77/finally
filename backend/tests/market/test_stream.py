"""Tests for the SSE streaming generator."""

import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events


class FakeRequest:
    """Minimal stand-in for fastapi.Request, enough for _generate_events()."""

    class _Client:
        host = "127.0.0.1"

    def __init__(self, disconnect_after: int | None = None):
        self.client = self._Client()
        self._calls = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._calls += 1
        if self._disconnect_after is None:
            return False
        return self._calls > self._disconnect_after


async def _collect(generator, max_events: int) -> list[str]:
    """Pull up to `max_events` from an async generator, then close it."""
    events = []
    async for event in generator:
        events.append(event)
        if len(events) >= max_events:
            break
    await generator.aclose()
    return events


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for _generate_events()."""

    async def test_first_event_is_retry_directive(self):
        cache = PriceCache()
        request = FakeRequest()
        events = await _collect(
            _generate_events(cache, request, interval=0.01, keepalive_interval=1.0), 1
        )
        assert events[0] == "retry: 1000\n\n"

    async def test_data_event_sent_when_cache_has_prices(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest()
        events = await _collect(
            _generate_events(cache, request, interval=0.01, keepalive_interval=1.0), 2
        )
        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) == 1
        payload = json.loads(data_events[0][len("data: ") :].strip())
        assert payload["AAPL"]["price"] == 190.0

    async def test_no_data_event_when_cache_empty(self):
        cache = PriceCache()
        request = FakeRequest(disconnect_after=5)
        events = [
            e
            async for e in _generate_events(cache, request, interval=0.001, keepalive_interval=1.0)
        ]
        assert not any(e.startswith("data:") for e in events)

    async def test_keepalive_sent_when_cache_idle(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)  # one real event, then silence

        request = FakeRequest(disconnect_after=20)
        events = [
            e
            async for e in _generate_events(
                cache, request, interval=0.01, keepalive_interval=0.02
            )
        ]
        assert any(e.startswith(": keepalive") for e in events)

    async def test_no_duplicate_data_events_without_version_change(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=10)
        events = [
            e
            async for e in _generate_events(cache, request, interval=0.001, keepalive_interval=5.0)
        ]
        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) == 1

    async def test_stream_stops_on_disconnect(self):
        cache = PriceCache()
        request = FakeRequest(disconnect_after=2)
        events = [
            e
            async for e in _generate_events(cache, request, interval=0.001, keepalive_interval=5.0)
        ]
        # Generator must terminate on its own (the test would hang otherwise).
        assert isinstance(events, list)

    async def test_new_price_after_idle_period_sent_as_data(self):
        """A price change after a quiet period is sent as a fresh data event.

        Iterates the generator manually (never calling aclose()) so it stays
        alive across the cache mutation in the middle of the test.
        """
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=15)

        gen = _generate_events(cache, request, interval=0.005, keepalive_interval=0.01)
        events = []
        async for event in gen:
            events.append(event)
            if len(events) >= 2:  # retry directive + the initial data event
                break

        cache.update("AAPL", 191.0)

        async for event in gen:
            events.append(event)
            if event.startswith("data:") and "191.0" in event:
                break

        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) >= 2
        last_payload = json.loads(data_events[-1][len("data: ") :].strip())
        assert last_payload["AAPL"]["price"] == 191.0
