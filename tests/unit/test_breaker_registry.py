from __future__ import annotations

from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.breaker_registry import BreakerRegistry, CircuitBreaker
from player_coach.portfolio.state import PortfolioState


def _constraints(**over) -> ConstraintSchema:
    base = dict(
        max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
        max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
        min_risk_reward=1.5, abort_on_violations=["max_leverage"],
        max_daily_loss_pct=0.02, consistency_rule_pct=0.50,
        trading_cutoff_time="23:59",  # far future → cutoff won't fire from clock
    )
    base.update(over)
    return ConstraintSchema(**base)


def _portfolio(capital=100_000.0, peak=100_000.0, daily_start=100_000.0,
               daily_pnl=0.0, cumulative=0.0) -> PortfolioState:
    return PortfolioState(
        capital=capital, daily_starting_balance=daily_start, peak_capital=peak,
        cash_available=capital, daily_pnl=daily_pnl, cumulative_pnl=cumulative,
    )


def test_default_registry_priority_order():
    assert BreakerRegistry().names() == [
        "mll_breached", "daily_loss_limit", "consistency_rule", "trading_cutoff",
    ]


def test_no_breach_returns_none():
    assert BreakerRegistry().first_breach(_portfolio(), _constraints()) is None


def test_mll_breach_detected():
    # peak 100k * (1 - 0.10) = 90k floor; capital at floor → breach.
    p = _portfolio(capital=90_000.0, daily_pnl=-10_000.0)
    assert BreakerRegistry().first_breach(p, _constraints()) == "mll_breached"


def test_highest_priority_wins_when_multiple_breach():
    # A 10% loss breaches both MLL and the daily loss limit → MLL (priority 1).
    p = _portfolio(capital=90_000.0, daily_pnl=-10_000.0)
    assert BreakerRegistry().first_breach(p, _constraints()) == "mll_breached"


def test_daily_loss_alone():
    p = _portfolio(capital=97_900.0, daily_pnl=-2_100.0)  # 2.1% loss, above MLL
    assert BreakerRegistry().first_breach(p, _constraints()) == "daily_loss_limit"


def test_register_custom_breaker_fires_by_priority():
    reg = BreakerRegistry()
    reg.register(CircuitBreaker("custom", 0, lambda p, c: True))
    assert reg.first_breach(_portfolio(), _constraints()) == "custom"


def test_custom_low_priority_breaker_runs_after_defaults():
    reg = BreakerRegistry()
    reg.register(CircuitBreaker("never_first", 99, lambda p, c: True))
    # Healthy portfolio → defaults pass, the custom one fires last.
    assert reg.first_breach(_portfolio(), _constraints()) == "never_first"
