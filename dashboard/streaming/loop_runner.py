from __future__ import annotations

import json
from collections.abc import Generator

from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.database.store import DatabaseStore
from player_coach.loop.circuit_breakers import (
    is_consistency_rule_breached,
    is_daily_loss_limit_breached,
    is_mll_breached,
    is_trading_cutoff_reached,
)
from player_coach.portfolio.state import PortfolioState

from dashboard.streaming.coach_stream import stream_coach_evaluation
from dashboard.streaming.player_stream import stream_player_decision
from player_coach.evaluators.reasoning_evaluator import ReasoningEvaluator
from player_coach.patterns.pattern_reader import read_patterns
from player_coach.patterns.pattern_writer import write_patterns


class DashboardRunner:
    def __init__(
        self,
        constraints: ConstraintSchema,
        world_state: dict,
        portfolio_state: PortfolioState | None,
        api_key: str,
        db_store: DatabaseStore | None = None,
        strategy_id: str | None = None,
    ) -> None:
        self._constraints = constraints
        self._world_state = world_state
        self._portfolio_state = portfolio_state
        self._api_key = api_key
        self._db_store = db_store
        self._strategy_id = strategy_id
        try:
            self._reasoning_evaluator: ReasoningEvaluator | None = ReasoningEvaluator(
                api_key=api_key
            )
        except ImportError:
            self._reasoning_evaluator = None

    def run(self) -> Generator[dict, None, None]:
        if self._portfolio_state is not None:
            checks = [
                (is_mll_breached, "mll_breached"),
                (is_daily_loss_limit_breached, "daily_loss_limit"),
                (is_consistency_rule_breached, "consistency_rule"),
                (is_trading_cutoff_reached, "trading_cutoff"),
            ]
            for fn, reason in checks:
                args = (
                    (self._constraints,)
                    if fn is is_trading_cutoff_reached
                    else (self._portfolio_state, self._constraints)
                )
                if fn(*args):
                    _writer = ArtifactWriter(output_dir="artifacts")
                    _path = _writer.write(
                        constraints=self._constraints.to_dict(),
                        world_state=self._world_state,
                        rounds=[],
                        outcome="ABORT",
                    )
                    _cb = json.loads(_path.read_text())
                    _cb["termination_reason"] = reason
                    _cb["constraint_snapshot"] = self._constraints.to_dict()
                    _cb["portfolio_snapshot"] = (
                        self._portfolio_state.to_dict()
                        if self._portfolio_state else None
                    )
                    _cb["strategy_id"] = self._strategy_id
                    _cb["symbol"] = self._world_state.get("symbol")
                    _cb["daily_pnl_at_time"] = (
                        self._portfolio_state.daily_pnl
                        if self._portfolio_state else None
                    )
                    _path.write_text(json.dumps(_cb, indent=2))
                    if self._db_store is not None:
                        self._db_store.save_exchange(_cb)
                        write_patterns(_cb, self._db_store,
                                       strategy_id=self._strategy_id)
                    yield {"type": "circuit_breaker", "reason": reason}
                    return

        patterns: list[dict] = []
        if self._db_store is not None:
            patterns = read_patterns(
                self._db_store,
                symbol=self._world_state.get("symbol"),
                strategy_id=self._strategy_id,
            )

        rounds: list[dict] = []
        history: list[dict] | None = None
        player_result: dict = {}
        outcome = "REJECT-MAX"

        for n in range(1, self._constraints.max_rounds + 1):
            yield {"type": "round_start", "round": n}

            player_tokens = 0
            coach_tokens = 0
            try:
                for event in stream_player_decision(
                    self._world_state, self._constraints, history, self._api_key,
                    patterns=patterns or None,
                ):
                    if isinstance(event, dict) and event.get("__done__"):
                        player_result = event["result"]
                        player_tokens = event.get("tokens", 0)
                        yield {"type": "player_done", "result": player_result}
                    else:
                        yield {"type": "player_token", "text": event}

                coach_result: dict = {}
                for event in stream_coach_evaluation(
                    player_result, self._constraints, self._world_state, self._api_key
                ):
                    if isinstance(event, dict) and event.get("__done__"):
                        coach_result = event["result"]
                        coach_tokens = event.get("tokens", 0)
                        yield {"type": "coach_done", "result": coach_result}
                    else:
                        yield {"type": "coach_token", "text": event}

            except Exception as exc:
                yield {"type": "error", "message": str(exc)}
                return

            verdict = coach_result.get("verdict", "REJECT")

            reasoning_result: dict = {}
            if self._reasoning_evaluator is not None:
                try:
                    reasoning_result = self._reasoning_evaluator.evaluate(
                        reasoning=player_result.get("reasoning", ""),
                        actions=player_result.get("actions", []),
                        world_state=self._world_state,
                    )
                except Exception:
                    reasoning_result = {
                        "reasoning_score": None,
                        "reasoning_critique": "evaluation unavailable",
                    }
            yield {
                "type": "reasoning_done",
                "score": reasoning_result.get("reasoning_score"),
                "critique": reasoning_result.get("reasoning_critique"),
            }

            round_dict = {
                "round": n,
                "proposal": {
                    "actions": player_result.get("actions", []),
                    "reasoning": player_result.get("reasoning", ""),
                },
                "evaluation": {
                    "decision": verdict,
                    "violations": coach_result.get("violations", []),
                    "feedback": coach_result.get("critique", ""),
                },
                "tokens_used": {"player": player_tokens, "coach": coach_tokens},
                "reasoning_score": reasoning_result.get("reasoning_score"),
                "reasoning_critique": reasoning_result.get("reasoning_critique"),
            }
            rounds.append(round_dict)
            yield {"type": "round_end", "round": round_dict}

            if verdict == "APPROVE":
                outcome = "APPROVE"
                break
            if verdict == "ABORT":
                outcome = "ABORT"
                break

            history = rounds

        writer = ArtifactWriter(output_dir="artifacts")
        artifact_path = writer.write(
            constraints=self._constraints.to_dict(),
            world_state=self._world_state,
            rounds=rounds,
            outcome=outcome,
        )
        artifact = json.loads(artifact_path.read_text())
        artifact["constraint_snapshot"] = self._constraints.to_dict()
        artifact["portfolio_snapshot"] = (
            self._portfolio_state.to_dict() if self._portfolio_state else None
        )
        artifact["strategy_id"] = self._strategy_id
        artifact["symbol"] = self._world_state.get("symbol")
        artifact["daily_pnl_at_time"] = (
            self._portfolio_state.daily_pnl if self._portfolio_state else None
        )
        artifact_path.write_text(json.dumps(artifact, indent=2))

        if self._db_store is not None:
            self._db_store.save_exchange(artifact)
            write_patterns(artifact, self._db_store,
                           strategy_id=self._strategy_id)

        yield {"type": "loop_done", "artifact": artifact}
