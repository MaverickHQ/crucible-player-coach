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
    "max_daily_loss_pct": 0.02,
    "consistency_rule_pct": 0.50,
    "trading_cutoff_time": "16:20",
    "min_stop_atr_multiple": 1.5,
    "prefer_entry_below_vwap": True,
    "trailing_max_drawdown_pct": 0.10,
    "consistency_warn_pct": 0.40,
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
        "max_daily_loss_pct",
        "consistency_rule_pct",
        "trading_cutoff_time",
        "min_stop_atr_multiple",
        "prefer_entry_below_vwap",
        "trailing_max_drawdown_pct",
        "consistency_warn_pct",
    }
    assert keys == expected


def test_max_rounds_defaults_to_3():
    without_rounds = {k: v for k, v in BASE.items() if k != "max_rounds"}
    schema = ConstraintSchema.from_dict(without_rounds)
    assert schema.max_rounds == 3


def test_min_stop_atr_multiple_defaults_to_1_5():
    # Old preset JSON without the F8 key must still load with the default.
    without = {k: v for k, v in BASE.items() if k != "min_stop_atr_multiple"}
    schema = ConstraintSchema.from_dict(without)
    assert schema.min_stop_atr_multiple == 1.5


def test_prefer_entry_below_vwap_defaults_true():
    # Old preset JSON without the F9 key must still load with the default.
    without = {k: v for k, v in BASE.items() if k != "prefer_entry_below_vwap"}
    schema = ConstraintSchema.from_dict(without)
    assert schema.prefer_entry_below_vwap is True


# ---------------------------------------------------------------- N10


def test_to_json_caches_across_calls():
    # N10 — within a single resolved-schema instance, to_json runs once.
    # Resolver returns a fresh schema per bar, so the cache is naturally
    # bar-scoped and across-round.
    schema = ConstraintSchema.from_dict(BASE)
    j1 = schema.to_json()
    j2 = schema.to_json()
    assert j1 is j2  # same string object, not just equal — cache hit


def test_to_json_returns_to_dict_serialised():
    schema = ConstraintSchema.from_dict(BASE)
    import json as _json
    assert _json.loads(schema.to_json()) == schema.to_dict()


def test_to_json_distinct_instances_distinct_caches():
    # Two separate schema instances each compute their own JSON the first
    # time — the cache is per-instance, not module-level.
    s1 = ConstraintSchema.from_dict(BASE)
    s2 = ConstraintSchema.from_dict({**BASE, "max_position_pct": 0.20})
    assert s1.to_json() != s2.to_json()
