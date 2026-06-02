from __future__ import annotations

from typing import Any

from player_coach.market.enricher import WorldStateEnricher
from player_coach.market.ohlcv import OHLCVBuffer
from player_coach.market.world_state import WorldState


def _ws() -> WorldState:
    return WorldState(symbol="AMZN", price=100.0, sma5=99.0, sma10=98.0, volume=1_000)


class _FixedFeature:
    """Test double: writes a fixed field set onto the world state."""

    def __init__(self, name: str, updates: dict[str, Any]) -> None:
        self.name = name
        self._updates = updates

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        return self._updates


class _BoomFeature:
    name = "boom"

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        raise RuntimeError("model blew up")


# ------------------------------------------------------------- empty scaffold

def test_empty_enricher_returns_world_state_unchanged():
    ws = _ws()
    out = WorldStateEnricher([]).enrich(ws, OHLCVBuffer())
    assert out.to_dict() == ws.to_dict()


# ------------------------------------------------------------- writes results

def test_feature_output_written_onto_world_state():
    feature = _FixedFeature("fake", {"regime_label": "high_vol"})
    out = WorldStateEnricher([feature]).enrich(_ws(), OHLCVBuffer())
    assert out.regime_label == "high_vol"


def test_multiple_features_all_applied():
    a = _FixedFeature("a", {"session": "LDN_open"})
    b = _FixedFeature("b", {"regime_label": "low_vol"})
    out = WorldStateEnricher([a, b]).enrich(_ws(), OHLCVBuffer())
    assert out.session == "LDN_open"
    assert out.regime_label == "low_vol"


# --------------------------------------------------------- graceful degradation

def test_failing_feature_is_skipped_not_raised():
    out = WorldStateEnricher([_BoomFeature()]).enrich(_ws(), OHLCVBuffer())
    assert out.regime_label == "unknown"  # untouched default, no exception


def test_failing_feature_does_not_block_later_features():
    a = _BoomFeature()
    b = _FixedFeature("b", {"session": "LDN_open"})
    out = WorldStateEnricher([a, b]).enrich(_ws(), OHLCVBuffer())
    assert out.session == "LDN_open"


# ----------------------------------------------------------------- reset (#7)

class _ResettableFeature:
    name = "resettable"

    def __init__(self) -> None:
        self.reset_called = False

    def compute(self, buffer: OHLCVBuffer) -> dict[str, Any]:
        return {}

    def reset(self) -> None:
        self.reset_called = True


def test_enricher_reset_calls_feature_reset():
    feature = _ResettableFeature()
    WorldStateEnricher([feature]).reset()
    assert feature.reset_called


def test_enricher_reset_tolerates_feature_without_reset():
    class _NoReset:
        name = "noreset"

        def compute(self, buffer):
            return {}

    WorldStateEnricher([_NoReset()]).reset()  # must not raise
