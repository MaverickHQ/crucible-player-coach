from __future__ import annotations

from player_coach.backtest.reporting import (
    backtest_metrics,
    format_progress_status,
    metric_caveats,
    regime_breakdown,
    short_range_warnings,
    walk_forward_report,
)
from player_coach.backtest.runner import BacktestResult


def _result(**over) -> BacktestResult:
    base = dict(
        symbol="AMZN", start_date="2024-01-01", end_date="2024-02-01",
        strategy_id="s", days_run=20, days_aborted=0, total_exchanges=20,
        final_capital=106_000.0, total_pnl=6_000.0, total_pnl_pct=0.06,
        max_drawdown_pct=0.04,
    )
    base.update(over)
    return BacktestResult(**base)


def test_backtest_metrics_surfaces_all_evaluation_fields():
    r = _result(sharpe=1.5, sortino=2.1, calmar=1.2, max_drawdown_duration=7,
                avg_recovery_time=3.5, mc_success_prob=0.55)
    m = backtest_metrics(r)
    assert m["total_return"] == 0.06
    assert m["max_drawdown"] == 0.04
    assert m["sharpe"] == 1.5
    assert m["sortino"] == 2.1
    assert m["calmar"] == 1.2
    assert m["max_drawdown_duration"] == 7
    assert m["avg_recovery_time"] == 3.5
    assert m["mc_success_prob"] == 0.55


def test_regime_breakdown_groups_result_exchanges():
    exchanges = [
        {"world_state": {"regime_label": "low_vol"}, "outcome": "APPROVE"},
        {"world_state": {"regime_label": "high_vol"}, "outcome": "REJECT-MAX"},
    ]
    b = regime_breakdown(_result(exchanges=exchanges))
    assert b["low_vol"]["count"] == 1
    assert b["low_vol"]["approve_rate"] == 1.0
    assert b["high_vol"]["approve_rate"] == 0.0


def test_regime_breakdown_empty_for_no_exchanges():
    assert regime_breakdown(_result()) == {}


def test_walk_forward_report_counts_folds_and_oos_sharpe():
    curve = [("d", float(100 + i)) for i in range(150)]  # rising
    rep = walk_forward_report(curve, fit_days=60, eval_days=30)
    assert rep["folds"] == 3
    assert rep["oos_sharpe"] > 0  # out-of-sample returns are all positive


def test_walk_forward_report_zero_folds_when_too_short():
    rep = walk_forward_report([("d", 100.0)] * 50, fit_days=60, eval_days=30)
    assert rep["folds"] == 0
    assert rep["oos_sharpe"] == 0.0


# ---------------------------------------------------------------- progress

def _payload(**over) -> dict:
    base = dict(
        day=7, total_days=20, date="2024-01-10", capital=102_500.0,
        daily_pnl=125.0, challenge_phase="building", outcome="APPROVE",
        termination_reason=None, days_aborted=1, mc_success_prob=0.62,
    )
    base.update(over); return base


def test_progress_status_contains_key_fields():
    s = format_progress_status(_payload())
    assert "Day 7/20" in s
    assert "2024-01-10" in s
    assert "$102,500" in s
    assert "building" in s
    assert "1 abort" in s


def test_progress_status_reports_abort_reason():
    s = format_progress_status(_payload(outcome="ABORT",
                                       termination_reason="mll_breached"))
    assert "abort" in s.lower()
    assert "mll_breached" in s


def test_progress_status_handles_missing_mc_prob():
    s = format_progress_status(_payload(mc_success_prob=None))
    # No KeyError, no None leaking into the string.
    assert "None" not in s


# ---------------------------------------------------- short-range guidance (#3)

def test_short_range_flags_walk_forward_when_under_90_days():
    w = short_range_warnings(30)
    assert any("walk-forward" in m.lower() for m in w)


def test_short_range_flags_regime_when_under_30_days():
    w = short_range_warnings(20)
    assert any("regime" in m.lower() for m in w)


def test_short_range_quiet_for_ample_window():
    assert short_range_warnings(180) == []


# --------------------------------------------- metric caveats (#1 / #4)

def test_metric_caveats_flags_tiny_max_drawdown():
    # A tiny but non-zero DD makes Sharpe/Calmar look mysteriously large.
    caveats = metric_caveats({
        "max_drawdown": 0.0004, "sharpe": -2.59,
        "mc_success_prob": 0.5, "total_return": -0.0003,
    })
    assert any("drawdown" in c.lower() and "tiny" in c.lower() for c in caveats)


def test_metric_caveats_explains_zero_pass_prob_on_losses():
    caveats = metric_caveats({
        "max_drawdown": 0.05, "sharpe": -1.0,
        "mc_success_prob": 0.0, "total_return": -0.01,
    })
    assert any("p(pass)" in c.lower() and "loss" in c.lower() for c in caveats)


def test_metric_caveats_silent_when_metrics_are_normal():
    caveats = metric_caveats({
        "max_drawdown": 0.05, "sharpe": 1.5,
        "mc_success_prob": 0.6, "total_return": 0.04,
    })
    assert caveats == []
