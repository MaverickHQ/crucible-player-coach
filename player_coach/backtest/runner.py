from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yfinance as yf

from player_coach.analytics import half_kelly, trade_stats
from player_coach.constraints.resolver import (
    ConstraintResolver,
    clamp_invariants,
    garch_scale,
    regime_overlay,
)
from player_coach.market import (
    ATRFeature,
    GARCHFeature,
    OHLCVBuffer,
    RegimeFeature,
    VWAPFeature,
    WorldState,
    WorldStateEnricher,
)
from player_coach.portfolio.state import PortfolioState

if TYPE_CHECKING:
    from player_coach.constraints.schema import ConstraintSchema
    from player_coach.database.store import DatabaseStore
    from player_coach.loop.coach_loop import CoachLoop


@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    strategy_id: str
    days_run: int
    days_aborted: int
    total_exchanges: int
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    max_drawdown_pct: float
    exchanges: list[dict] = field(default_factory=list)


@dataclass
class _RunnerPosition:
    symbol: str
    size_pct: float
    entry_price: float
    cost: float
    position_id: str
    prev_close: float = 0.0


def _compute_sma(prices, n: int) -> float:
    length = len(prices)
    if length == 0:
        return 0.0
    if length < n:
        return float(prices[-1])
    return float(sum(prices[-n:]) / n)


class BacktestRunner:
    def __init__(
        self,
        loop: CoachLoop,
        db_store: DatabaseStore,
        strategy_id: str,
        enricher: WorldStateEnricher | None = None,
        resolver: ConstraintResolver | None = None,
    ) -> None:
        self._loop = loop
        self._db_store = db_store
        self._strategy_id = strategy_id
        # F6 regime + F7 GARCH enrich world state; the resolver then layers the
        # regime overlay and (on top) garch volatility-scaling onto constraints.
        self._enricher = enricher or WorldStateEnricher(
            [RegimeFeature(), GARCHFeature(), ATRFeature(), VWAPFeature()]
        )
        self._resolver = resolver or ConstraintResolver(
            [regime_overlay(), garch_scale(), clamp_invariants()]
        )

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        constraints: ConstraintSchema,
        initial_capital: float = 100_000.0,
        output_dir: str | Path = "artifacts",
    ) -> BacktestResult:
        # Clear any stateful feature caches/smoothing from a previous run.
        reset = getattr(self._enricher, "reset", None)
        if callable(reset):
            reset()

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        capital = initial_capital
        cash_available = initial_capital
        peak_capital = initial_capital
        daily_starting_balance = initial_capital
        cumulative_pnl = 0.0
        open_positions: list[_RunnerPosition] = []

        days_run = 0
        days_aborted = 0
        exchanges: list[dict] = []
        realized_trade_returns: list[float] = []
        position_seq = 0
        buffer = OHLCVBuffer()

        for date, row in df.iterrows():
            close = float(row["Close"])
            high = float(row["High"])
            low = float(row["Low"])
            volume = int(row["Volume"])
            buffer.append(
                open=float(row["Open"]),
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
            closes = buffer.closes

            daily_pnl = sum(
                (close - p.prev_close) / p.prev_close * p.cost if p.prev_close else 0.0
                for p in open_positions
            )

            portfolio_state = PortfolioState(
                capital=capital,
                daily_starting_balance=daily_starting_balance,
                peak_capital=peak_capital,
                cash_available=cash_available,
                daily_pnl=daily_pnl,
                cumulative_pnl=cumulative_pnl,
            )

            world_state_obj = WorldState(
                symbol=symbol,
                price=close,
                sma5=_compute_sma(closes, 5),
                sma10=_compute_sma(closes, 10),
                volume=volume,
            )
            # F6: write regime_label/regime_probability, then resolve the
            # effective constraints for this regime (conservative if unknown).
            self._enricher.enrich(world_state_obj, buffer)
            world_state: dict[str, Any] = world_state_obj.to_dict()
            resolved_constraints = self._resolver.resolve(constraints, world_state)

            # F10: half-Kelly sizing reference from realised trades so far,
            # capped by the effective per-trade limit. None until a trade closes.
            stats = trade_stats(realized_trade_returns)
            if stats.count > 0:
                world_state["kelly_fraction"] = half_kelly(
                    stats, cap=resolved_constraints.max_single_trade_pct
                )

            artifact = self._loop.run(
                world_state=world_state,
                constraints=resolved_constraints,
                portfolio_state=portfolio_state,
                db_store=self._db_store,
                strategy_id=self._strategy_id,
                output_dir=output_dir,
            )
            exchanges.append(artifact)
            days_run += 1

            outcome = artifact.get("outcome")
            termination_reason = artifact.get("termination_reason")

            if outcome == "APPROVE":
                for action in artifact.get("rounds", [{}])[-1].get(
                    "proposal", {}
                ).get("actions", []):
                    action_type = action.get("action_type")
                    if action_type == "enter_long":
                        size_pct = float(action.get("size_pct", 0.0))
                        entry_price = float(action.get("entry_price", close))
                        cost = capital * size_pct
                        # Unique synthesized id so two id-less same-day entries
                        # are distinguishable (a shared id would let one exit
                        # close both).
                        pid = (
                            action.get("position_id")
                            or f"{symbol}-{date}-{position_seq}-long"
                        )
                        position_seq += 1
                        open_positions.append(
                            _RunnerPosition(
                                symbol=symbol,
                                size_pct=size_pct,
                                entry_price=entry_price,
                                cost=cost,
                                position_id=pid,
                                prev_close=entry_price,
                            )
                        )
                        cash_available -= cost
                    elif action_type == "exit_position":
                        pid = action.get("position_id")
                        if pid is None:
                            continue  # nothing identifiable to close
                        # An exit closes exactly one position — the first match.
                        for i, pos in enumerate(open_positions):
                            if pos.position_id == pid:
                                proceeds = pos.cost * (close / pos.entry_price)
                                cash_available += proceeds
                                realized_trade_returns.append(
                                    close / pos.entry_price - 1.0
                                )
                                del open_positions[i]
                                break

            position_value = sum(
                p.cost * (close / p.entry_price) for p in open_positions
            )
            capital = cash_available + position_value
            peak_capital = max(peak_capital, capital)
            cumulative_pnl = capital - initial_capital
            daily_starting_balance = capital
            for p in open_positions:
                p.prev_close = close

            self._db_store.save_portfolio_snapshot({
                "strategy_id": self._strategy_id,
                "snapshot_date": str(date)[:10],
                "capital": capital,
                "daily_pnl": daily_pnl,
                "cumulative_pnl": cumulative_pnl,
                "drawdown_pct": (peak_capital - capital) / peak_capital
                                if peak_capital else 0.0,
                "consistency_pct": 0.0,
                "open_positions": [p.position_id for p in open_positions],
            })

            if outcome == "ABORT" and termination_reason != "trading_cutoff":
                days_aborted += 1

            if outcome == "ABORT" and termination_reason == "mll_breached":
                break

            if outcome == "ABORT" and termination_reason in (
                "daily_loss_limit", "consistency_rule", "trading_cutoff"
            ):
                continue

        total_pnl = capital - initial_capital
        total_pnl_pct = total_pnl / initial_capital if initial_capital else 0.0
        max_drawdown_pct = (
            (peak_capital - capital) / peak_capital if peak_capital else 0.0
        )

        return BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            strategy_id=self._strategy_id,
            days_run=days_run,
            days_aborted=days_aborted,
            total_exchanges=len(exchanges),
            final_capital=capital,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            max_drawdown_pct=max_drawdown_pct,
            exchanges=exchanges,
        )
