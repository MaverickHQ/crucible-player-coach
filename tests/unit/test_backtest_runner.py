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


def test_world_state_carries_computed_vwap(tmp_path: Path) -> None:
    prices = [185.0, 186.0, 187.0]
    _, loop, _ = _run_with_prices(prices, tmp_path=tmp_path)
    ws = loop.run.call_args.kwargs["world_state"]
    assert ws["vwap"] is not None and ws["vwap"] > 0.0
    assert ws["price_vs_vwap"] is not None


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
