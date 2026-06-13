from __future__ import annotations

from player_coach.backtest.regime_decomposition import decompose_by_regime


def _ex(regime: str | None, outcome: str) -> dict:
    ws = {} if regime is None else {"regime_label": regime}
    return {"world_state": ws, "outcome": outcome}


def test_groups_by_regime_with_approve_rate():
    exchanges = [
        _ex("low_vol", "APPROVE"),
        _ex("low_vol", "REJECT-MAX"),
        _ex("high_vol", "APPROVE"),
    ]
    d = decompose_by_regime(exchanges)
    assert d["low_vol"]["count"] == 2
    assert d["low_vol"]["approve_rate"] == 0.5
    assert d["high_vol"]["count"] == 1
    assert d["high_vol"]["approve_rate"] == 1.0


def test_missing_regime_label_is_unknown():
    d = decompose_by_regime([_ex(None, "APPROVE")])
    assert d["unknown"]["count"] == 1


def test_empty_exchanges_yield_empty_decomposition():
    assert decompose_by_regime([]) == {}
