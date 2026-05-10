from __future__ import annotations
import json
import sys
from pathlib import Path

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.loop.coach_loop import CoachLoop

WORLD_STATE = {
    "symbol": "AMZN",
    "price": 185.00,
    "sma5": 183.00,
    "sma10": 180.00,
    "volume": 45_000_000,
    "position": "flat",
    "volatility_regime": "medium",
    "session": "NY_open",
}

CONSTRAINTS_PATH = Path("examples/constraints/moderate.json")
OUTPUT_DIR = Path("artifacts")


def _print_constraints(constraints: ConstraintSchema) -> None:
    print("  Active constraints:")
    print(f"    max_position_pct:      {constraints.max_position_pct:.0%}")
    print(f"    max_single_trade_pct:  {constraints.max_single_trade_pct:.0%}")
    print(f"    max_open_positions:    {constraints.max_open_positions}")
    print(f"    min_risk_reward:       {constraints.min_risk_reward}x")
    print(f"    max_leverage:          {constraints.max_leverage}x")
    print(f"    max_drawdown_pct:      {constraints.max_drawdown_pct:.0%}")
    print(f"    max_rounds:            {constraints.max_rounds}")
    print(f"    abort_on_violations:   {constraints.abort_on_violations}")
    print()


def main() -> None:
    constraints_raw = json.loads(CONSTRAINTS_PATH.read_text())
    constraints = ConstraintSchema.from_dict(constraints_raw)

    player = PlayerAgent()
    coach = CoachAgent()
    writer = ArtifactWriter(OUTPUT_DIR)
    loop = CoachLoop(player=player, coach=coach, artifact_writer=writer)

    print("Running player-coach loop...")
    print(f"World state: AMZN @ ${WORLD_STATE['price']}, session={WORLD_STATE['session']}")
    print(f"Max rounds: {constraints.max_rounds}\n")
    _print_constraints(constraints)

    artifact = loop.run(
        world_state=WORLD_STATE,
        constraints=constraints,
        output_dir=OUTPUT_DIR,
    )

    for round_ in artifact["rounds"]:
        n = round_["round"]
        proposal = round_["proposal"]
        evaluation = round_["evaluation"]
        actions = proposal.get("actions", [])
        action_summary = ", ".join(
            f"{a['side'].upper()} {a['symbol']} {a['size_pct']:.1%}"
            for a in actions
        ) or "(none)"
        reasoning = proposal.get("reasoning", "")
        print(f"Round {n}")
        print(f"  Player:  {action_summary}")
        if reasoning:
            print(f"  Reasoning: {reasoning[:120]}{'...' if len(reasoning) > 120 else ''}")
        print(f"  Verdict: {evaluation['decision']}")
        if evaluation["violations"]:
            print(f"  Violations: {', '.join(evaluation['violations'])}")
        if evaluation["feedback"]:
            print(f"  Critique: {evaluation['feedback']}")
        print()

    outcome = artifact["outcome"]
    run_id = artifact["run_id"]
    artifact_path = OUTPUT_DIR / f"{run_id}.json"
    print(f"Outcome: {outcome}")
    print(f"Artifact: {artifact_path}")

    print("\n" + "="*50)
    print("Scenario 2 — strict constraints")
    print("="*50 + "\n")

    strict_path = Path("examples/constraints/strict.json")
    strict_constraints = ConstraintSchema.from_dict(
        json.loads(strict_path.read_text())
    )
    _print_constraints(strict_constraints)

    artifact2 = loop.run(
        world_state=WORLD_STATE,
        constraints=strict_constraints,
        output_dir=OUTPUT_DIR,
    )

    for round_ in artifact2["rounds"]:
        n = round_["round"]
        proposal = round_["proposal"]
        evaluation = round_["evaluation"]
        actions = proposal.get("actions", [])
        action_summary = ", ".join(
            f"{a['side'].upper()} {a['symbol']} {a['size_pct']:.1%}"
            for a in actions
        ) or "(none)"
        reasoning = proposal.get("reasoning", "")
        print(f"Round {n}")
        print(f"  Player:  {action_summary}")
        if reasoning:
            print(f"  Reasoning: {reasoning[:120]}{'...' if len(reasoning) > 120 else ''}")
        print(f"  Verdict: {evaluation['decision']}")
        if evaluation["violations"]:
            print(f"  Violations: {', '.join(evaluation['violations'])}")
        if evaluation["feedback"]:
            print(f"  Critique: {evaluation['feedback']}")
        print()

    print(f"Outcome: {artifact2['outcome']}")
    print(f"Artifact: {OUTPUT_DIR / artifact2['run_id']}.json")


if __name__ == "__main__":
    main()
