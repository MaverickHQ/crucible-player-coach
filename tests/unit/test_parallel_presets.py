"""T2 — parallel preset execution helper.

The dashboard's two presets are independent — running them sequentially doubles
wall clock for no benefit. ``run_parallel`` runs them concurrently in a thread
pool, returning a per-preset result dict. Failures are isolated (one preset
crashing must not derail the other), and per-preset callbacks remain wired so
the dashboard's progress bars and sparklines keep updating live.
"""
from __future__ import annotations

import threading
import time

from dashboard.parallel import PresetOutcome, run_parallel


# ----------------------------------------------------------------- concurrency

def test_run_parallel_actually_runs_concurrently():
    # Two jobs that each sleep 0.4s sequentially would take ~0.8s; concurrently
    # ~0.4s. Allow generous headroom for CI jitter.
    def slow(_label, _on_event):
        time.sleep(0.4)
        return "ok"

    start = time.monotonic()
    out = run_parallel({"a": ("A", slow), "b": ("B", slow)})
    elapsed = time.monotonic() - start

    assert elapsed < 0.7, f"sequential — took {elapsed:.2f}s, expected <0.7"
    assert out["a"].result == "ok"
    assert out["b"].result == "ok"
    assert out["a"].error is None
    assert out["b"].error is None


# ------------------------------------------------------------ failure isolation

def test_failure_in_one_preset_does_not_kill_the_other():
    def winner(_label, _on_event):
        return "won"

    def loser(_label, _on_event):
        raise RuntimeError("boom")

    out = run_parallel({"a": ("A", winner), "b": ("B", loser)})

    assert out["a"].result == "won" and out["a"].error is None
    assert out["b"].result is None
    assert "boom" in str(out["b"].error)


def test_both_failing_returns_both_errors():
    def boom_a(_label, _on_event):
        raise ValueError("a-bad")

    def boom_b(_label, _on_event):
        raise ValueError("b-bad")

    out = run_parallel({"a": ("A", boom_a), "b": ("B", boom_b)})
    assert "a-bad" in str(out["a"].error)
    assert "b-bad" in str(out["b"].error)


# ------------------------------------------------------ callback / payload isolation

def test_per_preset_callbacks_do_not_cross_talk():
    # Each preset's on_event payload must include its own slot key — never the
    # other's. Lock guards list mutation under the thread pool.
    lock = threading.Lock()
    seen: dict[str, list[str]] = {"a": [], "b": []}

    def worker(label, on_event):
        for tag in ("start", "mid", "end"):
            on_event(f"{label}:{tag}")
        return label

    def cb_factory(slot):
        def cb(msg):
            with lock:
                seen[slot].append(msg)
        return cb

    run_parallel(
        {"a": ("A", worker), "b": ("B", worker)},
        on_events={"a": cb_factory("a"), "b": cb_factory("b")},
    )

    # Each preset's callback received only its own messages.
    assert all(m.startswith("A:") for m in seen["a"]), seen["a"]
    assert all(m.startswith("B:") for m in seen["b"]), seen["b"]
    assert len(seen["a"]) == 3
    assert len(seen["b"]) == 3


def test_returns_preset_outcome_objects():
    out = run_parallel({"a": ("A", lambda _l, _e: 1)})
    assert isinstance(out["a"], PresetOutcome)


# ------------------------------------------------ R3: thread_init for ScriptRunContext


def test_thread_init_runs_once_per_submit():
    # R3 — the dashboard's worker threads call Streamlit widget mutations
    # (panel["bar"].progress, .caption, .line_chart). Without a
    # ScriptRunContext attached, those mutations silently no-op on
    # Streamlit ≥1.25 (the progress UI looks frozen on Cloud). The fix is
    # a ``thread_init`` hook called once per submit before the worker
    # runs; the page passes a lambda that calls add_script_run_ctx so the
    # ctx is reattached every time, even if the pool reuses a thread.
    lock = threading.Lock()
    init_threads: list[int] = []

    def init():
        with lock:
            init_threads.append(threading.get_ident())

    def worker(_label, _on_event):
        # Sleep so both workers stay alive concurrently — guarantees the
        # pool spins up two threads, matching real backtests (long I/O on
        # every bar).
        time.sleep(0.2)
        return "ok"

    run_parallel(
        {"a": ("A", worker), "b": ("B", worker)},
        thread_init=init,
    )
    # Two submits → two thread-init invocations, one per concurrent worker.
    assert len(init_threads) == 2
    assert len(set(init_threads)) == 2


def test_thread_init_runs_before_worker_on_same_thread():
    # R3 — init must run BEFORE the worker on the SAME thread (otherwise
    # the worker's widget mutations fire without a ctx). Capture an
    # ordered event log keyed by thread id.
    lock = threading.Lock()
    events: list[tuple[int, str]] = []

    def init():
        with lock:
            events.append((threading.get_ident(), "init"))

    def worker(_label, _on_event):
        with lock:
            events.append((threading.get_ident(), "work"))
        return "ok"

    run_parallel(
        {"a": ("A", worker), "b": ("B", worker)},
        thread_init=init,
    )
    # For each thread, init appears strictly before work.
    by_thread: dict[int, list[str]] = {}
    for tid, kind in events:
        by_thread.setdefault(tid, []).append(kind)
    for tid, ordered in by_thread.items():
        assert ordered.index("init") < ordered.index("work"), (
            f"thread {tid}: init must precede work, got {ordered}"
        )


def test_thread_init_none_is_backwards_compatible():
    # R3 — existing callers don't pass thread_init; the helper must keep
    # working unchanged (otherwise we break every existing test in this
    # file).
    out = run_parallel({"a": ("A", lambda _l, _e: 42)})
    assert out["a"].result == 42


def test_thread_init_failure_does_not_kill_worker():
    # R3 — Streamlit internals change between versions; if the
    # ctx-attach call fails (e.g. private API moved), the page's
    # observable behaviour should be "progress bar doesn't update",
    # not "backtest crashes". The worker still runs to completion.
    def init():
        raise RuntimeError("streamlit API moved")

    out = run_parallel(
        {"a": ("A", lambda _l, _e: "won")},
        thread_init=init,
    )
    assert out["a"].result == "won"
    assert out["a"].error is None
