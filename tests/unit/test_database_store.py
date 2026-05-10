from pathlib import Path
import pytest
from player_coach.database.store import DatabaseStore

ARTIFACT = {
    "run_id": "run-001",
    "timestamp": "2026-05-10T09:30:00+00:00",
    "outcome": "APPROVE",
    "rounds_taken": 1,
    "total_tokens": 300,
    "rounds": [
        {
            "round": 1,
            "proposal": {"actions": [], "reasoning": "test"},
            "evaluation": {
                "decision": "APPROVE",
                "violations": [],
                "feedback": "All constraints passed.",
            },
            "tokens_used": {"player": 200, "coach": 100},
        }
    ],
}

STRATEGY = {
    "strategy_id": "strat-001",
    "name": "Moderate momentum",
    "description": "Buys on SMA crossover",
    "constraint_schema": {"max_position_pct": 0.15},
    "player_prompt_override": None,
}


@pytest.fixture
def store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path / "test.db")


def test_creates_tables_on_init(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store = DatabaseStore(db_path)
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"exchanges", "rounds", "strategies", "portfolio_snapshots", "coach_memory"} <= tables


def test_save_exchange_and_get_exchange_round_trip(store: DatabaseStore):
    store.save_exchange(ARTIFACT)
    result = store.get_exchange("run-001")
    assert result is not None
    assert result["run_id"] == "run-001"
    assert result["outcome"] == "APPROVE"
    assert result["approved"] == 1


def test_get_exchange_returns_none_for_missing_run_id(store: DatabaseStore):
    assert store.get_exchange("does-not-exist") is None


def test_get_exchanges_returns_list(store: DatabaseStore):
    store.save_exchange(ARTIFACT)
    results = store.get_exchanges()
    assert isinstance(results, list)
    assert len(results) == 1


def test_get_rounds_returns_round_rows(store: DatabaseStore):
    store.save_exchange(ARTIFACT)
    rounds = store.get_rounds("run-001")
    assert len(rounds) == 1
    assert rounds[0]["round_number"] == 1
    assert rounds[0]["verdict"] == "APPROVE"


def test_save_strategy_and_get_strategies(store: DatabaseStore):
    store.save_strategy(STRATEGY)
    results = store.get_strategies()
    assert len(results) == 1
    assert results[0]["strategy_id"] == "strat-001"
    assert results[0]["name"] == "Moderate momentum"


def test_approved_flag_zero_for_reject_outcome(store: DatabaseStore):
    rejected = {**ARTIFACT, "run_id": "run-002", "outcome": "REJECT-MAX"}
    store.save_exchange(rejected)
    result = store.get_exchange("run-002")
    assert result["approved"] == 0
