from __future__ import annotations
import json
import pytest
from pathlib import Path
from player_coach.artifacts.writer import ArtifactWriter

CONSTRAINTS = {
    "max_position_pct": 0.15,
    "max_single_trade_pct": 0.05,
    "max_leverage": 1.5,
    "max_drawdown_pct": 0.10,
    "allowed_symbols": ["AMZN"],
    "max_open_positions": 3,
    "min_risk_reward": 1.5,
    "max_rounds": 3,
    "abort_on_violations": ["max_leverage"],
}

WORLD_STATE = {"symbol": "AMZN", "price": 185.0}

ROUNDS = [
    {
        "round": 1,
        "proposal": {"actions": [], "reasoning": "test"},
        "evaluation": {"decision": "APPROVE", "violations": [], "feedback": None},
        "tokens_used": {"player": 100, "coach": 50},
    }
]


@pytest.fixture
def writer(tmp_path: Path) -> ArtifactWriter:
    return ArtifactWriter(tmp_path)


def test_write_produces_valid_json_file(writer: ArtifactWriter, tmp_path: Path):
    path = writer.write(
        constraints=CONSTRAINTS,
        world_state=WORLD_STATE,
        rounds=ROUNDS,
        outcome="APPROVE",
    )
    assert path.exists()
    data = json.loads(path.read_text())
    assert isinstance(data, dict)


def test_artifact_contains_required_keys(writer: ArtifactWriter):
    path = writer.write(
        constraints=CONSTRAINTS,
        world_state=WORLD_STATE,
        rounds=ROUNDS,
        outcome="APPROVE",
    )
    data = json.loads(path.read_text())
    for key in ("run_id", "timestamp", "approved", "rounds_taken", "total_tokens"):
        assert key in data, f"missing key: {key}"


def test_approved_true_when_outcome_approve(writer: ArtifactWriter):
    path = writer.write(
        constraints=CONSTRAINTS,
        world_state=WORLD_STATE,
        rounds=ROUNDS,
        outcome="APPROVE",
    )
    data = json.loads(path.read_text())
    assert data["approved"] is True


def test_approved_false_when_outcome_reject_max(writer: ArtifactWriter):
    path = writer.write(
        constraints=CONSTRAINTS,
        world_state=WORLD_STATE,
        rounds=ROUNDS,
        outcome="REJECT-MAX",
    )
    data = json.loads(path.read_text())
    assert data["approved"] is False
