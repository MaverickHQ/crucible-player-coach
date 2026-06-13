from __future__ import annotations

import math

from player_coach.backtest.metrics import (
    avg_recovery_time,
    calmar_ratio,
    drawdown_duration,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


def _curve(caps: list[float]) -> list[tuple[str, float]]:
    return [(f"2024-01-{i+1:02d}", c) for i, c in enumerate(caps)]


# ------------------------------------------------------------- max drawdown

def test_max_drawdown_golden():
    # peak 120 → trough 90 → (120-90)/120 = 0.25
    assert math.isclose(max_drawdown(_curve([100, 120, 90, 110])), 0.25)


def test_max_drawdown_monotonic_up_is_zero():
    assert max_drawdown(_curve([100, 110, 121])) == 0.0


# ----------------------------------------------------------------- sharpe

def test_sharpe_positive_for_rising_curve():
    assert sharpe_ratio(_curve([100, 101, 100.5, 102, 101.5, 103])) > 0


def test_sharpe_negative_for_falling_curve():
    assert sharpe_ratio(_curve([103, 101.5, 102, 100.5, 101, 100])) < 0


def test_sharpe_zero_for_flat_curve():
    assert sharpe_ratio(_curve([100, 100, 100])) == 0.0


# ----------------------------------------------------------------- sortino

def test_sortino_exceeds_sharpe_when_downside_is_smaller():
    # Mostly-up curve with small downside variance → sortino > sharpe.
    curve = _curve([100, 102, 101.5, 104, 103.5, 106])
    assert sortino_ratio(curve) > sharpe_ratio(curve)


# ----------------------------------------------------------------- calmar

def test_calmar_positive_for_profitable_curve_with_drawdown():
    assert calmar_ratio(_curve([100, 120, 90, 130])) > 0


# ----------------------------------------------------- drawdown duration / recovery

def test_drawdown_duration_golden():
    # [100,120,90,100,130]: underwater at idx 2,3 → longest run 2.
    assert drawdown_duration(_curve([100, 120, 90, 100, 130])) == 2


def test_avg_recovery_time_golden():
    # Drops below peak 120 at idx2, recovers (≥120) at idx4 → 2 periods.
    assert avg_recovery_time(_curve([100, 120, 90, 100, 130])) == 2.0


# --------------------------------------------------------------- empty guards

def test_metrics_handle_empty_curve():
    assert max_drawdown([]) == 0.0
    assert sharpe_ratio([]) == 0.0
    assert calmar_ratio([]) == 0.0
    assert drawdown_duration([]) == 0
    assert avg_recovery_time([]) == 0.0
