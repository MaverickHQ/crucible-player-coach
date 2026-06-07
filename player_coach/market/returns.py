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

    Bad bars (NaN, zero, negative) are forward-filled for price continuity, then
    the **artificial** return *into* a bad bar (a zero-variance flat) is dropped
    while the real move on resumption — computed against the last good price — is
    kept. Residual non-finite returns (e.g. a leading bad bar with no prior
    price) are also dropped. This keeps fake calm days out of the volatility
    models that consume these returns. For clean prices the result has the usual
    length ``len(prices) - 1``.
    """
    arr = _to_float_array(prices)
    if arr.size < 2:
        return np.empty(0, dtype=float)

    bad = ~np.isfinite(arr) | (arr <= 0.0)  # originally-bad bars
    filled = _forward_fill_prices(arr)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_returns = np.log(filled[1:] / filled[:-1])

    # Drop returns INTO a bad bar (artificial flats) and any residual non-finite.
    keep = ~bad[1:] & np.isfinite(log_returns)
    dropped = log_returns.size - int(keep.sum())
    if dropped:
        logger.warning(
            "compute_log_returns: dropped %d contaminated return(s) from bad bars",
            dropped,
        )
    return log_returns[keep]


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
