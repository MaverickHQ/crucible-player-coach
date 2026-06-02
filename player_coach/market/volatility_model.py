from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np

from player_coach.market.returns import validate_returns

logger = logging.getLogger(__name__)


class VolatilityModel:
    """GARCH(1,1) one-day-ahead conditional volatility forecast.

    Wraps ``arch.arch_model``. Returns are rescaled by ``rescale`` (×100 by
    default) before fitting — the optimiser is numerically happier on
    percentage-scale data — and the forecast is unscaled back to log-return
    units. MLE estimation is deterministic given the data, so no random restarts
    are needed (unlike the HMM).
    """

    def __init__(self, min_obs: int = 30, rescale: float = 100.0) -> None:
        self.min_obs = min_obs
        self.rescale = rescale
        self._result: Any | None = None

    def fit(self, returns: np.ndarray) -> VolatilityModel:
        from arch import arch_model

        validate_returns(returns, min_obs=self.min_obs)
        scaled = np.asarray(returns, dtype=float).ravel() * self.rescale
        model = arch_model(
            scaled, vol="GARCH", p=1, q=1, mean="Constant", dist="normal"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._result = model.fit(disp="off")
        return self

    def forecast_vol(self) -> float:
        """Next-day conditional volatility, in the input return's units."""
        if self._result is None:
            raise RuntimeError("call fit() before forecast_vol()")
        forecast = self._result.forecast(horizon=1, reindex=False)
        variance_scaled = float(forecast.variance.values[-1, 0])
        return float(np.sqrt(variance_scaled)) / self.rescale

    def fit_forecast(self, returns: np.ndarray) -> float:
        """Convenience: fit then forecast on the same series."""
        return self.fit(returns).forecast_vol()
