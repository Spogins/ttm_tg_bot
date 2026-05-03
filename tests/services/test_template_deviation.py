# -*- coding: utf-8 -*-
"""
Unit tests for the deviation_pct calculation used in handle_template_name.

The formula is:  (actual - planned) / planned * 100
Edge cases: zero planned hours, negative deviation (overestimate), exact match.
"""
import pytest


def _deviation(actual: float, planned: float) -> float:
    """Mirrors the logic in bot/handlers/common.py::handle_template_name."""
    if planned > 0:
        return round((actual - planned) / planned * 100, 1)
    return 0.0


class TestDeviationPct:
    def test_underestimate_returns_positive(self):
        # planned 4h, actual 6h → +50%
        assert _deviation(6.0, 4.0) == 50.0

    def test_overestimate_returns_negative(self):
        # planned 8h, actual 4h → -50%
        assert _deviation(4.0, 8.0) == -50.0

    def test_exact_match_returns_zero(self):
        assert _deviation(5.0, 5.0) == 0.0

    def test_zero_planned_returns_zero_not_division_error(self):
        # guard for the ZeroDivisionError case
        assert _deviation(3.0, 0.0) == 0.0

    def test_result_is_rounded_to_one_decimal(self):
        # 1/3 ≈ 33.333… rounds to 33.3
        assert _deviation(4.0, 3.0) == pytest.approx(33.3, abs=0.05)

    def test_small_underestimate(self):
        # planned 10h, actual 11h → +10%
        assert _deviation(11.0, 10.0) == 10.0

    def test_large_deviation(self):
        # planned 1h, actual 5h → +400%
        assert _deviation(5.0, 1.0) == 400.0
