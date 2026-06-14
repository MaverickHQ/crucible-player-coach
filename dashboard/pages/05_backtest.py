from __future__ import annotations

import uuid
from datetime import date, timedelta

import streamlit as st

from dashboard.db import get_store

_PRESETS: dict[str, dict] = {
    "conservative": {
        "max_position_pct": 0.10,
        "max_single_trade_pct": 0.03,
        "max_leverage": 1.0,
        "max_drawdown_pct": 0.05,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 2,
        "min_risk_reward": 2.0,
        "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
        "max_rounds": 3,
    },
    "moderate": {
        "max_position_pct": 0.15,
        "max_single_trade_pct": 0.05,
        "max_leverage": 1.5,
        "max_drawdown_pct": 0.10,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 3,
        "min_risk_reward": 1.5,
        "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
        "max_rounds": 3,
    },
    "aggressive": {
        "max_position_pct": 0.25,
        "max_single_trade_pct": 0.10,
        "max_leverage": 2.0,
        "max_drawdown_pct": 0.20,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 5,
        "min_risk_reward": 1.0,
        "abort_on_violations": ["max_leverage"],
        "max_rounds": 3,
    },
}


def _render_record(rec: dict) -> None:
    a_label = rec.get("preset_a", "A")
    b_label = rec.get("preset_b", "B")

    metrics = [
        ("Approval rate", rec.get("approve_rate_a"), rec.get("approve_rate_b"), True,  "{:.1%}"),
        ("Avg rounds",    rec.get("avg_rounds_a"),   rec.get("avg_rounds_b"),   False, "{:.2f}"),
        ("Days aborted",  rec.get("days_aborted_a"), rec.get("days_aborted_b"), False, "{}"),
        ("Total return",  rec.get("total_return_a"), rec.get("total_return_b"), True,  "{:.2%}"),
        ("Max drawdown",  rec.get("max_drawdown_a"), rec.get("max_drawdown_b"), False, "{:.2%}"),
    ]

    col_label, col_a, col_b = st.columns([2, 1, 1])
    col_a.markdown(f"**{a_label}**")
    col_b.markdown(f"**{b_label}**")

    for name, val_a, val_b, higher_is_better, fmt in metrics:
        if val_a is None or val_b is None:
            continue
        str_a = fmt.format(val_a)
        str_b = fmt.format(val_b)
        if val_a > val_b:
            winner = "a" if higher_is_better else "b"
        elif val_b > val_a:
            winner = "b" if higher_is_better else "a"
        else:
            winner = None
        str_a = f"**{str_a}** ✓" if winner == "a" else str_a
        str_b = f"**{str_b}** ✓" if winner == "b" else str_b

        c1, c2, c3 = st.columns([2, 1, 1])
        c1.write(name)
        c2.write(str_a)
        c3.write(str_b)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _fmt_dd(value: float) -> str:
    """Format a drawdown fraction with enough precision to be informative.

    Tiny drawdowns (< 0.1%) would round to 0.0% under :.1%, making Sharpe/Calmar
    look paradoxical next to a "0% DD". Fall back to two decimal places for the
    small case so the reader can see what's actually there.
    """
    if 0.0 < value < 0.001:
        return f"{value:.2%}"
    return f"{value:.1%}"


