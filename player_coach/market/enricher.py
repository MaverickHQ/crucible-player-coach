from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.world_state import WorldState

logger = logging.getLogger(__name__)


@runtime_checkable
class MarketFeature(Protocol):
    """A market-feature computation that contributes fields to the world state.

    Each Phase 3A feature (F6 regime, F7 garch, F8 atr, F9 vwap, F10 kelly)
    implements this and registers with the enricher. ``compute`` returns a dict
    of ``{world_state_field: value}`` to write. The field must already exist on
    ``WorldState`` (the feature adds it in the same change).
    """

    name: str

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        ...


class WorldStateEnricher:
    """Runs registered market features and writes their output onto a WorldState.

    Seam 4 ships this scaffold with *no* features — it returns the world state
    unchanged. Features are added one per Phase 3A feature. A feature that raises
    is logged and skipped so a single model failure degrades gracefully rather
    than aborting the exchange (taxonomy: graceful degradation).
    """

    def __init__(self, features: list[MarketFeature] | None = None) -> None:
        self._features: list[MarketFeature] = list(features or [])

    def reset(self) -> None:
        """Reset any stateful features (cached fits, smoothing) — call between
        backtest runs so state does not leak across them. Features without a
        ``reset`` are skipped."""
        for feature in self._features:
            reset = getattr(feature, "reset", None)
            if callable(reset):
                reset()

    def enrich(self, world_state: WorldState, buffer: OHLCVBuffer) -> WorldState:
        for feature in self._features:
            name = getattr(feature, "name", repr(feature))
            try:
                updates = feature.compute(buffer)
            except Exception:
                logger.warning(
                    "market feature %r failed; skipping", name, exc_info=True
                )
                continue
            for key, value in (updates or {}).items():
                setattr(world_state, key, value)
        return world_state
