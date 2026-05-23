from __future__ import annotations
from pathlib import Path

from player_coach.patterns.pattern_writer import extract_patterns, write_patterns
from player_coach.database.store import DatabaseStore


def _make_artifact(
    outcome: str,
    rounds_violations: list[list[str]],
    symbol: str = "AMZN",
) -> dict:
    rounds = [
        {
            "round": i + 1,
            "evaluation": {
                "decision": "REJECT",
                "violations": vs,
                "feedback": "critique",
            },
        }
        for i, vs in enumerate(rounds_violations)
    ]
    return {"outcome": outcome, "symbol": symbol, "rounds": rounds}


def test_empty_rounds_returns_empty():
    artifact = {"outcome": "ABORT", "symbol": "AMZN", "rounds": []}
    assert extract_patterns(artifact) == []


def test_no_violations_returns_empty():
    artifact = _make_artifact("REJECT-MAX", [[], []])
    assert extract_patterns(artifact) == []


def test_abort_violation_gets_high_confidence():
    artifact = _make_artifact("ABORT", [["max_leverage"]])
    patterns = extract_patterns(artifact)
    assert len(patterns) == 1
    assert patterns[0]["pattern_type"] == "max_leverage"
    assert patterns[0]["confidence"] == 0.9
    assert "ABORT" in patterns[0]["observation"]


def test_persistent_violation_gets_high_confidence():
    # same violation across 2 rounds
    artifact = _make_artifact("REJECT-MAX", [["min_risk_reward"], ["min_risk_reward"]])
    patterns = extract_patterns(artifact)
    assert len(patterns) == 1
    assert patterns[0]["confidence"] == 0.8
    assert "Persistent" in patterns[0]["observation"]


def test_single_round_violation_confidence_scaled():
    # 1 violation in 2 rounds → 0.5 + (1/2) * 0.3 = 0.65
    artifact = _make_artifact("REJECT-MAX", [["min_risk_reward"], []])
    patterns = extract_patterns(artifact)
    assert len(patterns) == 1
    assert patterns[0]["confidence"] == 0.65


def test_write_patterns_saves_to_store(tmp_path: Path):
    store = DatabaseStore(tmp_path / "test.db")
    artifact = _make_artifact("ABORT", [["max_leverage"]], symbol="TSLA")
    write_patterns(artifact, store, strategy_id="strat-x")
    rows = store.get_memory_patterns(symbol="TSLA")
    assert len(rows) == 1
    assert rows[0]["pattern_type"] == "max_leverage"
    assert rows[0]["strategy_id"] == "strat-x"
    assert rows[0]["confidence"] == 0.9
