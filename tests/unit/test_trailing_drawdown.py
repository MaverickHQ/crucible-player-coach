from __future__ import annotations

from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.circuit_breakers import is_mll_breached
from player_coach.portfolio.state import PortfolioState

_BASE = dict(
    max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
    max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
    min_risk_reward=1.5, abort_on_violations=["max_leverage"],
)


def _c(**over) -> ConstraintSchema:
    return ConstraintSchema(**{**_BASE, **over})


def _p(capital: float, peak: float) -> PortfolioState:
    return PortfolioState(
        capital=capital, daily_starting_balance=peak, peak_capital=peak,
        cash_available=capital, daily_pnl=0.0, cumulative_pnl=0.0,
    )


# --------------------------------------------------------- schema derivation

def test_trailing_defaults_to_max_drawdown():
    assert _c(max_drawdown_pct=0.10).trailing_max_drawdown_pct == 0.10


def test_trailing_explicit_value_kept():
    assert _c(trailing_max_drawdown_pct=0.08).trailing_max_drawdown_pct == 0.08


def test_from_dict_aliases_max_drawdown_when_trailing_absent():
    c = ConstraintSchema.from_dict({**_BASE})
    assert c.trailing_max_drawdown_pct == 0.10


def test_from_dict_prefers_trailing_key():
    c = ConstraintSchema.from_dict({**_BASE, "trailing_max_drawdown_pct": 0.07})
    assert c.trailing_max_drawdown_pct == 0.07


def test_to_dict_includes_trailing():
    assert _c().to_dict()["trailing_max_drawdown_pct"] == 0.10


# ----------------------------------------------------- breaker uses trailing

def test_mll_uses_trailing_value():
    # trailing 0.05 → floor = 100k * 0.95 = 95k. Boundary at the floor.
    c = _c(trailing_max_drawdown_pct=0.05)
    assert is_mll_breached(_p(95_000.0, 100_000.0), c) is True
    assert is_mll_breached(_p(95_001.0, 100_000.0), c) is False


def test_trailing_tightens_as_equity_rises():
    # Same 95k capital: fine at peak 100k (floor 90k) but breaches once the peak
    # rises to 110k (floor 99k) — the limit trails the high-water mark.
    c = _c(max_drawdown_pct=0.10)
    assert is_mll_breached(_p(95_000.0, 100_000.0), c) is False
    assert is_mll_breached(_p(95_000.0, 110_000.0), c) is True
