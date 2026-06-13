from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from player_coach.analytics.trade_stats import TradeStats


@dataclass(frozen=True)
class MonteCarloResult:
    success_probability: float
    n_paths: int


def simulate_challenge(
    stats: TradeStats,
    profit_target: float,
    drawdown_limit: float,
    days_remaining: int,
    trades_per_day: float,
    n_paths: int = 10_000,
    seed: int = 42,
) -> MonteCarloResult:
    """Probability of hitting ``profit_target`` before a trailing drawdown of
    ``drawdown_limit`` from the path peak, over the remaining trades.

    Each path draws ``round(days_remaining · trades_per_day)`` Bernoulli trades:
    ``+avg_win`` with probability ``win_rate``, else ``-avg_loss`` (both as return
    fractions). Seeded for reproducibility. With no realised edge → 0.0.
    """
    # No trades remaining (expired challenge) → cannot pass.
    if days_remaining <= 0 or trades_per_day <= 0:
        return MonteCarloResult(success_probability=0.0, n_paths=n_paths)
    # Need both a positive win and a positive loss magnitude to model the gamble.
    # With avg_loss == 0, losing draws add -0.0, drawdown never fires, and the
    # probability falsely inflates toward 1.0.
    if stats.count == 0 or stats.avg_win <= 0.0 or stats.avg_loss <= 0.0:
        return MonteCarloResult(success_probability=0.0, n_paths=n_paths)

    total_trades = max(1, int(round(days_remaining * trades_per_day)))
    rng = np.random.default_rng(seed)
    successes = 0

    for _ in range(n_paths):
        equity = 0.0
        peak = 0.0
        outcomes = rng.random(total_trades) < stats.win_rate
        for win in outcomes:
            equity += stats.avg_win if win else -stats.avg_loss
            if equity > peak:
                peak = equity
            if equity >= profit_target:
                successes += 1
                break
            if peak - equity >= drawdown_limit:
                break

    return MonteCarloResult(
        success_probability=successes / n_paths, n_paths=n_paths
    )


def apply_monte_carlo_trigger(
    phase: str, mc_prob: float | None, threshold: float = 0.40
) -> str:
    """Escalate ``building → conservation`` when the pass probability is below
    ``threshold`` (de-risk a challenge that's tracking to fail). A no-op when the
    probability is unknown or the phase is already protective."""
    if mc_prob is None:
        return phase
    if mc_prob < threshold and phase == "building":
        return "conservation"
    return phase
