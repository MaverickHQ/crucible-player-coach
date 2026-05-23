from __future__ import annotations
from pathlib import Path

from player_coach.database.store import DatabaseStore


def _store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path / "test.db")


def _row(
    preset_a: str = "conservative",
    preset_b: str = "aggressive",
    symbol: str = "AMZN",
    **kwargs,
) -> dict:
    base = {
        "preset_a": preset_a,
        "preset_b": preset_b,
        "symbol": symbol,
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "approve_rate_a": 0.6,
        "approve_rate_b": 0.4,
        "avg_rounds_a": 2.1,
        "avg_rounds_b": 1.8,
        "days_aborted_a": 2,
        "days_aborted_b": 5,
        "total_return_a": 0.05,
        "total_return_b": -0.02,
        "max_drawdown_a": 0.03,
        "max_drawdown_b": 0.08,
    }
    base.update(kwargs)
    return base


def test_empty_returns_empty(tmp_path: Path):
    assert _store(tmp_path).get_backtest_results() == []


def test_save_and_retrieve(tmp_path: Path):
    store = _store(tmp_path)
    store.save_backtest_result(_row())
    results = store.get_backtest_results()
    assert len(results) == 1
    r = results[0]
    assert r["preset_a"] == "conservative"
    assert r["preset_b"] == "aggressive"
    assert r["approve_rate_a"] == 0.6
    assert r["days_aborted_b"] == 5
    assert r["total_return_a"] == 0.05
    assert r["max_drawdown_b"] == 0.08


def test_symbol_filter(tmp_path: Path):
    store = _store(tmp_path)
    store.save_backtest_result(_row(symbol="AMZN"))
    store.save_backtest_result(_row(symbol="TSLA"))
    results = store.get_backtest_results(symbol="AMZN")
    assert len(results) == 1
    assert results[0]["symbol"] == "AMZN"


def test_limit_respected(tmp_path: Path):
    store = _store(tmp_path)
    for _ in range(5):
        store.save_backtest_result(_row())
    assert len(store.get_backtest_results(limit=3)) == 3


def test_ordered_newest_first(tmp_path: Path):
    from datetime import datetime, timedelta, timezone
    store = _store(tmp_path)
    older = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    newer = datetime.now(timezone.utc).isoformat()
    store.save_backtest_result(_row(preset_a="old", created_at=older))
    store.save_backtest_result(_row(preset_a="new", created_at=newer))
    results = store.get_backtest_results()
    assert results[0]["preset_a"] == "new"
    assert results[1]["preset_a"] == "old"
