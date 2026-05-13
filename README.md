# player-coach

Adversarial quality loop for trading decisions.
Part of the [Crucible](https://github.com/MaverickHQ) project.
GitHub: [github.com/MaverickHQ/crucible-player-coach](https://github.com/MaverickHQ/crucible-player-coach)

## Project status

**Current milestone: v1.0.0 — Full system complete**

**Backend:** PlayerAgent, CoachAgent, CoachLoop, circuit breakers, backtesting engine, SQLite persistence, ConstraintDeriver from ewm-core evidence policy.

**Dashboard:** Four-page Streamlit app — Trade Review (streaming exchange with animated characters), Constraints (12-field configuration with presets), History (SQLite-backed replay), Settings (BYOK).

Phase 3 (player-coach) is complete. Backlog: AWS AgentCore deployment.

## What this repository builds

A CoachAgent challenges and refines a PlayerAgent's trading proposals before execution. Both agents use Claude Haiku via the Anthropic API. Every proposal, rejection, revision, and approval is recorded as a structured artifact.

## Dashboard

A four-page Streamlit dashboard for running and reviewing player-coach exchanges.

**Trade Review** — Run a live exchange. Player and Coach characters animate with streaming speech bubbles. Round cards show proposals, verdicts, violations, and critique. Full artifact JSON viewer.

**Constraints** — Configure the Coach's constraint schema. Load presets, adjust sliders, export JSON, or push directly to the Trade Review page.

**History** — Browse past exchanges from SQLite. Filter by outcome. Select any row to inspect rounds and replay with animation.

**Settings** — BYOK API key entry and validation. Key lives in session memory only, never stored.

```bash
pip install player-coach-core[dashboard]
streamlit run dashboard/app.py
```

## Installation

```bash
pip install player-coach-core          # core only
pip install player-coach-core[llm]     # + Anthropic SDK
pip install player-coach-core[dashboard]  # + Streamlit dashboard
```

## Constraint schema

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

## Architecture

| Component | Description |
|---|---|
| `PlayerAgent` | Proposes actions given world state. Claude Haiku, max_tokens=512. |
| `CoachAgent` | Evaluates proposals against constraint schema. Claude Haiku, max_tokens=1024. |
| `CoachLoop` | Orchestrates the exchange. Up to 3 rounds. Writes structured artifact. |
| `BacktestRunner` | Runs CoachLoop over historical trading days. |
| `CircuitBreakers` | MLL, daily loss limit, consistency rule, trading cutoff. |
| `DatabaseStore` | SQLite persistence for exchanges, rounds, and strategies. |

## Essays

| Essay | Description |
|---|---|
| Essay 8a — Theory (coming soon) | Adversarial quality in agent systems |
| Essay 8b — Implementation (coming soon) | How player-coach works, GitHub link |
