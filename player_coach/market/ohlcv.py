from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from player_coach.market.returns import compute_log_returns


@dataclass(frozen=True)
class OHLCVBar:
    """A single daily bar. ``open`` shadows the builtin intentionally — it is the
    domain name for the bar's opening price."""

    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVBuffer:
    """Rolling buffer of OHLCV bars feeding the market-feature pipeline.

    Replaces the runner's close-only ``close_prices`` list so that ATR (F8,
    needs high/low/close) and VWAP (F9, needs typical price × volume) have the
    full bar, not just closes. Column accessors return aligned float arrays in
    insertion order; callers slice the tail they need (e.g. ``closes[-60:]``).

    ``maxlen`` optionally bounds the window (oldest bars are evicted).
    """

    def __init__(self, maxlen: int | None = None) -> None:
        self._bars: deque[OHLCVBar] = deque(maxlen=maxlen)

    def append(
        self,
        *,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        self._bars.append(OHLCVBar(open, high, low, close, volume))

    def __len__(self) -> int:
        return len(self._bars)

    def _column(self, attr: str) -> np.ndarray:
        return np.array([getattr(b, attr) for b in self._bars], dtype=float)

    @property
    def opens(self) -> np.ndarray:
        return self._column("open")

    @property
    def highs(self) -> np.ndarray:
        return self._column("high")

    @property
    def lows(self) -> np.ndarray:
        return self._column("low")

    @property
    def closes(self) -> np.ndarray:
        return self._column("close")

    @property
    def volumes(self) -> np.ndarray:
        return self._column("volume")

    def log_returns(self) -> np.ndarray:
        """Log returns of the close series (empty if fewer than 2 bars)."""
        return compute_log_returns(self.closes)
