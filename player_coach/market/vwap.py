from __future__ import annotations

import logging
from typing import Any

import numpy as np

from player_coach.market.ohlcv import OHLCVBuffer

logger = logging.getLogger(__name__)


def compute_vwap(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int | None = 20,
) -> float:
    """Rolling volume-weighted average price over the last ``lookback`` bars.

    Uses the typical price ``(H + L + C) / 3`` weighted by volume:
    ``Σ(typical · vol) / Σ(vol)``. ``lookback=None`` uses the whole series.
    Raises ``ValueError`` when total volume is zero (VWAP undefined).
    """
    h = np.asarray(highs, dtype=float).ravel()
    low_arr = np.asarray(lows, dtype=float).ravel()
    c = np.asarray(closes, dtype=float).ravel()
    v = np.asarray(volumes, dtype=float).ravel()

    if lookback is not None:
        h, low_arr, c, v = h[-lookback:], low_arr[-lookback:], c[-lookback:], v[-lookback:]

    total_volume = float(v.sum())
    if total_volume <= 0.0:
        raise ValueError("VWAP undefined: total volume is zero")

    typical = (h + low_arr + c) / 3.0
    return float((typical * v).sum() / total_volume)


class VWAPFeature:
    """Market feature (F9) writing ``vwap`` and the signed ``price_vs_vwap``
    deviation ``(price - vwap) / vwap`` (negative = current price below VWAP).
    Degrades both to ``None`` (never raises) on an empty buffer, zero volume, or
    a non-finite result."""

    name = "vwap"

    def __init__(self, lookback: int = 20) -> None:
        self._lookback = lookback

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        none_result = {"vwap": None, "price_vs_vwap": None}
        if len(buffer) < 1:
            return none_result
        try:
            vwap = compute_vwap(
                buffer.highs, buffer.lows, buffer.closes, buffer.volumes,
                self._lookback,
            )
        except Exception:
            logger.warning("VWAPFeature: compute failed; vwap=None", exc_info=True)
            return none_result

        if not np.isfinite(vwap) or vwap == 0.0:
            return none_result

        price = float(buffer.closes[-1])
        return {
            "vwap": round(vwap, 6),
            "price_vs_vwap": round((price - vwap) / vwap, 6),
        }
