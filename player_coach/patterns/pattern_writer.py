from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from player_coach.database.store import DatabaseStore


def extract_patterns(
    artifact: dict[str, Any],
    strategy_id: str | None = None,
) -> list[dict[str, Any]]:
    rounds = artifact.get("rounds", [])
    if not rounds:
        return []

    symbol = artifact.get("symbol")
    outcome = artifact.get("outcome", "")
    total_rounds = len(rounds)

    violation_counts: dict[str, int] = {}
    for r in rounds:
        for v in r.get("evaluation", {}).get("violations", []):
            violation_counts[v] = violation_counts.get(v, 0) + 1

    if not violation_counts:
        return []

    abort_violations: set[str] = set()
    if outcome == "ABORT":
        last_eval = rounds[-1].get("evaluation", {})
        abort_violations = set(last_eval.get("violations", []))

    now = datetime.now(timezone.utc).isoformat()
    patterns = []

    for violation, count in violation_counts.items():
        if violation in abort_violations:
            confidence = 0.9
            obs = f"Hard violation triggered ABORT — {violation} breached"
        elif count == total_rounds and total_rounds > 1:
            confidence = 0.8
            obs = f"Persistent violation across all {count} rounds — {violation}"
        else:
            confidence = round(0.5 + (count / total_rounds) * 0.3, 4)
            obs = f"Violation flagged in {count} of {total_rounds} rounds — {violation}"

        patterns.append({
            "strategy_id": strategy_id,
            "pattern_type": violation,
            "symbol": symbol,
            "observation": obs,
            "confidence": round(confidence, 4),
            "created_at": now,
        })

    return patterns


def write_patterns(
    artifact: dict[str, Any],
    store: "DatabaseStore",
    strategy_id: str | None = None,
) -> None:
    for pattern in extract_patterns(artifact, strategy_id):
        store.save_coach_memory(pattern)