def _render_metrics_panel(m: dict) -> None:
    """Render the Phase 4A evaluation metrics + regime breakdown for both runs."""
    from player_coach.backtest.reporting import metric_caveats, mode_label

    if m.get("mode"):
        st.caption(f"Backtest depth: **{mode_label(m['mode'])}**")
    st.markdown("**Risk-adjusted metrics**")
    for col, label, key in zip(
        st.columns(2), (m["label_a"], m["label_b"]), ("a", "b")
    ):
        with col:
            st.caption(label)
            mm = m[key]
            st.metric(
                "P(pass)", f"{mm['mc_success_prob']:.0%}",
                help=("Projected challenge pass probability from the realised "
                      "edge of this run. With losses, expect 0% — there are no "
                      "winning trades to extrapolate from."),
            )
            st.metric("Sharpe", f"{mm['sharpe']:.2f}")
            st.metric("Sortino", f"{mm['sortino']:.2f}")
            st.metric("Calmar", f"{mm['calmar']:.2f}")
            st.metric("Max DD", _fmt_dd(mm["max_drawdown"]))
            st.caption(
                f"DD duration {mm['max_drawdown_duration']}d · "
                f"avg recovery {mm['avg_recovery_time']:.1f}d"
            )
            for caveat in metric_caveats(mm):
                st.caption(f"ℹ️ {caveat}")
    st.markdown("**Walk-forward** (out-of-sample, 60/30 anchored)")
    for col, label, key in zip(
        st.columns(2), (m["label_a"], m["label_b"]), ("wf_a", "wf_b")
    ):
        with col:
            wf = m.get(key, {"oos_sharpe": 0.0, "folds": 0})
            st.caption(label)
            st.metric("OOS Sharpe", f"{wf['oos_sharpe']:.2f}",
                      help=f"{wf['folds']} fold(s)")

    st.markdown("**Regime breakdown** (count · approve rate)")
    for col, label, key in zip(
        st.columns(2), (m["label_a"], m["label_b"]), ("regime_a", "regime_b")
    ):
        with col:
            st.caption(label)
            breakdown = m[key]
            if breakdown:
                st.table([
                    {"regime": r, "count": d["count"],
                     "approve": f"{d['approve_rate']:.0%}"}
                    for r, d in breakdown.items()
                ])
            else:
                st.caption("no exchanges")


with st.sidebar:
    st.header("Backtest Parameters")
    preset_names = list(_PRESETS)
    preset_a = st.selectbox("Preset A", preset_names, index=0)
    preset_b = st.selectbox("Preset B", preset_names, index=2)
    symbol = st.selectbox("Symbol", ["AMZN", "MSFT", "TSLA", "BTC-USD"])
    default_end = date.today() - timedelta(days=1)
    # 6 months ≈ ~125 trading days — long enough for one walk-forward fold and
    # an HMM regime fit; users can shorten if they want a quick run.
    default_start = default_end - timedelta(days=180)
    start_date = st.date_input("Start date", value=default_start)
    end_date = st.date_input("End date", value=default_end)
    depth = st.radio(
        "Backtest depth",
        ["Fast (1 round)", "Standard (3 rounds)"],
        index=0,  # Fast is the new default — best for iteration
        help=(
            "Fast: max_rounds=1 — the Coach approves or rejects in one shot, "
            "no revisions. ~40–60% cheaper and faster, best for quick "
            "comparisons. Standard: max_rounds=3 — the Coach can ask the "
            "Player to revise, more realistic for serious A/B."
        ),
    )
    mode = "fast" if depth.startswith("Fast") else "standard"
    max_rounds = 1 if mode == "fast" else 3
    st.divider()
    run_clicked = st.button("Run Backtest", type="primary", width='stretch')

# ---------------------------------------------------------------------------
# Page title
# ---------------------------------------------------------------------------

