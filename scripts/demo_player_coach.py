from __future__ import annotations
import json
from pathlib import Path

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.artifacts.writer import ArtifactWriter
from player_coach.constraints.schema import ConstraintSchema
from player_coach.database.store import DatabaseStore
from player_coach.loop.coach_loop import CoachLoop
from player_coach.market import WorldState

WORLD_STATE = WorldState(
    symbol="AMZN",
    price=185.00,
    sma5=183.00,
    sma10=180.00,
    volume=45_000_000,
    position="flat",
    volatility_regime="medium",
).to_dict()

CONSTRAINTS_PATH = Path("examples/constraints/moderate.json")
DATA_DIR = Path("data")
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


def _print_rounds(artifact: dict, output_dir: Path) -> None:
    for round_ in artifact["rounds"]:
        n = round_["round"]
        proposal = round_["proposal"]
        evaluation = round_["evaluation"]
        actions = proposal.get("actions", [])
        action_summary = ", ".join(
            f"{a.get('action_type', 'unknown').upper()} {a.get('symbol', '')} "
            f"{a['size_pct']:.1%}" if a.get("size_pct") is not None
            else f"{a.get('action_type', 'unknown').upper()} {a.get('symbol', '')}"
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
        feedback = evaluation.get("feedback") or ""
        if feedback:
            print(f"  Coach: {feedback}")
        print()

    run_id = artifact["run_id"]
    print(f"Outcome: {artifact['outcome']}")
    print(f"Artifact: {output_dir / run_id}.json")


def _scenario_4(loop: CoachLoop, store: DatabaseStore, output_dir: Path) -> None:
    from player_coach.portfolio.state import PortfolioState

    print("\n" + "=" * 50)
    print("Scenario 4 — circuit breaker demo")
    print("=" * 50 + "\n")

    conservative_constraints = ConstraintSchema.from_dict(
        json.loads(Path("examples/constraints/conservative.json").read_text())
    )

    portfolio_state = PortfolioState(
        capital=9_780.0,
        daily_starting_balance=10_000.0,
        peak_capital=10_000.0,
        cash_available=9_780.0,
        daily_pnl=-220.0,
    )

    artifact = loop.run(
        world_state=WORLD_STATE,
        constraints=conservative_constraints,
        portfolio_state=portfolio_state,
        db_store=store,
        strategy_id="demo-circuit-breaker",
        output_dir=output_dir,
    )
    print(f"Outcome:            {artifact['outcome']}")
    print(f"Termination reason: {artifact.get('termination_reason', 'n/a')}")


def _scenario_5(loop: CoachLoop, store: DatabaseStore, output_dir: Path) -> None:
    from player_coach.constraints.deriver import ConstraintDeriver

    print("\n" + "=" * 50)
    print("Scenario 5 — ConstraintDeriver from evidence")
    print("=" * 50 + "\n")

    evidence_policy = {
        "runs": [
            {"outcome": "success", "trade_size_pct": 0.03, "risk_reward": 2.0},
            {"outcome": "success", "trade_size_pct": 0.04, "risk_reward": 2.5},
            {"outcome": "failure", "trade_size_pct": 0.15, "risk_reward": 0.5},
        ],
        "patterns": [
            {"symbol": "AMZN", "confidence": 0.85},
            {"symbol": "MSFT", "confidence": 0.70},
        ],
    }

    derived = ConstraintDeriver(evidence_policy).derive()
    print(f"max_single_trade_pct: {derived.max_single_trade_pct:.0%}")
    print(f"min_risk_reward:      {derived.min_risk_reward}x")
    print(f"allowed_symbols:      {derived.allowed_symbols}")
    print()

    artifact = loop.run(
        world_state=WORLD_STATE,
        constraints=derived,
        db_store=store,
        strategy_id="demo-derived-constraints",
        output_dir=output_dir,
    )
    print(f"Exchange outcome: {artifact['outcome']}")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    store = DatabaseStore(DATA_DIR / "player_coach.db")
    strategy_id = "demo-moderate"
    constraints_raw = json.loads(CONSTRAINTS_PATH.read_text())
    store.save_strategy({
        "strategy_id": strategy_id,
        "name": "Demo Moderate",
        "description": "Demo run — moderate constraints",
        "constraint_schema": constraints_raw,
    })

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
        db_store=store,
        strategy_id=strategy_id,
        output_dir=OUTPUT_DIR,
    )
    _print_rounds(artifact, OUTPUT_DIR)

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
        db_store=store,
        strategy_id=strategy_id,
        output_dir=OUTPUT_DIR,
    )
    _print_rounds(artifact2, OUTPUT_DIR)

    print("\n--- Exchange history ---")
    for ex in store.get_exchanges():
        print(
            f"{ex['run_id'][:8]}  "
            f"{ex['outcome']:12}  "
            f"rounds={ex['rounds_taken']}  "
            f"tokens={ex['total_tokens']}"
        )

    print("\n" + "="*50)
    print("Scenario 3 — backtest AMZN 2024-01-02 to 2024-01-15")
    print("="*50 + "\n")

    from player_coach.backtest.runner import BacktestRunner

    backtest_strategy_id = "demo-backtest-moderate"
    store.save_strategy({
        "strategy_id": backtest_strategy_id,
        "name": "Demo Backtest Moderate",
        "description": "10-day backtest — moderate constraints",
        "constraint_schema": constraints_raw,
    })

    runner = BacktestRunner(
        loop=loop,
        db_store=store,
        strategy_id=backtest_strategy_id,
    )
    result = runner.run(
        symbol="AMZN",
        start_date="2024-01-02",
        end_date="2024-01-15",
        constraints=constraints,
        output_dir=OUTPUT_DIR,
    )

    print(f"Days run:         {result.days_run}")
    print(f"Total exchanges:  {result.total_exchanges}")
    print(f"Final capital:    ${result.final_capital:,.2f}")
    print(f"Total P&L:        ${result.total_pnl:+,.2f} ({result.total_pnl_pct:+.2%})")
    print(f"Max drawdown:     {result.max_drawdown_pct:.2%}")

    _scenario_4(loop, store, OUTPUT_DIR)
    _scenario_5(loop, store, OUTPUT_DIR)


if __name__ == "__main__":
    main()
