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


# Minimum spans for the Phase 4A surfacing layers to produce non-trivial output.
# F15 walk-forward needs at least fit+eval (60+30) days for one fold;
# F6 HMM needs 30 daily returns (i.e. ~31 bars) to fit its 2-state model.
_WALK_FORWARD_MIN_DAYS = 90
_REGIME_MIN_DAYS = 31


def short_range_warnings(business_days: int) -> list[str]:
    """User-facing warnings when the chosen backtest range is too short to
    produce non-trivial 4A surfacing — empty when the window is ample."""
    msgs: list[str] = []
    if business_days < _WALK_FORWARD_MIN_DAYS:
        msgs.append(
            f"Walk-forward needs at least {_WALK_FORWARD_MIN_DAYS} trading days "
            f"for one fold; only {business_days} requested → OOS Sharpe will be 0."
        )
    if business_days < _REGIME_MIN_DAYS:
        msgs.append(
            f"Regime detection needs at least {_REGIME_MIN_DAYS} trading days "
            f"before the HMM can fit; before that the label stays 'unknown'."
        )
    return msgs


def metric_caveats(metrics: dict[str, float]) -> list[str]:
    """Caveats to display next to the metrics panel — explains apparent
    paradoxes (tiny drawdown but big Calmar, 0% P(pass) on a losing run) so the
    reader can tell *data* limits from *code* problems."""
    out: list[str] = []
    mdd = float(metrics.get("max_drawdown", 0.0))
    # 0 < mdd < 0.001 (0.1%) — the panel rounds it to 0.0% but Sharpe/Calmar
    # still divide by it, producing apparently mysterious values.
    if 0.0 < mdd < 0.001:
        out.append(
            "Max drawdown is tiny (<0.1%) — Sharpe / Calmar magnify near-zero "
            "denominators and may look out of scale."
        )
    if (float(metrics.get("mc_success_prob", 0.0)) == 0.0
            and float(metrics.get("total_return", 0.0)) <= 0.0):
        out.append(
            "P(pass) = 0% is the expected projection from a loss — the realised "
            "edge has no winning trades to extrapolate from."
        )
    return out


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
