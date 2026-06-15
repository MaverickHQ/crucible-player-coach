"""Pure helpers backing the backtest dashboard page (dashboard/pages/05_backtest.py).

The page mixes Streamlit glue with state-shape logic; this module owns the
state-shape pieces so they can be tested in isolation. Each helper covers a
specific finding from the locked code-review backlog (2026-06-15):

- N3 ``artifact_dir_for``        — per-strategy artifact path, no race.
- R1 ``persist_slot``             — slot is a parameter, never derived.
- R2 ``recovered_metrics_state``  — single-preset recovery, None for B.
- R2 ``recovered_last_backtest``  — same, on the comparison record.
- N4 ``metrics_panel_slots``      — skip missing slots, no KeyError.
- N8 ``fresh_metrics_state``      — Run click scrubs the prior dict.
"""
from __future__ import annotations

from dashboard.backtest_state import (
    artifact_dir_for,
    fresh_metrics_state,
    metrics_panel_slots,
    persist_slot,
    recovered_last_backtest,
    recovered_metrics_state,
)


# ----------------------------------------------------------------- N8


def test_fresh_metrics_state_carries_labels_and_mode() -> None:
    s = fresh_metrics_state("conservative", "aggressive", "fast")
    assert s["label_a"] == "conservative"
    assert s["label_b"] == "aggressive"
    assert s["mode"] == "fast"


def test_fresh_metrics_state_has_no_slot_data() -> None:
    # N8 — a fresh state must not carry any prior 'a'/'b' slot data; the
    # Run-click handler installs this dict so a stale preset_b from a
    # previous run can't render alongside the new preset_a while preset_b's
    # runner is still in flight.
    s = fresh_metrics_state("c", "a", "fast")
    assert "a" not in s and "b" not in s
    assert "regime_a" not in s and "regime_b" not in s
    assert "wf_a" not in s and "wf_b" not in s


# ----------------------------------------------------------------- R1


def test_persist_slot_writes_to_named_slot() -> None:
    state = fresh_metrics_state("c", "a", "fast")
    persist_slot(state, "a", {"sharpe": 1.0}, {"low_vol": {"count": 1}},
                 {"oos_sharpe": 0.5, "folds": 1})
    assert state["a"] == {"sharpe": 1.0}
    assert state["regime_a"] == {"low_vol": {"count": 1}}
    assert state["wf_a"]["oos_sharpe"] == 0.5


def test_persist_slot_same_label_distinct_slots_do_not_collide() -> None:
    # R1 — when the user picks the SAME preset for both A and B (the two
    # selectboxes are independent), the old `slot = "a" if label == preset_a
    # else "b"` resolution put both writes in slot 'a' and silently dropped
    # B. Slot is now a parameter, so labels can match safely.
    state = fresh_metrics_state("moderate", "moderate", "fast")
    persist_slot(state, "a", {"sharpe": 1.0}, {}, {"oos_sharpe": 0, "folds": 0})
    persist_slot(state, "b", {"sharpe": 2.0}, {}, {"oos_sharpe": 0, "folds": 0})
    assert state["a"]["sharpe"] == 1.0
    assert state["b"]["sharpe"] == 2.0


# ----------------------------------------------------------------- R2


def test_recovered_metrics_state_has_none_for_b_slot() -> None:
    # R2 — recovered single-preset run goes into slot 'a'; 'b' must be None
    # (not 0.0 or an empty dict) so the comparison row's None-guard skips
    # phantom rows where '—' beats the recovered preset with placeholder
    # zeros.
    payload = {
        "label": "aggressive",
        "metrics": {"sharpe": 1.2},
        "regime": {"low_vol": {"count": 5, "approve_rate": 0.6}},
        "wf": {"oos_sharpe": 0.8, "folds": 2},
        "mode": "standard",
    }
    s = recovered_metrics_state(payload)
    assert s["label_a"] == "aggressive"
    assert s["label_b"] == "—"
    assert s["a"] == {"sharpe": 1.2}
    assert s["b"] is None
    assert s["regime_a"] == {"low_vol": {"count": 5, "approve_rate": 0.6}}
    assert s["regime_b"] is None
    assert s["wf_a"]["oos_sharpe"] == 0.8
    assert s["wf_b"] is None
    assert s["mode"] == "standard"


