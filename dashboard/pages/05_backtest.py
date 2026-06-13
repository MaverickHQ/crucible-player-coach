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

def _render_metrics_panel(m: dict) -> None:
    """Render the Phase 4A evaluation metrics + regime breakdown for both runs."""
    st.markdown("**Risk-adjusted metrics**")
    for col, label, key in zip(
        st.columns(2), (m["label_a"], m["label_b"]), ("a", "b")
    ):
        with col:
            st.caption(label)
            mm = m[key]
            st.metric("P(pass)", f"{mm['mc_success_prob']:.0%}")
            st.metric("Sharpe", f"{mm['sharpe']:.2f}")
            st.metric("Sortino", f"{mm['sortino']:.2f}")
            st.metric("Calmar", f"{mm['calmar']:.2f}")
            st.metric("Max DD", f"{mm['max_drawdown']:.1%}")
            st.caption(
                f"DD duration {mm['max_drawdown_duration']}d · "
                f"avg recovery {mm['avg_recovery_time']:.1f}d"
            )
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
    default_start = default_end - timedelta(days=29)
    start_date = st.date_input("Start date", value=default_start)
    end_date = st.date_input("End date", value=default_end)
    st.divider()
    run_clicked = st.button("Run Backtest", type="primary", use_container_width=True)

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

        constraints_a = ConstraintSchema.from_dict(_PRESETS[preset_a])
        constraints_b = ConstraintSchema.from_dict(_PRESETS[preset_b])

        def _make_loop(key: str) -> CoachLoop:
            return CoachLoop(
                player=PlayerAgent(api_key=key),
                coach=CoachAgent(api_key=key),
                artifact_writer=ArtifactWriter("artifacts"),
            )

        from player_coach.backtest.reporting import format_progress_status

        def _run_with_progress(label: str, strategy_id: str, constraints):
            st.markdown(f"**{label}**")
            bar = st.progress(0.0)
            status = st.empty()
            chart_slot = st.empty()
            equity: list[float] = []

            def _on_day(payload):
                bar.progress(payload["day"] / max(1, payload["total_days"]))
                status.caption(format_progress_status(payload))
                equity.append(payload["capital"])
                if len(equity) >= 2:
                    chart_slot.line_chart(equity, height=120)

            try:
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
            except Exception as exc:
                st.error(f"Backtest {label} failed: {exc}")
                st.stop()

        result_a = _run_with_progress(preset_a, strategy_id_a, constraints_a)
        result_b = _run_with_progress(preset_b, strategy_id_b, constraints_b)

        run_ids_a = [e["run_id"] for e in result_a.exchanges]
        run_ids_b = [e["run_id"] for e in result_b.exchanges]

        comparison = StrategyComparator(store).compare(
            run_ids_a=run_ids_a,
            run_ids_b=run_ids_b,
            label_a=preset_a,
            label_b=preset_b,
        )

        record = {
            "preset_a": preset_a,
            "preset_b": preset_b,
            "symbol": symbol,
            "start_date": str(start_date),
            "end_date": str(end_date),
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

        from player_coach.backtest.reporting import (
            backtest_metrics,
            regime_breakdown,
            walk_forward_report,
        )
        st.session_state["last_metrics"] = {
            "label_a": preset_a,
            "label_b": preset_b,
            "a": backtest_metrics(result_a),
            "b": backtest_metrics(result_b),
            "regime_a": regime_breakdown(result_a),
            "regime_b": regime_breakdown(result_b),
            "wf_a": walk_forward_report(result_a.equity_curve, 60, 30),
            "wf_b": walk_forward_report(result_b.equity_curve, 60, 30),
        }
        st.success(comparison.summary)

# ---------------------------------------------------------------------------
# Side-by-side results for last run
# ---------------------------------------------------------------------------

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
