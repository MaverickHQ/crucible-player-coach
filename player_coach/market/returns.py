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


def compute_log_returns(prices: Any) -> np.ndarray:
    """Daily log returns ``ln(p_t / p_{t-1})`` for a price series.

    Returns an array of length ``len(prices) - 1`` (empty for 0 or 1 prices).
    Non-finite results — produced by NaN, zero, or negative prices — are
    replaced with ``0.0`` and a warning is logged, so a bad bar degrades to a
    flat return rather than propagating ``nan``/``inf`` into a downstream model.
    """
    arr = _to_float_array(prices)
    if arr.size < 2:
        return np.empty(0, dtype=float)

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
