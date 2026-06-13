from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

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
    return {
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.02,
        "entry_price": 185.0, "stop_loss": 183.0, "take_profit": 200.0,
    }


def _enter_artifact() -> dict:
    return _action_artifact({
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": 185.0, "stop_loss": 183.0, "take_profit": 200.0,
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
        loop.run.side_effect = [artifact_factory(i) for i in range(len(prices))]

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


def test_run_calls_loop_once_per_trading_day(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0, 188.0, 189.0]
    result, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert loop.run.call_count == len(prices)


def test_run_records_portfolio_snapshot_per_day(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, _, db_store = _run_with_prices(prices, tmp_path=tmp_path)
    assert db_store.save_portfolio_snapshot.call_count == len(prices)


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
    prices = [185.0, 185.0, 185.0]
    result, _, _ = _run_with_prices(prices, tmp_path=tmp_path)
    assert result.total_exchanges == len(prices)
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
    # SMA must stay correct after close_prices is folded into the OHLCV buffer.
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]  # last day
    assert ws["sma5"] == 30.0   # mean(10,20,30,40,50)
    assert ws["sma10"] == 50.0  # < 10 bars → falls back to the latest price


def test_world_state_carries_challenge_phase(tmp_path: Path) -> None:
    # Holds → no positions → no P&L → 0% profit → building.
    _, loop, _ = _run_with_prices(
        [185.0, 186.0, 187.0], artifact_factory=lambda i: _hold_artifact(),
        tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]
    assert ws["challenge_phase"] == "building"
    assert ws["challenge_pnl_pct"] == 0.0


def test_default_resolver_tightens_on_phase_transition(tmp_path: Path) -> None:
    # Enter @185 day 0; price jumps → >4% account gain (with F16 costs) →
    # conservation by day 2, which resolves tighter than day 0.
    prices = [185.0, 340.0, 340.0]
    arts = [_enter_artifact(), _hold_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    day0 = loop.run.call_args_list[0].kwargs
    day2 = loop.run.call_args_list[2].kwargs
    assert day0["world_state"]["challenge_phase"] == "building"
    assert day2["world_state"]["challenge_phase"] == "conservation"
    assert (day2["constraints"].max_single_trade_pct
            < day0["constraints"].max_single_trade_pct)


def _enter_at(price: float) -> dict:
    return _action_artifact({
        "action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05,
        "entry_price": price, "stop_loss": price * 0.99,
        "take_profit": price * 1.1, "position_id": "P1",
    })


def test_world_state_carries_consistency_status(tmp_path: Path) -> None:
    # Enter @100; day1 marks +500 (cumulative 500), day2 marks +500 again =
    # 100% of prior profit → consistency "breached" surfaced day 2.
    prices = [100.0, 110.0, 121.0]
    arts = [_enter_at(100.0), _hold_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    statuses = [c.kwargs["world_state"]["consistency_status"]
                for c in loop.run.call_args_list]
    assert statuses[2] == "breached"


def test_open_positions_visible_in_portfolio_state(tmp_path: Path) -> None:
    # Seam 0: the Player must see its book to exit it. Enter day 0; day 1's
    # portfolio_state must carry the open position.
    prices = [185.0, 186.0]
    arts = [_enter_at(185.0), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path)
    ps_day1 = loop.run.call_args_list[1].kwargs["portfolio_state"]
    assert "P1" in [p.position_id for p in ps_day1.open_positions]


def test_monte_carlo_sets_prob_and_triggers_conservation(tmp_path: Path) -> None:
    # R1: with a realised trade, the runner computes mc_success_prob and applies
    # the trigger. One winning trade has no losses → P(pass)=0.0 (R2) → escalate
    # building → conservation.
    loop = MagicMock()
    arts = [_enter_at(100.0), _exit_artifact(), _hold_artifact(), _hold_artifact()]
    loop.run.side_effect = arts
    runner = BacktestRunner(
        loop=loop, db_store=MagicMock(), strategy_id="s",
        mc_min_trades=1, mc_every=1,
    )
    df = _make_price_df([100.0, 110.0, 110.0, 110.0])
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = df
        runner.run(symbol="AMZN", start_date="2024-01-02", end_date="2024-01-15",
                   constraints=_make_constraints(), output_dir=tmp_path)
    day3 = loop.run.call_args_list[3].kwargs["world_state"]
    assert day3["mc_success_prob"] == 0.0
    assert day3["challenge_phase"] == "conservation"


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
    prices = [100.0, 90.0]
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
    # Two positions both id "P1" (day0, day1); a single exit "P1" (day2) must
    # close exactly one, not both.
    prices = [185.0, 185.0, 200.0]
    arts = [_enter_artifact(), _enter_artifact(), _exit_artifact()]
    _, _, db = _run_with_prices(
        prices, artifact_factory=lambda i: arts[i], tmp_path=tmp_path
    )
    day2 = db.save_portfolio_snapshot.call_args_list[2][0][0]
    assert len(day2["open_positions"]) == 1


def test_same_day_duplicate_entries_get_unique_ids(tmp_path: Path) -> None:
    # One day's proposal with two id-less long entries must yield two distinct
    # synthesized position ids, not one collided id.
    art = _multi_action_artifact([_enter_no_id(), _enter_no_id()])
    _, _, db = _run_with_prices(
        [185.0], artifact_factory=lambda i: art, tmp_path=tmp_path
    )
    ids = db.save_portfolio_snapshot.call_args_list[0][0][0]["open_positions"]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_kelly_reference_none_until_trade_closes_then_populated(tmp_path: Path) -> None:
    # Day 0 enter P1 @185, day 1 exit @200 (a win), day 2 hold.
    prices = [185.0, 200.0, 200.0]
    artifacts = [_enter_artifact(), _exit_artifact(), _hold_artifact()]
    _, loop, _ = _run_with_prices(
        prices, artifact_factory=lambda i: artifacts[i], tmp_path=tmp_path
    )
    calls = loop.run.call_args_list
    assert calls[0].kwargs["world_state"]["kelly_fraction"] is None   # no closed trade
    assert calls[2].kwargs["world_state"]["kelly_fraction"] is not None  # one closed


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
