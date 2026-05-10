import pytest
from player_coach.constraints.schema import ConstraintSchema


def _make_schema(**overrides) -> ConstraintSchema:
    defaults = dict(
        max_position_pct=0.15,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN", "MSFT"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage", "max_drawdown_pct"],
    )
    defaults.update(overrides)
    return ConstraintSchema(**defaults)


def test_is_daily_loss_breached_true_when_loss_exceeds_limit():
    schema = _make_schema(max_daily_loss_pct=0.02)
    # daily_pnl=-210 on a 10_000 balance = 2.1% loss, limit is 2%
    assert schema.is_daily_loss_breached(-210.0, 10_000.0) is True


def test_is_daily_loss_breached_false_when_within_limit():
    schema = _make_schema(max_daily_loss_pct=0.02)
    # daily_pnl=-200 on a 10_000 balance = exactly 2% — not exceeded
    assert schema.is_daily_loss_breached(-200.0, 10_000.0) is False


def test_is_daily_loss_breached_false_when_daily_starting_balance_zero():
    schema = _make_schema(max_daily_loss_pct=0.02)
    assert schema.is_daily_loss_breached(-500.0, 0.0) is False


def test_is_consistency_breached_true_when_day_exceeds_fraction():
    schema = _make_schema(consistency_rule_pct=0.50)
    # day_pnl=600 > 0.50 * 1_000 = 500
    assert schema.is_consistency_breached(600.0, 1_000.0) is True


def test_is_consistency_breached_false_when_within_fraction():
    schema = _make_schema(consistency_rule_pct=0.50)
    # day_pnl=500 == 0.50 * 1_000 — not strictly greater
    assert schema.is_consistency_breached(500.0, 1_000.0) is False


def test_is_consistency_breached_false_when_cumulative_pnl_zero():
    schema = _make_schema(consistency_rule_pct=0.50)
    assert schema.is_consistency_breached(999.0, 0.0) is False


def test_is_consistency_breached_false_when_cumulative_pnl_negative():
    schema = _make_schema(consistency_rule_pct=0.50)
    assert schema.is_consistency_breached(100.0, -500.0) is False


def test_from_dict_handles_new_fields_with_defaults():
    data = dict(
        max_position_pct=0.15,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=[],
        # new fields deliberately omitted
    )
    schema = ConstraintSchema.from_dict(data)
    assert schema.max_daily_loss_pct == 0.02
    assert schema.consistency_rule_pct == 0.50
    assert schema.trading_cutoff_time == "16:20"


def test_from_dict_accepts_explicit_new_fields():
    data = dict(
        max_position_pct=0.05,
        max_single_trade_pct=0.02,
        max_leverage=1.0,
        max_drawdown_pct=0.05,
        allowed_symbols=["AMZN"],
        max_open_positions=2,
        min_risk_reward=2.0,
        abort_on_violations=[],
        max_daily_loss_pct=0.01,
        consistency_rule_pct=0.40,
        trading_cutoff_time="15:55",
    )
    schema = ConstraintSchema.from_dict(data)
    assert schema.max_daily_loss_pct == 0.01
    assert schema.consistency_rule_pct == 0.40
    assert schema.trading_cutoff_time == "15:55"
