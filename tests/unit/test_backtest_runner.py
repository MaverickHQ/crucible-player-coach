from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from player_coach.backtest.runner import BacktestResult, BacktestRunner
from player_coach.constraints.schema import ConstraintSchema


def _make_constraints() -> ConstraintSchema:
    return ConstraintSchema(
        max_position_pct=0.15,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage", "max_drawdown_pct"],
        max_rounds=1,
        max_daily_loss_pct=0.02,
        consistency_rule_pct=0.50,
        trading_cutoff_time="23:59",
    )


def _make_price_df(prices: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "Open":   prices,
            "High":   [p * 1.005 for p in prices],
            "Low":    [p * 0.995 for p in prices],
            "Close":  prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=dates,
    )


def _make_ohlc_df(opens: list[float], closes: list[float]) -> pd.DataFrame:
    """Bars with explicit, *distinct* open vs close — needed to prove the fill
    price is the bar's open, not its close (Seam 0 bar-timing tests)."""
    assert len(opens) == len(closes)
    dates = pd.date_range("2024-01-02", periods=len(opens), freq="B")
    return pd.DataFrame(
        {
            "Open":   opens,
            "High":   [max(o, c) * 1.01 for o, c in zip(opens, closes)],
            "Low":    [min(o, c) * 0.99 for o, c in zip(opens, closes)],
            "Close":  closes,
            "Volume": [1_000_000] * len(opens),
        },
        index=dates,
    )


def _make_approve_artifact() -> dict:
    return {
        "outcome": "APPROVE",
        "run_id": "test-run-id",
        "rounds": [
            {
                "round": 1,
                "proposal": {
                    "actions": [
                        {
                            "action_type": "enter_long",
                            "symbol": "AMZN",
                            "size_pct": 0.05,
                            "entry_price": 185.0,
                            "stop_loss": 183.0,
                            "take_profit": 190.0,
                            "position_id": None,
                        }
                    ],
                    "reasoning": "Momentum setup.",
                },
                "evaluation": {"decision": "APPROVE", "violations": [], "feedback": ""},
                "tokens_used": {"player": 50, "coach": 30},
            }
        ],
    }


def _multi_action_artifact(actions: list[dict]) -> dict:
    return {
        "outcome": "APPROVE",
        "run_id": "r",
        "rounds": [{
            "round": 1,
            "proposal": {"actions": actions, "reasoning": ""},
            "evaluation": {"decision": "APPROVE", "violations": [], "feedback": ""},
            "tokens_used": {"player": 1, "coach": 1},
        }],
    }


def _action_artifact(action: dict) -> dict:
    return _multi_action_artifact([action])


def _enter_no_id() -> dict:
    # N2: lenient stop/tp that survive any reasonable bar-open gap — these
    # generic helpers exist for tests that just want "any approved entry".
    # Tests that exercise gap-rejection build their own action with tight
    # values inline.
    return {
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.02,
        "entry_price": 185.0, "stop_loss": 1.0, "take_profit": 10_000.0,
    }


def _enter_artifact() -> dict:
    # N2: lenient stop/tp — see note on _enter_no_id.
    return _action_artifact({
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": 185.0, "stop_loss": 1.0, "take_profit": 10_000.0,
        "position_id": "P1",
    })


def _exit_artifact() -> dict:
    return _action_artifact({
        "action_type": "exit_position", "symbol": "AMZN", "position_id": "P1",
    })


def _hold_artifact() -> dict:
    return _action_artifact({"action_type": "hold"})


def _make_runner(loop: MagicMock, db_store: MagicMock) -> BacktestRunner:
    return BacktestRunner(loop=loop, db_store=db_store, strategy_id="test-strategy")


def _run_with_prices(
    prices: list[float],
    artifact_factory=None,
    tmp_path: Path | None = None,
) -> tuple[BacktestResult, MagicMock, MagicMock]:
    loop = MagicMock()
    db_store = MagicMock()
    if artifact_factory is None:
        loop.run.return_value = _make_approve_artifact()
    else:
        # A1 — Seam 0 bar-timing: N bars produce N-1 decisions (day 0 has no
        # prior data). Generate exactly that many artifacts.
        n_decisions = max(0, len(prices) - 1)
        loop.run.side_effect = [
            artifact_factory(i) for i in range(n_decisions)
        ]

    df = _make_price_df(prices)
    runner = _make_runner(loop, db_store)

    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = df
        result = runner.run(
            symbol="AMZN",
            start_date="2024-01-02",
            end_date="2024-01-15",
            constraints=_make_constraints(),
            output_dir=tmp_path or Path("/tmp"),
        )

    return result, loop, db_store