st.title("Backtest")
st.caption("Compare two constraint presets over historical data side by side.")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if run_clicked:
    if not st.session_state.get("api_key_valid"):
        st.warning("Set your API key in Settings before running a backtest.")
    elif start_date >= end_date:
        st.error("Start date must be before end date.")
    else:
        # ~Trading-day estimate from the calendar gap (5/7 weekdays).
        from player_coach.backtest.reporting import short_range_warnings
        approx_business_days = max(
            1, int((end_date - start_date).days * 5 / 7)
        )
        for msg in short_range_warnings(approx_business_days):
            st.info(msg)
        from player_coach.agents.coach import CoachAgent
        from player_coach.agents.player import PlayerAgent
        from player_coach.artifacts.writer import ArtifactWriter
        from player_coach.backtest.compare import StrategyComparator
        from player_coach.backtest.runner import BacktestRunner
        from player_coach.constraints.schema import ConstraintSchema
        from player_coach.loop.coach_loop import CoachLoop

        api_key = st.session_state.api_key
        store = get_store()

        strategy_id_a = f"bt-{preset_a}-{symbol}-{start_date}-{uuid.uuid4().hex[:6]}"
        strategy_id_b = f"bt-{preset_b}-{symbol}-{start_date}-{uuid.uuid4().hex[:6]}"

        # Apply the selected depth — Fast (1 round) for iteration, Standard
        # (3 rounds) for full LLM revision fidelity.
        constraints_a = ConstraintSchema.from_dict(
            {**_PRESETS[preset_a], "max_rounds": max_rounds}
        )
        constraints_b = ConstraintSchema.from_dict(
            {**_PRESETS[preset_b], "max_rounds": max_rounds}
        )

        def _make_loop(key: str) -> CoachLoop:
            return CoachLoop(
                player=PlayerAgent(api_key=key),
                coach=CoachAgent(api_key=key),
                artifact_writer=ArtifactWriter("artifacts"),
            )

        from player_coach.backtest.reporting import format_progress_status

        # Pre-render BOTH preset panels so each has its own progress bar +
        # status caption + sparkline that fills concurrently while the threads
        # below race their respective runners.
        def _make_panel(label: str):
            st.markdown(f"### {label}")
            return {
                "bar": st.progress(0.0),
                "status": st.empty(),
                "chart": st.empty(),
                "equity": [],
            }

        panels = {"a": _make_panel(preset_a), "b": _make_panel(preset_b)}

        def _runner(strategy_id, constraints, panel):
            def _on_day(payload):
                panel["bar"].progress(
                    payload["day"] / max(1, payload["total_days"])
                )
                panel["status"].caption(format_progress_status(payload))
                panel["equity"].append(payload["capital"])
                if len(panel["equity"]) >= 2:
                    panel["chart"].line_chart(panel["equity"], height=120)

            return BacktestRunner(
                loop=_make_loop(api_key),
                db_store=store,
                strategy_id=strategy_id,
                on_day=_on_day,
            ).run(
                symbol=symbol,
                start_date=str(start_date),
                end_date=str(end_date),
                constraints=constraints,
            )

        from dashboard.recovery import save_snapshot
        from player_coach.backtest.reporting import (
            backtest_metrics,
            regime_breakdown,
            walk_forward_report,
        )

        def _persist_preset(label: str, result, other_label: str) -> dict:
            """Persist a single preset's result as soon as it finishes.

            Writes to disk (recovery), DB (Prior runs), and session_state — so a
            disconnect after this returns can't lose what we just earned.
            """
            metrics = backtest_metrics(result, mode=mode)
            preset_snapshot = {
                "label": label,
                "symbol": symbol,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "metrics": metrics,
                "regime": regime_breakdown(result),
                "wf": walk_forward_report(result.equity_curve, 60, 30),
                "equity_curve": [list(p) for p in result.equity_curve],
                "days_aborted": result.days_aborted,
                "total_return": result.total_pnl_pct,
                "max_drawdown": result.max_drawdown_pct,
            }
            save_snapshot(
                preset_snapshot, strategy_id=f"{label}-{symbol}-{start_date}",
            )
            # Mirror into session_state under per-preset keys so a fresh page
            # render can show "Latest results" even if only one preset finished.
            partial = st.session_state.get("last_metrics") or {
                "label_a": preset_a, "label_b": preset_b,
            }
            partial["mode"] = mode
            slot = "a" if label == preset_a else "b"
            partial[slot] = metrics
            partial[f"regime_{slot}"] = preset_snapshot["regime"]
            partial[f"wf_{slot}"] = preset_snapshot["wf"]
            st.session_state["last_metrics"] = partial
            st.session_state[f"last_result_{slot}"] = preset_snapshot
            return preset_snapshot

        # Run both presets in parallel — half the wall clock, no extra cost.
        # Failures are isolated per slot; one preset crashing leaves the other
        # free to finish and persist normally.
        from dashboard.parallel import run_parallel

        outcomes = run_parallel(
            {
                "a": (preset_a, lambda label, _on_event:
                      _runner(strategy_id_a, constraints_a, panels["a"])),
                "b": (preset_b, lambda label, _on_event:
                      _runner(strategy_id_b, constraints_b, panels["b"])),
            }
        )

        if outcomes["a"].error and outcomes["b"].error:
            st.error(f"Both backtests failed: {outcomes['a'].error}")
            st.stop()

        result_a = outcomes["a"].result
        result_b = outcomes["b"].result
        if outcomes["a"].error is not None:
            st.error(f"Backtest {preset_a} failed: {outcomes['a'].error}")
        else:
            snap_a = _persist_preset(preset_a, result_a, preset_b)
            st.success(
                f"{preset_a} finished — total return {snap_a['total_return']:.2%}, "
                f"P(pass) {snap_a['metrics']['mc_success_prob']:.0%}."
            )
        if outcomes["b"].error is not None:
            st.error(f"Backtest {preset_b} failed: {outcomes['b'].error}")
        else:
            snap_b = _persist_preset(preset_b, result_b, preset_a)

        # If either failed, we've persisted the survivor; bail before the
        # comparison (which needs both results).
        if outcomes["a"].error is not None or outcomes["b"].error is not None:
            st.stop()

        # Now both are saved; compute the side-by-side comparison.
        run_ids_a = [e["run_id"] for e in result_a.exchanges]
        run_ids_b = [e["run_id"] for e in result_b.exchanges]
        comparison = StrategyComparator(store).compare(
            run_ids_a=run_ids_a, run_ids_b=run_ids_b,
            label_a=preset_a, label_b=preset_b,
        )
        record = {
            "preset_a": preset_a, "preset_b": preset_b, "symbol": symbol,
            "start_date": str(start_date), "end_date": str(end_date),
            "approve_rate_a": comparison.approve_rate_a,
            "approve_rate_b": comparison.approve_rate_b,
            "avg_rounds_a": comparison.avg_rounds_a,
            "avg_rounds_b": comparison.avg_rounds_b,
            "days_aborted_a": result_a.days_aborted,
            "days_aborted_b": result_b.days_aborted,
            "total_return_a": result_a.total_pnl_pct,
            "total_return_b": result_b.total_pnl_pct,
            "max_drawdown_a": result_a.max_drawdown_pct,
            "max_drawdown_b": result_b.max_drawdown_pct,
        }
        store.save_backtest_result(record)
        st.session_state["last_backtest"] = record
        st.success(comparison.summary)

