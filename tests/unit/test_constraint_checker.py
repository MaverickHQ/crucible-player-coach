from __future__ import annotations

from player_coach.constraints.checker import check_constraints
from player_coach.constraints.schema import ConstraintSchema


def _c(**over) -> ConstraintSchema:
    base = dict(
        max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
        max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
        min_risk_reward=1.5, abort_on_violations=["max_leverage"],
        min_stop_atr_multiple=1.5,
    )
    base.update(over)
    return ConstraintSchema(**base)


def _entry(**over) -> dict:
    a = dict(action_type="enter_long", symbol="AMZN", size_pct=0.05,
             entry_price=185.0, stop_loss=183.0, take_profit=190.0)
    a.update(over)
    return a


def _prop(*actions) -> dict:
    return {"actions": list(actions), "reasoning": ""}


# ------------------------------------------------------------------ clean

def test_valid_entry_no_violations():
    assert check_constraints(_prop(_entry()), _c(), {}) == []


def test_hold_has_no_violations():
    assert check_constraints(_prop({"action_type": "hold"}), _c(), {}) == []


# --------------------------------------------------------------- violations

def test_oversized_single_trade():
    assert "max_single_trade_pct" in check_constraints(
        _prop(_entry(size_pct=0.10)), _c(), {})


def test_size_at_limit_is_ok():
    assert "max_single_trade_pct" not in check_constraints(
        _prop(_entry(size_pct=0.05)), _c(), {})


def test_disallowed_symbol():
    assert "allowed_symbols" in check_constraints(
        _prop(_entry(symbol="TSLA")), _c(), {})


def test_too_many_entries():
    v = check_constraints(
        _prop(_entry(size_pct=0.01), _entry(size_pct=0.01),
              _entry(size_pct=0.01), _entry(size_pct=0.01)),
        _c(max_open_positions=3, max_position_pct=1.0), {})
    assert "max_open_positions" in v


def test_existing_positions_count_toward_limit():
    ws = {"open_positions": [{"position_id": "a"}, {"position_id": "b"}]}
    v = check_constraints(
        _prop(_entry(size_pct=0.01), _entry(size_pct=0.01)),
        _c(max_open_positions=3, max_position_pct=1.0), ws)
    assert "max_open_positions" in v  # 2 existing + 2 new > 3


def test_position_pct_sum_exceeded():
    v = check_constraints(
        _prop(_entry(size_pct=0.05), _entry(size_pct=0.05),
              _entry(size_pct=0.05), _entry(size_pct=0.05)),
        _c(max_position_pct=0.15, max_open_positions=10), {})
    assert "max_position_pct" in v  # sum 0.20 > 0.15


def test_risk_reward_below_min():
    # entry 185, stop 183 (risk 2), target 186 (reward 1) → rr 0.5 < 1.5
    v = check_constraints(_prop(_entry(take_profit=186.0)), _c(), {})
    assert "min_risk_reward" in v


def test_atr_stop_too_tight():
    # |entry - stop| = 1, atr 2, mult 1.5 → need >= 3
    ws = {"atr": 2.0}
    v = check_constraints(
        _prop(_entry(stop_loss=184.0, take_profit=200.0)), _c(), ws)
    assert "min_stop_atr_multiple" in v


def test_atr_check_skipped_when_atr_absent():
    v = check_constraints(_prop(_entry(stop_loss=184.9)), _c(), {"atr": None})
    assert "min_stop_atr_multiple" not in v


def test_vwap_is_never_a_violation():
    # Soft preference must never appear as a hard violation.
    ws = {"vwap": 100.0, "price_vs_vwap": 0.5}
    assert "prefer_entry_below_vwap" not in check_constraints(
        _prop(_entry()), _c(), ws)