def test_run_calls_loop_once_per_decision_day(tmp_path: Path) -> None:
    # A1 — Seam 0 bar-timing: day 0 has no prior data, so no decision is made.
    # N bars -> N-1 decisions.
    prices = [185.0, 186.0, 187.0, 188.0, 189.0]
    result, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert loop.run.call_count == len(prices) - 1


def test_run_records_portfolio_snapshot_per_day(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, _, db_store = _run_with_prices(prices, tmp_path=tmp_path)
    assert db_store.save_portfolio_snapshot.call_count == len(prices)


def test_on_day_callback_invoked_per_day(tmp_path: Path) -> None:
    # Live progress: the callback fires exactly once per bar with a payload that
    # carries enough to update a Streamlit status line.
    calls: list[dict] = []
    loop = MagicMock()
    loop.run.return_value = _hold_artifact()
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s",
        on_day=lambda payload: calls.append(payload),
    )
    df = _make_price_df([100.0, 101.0, 102.0])
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = df
        runner.run(symbol="AMZN", start_date="2024-01-02",
                   end_date="2024-01-15", constraints=_make_constraints(),
                   output_dir=tmp_path)
    assert len(calls) == 3
    p = calls[0]
    for key in ("day", "total_days", "date", "capital",
                "challenge_phase", "outcome", "days_aborted"):
        assert key in p, f"missing key in progress payload: {key}"
    assert calls[0]["day"] == 1 and calls[-1]["day"] == 3
    assert calls[-1]["total_days"] == 3


def test_on_day_callback_optional(tmp_path: Path) -> None:
    # No callback = no regression: the runner must still run cleanly.
    # A1: 2 bars -> 1 decision (day 0 has no prior data).
    _, loop, _ = _run_with_prices([100.0, 101.0], tmp_path=tmp_path)
    assert loop.run.call_count == 1


def test_on_day_callback_failure_swallowed(tmp_path: Path) -> None:
    # A subscriber that raises must NOT derail the backtest.
    def boom(_payload):
        raise RuntimeError("ui blew up")
    loop = MagicMock()
    loop.run.return_value = _hold_artifact()
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s", on_day=boom)
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df(
            [100.0, 101.0, 102.0])
        result = runner.run(symbol="AMZN", start_date="2024-01-02",
                            end_date="2024-01-15",
                            constraints=_make_constraints(), output_dir=tmp_path)
    assert result.days_run == 3  # ran to completion despite the boom


def test_on_day_errors_counted_on_result(tmp_path: Path) -> None:
    # N12 — a buggy UI subscriber used to be silently swallowed; now the
    # count surfaces on BacktestResult.on_day_errors so the dashboard can
    # flag broken progress updates instead of looking frozen.
    def boom(_payload):
        raise RuntimeError("ui blew up")
    loop = MagicMock()
    loop.run.return_value = _hold_artifact()
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s", on_day=boom)
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df(
            [100.0, 101.0, 102.0])
        result = runner.run(symbol="AMZN", start_date="2024-01-02",
                            end_date="2024-01-15",
                            constraints=_make_constraints(), output_dir=tmp_path)
    # 3 bars, 3 callbacks, 3 raises → 3 counted errors.
    assert result.on_day_errors == 3


def test_on_day_errors_zero_when_subscriber_healthy(tmp_path: Path) -> None:
    # Healthy subscriber → zero counted errors.
    loop = MagicMock()
    loop.run.return_value = _hold_artifact()
    calls: list = []
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s",
        on_day=lambda p: calls.append(p))
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df(
            [100.0, 101.0, 102.0])
        result = runner.run(symbol="AMZN", start_date="2024-01-02",
                            end_date="2024-01-15",
                            constraints=_make_constraints(), output_dir=tmp_path)
    assert result.on_day_errors == 0
    assert len(calls) == 3


