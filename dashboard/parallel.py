"""Tiny ``run_parallel`` helper for the backtest page.

Two presets are independent: running them sequentially doubles wall clock for
no payoff. This runs each as a thread in a fixed pool, isolates failures so a
crash in one preset can't derail the other, and routes each preset's progress
events to its own callback.

Streamlit is thread-safe for `st.empty()` / `st.progress()` / `st.line_chart()`
mutations *if* the thread carrying the script context calls them. We don't
need that here — the dashboard's `_on_day` closure captures the placeholders
at submission time, and the worker thread invokes the callback directly.
Tested behaviour is the contract; the page is a thin renderer over it.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

# A worker takes the preset's display label and an event callback, returns
# anything (the actual backtest result, in practice).
PresetWorker = Callable[[str, Callable[[Any], None]], Any]


@dataclass(frozen=True)
class PresetOutcome:
    """Per-preset outcome from a parallel run."""

    result: Any | None = None
    error: BaseException | None = None


def run_parallel(
    jobs: dict[str, tuple[str, PresetWorker]],
    on_events: dict[str, Callable[[Any], None]] | None = None,
) -> dict[str, PresetOutcome]:
    """Run each ``(label, worker)`` job concurrently, returning per-slot
    outcomes.

    ``jobs`` is keyed by a slot name (``"a"`` / ``"b"`` in practice); each value
    is ``(display_label, worker_fn)``. ``on_events`` maps slot → callback; the
    worker receives a no-op callback if no entry is provided. Worker exceptions
    are captured on the corresponding ``PresetOutcome.error`` — they never
    propagate out, so one preset failing leaves the other free to finish.
    """
    on_events = on_events or {}
    noop: Callable[[Any], None] = lambda _e: None  # noqa: E731
    outcomes: dict[str, PresetOutcome] = {}

    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futures = {
            slot: pool.submit(worker, label, on_events.get(slot, noop))
            for slot, (label, worker) in jobs.items()
        }
        for slot, future in futures.items():
            try:
                outcomes[slot] = PresetOutcome(result=future.result())
            except BaseException as exc:  # noqa: BLE001 — isolate everything
                outcomes[slot] = PresetOutcome(error=exc)

    return outcomes
