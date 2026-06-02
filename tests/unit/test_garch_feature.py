from __future__ import annotations

import numpy as np

from player_coach.market.enricher import WorldStateEnricher
from player_coach.market.garch_feature import GARCHFeature
from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.world_state import WorldState


def _fill_buffer(n: int, seed: int = 0) -> OHLCVBuffer:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.01, size=n)
    buf = OHLCVBuffer()
    price = 100.0
    for r in rets:
        price *= float(np.exp(r))
        buf.append(open=price, high=price * 1.01, low=price * 0.99,
                   close=price, volume=1_000)
    return buf


def _ws() -> WorldState:
    return WorldState(symbol="AMZN", price=100.0, sma5=99.0, sma10=98.0, volume=1_000)


# --------------------------------------------------------------- produces value

def test_compute_returns_positive_garch_vol():
    out = GARCHFeature().compute(_fill_buffer(160))
    assert out["garch_vol"] is not None
    assert out["garch_vol"] > 0.0


def test_feature_name_is_garch():
    assert GARCHFeature().name == "garch"


# ------------------------------------------------------- graceful degradation

def test_insufficient_data_returns_none():
    assert GARCHFeature().compute(_fill_buffer(20))["garch_vol"] is None


def test_empty_buffer_returns_none():
    assert GARCHFeature().compute(OHLCVBuffer())["garch_vol"] is None


# ------------------------------------------------------------ enricher wiring

def test_enricher_writes_garch_vol_onto_world_state():
    ws = WorldStateEnricher([GARCHFeature()]).enrich(_ws(), _fill_buffer(160))
    assert ws.garch_vol is not None
    assert ws.to_dict()["garch_vol"] == ws.garch_vol


def test_world_state_garch_vol_defaults_none():
    assert _ws().garch_vol is None
    assert _ws().to_dict()["garch_vol"] is None
