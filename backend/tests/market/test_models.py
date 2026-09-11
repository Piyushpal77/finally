"""Tests for PriceUpdate dataclass."""

import pytest

from app.market.models import PriceUpdate


class TestPriceUpdate:
    """Unit tests for the PriceUpdate model."""

    def test_price_update_creation(self):
        """Test basic PriceUpdate creation."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert update.previous_price == 190.00
        assert update.anchor == 190.00
        assert update.timestamp == 1234567890.0

    def test_change_calculation(self):
        """Test price change calculation."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.change == 0.50

    def test_change_negative(self):
        """Test negative price change."""
        update = PriceUpdate(
            ticker="AAPL", price=189.50, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.change == -0.50

    def test_change_percent_up(self):
        """Test percentage change calculation (up)."""
        update = PriceUpdate(
            ticker="AAPL", price=190.00, previous_price=100.00, anchor=100.00, timestamp=1234567890.0
        )
        assert update.change_percent == 90.0

    def test_change_percent_down(self):
        """Test percentage change calculation (down)."""
        update = PriceUpdate(
            ticker="AAPL", price=100.00, previous_price=200.00, anchor=200.00, timestamp=1234567890.0
        )
        assert update.change_percent == -50.0

    def test_change_percent_zero_previous(self):
        """Test percentage change with zero previous price."""
        update = PriceUpdate(
            ticker="AAPL", price=100.00, previous_price=0.00, anchor=100.00, timestamp=1234567890.0
        )
        assert update.change_percent == 0.0

    def test_direction_up(self):
        """Test direction calculation (up)."""
        update = PriceUpdate(
            ticker="AAPL", price=191.00, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.direction == "up"

    def test_direction_down(self):
        """Test direction calculation (down)."""
        update = PriceUpdate(
            ticker="AAPL", price=189.00, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.direction == "down"

    def test_direction_flat(self):
        """Test direction calculation (flat)."""
        update = PriceUpdate(
            ticker="AAPL", price=190.00, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        assert update.direction == "flat"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )
        result = update.to_dict()

        assert result["ticker"] == "AAPL"
        assert result["price"] == 190.50
        assert result["previous_price"] == 190.00
        assert result["anchor"] == 190.00
        assert result["timestamp"] == 1234567890.0
        assert result["change"] == 0.50
        assert result["change_percent"] == 0.2632  # (0.50 / 190.00) * 100
        assert result["direction"] == "up"
        assert result["day_change"] == 0.50
        assert result["day_change_percent"] == 0.2632

    def test_immutability(self):
        """Test that PriceUpdate is immutable."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00, anchor=190.00, timestamp=1234567890.0
        )

        with pytest.raises(AttributeError):
            update.price = 200.00  # Should raise error


class TestPriceUpdateDayChange:
    """Unit tests for the day-change (anchor-relative) properties."""

    def test_day_change_calculation(self):
        """day_change measures the move vs. the anchor, not the previous tick."""
        update = PriceUpdate(
            ticker="AAPL", price=200.0, previous_price=198.0, anchor=190.0, timestamp=1234567890.0
        )
        assert update.day_change == 10.0

    def test_day_change_percent_calculation(self):
        update = PriceUpdate(
            ticker="AAPL", price=200.0, previous_price=198.0, anchor=190.0, timestamp=1234567890.0
        )
        assert update.day_change_percent == pytest.approx(5.2632, rel=1e-3)

    def test_day_change_percent_zero_anchor_is_safe(self):
        """A zero anchor must not raise ZeroDivisionError."""
        update = PriceUpdate(
            ticker="X", price=10.0, previous_price=10.0, anchor=0.0, timestamp=1234567890.0
        )
        assert update.day_change_percent == 0.0

    def test_day_change_independent_of_tick_change(self):
        """Tick-to-tick change and day-change can point in different directions."""
        update = PriceUpdate(
            ticker="AAPL", price=189.0, previous_price=190.0, anchor=180.0, timestamp=1234567890.0
        )
        assert update.direction == "down"  # down vs. previous tick
        assert update.day_change_percent > 0  # but up vs. the day's anchor

    def test_to_dict_includes_anchor_fields(self):
        update = PriceUpdate(
            ticker="AAPL", price=200.0, previous_price=198.0, anchor=190.0, timestamp=1234567890.0
        )
        d = update.to_dict()
        assert d["anchor"] == 190.0
        assert d["day_change"] == 10.0
        assert d["day_change_percent"] == pytest.approx(5.2632, rel=1e-3)
