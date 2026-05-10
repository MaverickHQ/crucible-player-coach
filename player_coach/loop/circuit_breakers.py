from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from player_coach.constraints.schema import ConstraintSchema
    from player_coach.portfolio.state import PortfolioState


def is_daily_loss_limit_breached(
    portfolio: PortfolioState,
    constraints: ConstraintSchema,
) -> bool:
    return constraints.is_daily_loss_breached(
        portfolio.daily_pnl,
        portfolio.daily_starting_balance,
    )


def is_consistency_rule_breached(
    portfolio: PortfolioState,
    constraints: ConstraintSchema,
) -> bool:
    return constraints.is_consistency_breached(
        portfolio.daily_pnl,
        portfolio.cumulative_pnl,
    )


def is_trading_cutoff_reached(
    constraints: ConstraintSchema,
    current_time_str: str | None = None,
) -> bool:
    if current_time_str is None:
        current_time_str = datetime.now().strftime("%H:%M")
    return current_time_str >= constraints.trading_cutoff_time


def is_mll_breached(
    portfolio: PortfolioState,
    constraints: ConstraintSchema,
) -> bool:
    floor = portfolio.daily_starting_balance * (1 - constraints.max_drawdown_pct)
    return portfolio.capital <= floor
