from __future__ import annotations
from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.circuit_breakers import (
    is_daily_loss_limit_breached,
    is_consistency_rule_breached,
    is_trading_cutoff_reached,
    is_mll_breached,
)
from player_coach.portfolio.state import PortfolioState


def _make_constraints() -> ConstraintSchema:
    return ConstraintSchema(
        max_position_pct=0.15,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage", "max_drawdown_pct"],
        max_rounds=3,
        max_daily_loss_pct=0.02,
        consistency_rule_pct=0.50,
        trading_cutoff_time="16:20",
    )


def _make_portfolio(
    capital: float = 100_000.0,
    daily_starting_balance: float = 100_000.0,
    daily_pnl: float = 0.0,
    cumulative_pnl: float = 0.0,
) -> PortfolioState:
    return PortfolioState(
        capital=capital,
        daily_starting_balance=daily_starting_balance,
        peak_capital=daily_starting_balance,
        cash_available=capital,
        daily_pnl=daily_pnl,
        cumulative_pnl=cumulative_pnl,
    )


# --- is_daily_loss_limit_breached ---

def test_daily_loss_limit_breached_when_loss_exceeds_limit() -> None:
    # 2.1% loss on 100k starting balance, limit is 2%
    portfolio = _make_portfolio(daily_pnl=-2_100.0)
    assert is_daily_loss_limit_breached(portfolio, _make_constraints()) is True


def test_daily_loss_limit_not_breached_when_within_limit() -> None:
    # 1.9% loss — under 2% limit
    portfolio = _make_portfolio(daily_pnl=-1_900.0)
    assert is_daily_loss_limit_breached(portfolio, _make_constraints()) is False


def test_daily_loss_limit_not_breached_when_no_loss() -> None:
    portfolio = _make_portfolio(daily_pnl=500.0)
    assert is_daily_loss_limit_breached(portfolio, _make_constraints()) is False


# --- is_consistency_rule_breached ---

def test_consistency_rule_breached_when_gain_exceeds_fraction() -> None:
    # Today +600, cumulative +1000, rule is 50% → 600 > 500 → breach
    portfolio = _make_portfolio(daily_pnl=600.0, cumulative_pnl=1_000.0)
    assert is_consistency_rule_breached(portfolio, _make_constraints()) is True


def test_consistency_rule_not_breached_when_within_fraction() -> None:
    # Today +400, cumulative +1000, rule is 50% → 400 <= 500 → ok
    portfolio = _make_portfolio(daily_pnl=400.0, cumulative_pnl=1_000.0)
    assert is_consistency_rule_breached(portfolio, _make_constraints()) is False


def test_consistency_rule_not_breached_when_cumulative_pnl_is_zero() -> None:
    portfolio = _make_portfolio(daily_pnl=1_000.0, cumulative_pnl=0.0)
    assert is_consistency_rule_breached(portfolio, _make_constraints()) is False


# --- is_trading_cutoff_reached ---

def test_trading_cutoff_reached_when_time_is_past_cutoff() -> None:
    assert is_trading_cutoff_reached(_make_constraints(), current_time_str="16:21") is True


def test_trading_cutoff_reached_when_time_equals_cutoff() -> None:
    assert is_trading_cutoff_reached(_make_constraints(), current_time_str="16:20") is True


def test_trading_cutoff_not_reached_when_one_minute_before() -> None:
    assert is_trading_cutoff_reached(_make_constraints(), current_time_str="16:19") is False


# --- is_mll_breached ---

def test_mll_breached_when_capital_at_floor() -> None:
    # floor = 100k * (1 - 0.10) = 90k; capital == floor → breach
    portfolio = _make_portfolio(capital=90_000.0)
    assert is_mll_breached(portfolio, _make_constraints()) is True


def test_mll_breached_when_capital_below_floor() -> None:
    portfolio = _make_portfolio(capital=89_999.0)
    assert is_mll_breached(portfolio, _make_constraints()) is True


def test_mll_not_breached_when_capital_above_floor() -> None:
    # floor = 90k; capital = 90_001 → ok
    portfolio = _make_portfolio(capital=90_001.0)
    assert is_mll_breached(portfolio, _make_constraints()) is False
