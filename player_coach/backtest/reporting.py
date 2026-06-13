from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from player_coach.backtest.metrics import EquityCurve
from player_coach.backtest.regime_decomposition import decompose_by_regime
from player_coach.backtest.walk_forward import oos_returns, walk_forward_windows

if TYPE_CHECKING:
    from player_coach.backtest.runner import BacktestResult


def backtest_metrics(result: BacktestResult) -> dict[str, float]:
    """Labelled evaluation metrics for a backtest result.

    Single place the dashboard (and any ranking) reads the Phase 4A metrics from,
    so the display stays in sync with what the runner computes.
    """
    return {
        "total_return": result.total_pnl_pct,
        "max_drawdown": result.max_drawdown_pct,
        "sharpe": result.sharpe,
        "sortino": result.sortino,
        "calmar": result.calmar,
        "max_drawdown_duration": result.max_drawdown_duration,
        "avg_recovery_time": result.avg_recovery_time,
        "mc_success_prob": result.mc_success_prob,
    }


def regime_breakdown(result: BacktestResult) -> dict[str, dict[str, Any]]:
    """Per-regime decomposition (F19) of a result's exchanges."""
    return decompose_by_regime(result.exchanges)


def format_progress_status(payload: dict[str, Any]) -> str:
    """Render a one-line status from a runner ``on_day`` callback payload.

    Used by the dashboard's live progress panel; living here keeps it unit-tested
    so the Streamlit page stays a thin renderer.
    """
    day = payload.get("day")
    total = payload.get("total_days")
    date = payload.get("date") or ""
    capital = payload.get("capital", 0.0)
    phase = payload.get("challenge_phase") or "—"
    outcome = (payload.get("outcome") or "—").upper()
    reason = payload.get("termination_reason")
    aborts = int(payload.get("days_aborted", 0) or 0)
    mc = payload.get("mc_success_prob")
    parts = [
        f"Day {day}/{total}",
        date,
        f"${capital:,.0f}",
        f"phase {phase}",
        f"verdict {outcome}" + (f"·{reason}" if outcome == "ABORT" and reason else ""),
        f"{aborts} abort{'s' if aborts != 1 else ''}",
    ]
    if mc is not None:
        parts.append(f"P(pass) {mc:.0%}")
    return " · ".join(parts)


def walk_forward_report(
    equity_curve: EquityCurve, fit_days: int, eval_days: int
) -> dict[str, Any]:
    """Out-of-sample walk-forward summary (F15): slice the equity curve into
    anchored eval windows and report the fold count and a combined out-of-sample
    Sharpe (the headline anti-data-snooping number)."""
    windows = walk_forward_windows(len(equity_curve), fit_days, eval_days)
    returns = oos_returns([equity_curve[ev] for _, ev in windows])
    oos_sharpe = 0.0
    if returns:
        arr = np.asarray(returns, dtype=float)
        sd = float(arr.std())
        if sd > 0:
            oos_sharpe = float(arr.mean() / sd * np.sqrt(252))
    return {"folds": len(windows), "oos_sharpe": oos_sharpe}
