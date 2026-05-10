from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema


class CoachLoop:
    def __init__(
        self,
        player: PlayerAgent,
        coach: CoachAgent,
        artifact_writer: ArtifactWriter,
    ) -> None:
        self._player = player
        self._coach = coach
        self._writer = artifact_writer

    def run(
        self,
        world_state: dict[str, Any],
        constraints: ConstraintSchema,
        output_dir: str | Path = "artifacts",
    ) -> dict[str, Any]:
        writer = (
            self._writer
            if Path(output_dir) == self._writer.output_dir
            else ArtifactWriter(output_dir)
        )
        max_rounds = constraints.max_rounds
        rounds: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = []

        for round_num in range(1, max_rounds + 1):
            player_result = self._player.decide(
                world_state=world_state,
                constraints=constraints,
                history=history or None,
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

            rounds.append({
                "round": round_num,
                "proposal": proposal,
                "evaluation": {
                    "decision": verdict,
                    "violations": coach_result["violations"],
                    "feedback": coach_result["critique"],
                },
                "tokens_used": {
                    "player": player_result["tokens_used"]["player"],
                    "coach": coach_result["tokens_used"]["coach"],
                },
            })
            history.append({
                "proposal": proposal,
                "critique": coach_result["critique"],
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
        return json.loads(artifact_path.read_text())
