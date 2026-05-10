from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArtifactWriter:
    def __init__(self, output_dir: str | Path = "artifacts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        constraints: dict[str, Any],
        world_state: dict[str, Any],
        rounds: list[dict[str, Any]],
        outcome: str,
    ) -> Path:
        artifact = {
            "run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,  # "APPROVE" | "REJECT-MAX" | "ABORT"
            "approved": outcome == "APPROVE",
            "rounds_taken": len(rounds),
            "termination_reason": outcome,
            "total_tokens": sum(
                r.get("tokens_used", {}).get("player", 0) +
                r.get("tokens_used", {}).get("coach", 0)
                for r in rounds
            ),
            "constraints": constraints,
            "world_state": world_state,
            "rounds": rounds,
            # rounds[n] = {
            #   "round": int,
            #   "proposal": {"actions": [...], "reasoning": str},
            #   "evaluation": {"decision": str, "violations": [...], "feedback": str},
            #   "tokens_used": {"player": int, "coach": int},
            # }
        }
        path = self.output_dir / f"{artifact['run_id']}.json"
        path.write_text(json.dumps(artifact, indent=2))
        return path
