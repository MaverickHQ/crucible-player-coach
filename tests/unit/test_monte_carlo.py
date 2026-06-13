from __future__ import annotations

from player_coach.analytics.monte_carlo import (
    apply_monte_carlo_trigger,
    simulate_challenge,
)
from player_coach.analytics.trade_stats import TradeStats, trade_stats


def _stats(win_rate: float, avg_win: float, avg_loss: float) -> TradeStats:
    return TradeStats(count=50, win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss)


# ----------------------------------------------------------- simulate_challenge

def test_probability_in_unit_range():
    r = simulate_challenge(_stats(0.55, 0.01, 0.01), 0.06, 0.10, 20, 1, n_paths=1000)
    assert 0.0 <= r.success_probability <= 1.0
    assert r.n_paths == 1000


def test_higher_win_rate_higher_success():
    low = simulate_challenge(
        _stats(0.45, 0.01, 0.01), 0.06, 0.10, 20, 1, n_paths=2000
    ).success_probability
    high = simulate_challenge(
        _stats(0.65, 0.01, 0.01), 0.06, 0.10, 20, 1, n_paths=2000
    ).success_probability
    assert high > low


def test_seeded_determinism():
    a = simulate_challenge(_stats(0.55, 0.01, 0.01), 0.06, 0.10, 20, 1,
                           n_paths=500, seed=7).success_probability
    b = simulate_challenge(_stats(0.55, 0.01, 0.01), 0.06, 0.10, 20, 1,
                           n_paths=500, seed=7).success_probability
    assert a == b


def test_no_edge_returns_zero():
    assert simulate_challenge(
        trade_stats([]), 0.06, 0.10, 20, 1, n_paths=100
    ).success_probability == 0.0


def test_strong_edge_high_probability():
    # 90% win rate, 5:1 payoff, small target → almost always reaches target.
    r = simulate_challenge(_stats(0.9, 0.05, 0.01), 0.06, 0.20, 20, 1, n_paths=1000)
    assert r.success_probability > 0.8


def test_no_losses_does_not_inflate_probability():
    # R2: avg_loss == 0 means downside can't be modelled — losing draws would add
    # -0.0 and drawdown could never fire, falsely reporting ~1.0. Must be 0.0.
    r = simulate_challenge(_stats(0.9, 0.02, 0.0), 0.06, 0.10, 20, 1, n_paths=500)
    assert r.success_probability == 0.0


def test_expired_challenge_returns_zero():
    # R3: no trades remaining → cannot pass. Must not floor to one trade.
    assert simulate_challenge(
        _stats(1.0, 0.10, 0.01), 0.06, 0.10, 0, 1, n_paths=100
    ).success_probability == 0.0
    assert simulate_challenge(
        _stats(1.0, 0.10, 0.01), 0.06, 0.10, 5, 0.0, n_paths=100
    ).success_probability == 0.0


# -------------------------------------------------------- auto-conservation

def test_trigger_escalates_building_to_conservation():
    assert apply_monte_carlo_trigger("building", 0.30) == "conservation"


def test_trigger_no_op_above_threshold():
    assert apply_monte_carlo_trigger("building", 0.50) == "building"


def test_trigger_no_op_when_prob_none():
    assert apply_monte_carlo_trigger("building", None) == "building"


def test_trigger_leaves_protective_phases_alone():
    assert apply_monte_carlo_trigger("lock_in", 0.10) == "lock_in"
    assert apply_monte_carlo_trigger("conservation", 0.10) == "conservation"
