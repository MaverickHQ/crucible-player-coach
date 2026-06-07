from __future__ import annotations

import math

import numpy as np
import pytest

from player_coach.market.atr import compute_atr


def test_wilder_atr_golden_fixture():
    # Hand-computed, period=2, 4 bars:
    #   TR1 = max(11-10, |11-9.5|, |10-9.5|)   = 1.5
    #   TR2 = max(13-10.5, |13-10.5|, |10.5-10.5|) = 2.5
    #   TR3 = max(12.5-11, |12.5-12|, |11-12|) = 1.5
    #   seed ATR = mean(TR1, TR2) = 2.0
    #   ATR     = (2.0*(2-1) + 1.5) / 2 = 1.75
    highs = [10.0, 11.0, 13.0, 12.5]
    lows = [9.0, 10.0, 10.5, 11.0]
    closes = [9.5, 10.5, 12.0, 11.5]
    assert math.isclose(compute_atr(highs, lows, closes, period=2), 1.75, rel_tol=1e-9)


def test_atr_is_positive_for_real_range():
    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 1, 50))
    highs = closes + 1.0
    lows = closes - 1.0
    assert compute_atr(highs, lows, closes, period=14) > 0.0


def test_atr_raises_on_insufficient_bars():
    # period=14 needs at least 15 bars.
    highs = [10.0] * 14
    lows = [9.0] * 14
    closes = [9.5] * 14
    with pytest.raises(ValueError):
        compute_atr(highs, lows, closes, period=14)


def test_atr_accepts_minimum_bars():
    highs = [10.0] * 15
    lows = [9.0] * 15
    closes = [9.5] * 15
    compute_atr(highs, lows, closes, period=14)  # must not raise


def test_wider_ranges_give_larger_atr():
    closes = [100.0] * 20
    tight = compute_atr([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes, 14)
    wide = compute_atr([c + 3.0 for c in closes], [c - 3.0 for c in closes], closes, 14)
    assert wide > tight
