from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.checker import check_constraints
from player_coach.constraints.schema import ConstraintSchema
from player_coach.evaluators.reasoning_evaluator import ReasoningEvaluator
from player_coach.loop.breaker_registry import BreakerRegistry
from player_coach.patterns.pattern_reader import read_patterns
from player_coach.patterns.pattern_writer import write_patterns

if TYPE_CHECKING:
    from player_coach.portfolio.state import PortfolioState
    from player_coach.database.store import DatabaseStore


class CoachLoop:
    def __init__(
        self,
        player: PlayerAgent,
        coach: CoachAgent,
        artifact_writer: ArtifactWriter,
        reasoning_evaluator: ReasoningEvaluator | None = None,
        breakers: BreakerRegistry | None = None,
    ) -> None:
        self._player = player
        self._coach = coach
        self._writer = artifact_writer
        self._reasoning_evaluator = reasoning_evaluator
        self._breakers = breakers or BreakerRegistry()

    def run(
        self,
        world_state: dict[str, Any],
        constraints: ConstraintSchema,
        portfolio_state: PortfolioState | None = None,
        db_store: DatabaseStore | None = None,
        strategy_id: str | None = None,
        output_dir: str | Path = "artifacts",
    ) -> dict[str, Any]:
        writer = (
            self._writer
            if Path(output_dir) == self._writer.output_dir
            else ArtifactWriter(output_dir)
        )

        if portfolio_state is not None:
            world_state = {**world_state, **portfolio_state.to_dict()}

        if portfolio_state is not None:
            # Circuit breakers, highest priority first (registry, Seam 3):
            # MLL (account terminated) → daily loss → consistency → cutoff.
            breach = self._breakers.first_breach(portfolio_state, constraints)
            if breach is not None:
                return self._abort_artifact(
                    breach, world_state, constraints,
                    portfolio_state, strategy_id,
                    db_store, writer, output_dir,
                )

        patterns: list[dict[str, Any]] = []
        if db_store is not None:
            patterns = read_patterns(
                db_store,
                symbol=world_state.get("symbol"),
                strategy_id=strategy_id,
            )

        max_rounds = constraints.max_rounds
        rounds: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = []

        for round_num in range(1, max_rounds + 1):
            player_result = self._player.decide(
                world_state=world_state,
                constraints=constraints,
                history=history or None,
                patterns=patterns or None,
            )
            proposal = {
                "actions": player_result["actions"],
                "reasoning": player_result["reasoning"],
            }

            coach_result = self._coach.evaluate(
                proposal=proposal,
                constraints=constraints,
                world_state=world_state,
            )
            verdict = coach_result["verdict"]
            violations = list(coach_result.get("violations", []))
            feedback = coach_result.get("critique") or ""

            # Mechanical enforcement: the numbers are authoritative. The LLM Coach
            # advises, but it cannot approve a proposal that breaks a numeric
            # constraint — and a hard breach aborts. Violations feed the Player's
            # next revision.
            mechanical = check_constraints(proposal, constraints, world_state)
            if mechanical:
                for v in mechanical:
                    if v not in violations:
                        violations.append(v)
                if verdict == "APPROVE":
                    verdict = "REJECT"
                note = "Mechanical constraint violations: " + ", ".join(mechanical)
                feedback = f"{feedback} | {note}" if feedback else note
            if verdict != "APPROVE" and any(
                v in constraints.abort_on_violations for v in violations
            ):
                verdict = "ABORT"

            reasoning_result: dict = {}
            if self._reasoning_evaluator is not None:
                reasoning_result = self._reasoning_evaluator.evaluate(
                    reasoning=player_result.get("reasoning", ""),
                    actions=player_result.get("actions", []),
                    world_state=world_state,
                )

            rounds.append({
                "round": round_num,
                "proposal": proposal,
                "evaluation": {
                    "decision": verdict,
                    "violations": violations,
                    "feedback": feedback,
                },
                # N5 — forward every key the agents reported, not just the
                # bare 'player'/'coach' counts. Otherwise cache_read_player /
                # cache_read_coach get dropped before reaching the DB or the
                # dashboard's token panel, and T1's whole observability
                # promise (cache-hit %) is invisible downstream.
                "tokens_used": {
                    **player_result["tokens_used"],
                    **coach_result["tokens_used"],
                },
                "reasoning_score": reasoning_result.get("reasoning_score"),
                "reasoning_critique": reasoning_result.get("reasoning_critique"),
            })
            history.append({
                "proposal": proposal,
                "evaluation": {"feedback": feedback},
            })

            if verdict in ("APPROVE", "ABORT"):
                outcome = verdict
                break
        else:
            outcome = "REJECT-MAX"

        artifact_path = writer.write(
            constraints=constraints.to_dict(),
            world_state=world_state,
            rounds=rounds,
            outcome=outcome,
        )
        artifact = json.loads(artifact_path.read_text())

        artifact["constraint_snapshot"] = constraints.to_dict()
        artifact["portfolio_snapshot"] = (
            portfolio_state.to_dict() if portfolio_state is not None else None
        )
        artifact["symbol"] = world_state.get("symbol")
        artifact["strategy_id"] = strategy_id
        artifact["daily_pnl_at_time"] = (
            portfolio_state.daily_pnl if portfolio_state is not None else None
        )

        artifact_path.write_text(json.dumps(artifact, indent=2))

        if db_store is not None:
            db_store.save_exchange(artifact)
            write_patterns(artifact, db_store, strategy_id=strategy_id)

        return artifact

    def _abort_artifact(
        self,
        reason: str,
        world_state: dict[str, Any],
        constraints: ConstraintSchema,
        portfolio_state: PortfolioState | None,
        strategy_id: str | None,
        db_store: DatabaseStore | None,
        writer: ArtifactWriter,
        output_dir: str | Path,
    ) -> dict[str, Any]:
        artifact_path = writer.write(
            constraints=constraints.to_dict(),
            world_state=world_state,
            rounds=[],
            outcome="ABORT",
        )
        artifact = json.loads(artifact_path.read_text())
        artifact["termination_reason"] = reason
        artifact["constraint_snapshot"] = constraints.to_dict()
        artifact["portfolio_snapshot"] = (
            portfolio_state.to_dict() if portfolio_state is not None else None
        )
        artifact["strategy_id"] = strategy_id
        artifact["symbol"] = world_state.get("symbol")
        artifact["daily_pnl_at_time"] = (
            portfolio_state.daily_pnl if portfolio_state is not None else None
        )

        artifact_path.write_text(json.dumps(artifact, indent=2))

        if db_store is not None:
            db_store.save_exchange(artifact)
            write_patterns(artifact, db_store, strategy_id=strategy_id)
        return artifact
