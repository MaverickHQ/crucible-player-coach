from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TradeStats:
    """Realised-trade summary. ``avg_win`` / ``avg_loss`` are positive
    magnitudes (mean of the winning returns and of the losing returns)."""

    count: int
    win_rate: float
    avg_win: float
    avg_loss: float
    n_wins: int = 0
    n_losses: int = 0

    @property
    def decisive_win_rate(self) -> float:
        """Win rate among *decisive* (non-scratch) trades — wins / (wins+losses).

        This is the Bernoulli win probability Monte Carlo should use: scratch
        (zero-return) trades shouldn't deflate the modelled win odds. Falls back
        to ``win_rate`` when the win/loss counts are unavailable.
        """
        decisive = self.n_wins + self.n_losses
        return self.n_wins / decisive if decisive > 0 else self.win_rate


def trade_stats(returns: Sequence[float]) -> TradeStats:
    """Summarise a sequence of realised trade returns (fractions or P&L).

    A zero return counts toward ``count`` but is neither a win nor a loss.
    Shared by F10 (Kelly), F14 (Monte Carlo), F17 (Sharpe).
    """
    values = [float(r) for r in returns]
    n = len(values)
    if n == 0:
        return TradeStats(count=0, win_rate=0.0, avg_win=0.0, avg_loss=0.0)

    wins = [r for r in values if r > 0]
    losses = [-r for r in values if r < 0]
    return TradeStats(
        count=n,
        win_rate=len(wins) / n,
        avg_win=(sum(wins) / len(wins)) if wins else 0.0,
        avg_loss=(sum(losses) / len(losses)) if losses else 0.0,
        n_wins=len(wins),
        n_losses=len(losses),
    )
