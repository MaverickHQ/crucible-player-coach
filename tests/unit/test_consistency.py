from __future__ import annotations

from player_coach.constraints.schema import ConstraintSchema


def _s(**over) -> ConstraintSchema:
    base = dict(
        max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
        max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
        min_risk_reward=1.5, abort_on_violations=["max_leverage"],
        consistency_rule_pct=0.50, consistency_warn_pct=0.40,
    )
    base.update(over)
    return ConstraintSchema(**base)


def test_ok_below_warn():
    assert _s().consistency_status(300.0, 1000.0) == "ok"      # 30%


def test_approaching_at_warn_boundary():
    assert _s().consistency_status(400.0, 1000.0) == "approaching"  # 40%


def test_approaching_between_warn_and_limit():
    assert _s().consistency_status(450.0, 1000.0) == "approaching"  # 45%


def test_at_limit_boundary_is_approaching_not_breached():
    # Exactly 50% is allowed (rule is strict >), but still in the warn zone.
    assert _s().consistency_status(500.0, 1000.0) == "approaching"


def test_breached_above_limit():
    assert _s().consistency_status(600.0, 1000.0) == "breached"  # 60%


def test_ok_when_total_non_positive():
    assert _s().consistency_status(500.0, 0.0) == "ok"
    assert _s().consistency_status(500.0, -100.0) == "ok"


def test_ok_when_day_non_positive():
    assert _s().consistency_status(0.0, 1000.0) == "ok"
    assert _s().consistency_status(-100.0, 1000.0) == "ok"


def test_warn_pct_defaults_to_0_4():
    schema = ConstraintSchema.from_dict({
        "max_position_pct": 0.15, "max_single_trade_pct": 0.05,
        "max_leverage": 1.5, "max_drawdown_pct": 0.10,
        "allowed_symbols": ["AMZN"], "max_open_positions": 3,
        "min_risk_reward": 1.5, "abort_on_violations": [],
    })
    assert schema.consistency_warn_pct == 0.40
