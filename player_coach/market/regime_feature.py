from __future__ import annotations

import logging
from typing import Any

from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)


class RegimeFeature:
    """Market feature (F6) that writes ``regime_label`` + ``regime_probability``.

    Fits the HMM on the last ``lookback`` daily log returns from the buffer and
    reports the regime of the most recent observation. Degrades to
    ``("unknown", 0.0)`` — never raises — when there are fewer than ``min_obs``
    returns (new symbol, data gap) or the model fails to converge, so the
    exchange continues with the conservative-fallback constraints.
    """

    name = "regime"

    def __init__(
        self,
        detector: RegimeDetector | None = None,
        lookback: int = 60,
        min_obs: int = 30,
    ) -> None:
        self._detector = detector or RegimeDetector()
        self._lookback = lookback
        self._min_obs = min_obs

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        returns = buffer.log_returns()
        if len(returns) < self._min_obs:
            logger.warning(
                "RegimeFeature: %d returns < %d minimum; regime=unknown",
                len(returns), self._min_obs,
            )
            return {"regime_label": "unknown", "regime_probability": 0.0}

        window = returns[-self._lookback:]
        try:
            label, probability = self._detector.fit_predict(window)
        except Exception:
            logger.warning("RegimeFeature: HMM fit failed; regime=unknown",
                           exc_info=True)
            return {"regime_label": "unknown", "regime_probability": 0.0}

        return {"regime_label": label, "regime_probability": round(probability, 6)}
