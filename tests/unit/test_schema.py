from __future__ import annotations
import pytest
from player_coach.constraints.schema import ConstraintSchema

BASE = {
    "max_position_pct": 0.15,
    "max_single_trade_pct": 0.05,
    "max_leverage": 1.5,
    "max_drawdown_pct": 0.10,
    "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
    "max_open_positions": 3,
    "min_risk_reward": 1.5,
    "max_rounds": 3,
    "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
}


def test_from_dict_round_trips():
    schema = ConstraintSchema.from_dict(BASE)
    result = schema.to_dict()
    assert result == BASE


def test_to_dict_expected_keys():
    schema = ConstraintSchema.from_dict(BASE)
    keys = set(schema.to_dict().keys())
    expected = {
        "max_position_pct",
        "max_single_trade_pct",
        "max_leverage",
        "max_drawdown_pct",
        "allowed_symbols",
        "max_open_positions",
        "min_risk_reward",
        "max_rounds",
        "abort_on_violations",
    }
    assert keys == expected


def test_max_rounds_defaults_to_3():
    without_rounds = {k: v for k, v in BASE.items() if k != "max_rounds"}
    schema = ConstraintSchema.from_dict(without_rounds)
    assert schema.max_rounds == 3
