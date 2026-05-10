from player_coach.portfolio.position import Position
from player_coach.portfolio.state import PortfolioState

POSITION = Position(
    position_id="pos-001",
    symbol="AMZN",
    direction="long",
    entry_price=185.00,
    quantity=10.0,
    size_pct=0.05,
    stop_loss=180.00,
    take_profit=195.00,
    opened_at="2026-05-10T09:30:00+00:00",
)


def _make_state(**overrides) -> PortfolioState:
    defaults = dict(
        capital=9_800.0,
        daily_starting_balance=10_000.0,
        peak_capital=10_000.0,
        cash_available=9_800.0,
    )
    defaults.update(overrides)
    return PortfolioState(**defaults)


def test_current_drawdown_pct_correct():
    state = _make_state(capital=9_800.0, daily_starting_balance=10_000.0)
    assert state.current_drawdown_pct == 0.02


def test_current_drawdown_pct_zero_when_no_loss():
    state = _make_state(capital=10_000.0, daily_starting_balance=10_000.0)
    assert state.current_drawdown_pct == 0.0


def test_current_drawdown_pct_zero_when_daily_starting_balance_is_zero():
    state = _make_state(capital=0.0, daily_starting_balance=0.0, cash_available=0.0)
    assert state.current_drawdown_pct == 0.0


def test_to_dict_from_dict_round_trip():
    state = _make_state(
        open_positions=[POSITION],
        daily_pnl=-200.0,
        cumulative_pnl=500.0,
        consistency_pct=0.4,
        trading_days_active=5,
    )
    assert PortfolioState.from_dict(state.to_dict()) == state


def test_consistency_pct_defaults_to_zero():
    state = _make_state()
    assert state.consistency_pct == 0.0


def test_open_positions_defaults_to_empty_list():
    state = _make_state()
    assert state.open_positions == []


def test_trading_days_active_defaults_to_zero():
    state = _make_state()
    assert state.trading_days_active == 0
