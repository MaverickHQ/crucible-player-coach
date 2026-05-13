from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch

from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.database.store import DatabaseStore
from player_coach.loop.coach_loop import CoachLoop
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


def _make_loop(tmp_path: Path) -> CoachLoop:
    player = MagicMock()
    player.decide.return_value = {
        "actions": [{"action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
                     "entry_price": 185.0, "stop_loss": 183.0, "take_profit": 190.0,
                     "position_id": None}],
        "reasoning": "Momentum setup.",
        "tokens_used": {"player": 50},
    }
    coach = MagicMock()
    coach.evaluate.return_value = {
        "verdict": "APPROVE",
        "violations": [],
        "critique": "All checks pass.",
        "tokens_used": {"coach": 30},
    }
    writer = ArtifactWriter(tmp_path)
    return CoachLoop(player=player, coach=coach, artifact_writer=writer)


def _healthy_portfolio() -> PortfolioState:
    return PortfolioState(
        capital=100_000.0,
        daily_starting_balance=100_000.0,
        peak_capital=100_000.0,
        cash_available=100_000.0,
        daily_pnl=0.0,
        cumulative_pnl=0.0,
    )


def _mll_portfolio() -> PortfolioState:
    # capital == floor (100k * 0.90) → MLL breached
    return PortfolioState(
        capital=90_000.0,
        daily_starting_balance=100_000.0,
        peak_capital=100_000.0,
        cash_available=90_000.0,
        daily_pnl=-10_000.0,
        cumulative_pnl=0.0,
    )


def _daily_loss_portfolio() -> PortfolioState:
    # 2.1% loss → daily loss limit breached, but capital still above MLL floor
    return PortfolioState(
        capital=97_900.0,
        daily_starting_balance=100_000.0,
        peak_capital=100_000.0,
        cash_available=97_900.0,
        daily_pnl=-2_100.0,
        cumulative_pnl=0.0,
    )


def test_mll_breach_returns_abort_with_no_rounds(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    store = DatabaseStore(tmp_path / "test.db")
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        portfolio_state=_mll_portfolio(),
        db_store=store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    assert artifact["outcome"] == "ABORT"
    assert artifact["rounds"] == []
    assert artifact["termination_reason"] == "mll_breached"


def test_daily_loss_breach_returns_abort_with_no_rounds(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    store = DatabaseStore(tmp_path / "test.db")
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        portfolio_state=_daily_loss_portfolio(),
        db_store=store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    assert artifact["outcome"] == "ABORT"
    assert artifact["rounds"] == []
    assert artifact["termination_reason"] == "daily_loss_limit"


def test_trading_cutoff_breach_returns_abort_with_no_rounds(tmp_path: Path) -> None:
    constraints = _make_constraints()
    constraints.trading_cutoff_time = "09:00"
    loop = _make_loop(tmp_path)
    store = DatabaseStore(tmp_path / "test.db")
    with patch(
        "player_coach.loop.coach_loop.is_trading_cutoff_reached",
        return_value=True,
    ):
        artifact = loop.run(
            world_state={"symbol": "AMZN", "price": 185.0},
            constraints=constraints,
            portfolio_state=_healthy_portfolio(),
            db_store=store,
            strategy_id="test-strategy",
            output_dir=tmp_path,
        )
    assert artifact["outcome"] == "ABORT"
    assert artifact["rounds"] == []
    assert artifact["termination_reason"] == "trading_cutoff"


def test_no_breach_loop_runs_normally(tmp_path: Path) -> None:
    constraints = _make_constraints()
    constraints.trading_cutoff_time = "23:59"
    loop = _make_loop(tmp_path)
    store = DatabaseStore(tmp_path / "test.db")
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=constraints,
        portfolio_state=_healthy_portfolio(),
        db_store=store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    assert artifact["outcome"] == "APPROVE"
    assert len(artifact["rounds"]) == 1
