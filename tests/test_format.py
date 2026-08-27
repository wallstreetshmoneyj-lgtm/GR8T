"""Percent-change and display-formatting edge cases (SPEC 9.3, 15)."""
from __future__ import annotations

import pytest

from app.format import fmt_millions, fmt_pct, fmt_ratio, fmt_statement_value, pct_change


class TestPctChange:
    def test_ordinary_increase(self):
        assert pct_change(110, 100) == pytest.approx(0.10)

    def test_ordinary_decrease(self):
        assert pct_change(90, 100) == pytest.approx(-0.10)

    def test_zero_older_is_none(self):
        # "render '-' when the older value is 0 or missing"
        assert pct_change(100, 0) is None

    def test_missing_values_are_none(self):
        assert pct_change(None, 100) is None
        assert pct_change(100, None) is None
        assert pct_change(None, None) is None

    def test_zero_newer_is_minus_one_not_none(self):
        # Going to zero is a real -100% change, not missing data.
        assert pct_change(0, 100) == pytest.approx(-1.0)

    def test_negative_to_positive_sign_flip(self):
        # abs() in the denominator: -50 -> 50 is +200%, not -200%.
        assert pct_change(50, -50) == pytest.approx(2.0)

    def test_positive_to_negative_sign_flip(self):
        assert pct_change(-50, 50) == pytest.approx(-2.0)

    def test_negative_to_less_negative(self):
        # -100 -> -50 is an improvement: +50%.
        assert pct_change(-50, -100) == pytest.approx(0.5)

    def test_tiny_older_produces_huge_magnitude_and_is_kept(self):
        # "Negative-to-positive flips will produce large magnitudes; render
        # them anyway" — no clamping.
        assert pct_change(1000, 0.001) == pytest.approx(999_999.0)


class TestNumberFormatting:
    def test_millions_with_separators(self):
        assert fmt_millions(67_357_000_000) == "67,357"

    def test_negatives_in_parentheses(self):
        assert fmt_millions(-23_686_000_000) == "(23,686)"

    def test_none_renders_as_dash(self):
        assert fmt_millions(None) == "-"
        assert fmt_statement_value(None, "USD") == "-"
        assert fmt_pct(None) == "-"

    def test_per_share_values_are_not_scaled_to_millions(self):
        assert fmt_statement_value(5.83, "USD/shares") == "5.83"
        assert fmt_statement_value(-1.25, "USD/shares") == "(1.25)"

    def test_ratio_formats(self):
        assert fmt_ratio(0.2536781626, "percent") == "25.4%"
        assert fmt_ratio(1.1150033521693323, "x") == "1.12x"
        assert fmt_ratio(51.32499, "days") == "51.3"
        assert fmt_ratio(None, "x") == "n/a"

    def test_large_ratios_keep_thousands_separators(self):
        # ORCL's FY2022 ROE is ~7,301% — rendered, not clamped.
        assert fmt_ratio(73.0109, "percent") == "7,301.1%"
