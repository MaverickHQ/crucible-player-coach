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
        # Materialised columns / log returns, rebuilt lazily and invalidated on
        # append. Avoids an O(n) deque->array rebuild on every accessor call
        # (each feature reads several columns per bar — otherwise O(n^2) runs).
        self._cache: dict[str, np.ndarray] = {}

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
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._bars)

    def _column(self, attr: str) -> np.ndarray:
        cached = self._cache.get(attr)
        if cached is None:
            cached = np.array([getattr(b, attr) for b in self._bars], dtype=float)
            self._cache[attr] = cached
        return cached

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
        """Log returns of the close series (empty if fewer than 2 bars).

        Cached and shared across features (regime + garch both read it per bar).
        """
        cached = self._cache.get("_log_returns")
        if cached is None:
            cached = compute_log_returns(self.closes)
            self._cache["_log_returns"] = cached
        return cached
