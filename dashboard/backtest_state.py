"""Pure state-shape helpers backing dashboard/pages/05_backtest.py.

The page mixes Streamlit glue with state-shape logic; this module owns the
state-shape pieces in isolation. Each helper covers a specific finding from
the locked code-review backlog (2026-06-15):

- N3 ``artifact_dir_for``        — per-strategy artifact path, no race.
- R1 ``persist_slot``             — slot is a parameter, never derived.
- R2 ``recovered_metrics_state``  — single-preset recovery, None for B.
- R2 ``recovered_last_backtest``  — same, on the comparison record.
- N4 ``metrics_panel_slots``      — skip missing slots, no KeyError.
- N8 ``fresh_metrics_state``      — Run click scrubs the prior dict.

The module deliberately does NOT import streamlit — every helper is a pure
function of its inputs, so it can be unit-tested without spinning up the
session machinery.
"""
from __future__ import annotations

from typing import Any


def fresh_metrics_state(preset_a: str, preset_b: str, mode: str) -> dict[str, Any]:
    """N8 — return a fresh per-run metrics scaffold.

    The Run-click handler installs this dict so a stale ``b`` slot from a
    previous run can't shadow the new run's A while B is still in flight.
    The previous code merged into the existing ``last_metrics`` via
    ``or {...}`` fallback, which preserved old slot data across runs.
    """
    return {
        "label_a": preset_a,
        "label_b": preset_b,
        "mode": mode,
    }


def persist_slot(
    state: dict[str, Any],
    slot: str,
    metrics: dict[str, Any],
    regime: dict[str, Any],
    wf: dict[str, Any],
) -> dict[str, Any]:
    """R1 — write a preset's metrics into its slot of a metrics dict.

    Uses the ``slot`` argument directly ("a" or "b") — never derives slot
    from label equality. The previous code resolved slot by comparing the
    finishing preset's label to ``preset_a``; when the user picked the same
    preset name for both selectboxes, both writes landed in slot "a" and
    silently dropped B. The dict literal at ``run_parallel({"a":..., "b":...})``
    already names the slot — thread that through and the bug disappears.
    """
    state[slot] = metrics
    state[f"regime_{slot}"] = regime
    state[f"wf_{slot}"] = wf
    return state


def recovered_metrics_state(payload: dict[str, Any]) -> dict[str, Any]:
    """R2 — rehydrate ``last_metrics`` from a single-preset recovery snapshot.

    The surviving preset goes into slot ``a``; slot ``b`` stays None (not
    a placeholder dict or 0.0) so the side-by-side comparison's None-guard
    skips comparison rows rather than rendering a phantom '—' preset that
    "beats" the recovered run on every lower-is-better metric.
    """
    return {
        "label_a": payload.get("label", "recovered"),
        "label_b": "—",
        "mode": payload.get("mode"),
        "a": payload.get("metrics", {}),
        "b": None,
        "regime_a": payload.get("regime", {}),
        "regime_b": None,
        "wf_a": payload.get("wf", {"oos_sharpe": 0.0, "folds": 0}),
        "wf_b": None,
    }


def recovered_last_backtest(payload: dict[str, Any]) -> dict[str, Any]:
    """R2 — rehydrate the ``last_backtest`` comparison record.

    All ``_b`` numeric fields are None for a single-preset recovery; the
    comparison row's None-guard then skips them. Previous code set
    ``total_return_b=0.0``, ``max_drawdown_b=0.0``, ``days_aborted_b=0`` —
    valid numbers that compared favourably against the recovered preset
    on every lower-is-better metric, flagging '—' as the winner.
    """
    return {
        "preset_a": payload.get("label", "recovered"),
        "preset_b": "—",
        "symbol": payload.get("symbol"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "approve_rate_a": 0.0,
        "approve_rate_b": None,
        "avg_rounds_a": 0.0,
        "avg_rounds_b": None,
        "days_aborted_a": payload.get("days_aborted", 0),
        "days_aborted_b": None,
        "total_return_a": payload.get("total_return", 0.0),
        "total_return_b": None,
        "max_drawdown_a": payload.get("max_drawdown", 0.0),
        "max_drawdown_b": None,
    }


def metrics_panel_slots(m: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """N4 — yield ``(label, slot_key, slot_data)`` for the metrics panel,
    skipping slots whose data is missing, empty, or None.

    ``_render_metrics_panel`` previously indexed ``m['a']`` / ``m['b']``
    unconditionally; partial persistence (one preset errored mid-run, or
    a single-preset recovery) left a slot absent and the page crashed
    with KeyError on the next render.
    """
    out: list[tuple[str, str, dict[str, Any]]] = []
    for slot in ("a", "b"):
        data = m.get(slot)
        if not data:
            continue
        label = m.get(f"label_{slot}") or slot.upper()
        out.append((label, slot, data))
    return out


def artifact_dir_for(strategy_id: str, base: str = "artifacts") -> str:
    """N3 — per-strategy artifact directory.

    Both parallel presets shared a single ``artifacts/`` root and could race
    on filenames (last-write-wins on day-stamped artifact files). Scoping
    each writer to ``<base>/<strategy_id>`` isolates them; strategy IDs
    already carry a uuid suffix so distinct presets produce distinct paths.

    Filesystem-unsafe characters are replaced with ``-``.
    """
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in strategy_id)
    safe = safe.strip("-") or "snapshot"
    return f"{base}/{safe}"
