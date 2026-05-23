from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path

from player_coach.database.store import DatabaseStore
from player_coach.patterns.pattern_reader import read_patterns


def _store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path / "test.db")


def _save_pattern(
    store: DatabaseStore,
    symbol: str,
    pattern_type: str,
    confidence: float,
    strategy_id: str | None = None,
    days_ago: int = 0,
) -> None:
    created_at = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat()
    store.save_coach_memory({
        "strategy_id": strategy_id,
        "pattern_type": pattern_type,
        "symbol": symbol,
        "observation": f"obs for {pattern_type}",
        "confidence": confidence,
        "created_at": created_at,
    })


def test_empty_store_returns_empty(tmp_path: Path):
    assert read_patterns(_store(tmp_path), symbol="AMZN") == []


def test_recent_pattern_not_discounted(tmp_path: Path):
    store = _store(tmp_path)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.8, days_ago=0)
    results = read_patterns(store, symbol="AMZN")
    assert len(results) == 1
    assert results[0]["weighted_confidence"] == 0.8


def test_old_pattern_discounted(tmp_path: Path):
    store = _store(tmp_path)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.8, days_ago=31)
    results = read_patterns(store, symbol="AMZN")
    assert len(results) == 1
    assert results[0]["weighted_confidence"] == 0.4  # 0.8 * 0.5


def test_deduplicates_by_pattern_type_keeps_highest(tmp_path: Path):
    store = _store(tmp_path)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.6, days_ago=0)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.9, days_ago=0)
    results = read_patterns(store, symbol="AMZN")
    assert len(results) == 1
    assert results[0]["weighted_confidence"] == 0.9


def test_symbol_filter(tmp_path: Path):
    store = _store(tmp_path)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.8, days_ago=0)
    _save_pattern(store, "TSLA", "max_leverage", 0.9, days_ago=0)
    results = read_patterns(store, symbol="AMZN")
    assert len(results) == 1
    assert results[0]["symbol"] == "AMZN"


def test_min_confidence_filter(tmp_path: Path):
    store = _store(tmp_path)
    # discounted to 0.3 (below default min_confidence=0.4)
    _save_pattern(store, "AMZN", "min_risk_reward", 0.6, days_ago=31)
    results = read_patterns(store, symbol="AMZN")
    assert results == []
