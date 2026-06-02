from __future__ import annotations

import logging
from typing import Any

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
    ) -> None:
        self._model = model or VolatilityModel(min_obs=min_obs)
        self._lookback = lookback
        self._min_obs = min_obs

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
            vol = self._model.fit_forecast(window)
        except Exception:
            logger.warning("GARCHFeature: fit failed; garch_vol=None", exc_info=True)
            return {"garch_vol": None}

        return {"garch_vol": round(float(vol), 8)}
