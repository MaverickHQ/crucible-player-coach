from __future__ import annotations

from player_coach.analytics.trade_stats import TradeStats


def half_kelly(stats: TradeStats, cap: float | None = None) -> float:
    """Half-Kelly position fraction from realised trade statistics.

    Full Kelly is ``f = W − (1 − W) / b`` where ``W`` is the win rate and
    ``b = avg_win / avg_loss`` the payoff ratio. We return ``0.5 · max(f, 0)``
    — the half-Kelly discount (standard for imprecise probability estimates)
    and no shorting (a negative edge sizes to zero). Optionally capped.

    Degenerate inputs — no trades, no wins, or no losses (payoff undefined) —
    return ``0.0``.
    """
    if stats.count == 0 or stats.avg_win <= 0.0 or stats.avg_loss <= 0.0:
        return 0.0

    payoff = stats.avg_win / stats.avg_loss
    full = stats.win_rate - (1.0 - stats.win_rate) / payoff
    kelly = 0.5 * max(full, 0.0)
    if cap is not None:
        kelly = min(kelly, cap)
    return round(kelly, 6)
