from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock

from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.coach_loop import CoachLoop


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


def test_run_with_db_store_saves_exchange(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    db_store = MagicMock()
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        db_store=db_store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    db_store.save_exchange.assert_called_once_with(artifact)


def test_run_with_db_store_saved_artifact_has_correct_outcome(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    db_store = MagicMock()
    loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        db_store=db_store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    saved = db_store.save_exchange.call_args[0][0]
    assert saved["outcome"] == "APPROVE"
    assert "run_id" in saved


def test_run_with_db_store_saved_rounds_match_artifact(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    db_store = MagicMock()
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        db_store=db_store,
        strategy_id="test-strategy",
        output_dir=tmp_path,
    )
    saved = db_store.save_exchange.call_args[0][0]
    assert saved["rounds"] == artifact["rounds"]
    assert len(saved["rounds"]) == 1


def test_run_without_db_store_does_not_raise(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        output_dir=tmp_path,
    )
    assert artifact["outcome"] == "APPROVE"


# ---------------------------------------------------------------- N5: cache tokens


def _loop_with_cache_tokens(tmp_path: Path) -> CoachLoop:
    """Variant of _make_loop where the agents report cache_read_* tokens.
    Used to pin that CoachLoop forwards every key on tokens_used, not just
    the bare 'player'/'coach' keys (which dropped T1's cache observability).
    """
    player = MagicMock()
    player.decide.return_value = {
        "actions": [{"action_type": "hold"}],
        "reasoning": "wait.",
        "tokens_used": {"player": 50, "cache_read_player": 4000},
    }
    coach = MagicMock()
    coach.evaluate.return_value = {
        "verdict": "APPROVE", "violations": [], "critique": "ok",
        "tokens_used": {"coach": 30, "cache_read_coach": 2500},
    }
    writer = ArtifactWriter(tmp_path)
    return CoachLoop(player=player, coach=coach, artifact_writer=writer)


def test_coach_loop_forwards_cache_read_tokens_to_round(tmp_path: Path) -> None:
    # N5 — the per-round tokens_used dict in the artifact MUST carry every
    # key the agents returned, not just 'player'/'coach'. The old code did
    # tokens_used={'player': ..., 'coach': ...}, which dropped
    # cache_read_player and cache_read_coach before they reached the DB or
    # the dashboard's token panel. T1's observability promise died here.
    loop = _loop_with_cache_tokens(tmp_path)
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        output_dir=tmp_path,
    )
    round0_tokens = artifact["rounds"][0]["tokens_used"]
    assert round0_tokens["player"] == 50
    assert round0_tokens["coach"] == 30
    assert round0_tokens["cache_read_player"] == 4000
    assert round0_tokens["cache_read_coach"] == 2500


def test_coach_loop_tolerates_missing_cache_keys(tmp_path: Path) -> None:
    # Back-compat — agents that don't report cache_read_* must still work.
    loop = _make_loop(tmp_path)  # uses {'player': 50}, {'coach': 30}
    artifact = loop.run(
        world_state={"symbol": "AMZN", "price": 185.0},
        constraints=_make_constraints(),
        output_dir=tmp_path,
    )
    round0_tokens = artifact["rounds"][0]["tokens_used"]
    assert round0_tokens["player"] == 50
    assert round0_tokens["coach"] == 30
    # Missing keys absent, not crashy.
    assert "cache_read_player" not in round0_tokens
    assert "cache_read_coach" not in round0_tokens