# ---------------------------------------------------------------------------
# Side-by-side results for last run
# ---------------------------------------------------------------------------

# Recovery banner — when the session has no last_backtest but there's a recent
# snapshot on disk, offer to rehydrate. Saves a previously-dropped 30-min run.
if not st.session_state.get("last_backtest"):
    from dashboard.recovery import list_recoverable
    _recoverable = list_recoverable()
    if _recoverable:
        from datetime import datetime
        _newest = _recoverable[0]
        _when = datetime.fromtimestamp(_newest["mtime"]).strftime("%H:%M:%S")
        _payload = _newest["payload"]
        with st.container(border=True):
            st.markdown(
                f"**Recoverable backtest** — `{_payload.get('label', '?')}` finished "
                f"at {_when} (return {_payload.get('total_return', 0):.2%})."
            )
            if st.button("Restore", key="recover_btn"):
                metrics = _payload.get("metrics", {})
                slot = "a"  # show recovered preset on the left
                st.session_state["last_metrics"] = {
                    "label_a": _payload.get("label", "recovered"),
                    "label_b": "—",
                    slot: metrics,
                    "b": {},
                    f"regime_{slot}": _payload.get("regime", {}),
                    "regime_b": {},
                    f"wf_{slot}": _payload.get("wf", {"oos_sharpe": 0.0, "folds": 0}),
                    "wf_b": {"oos_sharpe": 0.0, "folds": 0},
                }
                st.session_state["last_backtest"] = {
                    "preset_a": _payload.get("label", "recovered"),
                    "preset_b": "—",
                    "symbol": _payload.get("symbol"),
                    "start_date": _payload.get("start_date"),
                    "end_date": _payload.get("end_date"),
                    "approve_rate_a": 0.0, "approve_rate_b": 0.0,
                    "avg_rounds_a": 0.0, "avg_rounds_b": 0.0,
                    "days_aborted_a": _payload.get("days_aborted", 0),
                    "days_aborted_b": 0,
                    "total_return_a": _payload.get("total_return", 0.0),
                    "total_return_b": 0.0,
                    "max_drawdown_a": _payload.get("max_drawdown", 0.0),
                    "max_drawdown_b": 0.0,
                }
                st.rerun()

_last = st.session_state.get("last_backtest")
if _last:
    st.subheader("Latest results")
    _render_record(_last)
    _metrics = st.session_state.get("last_metrics")
    if _metrics:
        _render_metrics_panel(_metrics)

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Prior runs")
_history = get_store().get_backtest_results()

if not _history:
    st.caption("No backtest results yet.")
else:
    for rec in _history:
        label = (
            f"{rec['preset_a']} vs {rec['preset_b']} — "
            f"{rec['symbol']}  {rec['start_date']} → {rec['end_date']}"
        )
        with st.expander(label):
            _render_record(rec)
