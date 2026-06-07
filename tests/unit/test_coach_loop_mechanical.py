from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.coach_loop import CoachLoop


def _constraints(**over) -> ConstraintSchema:
    base = dict(
        max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
        max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage", "max_drawdown_pct"],
        max_rounds=2,
    )
    base.update(over)
    return ConstraintSchema(**base)


_VALID = {"action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
          "entry_price": 185.0, "stop_loss": 183.0, "take_profit": 190.0}
_OVERSIZED = {**_VALID, "size_pct": 0.10}
_WS = {"symbol": "AMZN", "price": 185.0}


def _loop(actions: list[dict], tmp_path: Path) -> CoachLoop:
    player = MagicMock()
    player.decide.return_value = {
        "actions": actions, "reasoning": "x", "tokens_used": {"player": 1},
    }
    coach = MagicMock()
    coach.evaluate.return_value = {  # Coach hallucinates APPROVE
        "verdict": "APPROVE", "violations": [], "critique": "ok",
        "tokens_used": {"coach": 1},
    }
    return CoachLoop(player=player, coach=coach, artifact_writer=ArtifactWriter(tmp_path))


def test_mechanical_downgrades_hallucinated_approve(tmp_path: Path):
    art = _loop([_OVERSIZED], tmp_path).run(
        world_state=_WS, constraints=_constraints(), output_dir=tmp_path)
    assert art["outcome"] == "REJECT-MAX"
    assert "max_single_trade_pct" in art["rounds"][0]["evaluation"]["violations"]


def test_valid_proposal_still_approves(tmp_path: Path):
    art = _loop([_VALID], tmp_path).run(
        world_state=_WS, constraints=_constraints(), output_dir=tmp_path)
    assert art["outcome"] == "APPROVE"


def test_mechanical_hard_violation_aborts(tmp_path: Path):
    art = _loop([_OVERSIZED], tmp_path).run(
        world_state=_WS,
        constraints=_constraints(abort_on_violations=["max_single_trade_pct"]),
        output_dir=tmp_path)
    assert art["outcome"] == "ABORT"


def test_mechanical_violation_surfaced_in_feedback(tmp_path: Path):
    art = _loop([_OVERSIZED], tmp_path).run(
        world_state=_WS, constraints=_constraints(), output_dir=tmp_path)
    assert "max_single_trade_pct" in art["rounds"][0]["evaluation"]["feedback"]
