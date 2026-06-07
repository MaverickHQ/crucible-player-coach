from __future__ import annotations

from typing import Any

from player_coach.constraints.schema import ConstraintSchema

_EPS = 1e-9
_ENTRY_TYPES = ("enter_long", "enter_short")


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_constraints(
    proposal: dict[str, Any],
    constraints: ConstraintSchema,
    world_state: dict[str, Any],
) -> list[str]:
    """Deterministically check a proposal against the numeric constraints.

    Returns the list of breached constraint names (empty if compliant). This is
    the mechanical, LLM-independent guarantee layered under the adversarial
    Coach: the model advises, but it cannot approve a proposal that violates the
    numbers. Soft preferences (VWAP) are never reported here. Checks that cannot
    be evaluated for missing data (e.g. ATR when ``atr`` is null, or risk/reward
    when prices are absent) are skipped rather than failed.
    """
    violations: list[str] = []

    def add(name: str) -> None:
        if name not in violations:
            violations.append(name)

    actions = proposal.get("actions", []) or []
    entries = [a for a in actions if a.get("action_type") in _ENTRY_TYPES]
    if not entries:
        return violations

    # allowed_symbols
    if any(a.get("symbol") not in constraints.allowed_symbols for a in entries):
        add("allowed_symbols")

    # max_single_trade_pct
    for a in entries:
        size = _to_float(a.get("size_pct"))
        if size is not None and size > constraints.max_single_trade_pct + _EPS:
            add("max_single_trade_pct")
            break

    # max_open_positions — existing book plus the proposed entries
    existing = len(world_state.get("open_positions", []) or [])
    if existing + len(entries) > constraints.max_open_positions:
        add("max_open_positions")

    # max_position_pct — total proposed exposure
    total = sum((_to_float(a.get("size_pct")) or 0.0) for a in entries)
    if total > constraints.max_position_pct + _EPS:
        add("max_position_pct")

    # min_risk_reward
    for a in entries:
        entry = _to_float(a.get("entry_price"))
        stop = _to_float(a.get("stop_loss"))
        target = _to_float(a.get("take_profit"))
        if None in (entry, stop, target):
            continue
        risk = abs(entry - stop)
        if risk == 0.0:
            continue
        if abs(target - entry) / risk + _EPS < constraints.min_risk_reward:
            add("min_risk_reward")
            break

    # min_stop_atr_multiple — only when ATR is available
    atr = _to_float(world_state.get("atr"))
    if atr is not None and atr > 0.0:
        floor = constraints.min_stop_atr_multiple * atr
        for a in entries:
            entry = _to_float(a.get("entry_price"))
            stop = _to_float(a.get("stop_loss"))
            if None in (entry, stop):
                continue
            if abs(entry - stop) + _EPS < floor:
                add("min_stop_atr_multiple")
                break

    return violations
