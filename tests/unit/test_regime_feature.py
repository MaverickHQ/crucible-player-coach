from __future__ import annotations

import numpy as np

from player_coach.market.enricher import WorldStateEnricher
from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.regime_feature import RegimeFeature
from player_coach.market.world_state import WorldState


def _fill_buffer(n: int, seed: int = 0) -> OHLCVBuffer:
    """Build a buffer of n bars from a two-volatility-regime price path."""
    rng = np.random.default_rng(seed)
    half = n // 2
    rets = np.concatenate([
        rng.normal(0.0, 0.005, size=half),
        rng.normal(0.0, 0.04, size=n - half),
    ])
    buf = OHLCVBuffer()
    price = 100.0
    for r in rets:
        price *= float(np.exp(r))
        buf.append(open=price, high=price * 1.01, low=price * 0.99,
                   close=price, volume=1_000)
    return buf


def _ws() -> WorldState:
    return WorldState(symbol="AMZN", price=100.0, sma5=99.0, sma10=98.0, volume=1_000)


# ------------------------------------------------------------- produces fields

def test_compute_returns_regime_fields():
    out = RegimeFeature().compute(_fill_buffer(120))
    assert out["regime_label"] in {"low_vol", "high_vol"}
    assert 0.0 <= out["regime_probability"] <= 1.0


def test_feature_name_is_regime():
    assert RegimeFeature().name == "regime"


# ------------------------------------------------------- graceful degradation

def test_insufficient_data_returns_unknown():
    # 20 bars → 19 returns → below the 30-observation minimum.
    out = RegimeFeature().compute(_fill_buffer(20))
    assert out["regime_label"] == "unknown"
    assert out["regime_probability"] == 0.0


def test_min_obs_boundary():
    # 30 returns is the minimum that fits; 29 degrades to unknown.
    assert RegimeFeature().compute(_fill_buffer(31))["regime_label"] != "unknown"
    assert RegimeFeature().compute(_fill_buffer(30))["regime_label"] == "unknown"


def test_empty_buffer_returns_unknown():
    out = RegimeFeature().compute(OHLCVBuffer())
    assert out["regime_label"] == "unknown"


# ------------------------------------------------------------ enricher wiring

def test_enricher_writes_regime_onto_world_state():
    ws = WorldStateEnricher([RegimeFeature()]).enrich(_ws(), _fill_buffer(120))
    assert ws.regime_label in {"low_vol", "high_vol"}
    assert ws.to_dict()["regime_label"] == ws.regime_label


def test_enricher_unknown_when_buffer_too_short():
    ws = WorldStateEnricher([RegimeFeature()]).enrich(_ws(), _fill_buffer(20))
    assert ws.regime_label == "unknown"
    assert ws.regime_probability == 0.0
