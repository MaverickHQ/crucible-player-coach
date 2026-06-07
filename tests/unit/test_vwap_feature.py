from __future__ import annotations

from player_coach.market.enricher import WorldStateEnricher
from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.vwap import VWAPFeature
from player_coach.market.world_state import WorldState


def _buffer(bars: list[tuple[float, float]]) -> OHLCVBuffer:
    """bars = [(close, volume), ...]; high/low straddle close by ±1."""
    buf = OHLCVBuffer()
    for close, volume in bars:
        buf.append(open=close, high=close + 1.0, low=close - 1.0,
                   close=close, volume=volume)
    return buf


def _ws() -> WorldState:
    return WorldState(symbol="AMZN", price=100.0, sma5=99.0, sma10=98.0, volume=1_000)


def test_compute_returns_vwap_and_price_vs_vwap():
    out = VWAPFeature().compute(_buffer([(100.0, 1_000), (102.0, 1_000)]))
    assert out["vwap"] is not None
    assert out["price_vs_vwap"] is not None


def test_feature_name_is_vwap():
    assert VWAPFeature().name == "vwap"


def test_empty_buffer_returns_none():
    out = VWAPFeature().compute(OHLCVBuffer())
    assert out["vwap"] is None
    assert out["price_vs_vwap"] is None


def test_price_below_vwap_is_negative():
    # Heavy volume at 12, then a light bar closing at 10 → last price below VWAP.
    out = VWAPFeature().compute(_buffer([(12.0, 1_000), (10.0, 1)]))
    assert out["price_vs_vwap"] < 0.0


def test_price_above_vwap_is_positive():
    out = VWAPFeature().compute(_buffer([(10.0, 1_000), (12.0, 1)]))
    assert out["price_vs_vwap"] > 0.0


def test_enricher_writes_vwap_onto_world_state():
    ws = WorldStateEnricher([VWAPFeature()]).enrich(
        _ws(), _buffer([(100.0, 1_000), (101.0, 1_000)])
    )
    assert ws.vwap is not None
    assert ws.to_dict()["vwap"] == ws.vwap
    assert ws.to_dict()["price_vs_vwap"] == ws.price_vs_vwap


def test_world_state_vwap_defaults_none():
    ws = _ws()
    assert ws.vwap is None
    assert ws.price_vs_vwap is None
    assert ws.to_dict()["vwap"] is None
