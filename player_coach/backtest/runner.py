from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yfinance as yf

from player_coach.analytics import (
    apply_monte_carlo_trigger,
    half_kelly,
    simulate_challenge,
    trade_stats,
)
from player_coach.backtest.metrics import (
    avg_recovery_time,
    calmar_ratio,
    drawdown_duration,
    sharpe_ratio,
    sortino_ratio,
)
from player_coach.constraints.phase_profiles import challenge_phase
from player_coach.constraints.resolver import (
    ConstraintResolver,
    clamp_invariants,
    garch_scale,
    phase_profile,
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
    # Seam 5: per-day (date, capital) — the basis for risk/drawdown metrics.
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    # Feature 17: risk-adjusted return metrics computed from the equity curve.
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    # Feature 18: drawdown profile — distinguishes one-catastrophe from
    # many-small-loss strategies at the same max drawdown.
    max_drawdown_duration: int = 0
    avg_recovery_time: float = 0.0
    # Feature 17 (A3): challenge P(pass) projected from this config's realised
    # edge — the challenge-specific evaluation criterion (vs raw return).
    mc_success_prob: float = 0.0


@dataclass
class _RunnerPosition:
    symbol: str
    size_pct: float
    entry_price: float
    cost: float
    position_id: str
    direction: str = "long"
    prev_close: float = 0.0

    def value(self, price: float) -> float:
        """Mark-to-market value; a short gains as price falls."""
        if self.entry_price == 0:
            return self.cost
        ratio = price / self.entry_price
        return self.cost * (2.0 - ratio) if self.direction == "short" else self.cost * ratio

    def daily_change(self, close: float) -> float:
        if not self.prev_close:
            return 0.0
        move = (close - self.prev_close) / self.prev_close
        if self.direction == "short":
            move = -move
        return move * self.cost

    def realized_return(self, close: float) -> float:
        if self.entry_price == 0:
            return 0.0
        r = close / self.entry_price - 1.0
        return -r if self.direction == "short" else r

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "size_pct": self.size_pct,
        }


def _compute_sma(prices, n: int) -> float:
    length = len(prices)
    if length == 0:
        return 0.0
    if length < n:
        return float(prices[-1])
    return float(sum(prices[-n:]) / n)


def _gap_preserves_setup(
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    min_risk_reward: float,
) -> bool:
    """N2 — at fill time, the Player's proposed entry_price has been replaced
    with today's open. The Coach already approved direction + RR against the
    proposal; re-check both against the actual fill so we don't book a trade
    whose geometry the gap has broken.

    Returns False for malformed proposals (non-positive stop/tp) and for any
    fill where the gap inverts direction or compresses RR below the schema's
    floor. Uses the same |tp - entry| / |entry - stop| formula the Coach
    uses (player_coach/agents/coach.py:108), so the two paths cannot diverge.
    """
    if stop_loss <= 0 or take_profit <= 0:
        return False
    if direction == "long":
        if not (stop_loss < entry_price < take_profit):
            return False
    else:  # short
        if not (take_profit < entry_price < stop_loss):
            return False
    risk = abs(entry_price - stop_loss)
    if risk == 0:
        return False
    return abs(take_profit - entry_price) / risk >= min_risk_reward


