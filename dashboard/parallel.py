"""Tiny ``run_parallel`` helper for the backtest page.

Two presets are independent: running them sequentially doubles wall clock for
no payoff. This runs each as a thread in a fixed pool, isolates failures so a
crash in one preset can't derail the other, and routes each preset's progress
events to its own callback.

R3 — Streamlit widget mutations (`st.empty()`, `st.progress()`,
`st.line_chart()`) made from a thread without a ScriptRunContext attached are
silently dropped on Streamlit ≥1.25 (logs `NoSessionContext` and updates the
wrong session). The dashboard's `_on_day` closure mutates exactly such
widgets, so the page needs to attach its own ctx to each worker thread before
the worker runs. ``thread_init`` is the seam: a Streamlit-agnostic callable
the caller can wire to ``add_script_run_ctx(threading.current_thread(), ctx)``.
"""
from __future__ import annotations

import threading
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
    thread_init: Callable[[], None] | None = None,
) -> dict[str, PresetOutcome]:
    """Run each ``(label, worker)`` job concurrently, returning per-slot
    outcomes.

    ``jobs`` is keyed by a slot name (``"a"`` / ``"b"`` in practice); each value
    is ``(display_label, worker_fn)``. ``on_events`` maps slot → callback; the
    worker receives a no-op callback if no entry is provided. Worker exceptions
    are captured on the corresponding ``PresetOutcome.error`` — they never
    propagate out, so one preset failing leaves the other free to finish.

    ``thread_init`` is called once per worker thread, on that thread, before
    the worker runs. The dashboard uses this to attach a Streamlit
    ScriptRunContext via ``add_script_run_ctx(threading.current_thread(), ctx)``
    so widget mutations the worker fires (progress bar, sparkline) land in
    the right session. An exception inside ``thread_init`` is swallowed so a
    Streamlit-internals change can't crash a long backtest — the observable
    failure mode becomes "progress UI looks frozen", not "run aborted".
    """
    on_events = on_events or {}
    noop: Callable[[Any], None] = lambda _e: None  # noqa: E731
    outcomes: dict[str, PresetOutcome] = {}

    def _attached(worker: PresetWorker, label: str,
                  on_event: Callable[[Any], None]) -> Any:
        if thread_init is not None:
            try:
                thread_init()
            except Exception:
                # Surface as "UI silent" rather than "run dies". A future
                # Streamlit version that moves add_script_run_ctx would
                # otherwise abort every parallel backtest on first call.
                pass
        return worker(label, on_event)

    # Re-create the thread pool per call (matches the prior behaviour); each
    # worker carries the attached ctx so per-call workers see the right
    # session even if Streamlit reuses thread pool threads internally elsewhere.
    with ThreadPoolExecutor(
        max_workers=max(1, len(jobs)),
        thread_name_prefix="bt-preset",
    ) as pool:
        futures = {
            slot: pool.submit(_attached, worker, label,
                              on_events.get(slot, noop))
            for slot, (label, worker) in jobs.items()
        }
        for slot, future in futures.items():
            try:
                outcomes[slot] = PresetOutcome(result=future.result())
            except BaseException as exc:  # noqa: BLE001 — isolate everything
                outcomes[slot] = PresetOutcome(error=exc)

    return outcomes


# Silence the unused-import lint; ``threading`` is part of the public contract
# documented in the docstring (callers wire `threading.current_thread()` into
# `add_script_run_ctx`).
_ = threading
