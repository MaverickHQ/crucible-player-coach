from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from player_coach.database.store import DatabaseStore

_DISCOUNT_DAYS = 30
_DISCOUNT_FACTOR = 0.5


def read_patterns(
    store: "DatabaseStore",
    symbol: str | None = None,
    strategy_id: str | None = None,
    min_confidence: float = 0.4,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    rows = store.get_memory_patterns(symbol=symbol, strategy_id=strategy_id)
    now = datetime.now(timezone.utc)

    seen: dict[str, dict[str, Any]] = {}

    for row in rows:
        confidence = row.get("confidence") or 0.0
        age_days = _age_days(row.get("created_at", ""), now)
        if age_days > _DISCOUNT_DAYS:
            confidence *= _DISCOUNT_FACTOR
        confidence = round(confidence, 4)
        if confidence < min_confidence:
            continue

        pt = row.get("pattern_type", "")
        if pt not in seen or confidence > seen[pt]["weighted_confidence"]:
            seen[pt] = {
                "symbol": row.get("symbol"),
                "pattern_type": pt,
                "observation": row.get("observation"),
                "weighted_confidence": confidence,
            }

    result = sorted(seen.values(), key=lambda x: x["weighted_confidence"], reverse=True)
    return result[:max_results]


def _age_days(created_at: str, now: datetime) -> float:
    if not created_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        return 0.0
