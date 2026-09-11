"""Tests for ticker symbol validation."""

import pytest

from app.market.validation import InvalidTickerError, validate_ticker


class TestValidateTicker:
    """Unit tests for validate_ticker()."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("aapl", "AAPL"),
            (" TSLA ", "TSLA"),
            ("V", "V"),
            ("v", "V"),
            ("GOOGL", "GOOGL"),
            ("goog", "GOOG"),
        ],
    )
    def test_valid_tickers_normalize(self, raw, expected):
        assert validate_ticker(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "TOOLONG", "AB3", "AB-C", "aapl$", "123", "A B", "TOO-LONG-NAME"],
    )
    def test_invalid_tickers_raise(self, raw):
        with pytest.raises(InvalidTickerError):
            validate_ticker(raw)

    def test_unicode_case_folding_expansion_rejected(self):
        """'ß'.upper() == 'SS' would otherwise pass the 1-5-letter regex despite
        being a single non-ASCII character, not 1-5 letters in the input."""
        with pytest.raises(InvalidTickerError):
            validate_ticker("ß")

    def test_error_message_includes_original_input(self):
        with pytest.raises(InvalidTickerError, match="NOT-A-TICKER"):
            validate_ticker("NOT-A-TICKER")

    def test_invalid_ticker_error_is_value_error(self):
        """InvalidTickerError should be catchable as a ValueError by generic handlers."""
        assert issubclass(InvalidTickerError, ValueError)
