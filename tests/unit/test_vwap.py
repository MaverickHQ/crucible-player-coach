from __future__ import annotations

import math

import pytest

from player_coach.market.vwap import compute_vwap


def test_vwap_golden_fixture():
    # typical = (H+L+C)/3:  bar0 = 10 (vol 100), bar1 = 12 (vol 300)
    # vwap = (10*100 + 12*300) / (100+300) = 4600/400 = 11.5
    highs = [11.0, 13.0]
    lows = [9.0, 11.0]
    closes = [10.0, 12.0]
    volumes = [100.0, 300.0]
    assert math.isclose(compute_vwap(highs, lows, closes, volumes), 11.5, rel_tol=1e-9)


def test_vwap_single_bar_is_typical_price():
    assert math.isclose(
        compute_vwap([12.0], [6.0], [9.0], [500.0]), 9.0, rel_tol=1e-9
    )


def test_lookback_windows_to_recent_bars():
    # With lookback=1 only the last bar counts → its typical price.
    highs = [11.0, 13.0]
    lows = [9.0, 11.0]
    closes = [10.0, 12.0]
    volumes = [100.0, 300.0]
    assert math.isclose(
        compute_vwap(highs, lows, closes, volumes, lookback=1), 12.0, rel_tol=1e-9
    )


def test_zero_total_volume_raises():
    with pytest.raises(ValueError):
        compute_vwap([10.0, 11.0], [9.0, 10.0], [9.5, 10.5], [0.0, 0.0])


def test_higher_volume_bar_pulls_vwap_toward_its_price():
    # Heavy volume on the high-price bar drags VWAP up near 12.
    vwap = compute_vwap([11.0, 13.0], [9.0, 11.0], [10.0, 12.0], [1.0, 999.0])
    assert vwap > 11.9
