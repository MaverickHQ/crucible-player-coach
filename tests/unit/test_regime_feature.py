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


# ----------------------------------------------------- refit cadence (#3)

class _CountingDetector:
    def __init__(self) -> None:
        self.fit_calls = 0
        self.predict_calls = 0

    def fit(self, returns):
        self.fit_calls += 1
        return self

    def predict(self, returns):
        self.predict_calls += 1
        return ("high_vol", 0.9)

    def confirm_regime(self, label):
        return label

    def reset(self):
        self.fit_calls = 0
        self.predict_calls = 0


def test_refits_on_cadence_not_every_call():
    det = _CountingDetector()
    feature = RegimeFeature(detector=det, refit_every=20)
    buf = _fill_buffer(120)
    for _ in range(25):
        feature.compute(buf)
    assert det.fit_calls == 2      # refit at call 1 and call 22, not all 25
    assert det.predict_calls == 25  # predicted every day on the cached model


def test_insufficient_data_does_not_fit():
    det = _CountingDetector()
    RegimeFeature(detector=det).compute(_fill_buffer(20))
    assert det.fit_calls == 0


# ----------------------------------------------- persistence wiring (#2)

class _SmoothingSpyDetector:
    """Smooths by tagging — proves the feature routes labels through it."""

    def fit(self, returns):
        return self

    def predict(self, returns):
        return ("high_vol", 0.9)

    def confirm_regime(self, label):
        return "smoothed_" + label

    def reset(self):
        pass


def test_compute_applies_persistence_smoothing():
    out = RegimeFeature(detector=_SmoothingSpyDetector()).compute(_fill_buffer(120))
    assert out["regime_label"] == "smoothed_high_vol"


def test_smoothing_keeps_raw_probability():
    out = RegimeFeature(detector=_SmoothingSpyDetector()).compute(_fill_buffer(120))
    assert out["regime_probability"] == 0.9
