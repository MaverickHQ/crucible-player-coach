# player-coach — Claude Code Guide

Adversarial quality loop for trading decisions.
Part of the Crucible project.
GitHub: github.com/MaverickHQ/crucible-player-coach

## What this builds
A CoachAgent challenges and refines a PlayerAgent's trading
proposals before execution. Both agents use Claude Haiku via
Anthropic API. Every proposal, rejection, revision, and
approval is recorded as a structured artifact.

## Working directory
/Users/maverick/crucible/player-coach

## Package targets
pip install player-coach-core
pip install player-coach-core[llm]   # Anthropic SDK
pip install player-coach-core[aws]   # Bedrock backend (backlog)

## Depends on
ewm-core (trajectory, artifact, evaluation infrastructure)

## Architecture

### PlayerAgent (player_coach/agents/player.py)
- Proposes a plan of actions given current world state
- Claude Haiku via Anthropic API, max_tokens=512
- Returns proposed actions with reasoning
- On revision: receives full history of all prior proposals
  and critiques from the Coach

### CoachAgent (player_coach/agents/coach.py)
- Evaluates proposals against a formal constraint schema
- Claude Haiku via Anthropic API, max_tokens=256
- Returns: approved/rejected + named constraint violations
- Evaluates mechanically against constraint numbers — not vaguely
- Hard violations abort immediately (no revision allowed)

### CoachLoop (player_coach/loop/coach_loop.py)
- Orchestrates the exchange between Player and Coach
- Maximum 3 rounds by default (configurable)
- Termination policies:
    APPROVE       — Coach approves at any round
    REJECT-MAX    — 3 rounds reached without approval
    ABORT         — Hard constraint violation, no revision
- Feeds full exchange history to Player on each revision
- Writes structured artifact after every run via ArtifactWriter

## Constraint schema format
Defined in player_coach/constraints/schema.py
Presets in examples/constraints/
Hard violations defined per schema (abort immediately)

```json
{
  "max_position_pct": 0.15,
  "max_single_trade_pct": 0.05,
  "max_leverage": 1.5,
  "max_drawdown_pct": 0.10,
  "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
  "max_open_positions": 3,
  "min_risk_reward": 1.5,
  "max_rounds": 3,
  "abort_on_violations": ["max_leverage", "max_drawdown_pct"]
}
```

## Token budgets
PlayerAgent: max_tokens=512
CoachAgent:  max_tokens=256
Max API calls per exchange: 6 (3 rounds x 2 agents)

## Phase checklist
- [ ] Phase 1: Scaffold — pyproject.toml, package structure,
                constraint schema, artifact format defined
- [ ] Phase 2: PlayerAgent
- [ ] Phase 3: CoachAgent
- [ ] Phase 4: CoachLoop + artifact writer
- [ ] Phase 5: Demo script + unit tests
- [ ] Phase 6: Streamlit dashboard (exchange panel, constraint
                config page, history panel, BYOK page)
- [ ] Phase 7: Animated characters (SVG Player + Coach,
                streaming speech bubbles, state changes)
- [ ] Phase 8: PyPI publish player-coach-core v1.0.0

## Backlog
- AWS AgentCore deployment (Phase 5b of full Crucible series)
- Code domain: PlayerAgent writes code, CoachAgent reviews

## Essays
Essay 8a: theory — adversarial quality in agent systems
Essay 8b: implementation — how player-coach works, GitHub link

## Session rules
- One phase per session
- /compact after completing each file
- Never read the whole repo before starting a task
- Define constraint schema and artifact format in Phase 1
  before writing any agent code
- Run tests after each component before moving on
