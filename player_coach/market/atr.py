from __future__ import annotations

import logging
from typing import Any

import numpy as np

from player_coach.market.ohlcv import OHLCVBuffer

logger = logging.getLogger(__name__)


def compute_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> float:
    """Wilder's Average True Range over the most recent ``period`` bars.

    True range for bar ``t`` is
    ``max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)``. The first ATR seeds
    from the simple mean of the first ``period`` true ranges, then applies
    Wilder smoothing ``ATR_t = (ATR_{t-1}·(period-1) + TR_t) / period``.

    Requires at least ``period + 1`` bars (``period`` true ranges need a prior
    close); raises ``ValueError`` otherwise.
    """
    h = np.asarray(highs, dtype=float).ravel()
    low_arr = np.asarray(lows, dtype=float).ravel()
    c = np.asarray(closes, dtype=float).ravel()

    n = c.size
    if n < period + 1:
        raise ValueError(
            f"ATR needs >= {period + 1} bars, got {n}"
        )

    prev_close = c[:-1]
    true_range = np.maximum.reduce([
        h[1:] - low_arr[1:],
        np.abs(h[1:] - prev_close),
        np.abs(low_arr[1:] - prev_close),
    ])

    atr = float(np.mean(true_range[:period]))
    for tr in true_range[period:]:
        atr = (atr * (period - 1) + float(tr)) / period
    return atr


class ATRFeature:
    """Market feature (F8) that writes ``atr`` — the 14-day Wilder ATR — onto the
    world state. Degrades to ``None`` (never raises) when there are fewer than
    ``period + 1`` bars or the result is non-finite."""

    name = "atr"

    def __init__(self, period: int = 14) -> None:
        self._period = period

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        if len(buffer) < self._period + 1:
            logger.warning(
                "ATRFeature: %d bars < %d minimum; atr=None",
                len(buffer), self._period + 1,
            )
            return {"atr": None}
        try:
            atr = compute_atr(
                buffer.highs, buffer.lows, buffer.closes, self._period
            )
        except Exception:
            logger.warning("ATRFeature: compute failed; atr=None", exc_info=True)
            return {"atr": None}

        if not np.isfinite(atr):
            return {"atr": None}
        return {"atr": round(float(atr), 6)}
