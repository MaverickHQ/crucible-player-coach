from __future__ import annotations
import json
from typing import Any


def build_evidence_policy(
    approved_runs: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    rounds_by_run: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    runs = []
    for exchange in approved_runs:
        run_id = exchange.get("run_id")
        rounds = rounds_by_run.get(run_id, [])
        proposal = _last_proposal(rounds)
        if not proposal or not proposal.get("actions"):
            continue
        entry: dict[str, Any] = {"outcome": "success"}
        size_pct = _extract_size_pct(proposal)
        rr = _extract_risk_reward(proposal)
        if size_pct is not None:
            entry["trade_size_pct"] = size_pct
        if rr is not None:
            entry["risk_reward"] = rr
        runs.append(entry)

    pattern_list = [
        {"symbol": p["symbol"], "confidence": p["confidence"]}
        for p in patterns
        if p.get("symbol") and p.get("confidence") is not None
    ]

    return {"runs": runs, "patterns": pattern_list}


def _last_proposal(rounds: list[dict[str, Any]]) -> dict[str, Any] | None:
    for r in reversed(rounds):
        raw = r.get("proposal")
        if not raw:
            continue
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _extract_size_pct(proposal: dict[str, Any]) -> float | None:
    actions = proposal.get("actions", [])
    if not actions:
        return None
    return actions[0].get("size_pct")


def _extract_risk_reward(proposal: dict[str, Any]) -> float | None:
    actions = proposal.get("actions", [])
    if not actions:
        return None
    a = actions[0]
    entry, stop, target = a.get("entry_price"), a.get("stop_loss"), a.get("take_profit")
    if None in (entry, stop, target):
        return None
    try:
        entry, stop, target = float(entry), float(stop), float(target)
    except (TypeError, ValueError):
        return None
    risk = abs(entry - stop)
    if risk == 0:
        return None
    return round(abs(target - entry) / risk, 4)
