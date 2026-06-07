from __future__ import annotations

import math

from player_coach.analytics.trade_stats import TradeStats, trade_stats


def test_empty_returns_zero_stats():
    s = trade_stats([])
    assert s == TradeStats(count=0, win_rate=0.0, avg_win=0.0, avg_loss=0.0)


def test_mixed_wins_and_losses():
    # returns: +0.02, -0.01, +0.04, -0.03  → 2 wins / 4
    s = trade_stats([0.02, -0.01, 0.04, -0.03])
    assert s.count == 4
    assert math.isclose(s.win_rate, 0.5)
    assert math.isclose(s.avg_win, 0.03)   # (0.02 + 0.04) / 2
    assert math.isclose(s.avg_loss, 0.02)  # (0.01 + 0.03) / 2


def test_all_wins_has_zero_avg_loss():
    s = trade_stats([0.01, 0.02, 0.03])
    assert s.win_rate == 1.0
    assert s.avg_loss == 0.0
    assert math.isclose(s.avg_win, 0.02)


def test_all_losses_has_zero_avg_win():
    s = trade_stats([-0.01, -0.02])
    assert s.win_rate == 0.0
    assert s.avg_win == 0.0
    assert math.isclose(s.avg_loss, 0.015)


def test_avg_loss_is_positive_magnitude():
    s = trade_stats([-0.05])
    assert s.avg_loss == 0.05  # magnitude, not signed
