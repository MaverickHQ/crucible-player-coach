from __future__ import annotations

from unittest.mock import MagicMock

from player_coach.backtest.compare import ComparisonResult, StrategyComparator


def _make_exchange(outcome: str, rounds: int = 1, tokens_per_round: int = 80) -> dict:
    return {
        "outcome": outcome,
        "rounds": [
            {
                "player_tokens": tokens_per_round // 2,
                "coach_tokens": tokens_per_round // 2,
            }
            for _ in range(rounds)
        ],
    }


def _make_db_store(exchanges_by_run_id: dict[str, dict | None]) -> MagicMock:
    db_store = MagicMock()

    def _get_exchange(run_id: str) -> dict | None:
        return exchanges_by_run_id.get(run_id)

    def _get_rounds(run_id: str) -> list:
        ex = exchanges_by_run_id.get(run_id)
        return ex["rounds"] if ex is not None else []

    db_store.get_exchange.side_effect = _get_exchange
    db_store.get_rounds.side_effect = _get_rounds
    return db_store


def test_compare_returns_comparison_result() -> None:
    db_store = _make_db_store({
        "run-a1": _make_exchange("APPROVE"),
        "run-b1": _make_exchange("REJECT"),
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["run-a1"], ["run-b1"])
    assert isinstance(result, ComparisonResult)


def test_approve_rate_computed_correctly() -> None:
    # Strategy A: 2 APPROVE, 1 REJECT → 66.7%
    # Strategy B: 1 APPROVE, 2 REJECT → 33.3%
    db_store = _make_db_store({
        "a1": _make_exchange("APPROVE"),
        "a2": _make_exchange("APPROVE"),
        "a3": _make_exchange("REJECT"),
        "b1": _make_exchange("APPROVE"),
        "b2": _make_exchange("REJECT"),
        "b3": _make_exchange("REJECT"),
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["a1", "a2", "a3"], ["b1", "b2", "b3"])
    assert abs(result.approve_rate_a - 2 / 3) < 1e-9
    assert abs(result.approve_rate_b - 1 / 3) < 1e-9


def test_summary_is_non_empty() -> None:
    db_store = _make_db_store({
        "a1": _make_exchange("APPROVE"),
        "b1": _make_exchange("REJECT"),
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["a1"], ["b1"], label_a="Aggressive", label_b="Conservative")
    assert isinstance(result.summary, str)
    assert len(result.summary) > 0


def test_summary_names_winner_when_rates_differ() -> None:
    db_store = _make_db_store({
        "a1": _make_exchange("APPROVE"),
        "b1": _make_exchange("REJECT"),
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["a1"], ["b1"], label_a="Alpha", label_b="Beta")
    assert "Alpha" in result.summary


def test_summary_tie_when_rates_equal() -> None:
    db_store = _make_db_store({
        "a1": _make_exchange("APPROVE"),
        "b1": _make_exchange("APPROVE"),
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["a1"], ["b1"], label_a="Alpha", label_b="Beta")
    assert result.approve_rate_a == result.approve_rate_b
    assert "identical" in result.summary


def test_missing_run_id_is_skipped() -> None:
    db_store = _make_db_store({
        "a1": _make_exchange("APPROVE"),
        "a2": None,
    })
    comparator = StrategyComparator(db_store)
    result = comparator.compare(["a1", "a2"], [])
    assert result.total_exchanges_a == 1


def test_empty_run_ids_returns_zero_rates() -> None:
    db_store = MagicMock()
    comparator = StrategyComparator(db_store)
    result = comparator.compare([], [])
    assert result.approve_rate_a == 0.0
    assert result.approve_rate_b == 0.0
    assert result.total_exchanges_a == 0
    assert result.total_exchanges_b == 0
