from __future__ import annotations

from player_coach.market.world_state import WorldState


def _make_world_state(**overrides) -> WorldState:
    base = dict(
        symbol="AMZN",
        price=185.0,
        sma5=183.0,
        sma10=180.0,
        volume=45_000_000,
    )
    base.update(overrides)
    return WorldState(**base)


# --------------------------------------------------------------- canonical shape

def test_to_dict_has_canonical_market_keys():
    ws = _make_world_state()
    d = ws.to_dict()
    for key in ("symbol", "price", "sma5", "sma10", "volume",
                "regime_label", "session"):
        assert key in d, f"missing canonical key: {key}"


def test_runner_shape_has_no_position_key():
    # The backtest runner builds no "position"; F6/F7 added regime + garch.
    ws = _make_world_state(regime_label="high_vol", session="NY_open")
    assert set(ws.to_dict()) == {
        "symbol", "price", "sma5", "sma10", "volume",
        "regime_label", "regime_probability", "garch_vol", "atr", "session",
    }


def test_matches_demo_shape_with_position():
    # The demo/dashboard dict additionally carries a "position" hint.
    ws = _make_world_state(position="flat")
    assert ws.to_dict() == {
        "symbol": "AMZN",
        "price": 185.0,
        "sma5": 183.0,
        "sma10": 180.0,
        "volume": 45_000_000,
        "position": "flat",
        "regime_label": "unknown",
        "regime_probability": 0.0,
        "garch_vol": None,
        "atr": None,
        "session": "NY_open",
    }


def test_regime_fields_default_to_unknown():
    ws = _make_world_state()
    assert ws.regime_label == "unknown"
    assert ws.regime_probability == 0.0


def test_position_omitted_when_none():
    # Runner builds no position; its serialized shape must not gain a key.
    assert "position" not in _make_world_state().to_dict()


# --------------------------------------------------------------------- defaults

def test_defaults_applied_for_optional_fields():
    ws = _make_world_state()
    assert ws.session == "NY_open"
    assert ws.regime_label == "unknown"
    assert ws.position is None


# ------------------------------------------------------------------ round-trip

def test_to_dict_from_dict_round_trips():
    ws = _make_world_state(position="flat", regime_label="low_vol")
    assert WorldState.from_dict(ws.to_dict()) == ws


def test_from_dict_ignores_unknown_keys():
    # The coach loop merges portfolio fields into the prompt dict; from_dict
    # must tolerate keys it does not model rather than raising.
    d = _make_world_state().to_dict()
    d.update({"capital": 100_000, "open_positions": [], "daily_pnl": 0.0})
    ws = WorldState.from_dict(d)
    assert ws.symbol == "AMZN"


def test_from_dict_applies_defaults_for_missing_optionals():
    ws = WorldState.from_dict({
        "symbol": "MSFT", "price": 400.0, "sma5": 398.0,
        "sma10": 395.0, "volume": 20_000_000,
    })
    assert ws.session == "NY_open"
    assert ws.regime_label == "unknown"


# --------------------------------------------------------- purity / non-mutation

def test_to_dict_returns_fresh_dict():
    ws = _make_world_state()
    d = ws.to_dict()
    d["price"] = 999.0
    assert ws.price == 185.0  # mutating the dict must not touch the model


# ---------------------------------------------------------------- F7 cleanup

def test_volatility_regime_fully_removed():
    # Deprecated in F6, removed in F7: the heuristic field is gone from the
    # model and the serialized shape, leaving regime_label as the sole signal.
    ws = _make_world_state()
    assert not hasattr(ws, "volatility_regime")
    assert "volatility_regime" not in ws.to_dict()
