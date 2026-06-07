from __future__ import annotations

import logging
from typing import Any

import numpy as np

from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.volatility_model import VolatilityModel

logger = logging.getLogger(__name__)


class GARCHFeature:
    """Market feature (F7) that writes ``garch_vol`` — tomorrow's conditional
    volatility forecast — onto the world state.

    Fits GARCH(1,1) on the last ``lookback`` daily log returns. Degrades to
    ``None`` (no forecast) — never raises — when there are fewer than
    ``min_obs`` returns or the optimiser fails, so the exchange proceeds with no
    vol scaling rather than aborting.
    """

    name = "garch"

    def __init__(
        self,
        model: VolatilityModel | None = None,
        lookback: int = 250,
        min_obs: int = 30,
        refit_every: int = 20,
    ) -> None:
        self._model = model or VolatilityModel(min_obs=min_obs)
        self._lookback = lookback
        self._min_obs = min_obs
        self._refit_every = max(1, refit_every)
        self._fitted = False
        self._since_fit = 0

    def reset(self) -> None:
        """Clear cadence state and the underlying model's cached fit (call
        between backtest runs)."""
        self._fitted = False
        self._since_fit = 0
        model_reset = getattr(self._model, "reset", None)
        if callable(model_reset):
            model_reset()

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        returns = buffer.log_returns()
        if len(returns) < self._min_obs:
            logger.warning(
                "GARCHFeature: %d returns < %d minimum; garch_vol=None",
                len(returns), self._min_obs,
            )
            return {"garch_vol": None}

        window = returns[-self._lookback:]
        try:
            # Re-estimate params only on cadence; forecast daily on the current
            # window using cached params (cheap GARCH filter, no optimisation).
            if not self._fitted:
                self._model.fit(window)
                self._fitted = True
                self._since_fit = 0
            else:
                self._since_fit += 1
                if self._since_fit >= self._refit_every:
                    self._model.fit(window)
                    self._since_fit = 0
            vol = self._model.forecast_vol_on(window)
        except Exception:
            logger.warning("GARCHFeature: fit failed; garch_vol=None", exc_info=True)
            return {"garch_vol": None}

        if vol is None or not np.isfinite(vol):
            logger.warning("GARCHFeature: non-finite forecast; garch_vol=None")
            return {"garch_vol": None}

        return {"garch_vol": round(float(vol), 8)}
