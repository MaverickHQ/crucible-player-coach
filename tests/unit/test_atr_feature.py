from __future__ import annotations

import numpy as np

from player_coach.market.atr import ATRFeature
from player_coach.market.enricher import WorldStateEnricher
from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.world_state import WorldState


def _fill_buffer(n: int, seed: int = 0) -> OHLCVBuffer:
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    buf = OHLCVBuffer()
    for c in closes:
        buf.append(open=float(c), high=float(c) + 1.0, low=float(c) - 1.0,
                   close=float(c), volume=1_000)
    return buf


def _ws() -> WorldState:
    return WorldState(symbol="AMZN", price=100.0, sma5=99.0, sma10=98.0, volume=1_000)


def test_compute_returns_positive_atr():
    out = ATRFeature().compute(_fill_buffer(40))
    assert out["atr"] is not None
    assert out["atr"] > 0.0


def test_feature_name_is_atr():
    assert ATRFeature().name == "atr"


def test_insufficient_bars_returns_none():
    # period 14 needs 15 bars; 10 is too few.
    assert ATRFeature().compute(_fill_buffer(10))["atr"] is None


def test_empty_buffer_returns_none():
    assert ATRFeature().compute(OHLCVBuffer())["atr"] is None


def test_enricher_writes_atr_onto_world_state():
    ws = WorldStateEnricher([ATRFeature()]).enrich(_ws(), _fill_buffer(40))
    assert ws.atr is not None
    assert ws.to_dict()["atr"] == ws.atr


def test_world_state_atr_defaults_none():
    assert _ws().atr is None
    assert _ws().to_dict()["atr"] is None
