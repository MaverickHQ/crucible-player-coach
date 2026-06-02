from __future__ import annotations

import os
from pathlib import Path

import pytest

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.database.store import DatabaseStore
from player_coach.loop.coach_loop import CoachLoop
from player_coach.portfolio.state import PortfolioState


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

_FUTURES_CONSTRAINTS = Path("examples/constraints/futures_compatible.json")


def _make_constraints() -> ConstraintSchema:
    import json
    return ConstraintSchema.from_dict(json.loads(_FUTURES_CONSTRAINTS.read_text()))


def _make_world_state() -> dict:
    return {
        "symbol": "AMZN",
        "price": 185.00,
        "sma5": 183.00,
        "sma10": 180.00,
        "volume": 45_000_000,
        "position": "flat",
        "regime_label": "unknown",
        "session": "NY_open",
    }


def test_full_loop_returns_valid_artifact(tmp_path: Path) -> None:
    db_store = DatabaseStore(tmp_path / "test.db")
    writer = ArtifactWriter(tmp_path)
    loop = CoachLoop(
        player=PlayerAgent(),
        coach=CoachAgent(),
        artifact_writer=writer,
    )
    portfolio_state = PortfolioState(
        capital=10_000.0,
        daily_starting_balance=10_000.0,
        peak_capital=10_000.0,
        cash_available=10_000.0,
        daily_pnl=0.0,
    )

    artifact = loop.run(
        world_state=_make_world_state(),
        constraints=_make_constraints(),
        portfolio_state=portfolio_state,
        db_store=db_store,
        strategy_id="integration-test",
        output_dir=tmp_path,
    )

    assert artifact["outcome"] in ("APPROVE", "REJECT-MAX", "ABORT")
    assert artifact["run_id"] is not None
    assert len(artifact["rounds"]) >= 0
    assert db_store.get_exchange(artifact["run_id"]) is not None