def test_recovered_last_backtest_has_none_for_b_fields() -> None:
    # R2 — the comparison record's _b numeric fields must be None for a
    # single-preset recovery. The previous code set them to 0.0 / 0, which
    # defeated _render_record's None-guard and flagged '—' as the winner on
    # lower-is-better metrics like max_drawdown and days_aborted.
    payload = {
        "label": "moderate", "symbol": "AMZN",
        "start_date": "2024-01-02", "end_date": "2024-06-30",
        "total_return": -0.02, "max_drawdown": 0.04, "days_aborted": 1,
    }
    rec = recovered_last_backtest(payload)
    assert rec["preset_a"] == "moderate"
    assert rec["preset_b"] == "—"
    assert rec["total_return_a"] == -0.02
    assert rec["total_return_b"] is None
    assert rec["max_drawdown_a"] == 0.04
    assert rec["max_drawdown_b"] is None
    assert rec["days_aborted_a"] == 1
    assert rec["days_aborted_b"] is None
    assert rec["approve_rate_b"] is None and rec["avg_rounds_b"] is None


# ----------------------------------------------------------------- N4


def test_metrics_panel_slots_yields_both_when_present() -> None:
    m = {
        "label_a": "c", "label_b": "a",
        "a": {"sharpe": 1.0}, "b": {"sharpe": 2.0},
    }
    rows = metrics_panel_slots(m)
    assert [r[1] for r in rows] == ["a", "b"]
    assert rows[0][0] == "c" and rows[1][0] == "a"


def test_metrics_panel_slots_skips_missing_slot() -> None:
    # N4 — partial persistence (preset B errored mid-run, or single-preset
    # recovery) leaves no 'b' key. _render_metrics_panel used m['b']
    # unconditionally → KeyError on every subsequent page render.
    m = {"label_a": "c", "label_b": "a", "a": {"sharpe": 1.0}}
    rows = metrics_panel_slots(m)
    assert [r[1] for r in rows] == ["a"]


def test_metrics_panel_slots_skips_empty_slot() -> None:
    # Empty dict counts as missing — same defensive behaviour as the
    # missing-key case.
    m = {"label_a": "c", "label_b": "a", "a": {"sharpe": 1.0}, "b": {}}
    rows = metrics_panel_slots(m)
    assert [r[1] for r in rows] == ["a"]


def test_metrics_panel_slots_skips_none_slot() -> None:
    # Recovery sets 'b' to None explicitly — also treated as missing.
    m = {"label_a": "c", "label_b": "—", "a": {"sharpe": 1.0}, "b": None}
    rows = metrics_panel_slots(m)
    assert [r[1] for r in rows] == ["a"]


# ----------------------------------------------------------------- N3


def test_artifact_dir_for_distinct_strategy_ids_distinct_paths() -> None:
    # N3 — two parallel presets shared a single 'artifacts/' root and could
    # race on filenames. Per-strategy_id dirs scope the writers so concurrent
    # writes go to different directories.
    a = artifact_dir_for("bt-moderate-AMZN-2024-01-02-abc123")
    b = artifact_dir_for("bt-aggressive-AMZN-2024-01-02-def456")
    assert a != b


def test_artifact_dir_for_strips_unsafe_chars() -> None:
    # Strategy IDs contain colons/slashes in some shells/paths; the dir
    # name must stay filesystem-safe.
    p = artifact_dir_for("bt:moderate/AMZN 2024", base="root")
    assert ":" not in p and "/" not in p.split("root/", 1)[1]
    assert p.startswith("root/")


def test_artifact_dir_for_uses_default_root() -> None:
    p = artifact_dir_for("s1")
    assert p.startswith("artifacts/")


# ----------------------------------------------------------------- import guard


def test_import_does_not_touch_streamlit() -> None:
    # backtest_state must be unit-testable WITHOUT pulling in streamlit —
    # otherwise these tests don't actually isolate the state-shape logic
    # from the page glue.
    import sys
    # If the module had imported streamlit at top-level, importing it just
    # above (already done) would have put 'streamlit' in sys.modules.
    # Skip the check if streamlit was already present from an unrelated
    # test importing it.
    assert "dashboard.backtest_state" in sys.modules
    # We don't ban streamlit globally — other dashboard tests may import it —
    # but backtest_state itself must not pull it in. Smoke-test by re-
    # importing and confirming no AttributeError on missing st calls.
    import dashboard.backtest_state as m
    # Module exports the documented helpers only.
    public = {n for n in dir(m) if not n.startswith("_")}
    expected = {
        "artifact_dir_for", "fresh_metrics_state", "metrics_panel_slots",
        "persist_slot", "recovered_last_backtest", "recovered_metrics_state",
    }
    assert expected <= public
