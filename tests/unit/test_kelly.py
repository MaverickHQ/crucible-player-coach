from __future__ import annotations

import math

from player_coach.analytics.kelly import half_kelly
from player_coach.analytics.trade_stats import TradeStats, trade_stats


def _stats(win_rate: float, avg_win: float, avg_loss: float) -> TradeStats:
    return TradeStats(count=10, win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss)


def test_known_half_kelly_value():
    # W=0.6, payoff=2 → full = 0.6 - 0.4/2 = 0.4 → half = 0.2
    assert math.isclose(half_kelly(_stats(0.6, 0.02, 0.01)), 0.2, rel_tol=1e-9)


def test_cap_is_enforced():
    assert half_kelly(_stats(0.6, 0.02, 0.01), cap=0.05) == 0.05


def test_monotonic_in_win_rate():
    low = half_kelly(_stats(0.55, 0.02, 0.01))
    high = half_kelly(_stats(0.75, 0.02, 0.01))
    assert high > low


def test_negative_full_kelly_floored_at_zero():
    # W=0.3, payoff=1 → full = 0.3 - 0.7 = -0.4 → floored to 0.0
    assert half_kelly(_stats(0.3, 0.01, 0.01)) == 0.0


def test_no_trades_returns_zero():
    assert half_kelly(trade_stats([])) == 0.0


def test_all_wins_uses_winrate_as_full_kelly():
    # No losses → payoff unbounded → full Kelly -> win_rate; half = 0.5 * win_rate.
    # (The old behavior returned 0.0 — wrong exactly when the record is best.)
    assert half_kelly(_stats(1.0, 0.02, 0.0)) == 0.5
    assert half_kelly(_stats(0.5, 0.02, 0.0)) == 0.25


def test_all_wins_still_capped():
    assert half_kelly(_stats(1.0, 0.02, 0.0), cap=0.05) == 0.05


def test_is_half_of_full_kelly():
    # half_kelly should be exactly 0.5 * full Kelly when full is positive.
    s = _stats(0.6, 0.02, 0.01)
    full = s.win_rate - (1 - s.win_rate) / (s.avg_win / s.avg_loss)
    assert math.isclose(half_kelly(s), 0.5 * full, rel_tol=1e-9)
