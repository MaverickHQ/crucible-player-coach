from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from player_coach.database.store import DatabaseStore


@dataclass
class ComparisonResult:
    label_a: str
    label_b: str
    total_exchanges_a: int
    total_exchanges_b: int
    approve_rate_a: float
    approve_rate_b: float
    avg_rounds_a: float
    avg_rounds_b: float
    avg_tokens_a: float
    avg_tokens_b: float
    summary: str


def _approve_rate(exchanges: list[dict]) -> float:
    if not exchanges:
        return 0.0
    approved = sum(1 for e in exchanges if e.get("outcome") == "APPROVE")
    return approved / len(exchanges)


def _avg_rounds(exchanges: list[dict]) -> float:
    if not exchanges:
        return 0.0
    return sum(len(e.get("rounds", [])) for e in exchanges) / len(exchanges)


def _avg_tokens(exchanges: list[dict]) -> float:
    if not exchanges:
        return 0.0
    totals = []
    for e in exchanges:
        total = sum(
            r.get("tokens_used", {}).get("player", 0)
            + r.get("tokens_used", {}).get("coach", 0)
            for r in e.get("rounds", [])
        )
        totals.append(total)
    return sum(totals) / len(totals)


class StrategyComparator:
    def __init__(self, db_store: DatabaseStore) -> None:
        self._db_store = db_store

    def compare(
        self,
        run_ids_a: list[str],
        run_ids_b: list[str],
        label_a: str = "Strategy A",
        label_b: str = "Strategy B",
    ) -> ComparisonResult:
        def _fetch(run_ids: list[str]) -> list[dict]:
            results = []
            for rid in run_ids:
                ex = self._db_store.get_exchange(rid)
                if ex is not None:
                    ex["rounds"] = self._db_store.get_rounds(rid)
                    results.append(ex)
            return results

        exchanges_a = _fetch(run_ids_a)
        exchanges_b = _fetch(run_ids_b)

        approve_rate_a = _approve_rate(exchanges_a)
        approve_rate_b = _approve_rate(exchanges_b)
        avg_rounds_a = _avg_rounds(exchanges_a)
        avg_rounds_b = _avg_rounds(exchanges_b)
        avg_tokens_a = _avg_tokens(exchanges_a)
        avg_tokens_b = _avg_tokens(exchanges_b)

        if approve_rate_a > approve_rate_b:
            winner = label_a
            diff = approve_rate_a - approve_rate_b
        elif approve_rate_b > approve_rate_a:
            winner = label_b
            diff = approve_rate_b - approve_rate_a
        else:
            winner = None
            diff = 0.0

        if winner:
            summary = (
                f"{winner} outperforms on approval rate "
                f"by {diff:.1%} ({approve_rate_a:.1%} vs {approve_rate_b:.1%})."
            )
        else:
            summary = (
                f"{label_a} and {label_b} have identical approval rates "
                f"({approve_rate_a:.1%})."
            )

        return ComparisonResult(
            label_a=label_a,
            label_b=label_b,
            total_exchanges_a=len(exchanges_a),
            total_exchanges_b=len(exchanges_b),
            approve_rate_a=approve_rate_a,
            approve_rate_b=approve_rate_b,
            avg_rounds_a=avg_rounds_a,
            avg_rounds_b=avg_rounds_b,
            avg_tokens_a=avg_tokens_a,
            avg_tokens_b=avg_tokens_b,
            summary=summary,
        )