def test_backtest_result_has_equity_curve(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    result, _, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert len(result.equity_curve) == result.days_run
    assert result.equity_curve[-1][1] == result.final_capital


def test_backtest_result_has_risk_metrics(tmp_path: Path) -> None:
    from player_coach.backtest.metrics import (
        calmar_ratio, sharpe_ratio, sortino_ratio,
    )
    result, _, _ = _run_with_prices([100.0, 110.0, 105.0, 115.0], tmp_path=tmp_path)
    assert result.sharpe == sharpe_ratio(result.equity_curve)
    assert result.sortino == sortino_ratio(result.equity_curve)
    assert result.calmar == calmar_ratio(result.equity_curve)


def test_backtest_result_has_config_mc_prob(tmp_path: Path) -> None:
    # A3: P(pass) projected from the config's realised edge. Two closed trades:
    # win (+0.10) and loss (-0.10).
    # A1 — Seam 0: day 0 has no decision, so we need one more price than the
    # number of decisions. 4 decisions [enter/exit/enter/exit] need 5 bars.
    # Entries fill at open == close == 100; exits at open == close == 110/90.
    from player_coach.analytics import simulate_challenge, trade_stats
    prices = [100.0, 100.0, 110.0, 100.0, 90.0]
    arts = [_enter_at(100.0), _exit_artifact(),
            _enter_at(100.0), _exit_artifact()]
    result, _, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    # Realised returns reproduce the runner's float math (open / open - 1).
    realized = [110.0 / 100.0 - 1.0, 90.0 / 100.0 - 1.0]
    expected = simulate_challenge(
        trade_stats(realized), profit_target=0.06, drawdown_limit=0.10,
        days_remaining=20, trades_per_day=1.0, n_paths=1000,
    ).success_probability
    assert result.mc_success_prob == expected


def test_no_trades_config_mc_prob_zero(tmp_path: Path) -> None:
    result, _, _ = _run_with_prices(
        [100.0, 101.0, 102.0], artifact_factory=lambda i: _hold_artifact(),
        tmp_path=tmp_path)
    assert result.mc_success_prob == 0.0


def test_backtest_result_has_drawdown_profile(tmp_path: Path) -> None:
    from player_coach.backtest.metrics import avg_recovery_time, drawdown_duration
    result, _, _ = _run_with_prices([100.0, 120.0, 90.0, 130.0], tmp_path=tmp_path)
    assert result.max_drawdown_duration == drawdown_duration(result.equity_curve)
    assert result.avg_recovery_time == avg_recovery_time(result.equity_curve)


def test_backtest_result_has_correct_days_run(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0, 188.0]
    result, _, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert result.days_run == len(prices)


def test_backtest_result_total_pnl_pct_computed_correctly(tmp_path: Path) -> None:
    # No positions entered (enter_long artifact but size_pct=0 effects are
    # minimal). Capital stays at 100k. total_pnl_pct should be 0.0.
    # A1: N bars -> N-1 exchanges (day 0 no decision).
    prices = [185.0, 185.0, 185.0]
    result, _, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert result.total_exchanges == len(prices) - 1
    assert result.total_pnl_pct == result.total_pnl / 100_000.0


# ----------------------------------------------------- F6 regime wiring (Seam 0)

def test_world_state_passed_to_loop_has_regime_fields(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    world_state = loop.run.call_args.kwargs["world_state"]
    assert "regime_label" in world_state
    assert "regime_probability" in world_state


def test_short_history_yields_unknown_regime(tmp_path: Path) -> None:
    # Fewer than 30 returns → the detector degrades to "unknown".
    prices = [185.0, 186.0, 187.0, 188.0, 189.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert loop.run.call_args.kwargs["world_state"]["regime_label"] == "unknown"


def test_unknown_regime_applies_conservative_constraints(tmp_path: Path) -> None:
    # Base max_single_trade_pct is 0.05; the conservative (unknown) profile
    # multiplies by 0.6 → 0.03. Confirms the resolver is wired into the runner.
    prices = [185.0, 186.0, 187.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    resolved = loop.run.call_args.kwargs["constraints"]
    assert resolved.max_single_trade_pct == 0.03
    assert resolved.max_open_positions == 2


def test_world_state_passed_to_loop_has_garch_vol_key(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert "garch_vol" in loop.run.call_args.kwargs["world_state"]


def test_world_state_carries_computed_atr(tmp_path: Path) -> None:
    # 20 bars is enough for ATR (needs 15) but below the 30-return HMM/GARCH
    # threshold, so this stays fast while proving ATRFeature is wired.
    prices = [185.0 + i * 0.5 for i in range(20)]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    atr = loop.run.call_args.kwargs["world_state"]["atr"]
    assert atr is not None and atr > 0.0


def test_sma_computed_from_buffer_closes(tmp_path: Path) -> None:
    # A1: the last decision (for bar 4) sees the buffer with bars [0..3] only —
    # not bar 4. So SMAs are computed over [10, 20, 30, 40], not [10..50].
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]  # last decision
    assert ws["sma5"] == 40.0   # 4 bars in buffer < 5 → falls back to last close
    assert ws["sma10"] == 40.0  # same fallback


def test_world_state_carries_challenge_phase(tmp_path: Path) -> None:
    # Holds → no positions → no P&L → 0% profit → building.
    _, loop, _ = _run_with_prices(
        [185.0, 186.0, 187.0], artifact_factory=lambda i: _hold_artifact(),
        tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]
    assert ws["challenge_phase"] == "building"
    assert ws["challenge_pnl_pct"] == 0.0


def test_default_resolver_tightens_on_phase_transition(tmp_path: Path) -> None:
    # A1: 4 bars (185, 185, 340, 340) → 3 decisions.
    # Decision 0 (bar 1) = enter; fills at bar 1 open=185, P&L=0 → building.
    # Decision 1 (bar 2) = hold; capital marks up at bar 2 close=340 → +4.2% →
    #   phase becomes conservation on the NEXT decision (decision 2).
    # Decision 2 (bar 3) = hold → conservation, tighter constraints.
    prices = [185.0, 185.0, 340.0, 340.0]
    arts = [_enter_artifact(), _hold_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    first = loop.run.call_args_list[0].kwargs
    last = loop.run.call_args_list[-1].kwargs
    assert first["world_state"]["challenge_phase"] == "building"
    assert last["world_state"]["challenge_phase"] == "conservation"
    assert (last["constraints"].max_single_trade_pct
            < first["constraints"].max_single_trade_pct)


def _enter_at(price: float) -> dict:
    return _action_artifact({
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": price, "stop_loss": price * 0.99,
        "take_profit": price * 1.1, "position_id": "P1",
    })


def test_world_state_carries_consistency_status(tmp_path: Path) -> None:
    # A1: at decision time the agent sees YESTERDAY's realised daily P&L
    # against the running cumulative — today's P&L hasn't happened yet.
    # Setup: 5 bars, 4 decisions [enter, hold, hold, hold].
    # - decision 0 (bar 1): yesterday (bar 0) had no positions → daily=0 → ok
    # - decision 1 (bar 2): bar 1 entered at 100, day-end mark also 100 → daily=0
    # - decision 2 (bar 3): bar 2 close=110 marks +500 → daily=+500 vs cum=+500
    #   → daily/cum = 100% > 50% rule → 'breached' surfaced here
    prices = [100.0, 100.0, 100.0, 110.0, 121.0]
    arts = [_enter_at(100.0), _hold_artifact(), _hold_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    statuses = [c.kwargs["world_state"]["consistency_status"]
                for c in loop.run.call_args_list]
    assert "breached" in statuses


def test_open_positions_visible_in_portfolio_state(tmp_path: Path) -> None:
    # Seam 0: the Player must see its book to exit it.
    # A1: 3 bars → 2 decisions. Decision 0 (bar 1) enters; decision 1 (bar 2)
    # observes the open book in portfolio_state.
    prices = [185.0, 185.0, 186.0]
    arts = [_enter_at(185.0), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    ps_next = loop.run.call_args_list[1].kwargs["portfolio_state"]
    assert "P1" in [p.position_id for p in ps_next.open_positions]


def test_monte_carlo_sets_prob_and_triggers_conservation(tmp_path: Path) -> None:
    # R1: with a realised trade, the runner computes mc_success_prob and applies
    # the trigger. One winning trade has no losses → P(pass)=0.0 (R2) → escalate
    # building → conservation.
    # A1: 5 bars → 4 decisions [enter, exit, hold, hold]. The last decision's
    # world_state carries the auto-escalated phase.
    loop = MagicMock()
    arts = [_enter_at(100.0), _exit_artifact(), _hold_artifact(), _hold_artifact()]
    loop.run.side_effect = arts
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s",
        mc_min_trades=1, mc_every=1,
    )
    df = _make_price_df([100.0, 100.0, 110.0, 110.0, 110.0])
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = df
        runner.run(symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
                   constraints=_make_constraints(), output_dir=tmp_path)
    last = loop.run.call_args_list[-1].kwargs["world_state"]
    assert last["mc_success_prob"] == 0.0
    assert last["challenge_phase"] == "conservation"


def _run_costs(cost_pct: float, tmp_path: Path):
    loop = MagicMock()
    loop.run.side_effect = [_enter_at(100.0), _exit_artifact()]
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s",
        transaction_cost_pct=cost_pct,
    )
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df([100.0, 100.0])
        return runner.run(symbol="AMZN", start_date="2024-01-02",
                          end_date="2024-01-15", constraints=_make_constraints(),
                          output_dir=tmp_path)


def test_transaction_costs_reduce_pnl(tmp_path: Path) -> None:
    # Flat round trip (enter @100, exit @100): only the fee is lost.
    assert _run_costs(0.01, tmp_path).total_pnl < 0


def test_zero_transaction_cost_leaves_flat_trade_flat(tmp_path: Path) -> None:
    assert _run_costs(0.0, tmp_path).total_pnl == 0.0


def test_winning_short_increases_pnl(tmp_path: Path) -> None:
    # Seam 0: an approved enter_short must actually take a position; a short into
    # a falling price profits.
    # A1: 3 bars → 2 decisions. Decision 0 (bar 1) shorts at open=100, hold;
    # bar 2 marks to close=90 → short profits.
    prices = [100.0, 100.0, 90.0]
    short = _action_artifact({
        "action_type": "enter_short", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": 100.0, "stop_loss": 105.0, "take_profit": 90.0,
        "position_id": "S1",
    })
    result, _, _ = _run_with_prices(
        prices, artifact_factory=lambda i: [short, _hold_artifact()][i],
        tmp_path=tmp_path)
    assert result.total_pnl > 0


def test_world_state_carries_computed_vwap(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]
    assert ws["vwap"] is not None and ws["vwap"] > 0.0
    assert ws["price_vs_vwap"] is not None


def test_exit_closes_only_one_of_duplicate_ids(tmp_path: Path) -> None:
    # Two positions both id "P1" opened on bars 1 and 2; a single exit "P1" on
    # bar 3 must close exactly one, not both.
    # A1: 4 bars → 3 decisions [enter, enter, exit].
    prices = [185.0, 185.0, 185.0, 200.0]
    arts = [_enter_artifact(), _enter_artifact(), _exit_artifact()]
    _, _, db = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path
    )
    # Last snapshot is after the exit: one position still open.
    last_snap = db.save_portfolio_snapshot.call_args_list[-1][0][0]
    assert len(last_snap["open_positions"]) == 1


def test_same_day_duplicate_entries_get_unique_ids(tmp_path: Path) -> None:
    # One decision's proposal with two id-less long entries must yield two
    # distinct synthesized position ids, not one collided id.
    # A1: needs ≥2 bars to make any decision; the decision fires on bar 1.
    art = _multi_action_artifact([_enter_no_id(), _enter_no_id()])
    _, _, db = _run_with_prices(
        [185.0, 185.0], artifact_factory=lambda i: art, tmp_path=tmp_path
    )
    # Snapshot for bar 1 is the second one written (bar 0's came first,
    # before any decisions were possible).
    ids = db.save_portfolio_snapshot.call_args_list[1][0][0]["open_positions"]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_kelly_reference_none_until_trade_closes_then_populated(tmp_path: Path) -> None:
    # A1: 4 bars → 3 decisions [enter, exit, hold]. Decision 0 (bar 1) enters
    # at open=185 — no closed trade yet. Decision 1 (bar 2) exits at open=200 —
    # closes a +8.1% trade. Decision 2 (bar 3) is the first to see a
    # populated kelly_fraction.
    prices = [185.0, 185.0, 200.0, 200.0]
    artifacts = [_enter_artifact(), _exit_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: artifacts[i], tmp_path=tmp_path
    )
    calls = loop.run.call_args_list
    assert calls[0].kwargs["world_state"]["kelly_fraction"] is None   # no closed trade
    assert calls[-1].kwargs["world_state"]["kelly_fraction"] is not None  # one closed


class _FakeEnricher:
    """Writes a fixed regime + garch forecast so the resolver wiring is testable
    without fitting models on a long synthetic series."""

    def enrich(self, world_state, buffer):
        world_state.regime_label = "low_vol"
        world_state.garch_vol = 0.04
        return world_state


class _SpyEnricher:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1

    def enrich(self, world_state, buffer):
        return world_state


def test_runner_resets_enricher_at_run_start(tmp_path: Path) -> None:
    loop = MagicMock()
    loop.run.return_value = _make_approve_artifact()
    spy = _SpyEnricher()
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s", enricher=spy,
    )
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df([185.0, 186.0])
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    assert spy.reset_calls == 1


def test_runner_default_resolver_applies_garch_scaling(tmp_path: Path) -> None:
    loop = MagicMock()
    loop.run.return_value = _make_approve_artifact()
    runner = BacktestRunner(
        loop=loop,
        db_store=MagicMock(),
        strategy_id="s",
        enricher=_FakeEnricher(),
    )
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_price_df([185.0, 186.0])
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    resolved = loop.run.call_args.kwargs["constraints"]
    # low_vol overlay (1.0x) then garch 0.04 → 0.5 floor → 0.05 * 0.5 = 0.025.
    assert resolved.max_single_trade_pct == 0.025


# ============================================================================
# A1 — Seam 0 bar-timing fidelity
# ----------------------------------------------------------------------------
# Today the runner uses bar t's *close* both for the decision and the fill —
# look-ahead, since you can't trade at a close you only know after the market
# shuts. The fix: decide using bars [0..t-1], fill at bar t's *open*. These
# tests pin that contract.
# ============================================================================

def test_no_decision_on_first_day(tmp_path: Path) -> None:
    # Day 0 has no prior bars. With no past data, no decision is possible —
    # the runner appends the bar and marks to market, but does not call the
    # CoachLoop. N bars -> N-1 decisions.
    prices = [100.0, 110.0, 120.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert loop.run.call_count == len(prices) - 1


def test_decision_sees_prior_close_not_current(tmp_path: Path) -> None:
    # The world_state.price field carries the *latest past* close (the buffer
    # tip *before* today's bar), not today's close. If it carried today's, the
    # agent would be peeking at intraday data it cannot have at decision time.
    prices = [100.0, 200.0, 300.0]  # huge moves so the bug would be obvious
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    # First decision (loop call index 0) corresponds to bar 1. It must see
    # day 0's close (100), not day 1's close (200).
    first_ws = loop.run.call_args_list[0].kwargs["world_state"]
    assert first_ws["price"] == 100.0
    # Last decision (bar 2) sees day 1's close (200), not day 2's (300).
    last_ws = loop.run.call_args_list[-1].kwargs["world_state"]
    assert last_ws["price"] == 200.0


def test_entry_fills_at_current_bar_open_not_decision_close(tmp_path: Path) -> None:
    # An approved enter_long on bar t's decision fills at bar t's *open*.
    # Setup: distinct open vs close. Day 1 open = 50, day 1 close = 100.
    # An entry fired by day 1's decision should fill at 50, then end day 1
    # marked to 100, yielding +100% on the invested fraction.
    opens =  [50.0,  50.0, 50.0]
    closes = [100.0, 100.0, 100.0]
    loop = MagicMock()
    # Day 1 decision (loop call 0) enters; day 2 decision (call 1) holds.
    loop.run.side_effect = [_enter_artifact(), _hold_artifact()]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(symbol="AMZN", start_date="2024-01-02",
                            end_date="2024-01-15",
                            constraints=_make_constraints(), output_dir=tmp_path)
    # The enter_artifact size_pct is 0.05. Entry at open=50, mark-to-market at
    # close=100 = +100% on the position. Expected PnL = 100_000 * 0.05 = +5000.
    # (Allow a small fudge for transaction costs, which are 0.1% round-trip.)
    assert 4900 < result.total_pnl < 5100


def test_exit_fills_at_current_bar_open(tmp_path: Path) -> None:
    # An approved exit_position on bar t fills at bar t's *open*, not its close.
    # Buy at bar 1 open (50), exit at bar 3 open (90). Days 1/2 close at 50.
    # The exit's *fill* is 90 (open), not 200 (close).
    opens =  [50.0,  50.0, 90.0,  90.0]
    closes = [50.0,  50.0, 200.0, 90.0]
    loop = MagicMock()
    # Decision sequence (one per bar, starting bar 1):
    loop.run.side_effect = [
        _enter_artifact(),   # bar 1: open long → fill at 50
        _hold_artifact(),    # bar 2: hold
        _exit_artifact(),    # bar 3: exit → fill at 90 (NOT bar 3's close 200)
    ]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(symbol="AMZN", start_date="2024-01-02",
                            end_date="2024-01-15",
                            constraints=_make_constraints(), output_dir=tmp_path)
    # Realised return on the closed trade: (90 / 50) - 1 = +80%. With size_pct
    # 0.05, that's +0.04 * starting capital = +4000 booked. If the runner had
    # used bar 3's CLOSE (200), realised return would have been +300% → +15000.
    # Use a wide window because day 3 still marks to its close (no open
    # position by then, so close mark only affects timing, not realised P&L).
    assert 3500 < result.total_pnl < 4500


# ---------------------------------------------------------------------------
# N1 + N7 — decision-time PortfolioState fidelity
#
# Both come from the local code-review backlog (2026-06-15). A1 left
# PortfolioState.daily_pnl pinned to 0.0 at decision time and routed
# yesterday's realised P&L into consistency_status — both make hard breakers
# and the F13 soft signal silent. The correct value at decision time is the
# overnight gap MTM on open positions: the unrealised move from yesterday's
# close to today's open, which is what the breakers and the consistency
# signal should mechanically check before the Player is even asked.
# ---------------------------------------------------------------------------


def test_decision_time_daily_pnl_reflects_overnight_gap(tmp_path: Path) -> None:
    # N1 — at decision time portfolio_state.daily_pnl must carry the
    # overnight gap MTM on open positions, so the daily_loss_limit breaker
    # (`is_daily_loss_breached(daily_pnl, daily_starting_balance)`) can fire
    # pre-LLM on a gap loser. Old behaviour: hardcoded 0.0 → breaker dies.
    #
    # Setup: day 1 enters at open=100 (size_pct=0.05 → cost=5000), day 1
    # closes flat at 100 → position prev_close=100 at EOD. Day 2 gaps to
    # open=60: gap_mtm = (60-100)/100 * 5000 = -2000 = -2% of starting cap.
    opens = [100.0, 100.0, 60.0]
    closes = [100.0, 100.0, 60.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_at(100.0), _hold_artifact()]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    # Decision on day 2 corresponds to loop call index 1 (day 0 had no decision).
    day2_ps = loop.run.call_args_list[1].kwargs["portfolio_state"]
    assert day2_ps.daily_pnl == pytest.approx(-2000.0, abs=1.0)


def test_decision_time_daily_pnl_zero_when_no_overnight_book(tmp_path: Path) -> None:
    # N1 corollary — first decision (day 1) has no positions yet (day 0
    # didn't decide), so gap MTM is exactly 0. The breaker correctly does
    # nothing on day 1.
    opens = [100.0, 60.0]
    closes = [100.0, 60.0]
    loop = MagicMock()
    loop.run.side_effect = [_hold_artifact()]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    day1_ps = loop.run.call_args_list[0].kwargs["portfolio_state"]
    assert day1_ps.daily_pnl == 0.0


def test_decision_time_consistency_uses_today_gap_not_prior_day(tmp_path: Path) -> None:
    # N7 — consistency_status at decision time uses today's projected day-PnL
    # (the overnight gap MTM), not yesterday's full realised P&L. Old code
    # passed prior_daily_pnl=cumulative_pnl on day 2 → ratio 1.0 → "breached"
    # every time the first day was profitable. New code passes a small gap
    # (or 0) → status reflects today's risk, not yesterday's outcome.
    #
    # Setup: day 1 enters at open=100, closes +10% at 110 → cumulative=+500
    # at EOD (position prev_close=110). Day 2 opens at 110 — gap_mtm = 0.
    # Under old logic consistency_status(500, 500) → "breached". Under new
    # logic consistency_status(0, 500) → "ok".
    opens = [100.0, 100.0, 110.0]
    closes = [100.0, 110.0, 110.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_at(100.0), _hold_artifact()]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    day2_status = loop.run.call_args_list[1].kwargs["world_state"]["consistency_status"]
    assert day2_status == "ok"


def test_decision_time_consistency_breached_when_today_gap_exceeds_rule(tmp_path: Path) -> None:
    # N7 (positive case) — when today's gap MTM exceeds consistency_rule_pct
    # of cumulative profit, the signal correctly says "breached". This pins
    # that the gap-MTM-based signal still surfaces real breaches.
    #
    # Setup: day 1 enters at 100, closes +4% at 104 → tiny cumulative=+200
    # (size_pct=0.05 → cost=5000, 4% of 5000=200). Day 2 opens at 110 — gap
    # = (110-104)/104 * 5000 ≈ +288. 288/200 = 144% > 50% rule → "breached".
    opens = [100.0, 100.0, 110.0]
    closes = [100.0, 104.0, 110.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_at(100.0), _hold_artifact()]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    day2_status = loop.run.call_args_list[1].kwargs["world_state"]["consistency_status"]
    assert day2_status == "breached"


# ---------------------------------------------------------------------------
# N2 — fill-time re-validation of the Coach-approved setup
#
# The Coach validates direction (long: stop<entry<tp; short: tp<entry<stop)
# and min_risk_reward against the Player's PROPOSED entry_price. The runner
# fills at today_open. If today's gap moves entry past the stop or take_profit
# (direction inverted) or compresses the reward/risk distance below the
# schema's min_risk_reward, the trade the Coach approved is no longer the
# trade we'd execute. The runner must drop the entry rather than fill on
# broken geometry.
# ---------------------------------------------------------------------------


def _enter_with_stops(stop: float, take_profit: float, size_pct: float = 0.05) -> dict:
    """Build a long-entry artifact with explicit stop/tp — used by N2 tests
    where the gap from proposed entry to today's open must drive rejection."""
    return _action_artifact({
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": size_pct,
        "entry_price": 100.0, "stop_loss": stop, "take_profit": take_profit,
        "position_id": "P1",
    })


def test_runner_drops_entry_when_gap_inverts_long_direction(tmp_path: Path) -> None:
    # N2 — Player proposes long at 100 (stop 99, tp 110) — Coach approves.
    # Day 1 opens at 95 — entry would fill BELOW the proposed stop. The setup
    # is broken: stop (99) is now ABOVE entry (95), inverting the long. The
    # runner must skip this entry rather than book a position with an
    # immediately-stopped-out shape.
    opens = [100.0, 95.0]
    closes = [100.0, 95.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_with_stops(stop=99.0, take_profit=110.0)]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    # No position was booked: total_exchanges = 1 (Coach was still called),
    # but capital is unchanged from initial.
    assert result.total_pnl == 0.0


def test_runner_drops_entry_when_gap_compresses_rr_below_min(tmp_path: Path) -> None:
    # N2 — Coach approved on proposed RR. After the gap-up, the reward
    # shrinks faster than the risk → actual RR < min_risk_reward (1.5).
    # Setup: stop=80, tp=110. Proposed entry=100 → RR=(110-100)/(100-80)=0.5.
    # That's already below 1.5 — Coach normally wouldn't approve. But the
    # Coach is mocked: it returns APPROVE regardless. The runner's NEW check
    # catches it.
    opens = [100.0, 100.0]
    closes = [100.0, 100.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_with_stops(stop=80.0, take_profit=110.0)]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    # Entry skipped — total_pnl stays at zero.
    assert result.total_pnl == 0.0


def test_runner_keeps_entry_when_gap_preserves_valid_setup(tmp_path: Path) -> None:
    # N2 — Sanity: a small gap that still preserves direction and RR ≥ 1.5
    # must NOT be skipped. Setup: stop=70, tp=200. Today opens at 100 — long
    # direction OK (70 < 100 < 200), RR=(200-100)/(100-70)=3.33 > 1.5. Entry
    # should fill normally; day 2 marks to 100 → ~0 P&L on the position.
    opens = [100.0, 100.0]
    closes = [100.0, 100.0]
    loop = MagicMock()
    loop.run.side_effect = [_enter_with_stops(stop=70.0, take_profit=200.0)]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    # Entry fired: capital reduced by transaction cost on the round-trip
    # entry half (0.05% of 5000 = 2.5). Position still open at the end so
    # no realised P&L; capital is initial - entry_tc = 99_997.5.
    assert result.total_pnl == pytest.approx(-2.5, abs=0.1)


def test_runner_drops_entry_when_gap_inverts_short_direction(tmp_path: Path) -> None:
    # N2 — Symmetric case for shorts. Coach approves a short at 100 with
    # stop=101, tp=90 (short: tp < entry < stop). Day 1 opens at 102 — entry
    # fills ABOVE the stop, inverting the short. Skip.
    opens = [100.0, 102.0]
    closes = [100.0, 102.0]
    loop = MagicMock()
    loop.run.side_effect = [_action_artifact({
        "action_type": "enter_short", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": 100.0, "stop_loss": 101.0, "take_profit": 90.0,
        "position_id": "S1",
    })]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    assert result.total_pnl == 0.0


# ---------------------------------------------------------------------------
# R4 — defensive guard on artifact["rounds"][-1] indexing
# ---------------------------------------------------------------------------


def test_runner_handles_approve_artifact_with_empty_rounds(tmp_path: Path) -> None:
    # R4 — `dict.get("rounds", [{}])` only returns the default when the key
    # is ABSENT. If a CoachLoop short-circuit ever emits
    # `{"outcome": "APPROVE", "rounds": []}` (explicit empty list), the
    # subsequent `[-1]` raises IndexError, the exception bubbles out of
    # runner.run, and the whole run dies mid-day. Guard so an empty-rounds
    # APPROVE is interpreted as "no actions proposed" — no fills, no crash.
    opens = [100.0, 100.0]
    closes = [100.0, 100.0]
    loop = MagicMock()
    loop.run.side_effect = [{
        "outcome": "APPROVE", "run_id": "r", "rounds": [],
    }]
    runner = BacktestRunner(loop=loop, db_store=MagicMock(), strategy_id="s")
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_ohlc_df(opens, closes)
        result = runner.run(
            symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
            constraints=_make_constraints(), output_dir=tmp_path,
        )
    # No entry attempted → no PnL, no aborts, run completes.
    assert result.total_pnl == 0.0
    assert result.days_aborted == 0
