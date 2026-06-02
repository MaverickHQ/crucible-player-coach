from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _to_float_array(prices: Any) -> np.ndarray:
    """Coerce a list / numpy array / pandas Series to a 1-D float array."""
    if hasattr(prices, "to_numpy"):  # pandas Series / Index
        prices = prices.to_numpy()
    return np.asarray(prices, dtype=float).ravel()


def _forward_fill_prices(arr: np.ndarray) -> np.ndarray:
    """Carry the last valid (finite, positive) price over bad bars.

    A single bad bar then yields one flat (0.0) return on the gap day while the
    real move is preserved when good data resumes — instead of distorting the
    two returns that touch the bad bar. Leading bad bars (no prior valid price)
    are left as-is and handled by the non-finite guard in ``compute_log_returns``.
    """
    out = arr.copy()
    last_valid = np.nan
    for i in range(out.size):
        if np.isfinite(out[i]) and out[i] > 0:
            last_valid = out[i]
        elif np.isfinite(last_valid):
            out[i] = last_valid
    return out


def compute_log_returns(prices: Any) -> np.ndarray:
    """Daily log returns ``ln(p_t / p_{t-1})`` for a price series.

    Returns an array of length ``len(prices) - 1`` (empty for 0 or 1 prices).
    Bad bars (NaN, zero, negative) are forward-filled from the last valid price,
    so a gap produces a single flat return and preserves the real move on
    resumption. Any residual non-finite result (e.g. a leading bad bar) is
    replaced with ``0.0`` and a warning logged, so nothing leaks downstream.
    """
    arr = _to_float_array(prices)
    if arr.size < 2:
        return np.empty(0, dtype=float)

    arr = _forward_fill_prices(arr)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_returns = np.log(arr[1:] / arr[:-1])

    non_finite = ~np.isfinite(log_returns)
    if non_finite.any():
        logger.warning(
            "compute_log_returns: %d non-finite return(s) from bad prices "
            "replaced with 0.0",
            int(non_finite.sum()),
        )
        log_returns = np.where(non_finite, 0.0, log_returns)
    return log_returns


def validate_returns(returns: Any, min_obs: int = 30) -> None:
    """Raise ``ValueError`` if fewer than ``min_obs`` observations are present.

    The market models (HMM, GARCH) are unstable on short samples; callers that
    can degrade gracefully should catch this and fall back rather than fit.
    """
    n = len(returns)
    if n < min_obs:
        raise ValueError(
            f"insufficient observations: need >= {min_obs}, got {n}"
        )