class BacktestRunner:
    def __init__(
        self,
        loop: CoachLoop,
        db_store: DatabaseStore,
        strategy_id: str,
        enricher: WorldStateEnricher | None = None,
        resolver: ConstraintResolver | None = None,
        transaction_cost_pct: float = 0.001,
        profit_target: float = 0.06,
        mc_min_trades: int = 10,
        mc_every: int = 20,
        mc_paths: int = 1_000,
        mc_trades_per_day: float = 1.0,
        mc_eval_horizon: int = 20,
        on_day: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._loop = loop
        self._db_store = db_store
        self._strategy_id = strategy_id
        # F16: round-trip transaction cost, charged half on entry, half on exit.
        self._transaction_cost_pct = transaction_cost_pct
        # F14: Monte Carlo P(pass) is recomputed on a cadence (not every bar) once
        # enough trades have closed; it feeds the auto-conservation trigger.
        self._profit_target = profit_target
        self._mc_min_trades = mc_min_trades
        self._mc_every = mc_every
        self._mc_paths = mc_paths
        self._mc_trades_per_day = mc_trades_per_day
        self._mc_eval_horizon = mc_eval_horizon
        # Optional per-day progress callback for live dashboards (Streamlit).
        # Called once per bar, after the day's accounting; never raises into the
        # loop so a bad subscriber can't kill a long run.
        self._on_day = on_day
        # F6 regime + F7 GARCH enrich world state; the resolver then layers the
        # regime overlay and (on top) garch volatility-scaling onto constraints.
        self._enricher = enricher or WorldStateEnricher(
            [RegimeFeature(), GARCHFeature(), ATRFeature(), VWAPFeature()]
        )
        self._resolver = resolver or ConstraintResolver(
            [regime_overlay(), garch_scale(), phase_profile(), clamp_invariants()]
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
        equity_curve: list[tuple[str, float]] = []
        total_days = len(df)
        mc_prob: float | None = None

        for day_index, (date, row) in enumerate(df.iterrows()):
            today_open = float(row["Open"])
            close = float(row["Close"])
            high = float(row["High"])
            low = float(row["Low"])
            volume = int(row["Volume"])

            # A1 — Seam 0 bar-timing fidelity. The decision uses the buffer
            # *before* today's bar is appended (so the agent sees only data
            # through yesterday), and any approved entry/exit fills at TODAY's
            # OPEN — the first price you could realistically transact at.
            # Mark-to-market still happens at today's close at the end of the
            # iteration. Day 0 has no prior bars, so it can't make a decision —
            # we just append the bar and mark to market.
            artifact: dict | None = None
            outcome: str | None = None
            termination_reason: str | None = None
            phase: str | None = None

            if day_index > 0:
                closes = buffer.closes  # buffer holds bars [0..day_index-1]
                prior_close = float(closes[-1])

                # N1 + N7 — overnight gap MTM on held positions. This is the
                # ONLY P&L that has accrued by decision time today (no trades
                # yet), and it's the mechanically correct input for both the
                # daily_loss_limit breaker AND the F13 consistency signal:
                # "if you locked in right now, this is today's day_pnl".
                gap_mtm = sum(p.daily_change(today_open) for p in open_positions)

                # F14: recompute P(pass) on cadence.
                if (len(realized_trade_returns) >= self._mc_min_trades
                        and day_index % self._mc_every == 0):
                    mc_prob = simulate_challenge(
                        trade_stats(realized_trade_returns),
                        profit_target=self._profit_target,
                        drawdown_limit=constraints.trailing_max_drawdown_pct,
                        days_remaining=max(0, total_days - day_index),
                        trades_per_day=self._mc_trades_per_day,
                        n_paths=self._mc_paths,
                    ).success_probability

                portfolio_state = PortfolioState(
                    capital=capital,
                    daily_starting_balance=daily_starting_balance,
                    peak_capital=peak_capital,
                    cash_available=cash_available,
                    # Seam 0: the Player sees its open book and can propose exits.
                    open_positions=list(open_positions),
                    daily_pnl=gap_mtm,
                    cumulative_pnl=cumulative_pnl,
                )

                challenge_pnl_pct = (
                    cumulative_pnl / initial_capital if initial_capital else 0.0
                )
                phase = apply_monte_carlo_trigger(
                    challenge_phase(challenge_pnl_pct), mc_prob
                )
                world_state_obj = WorldState(
                    symbol=symbol,
                    price=prior_close,  # yesterday's close — past data only
                    sma5=_compute_sma(closes, 5),
                    sma10=_compute_sma(closes, 10),
                    volume=volume,
                    challenge_pnl_pct=challenge_pnl_pct,
                    challenge_phase=phase,
                    consistency_status=constraints.consistency_status(
                        gap_mtm, cumulative_pnl
                    ),
                    mc_success_prob=mc_prob,
                )
                self._enricher.enrich(world_state_obj, buffer)
                world_state: dict[str, Any] = world_state_obj.to_dict()
                resolved_constraints = self._resolver.resolve(
                    constraints, world_state
                )

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
                outcome = artifact.get("outcome")
                termination_reason = artifact.get("termination_reason")

                if outcome == "APPROVE":
                    for action in artifact.get("rounds", [{}])[-1].get(
                        "proposal", {}
                    ).get("actions", []):
                        action_type = action.get("action_type")
                        if action_type in ("enter_long", "enter_short"):
                            direction = (
                                "short" if action_type == "enter_short" else "long"
                            )
                            # Fill at today's OPEN — the actionable price.
                            entry_price = today_open
                            # N2 — Coach approved direction + RR against the
                            # Player's proposal, but the fill price is today's
                            # open. If the gap broke the geometry, skip rather
                            # than book a trade the Coach would never approve
                            # at the actual fill price.
                            if not _gap_preserves_setup(
                                direction,
                                entry_price,
                                float(action.get("stop_loss", 0.0)),
                                float(action.get("take_profit", 0.0)),
                                resolved_constraints.min_risk_reward,
                            ):
                                continue
                            size_pct = float(action.get("size_pct", 0.0))
                            cost = capital * size_pct
                            pid = (
                                action.get("position_id")
                                or f"{symbol}-{date}-{position_seq}-{direction}"
                            )
                            position_seq += 1
                            open_positions.append(
                                _RunnerPosition(
                                    symbol=symbol, size_pct=size_pct,
                                    entry_price=entry_price, cost=cost,
                                    position_id=pid, direction=direction,
                                    prev_close=entry_price,
                                )
                            )
                            cash_available -= cost
                            cash_available -= (
                                cost * self._transaction_cost_pct / 2.0
                            )
                        elif action_type == "exit_position":
                            pid = action.get("position_id")
                            if pid is None:
                                continue
                            for i, pos in enumerate(open_positions):
                                if pos.position_id == pid:
                                    # Exit fills at today's OPEN.
                                    cash_available += pos.value(today_open)
                                    cash_available -= (
                                        pos.cost
                                        * self._transaction_cost_pct
                                        / 2.0
                                    )
                                    realized_trade_returns.append(
                                        pos.realized_return(today_open)
                                    )
                                    del open_positions[i]
                                    break

            # End-of-day: append today's bar, mark to market at today's close.
            buffer.append(
                open=today_open, high=high, low=low,
                close=close, volume=volume,
            )
            daily_pnl = sum(p.daily_change(close) for p in open_positions)
            position_value = sum(p.value(close) for p in open_positions)
            capital = cash_available + position_value
            peak_capital = max(peak_capital, capital)
            cumulative_pnl = capital - initial_capital
            daily_starting_balance = capital
            equity_curve.append((str(date)[:10], capital))
            for p in open_positions:
                p.prev_close = close
            days_run += 1

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

            # Live progress: fire AFTER accounting but BEFORE any break/continue
            # short-circuit so abort days are reported too. A subscriber raising
            # is swallowed; we never let a UI bug derail a long backtest.
            if self._on_day is not None:
                try:
                    self._on_day({
                        "day": day_index + 1,
                        "total_days": total_days,
                        "date": str(date)[:10],
                        "capital": capital,
                        "daily_pnl": daily_pnl,
                        "challenge_phase": phase,
                        "outcome": outcome,
                        "termination_reason": termination_reason,
                        "days_aborted": days_aborted,
                        "mc_success_prob": mc_prob,
                    })
                except Exception:
                    pass

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
            equity_curve=equity_curve,
            sharpe=sharpe_ratio(equity_curve),
            sortino=sortino_ratio(equity_curve),
            calmar=calmar_ratio(equity_curve),
            max_drawdown_duration=drawdown_duration(equity_curve),
            avg_recovery_time=avg_recovery_time(equity_curve),
            mc_success_prob=simulate_challenge(
                trade_stats(realized_trade_returns),
                profit_target=self._profit_target,
                drawdown_limit=constraints.trailing_max_drawdown_pct,
                days_remaining=self._mc_eval_horizon,
                trades_per_day=self._mc_trades_per_day,
                n_paths=self._mc_paths,
            ).success_probability,
        )
