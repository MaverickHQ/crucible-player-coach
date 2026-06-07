from __future__ import annotations
import json
import os
import re
from typing import Any

from player_coach.constraints.schema import ConstraintSchema


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : i + 1]
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        return text


class PlayerAgent:
    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "Install player-coach-core[llm] to use PlayerAgent"
            ) from e
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = "claude-haiku-4-5-20251001"

    def decide(
        self,
        world_state: dict[str, Any],
        constraints: ConstraintSchema,
        history: list[dict[str, Any]] | None = None,
        patterns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_content = _build_user_prompt(world_state, constraints, history, patterns)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as e:
            raise RuntimeError(f"PlayerAgent API call failed: {e}") from e
        if not response.content:
            raise ValueError("PlayerAgent received empty response from API")
        text = response.content[0].text.strip()
        text = _extract_json(text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"actions": [], "reasoning": text}
        return {
            "actions": parsed.get("actions", []),
            "reasoning": parsed.get("reasoning", ""),
            "tokens_used": {
                "player": response.usage.input_tokens + response.usage.output_tokens
            },
        }


_SYSTEM_PROMPT = """\
You are a trading planner. Given the current market state and risk constraints, \
propose 1-3 trading actions.

Respond ONLY with a single JSON object. No text before or after the JSON. No markdown.
Keep reasoning to 3-4 sentences. State your final calculation once — do not show multiple attempts.
{
  "actions": [
    {
      "action_type": "enter_long" | "enter_short" | "exit_position" | "hold",
      "symbol": "<ticker>",
      "position_id": "<uuid or null>",
      "size_pct": <float or null for exits/holds>,
      "entry_price": <float or null>,
      "stop_loss": <float or null>,
      "take_profit": <float or null>
    }
  ],
  "reasoning": "<one paragraph explaining the rationale>"
}

Rules:
- Only propose symbols from the allowed list.
- Each entry action's size_pct must not exceed max_single_trade_pct.
- If world_state.kelly_fraction is present, treat it as a suggested sizing \
reference (derived from your historical win rate) — let it guide size_pct, but \
it is a guide, not a requirement, and never exceed max_single_trade_pct.
- Total open positions must not exceed max_open_positions.
- Risk/reward (|take_profit - entry| / |entry - stop_loss|) must meet min_risk_reward for entry actions.
- Do not exceed max_leverage.
- For exit_position: include the position_id of the position being closed from open_positions.
- For hold: actions list may be empty or contain one hold action.
- If world_state.consistency_status is "approaching" or "breached", today's gain \
is becoming a large share of total profit (the daily consistency rule) — prefer \
smaller size or hold so no single day dominates the equity curve.
- Only propose exit_position if there is an open position to close.
- If revising, address every critique raised by the Coach.\
"""


def _build_user_prompt(
    world_state: dict[str, Any],
    constraints: ConstraintSchema,
    history: list[dict[str, Any]] | None,
    patterns: list[dict[str, Any]] | None = None,
) -> str:
    parts: list[str] = []
    parts.append("## World state\n" + json.dumps(world_state, indent=2))

    if "capital" in world_state:
        capital = world_state.get("capital", 0)
        cash_available = world_state.get("cash_available", 0)
        daily_pnl = world_state.get("daily_pnl", 0.0)
        daily_pnl_pct = world_state.get("daily_pnl_pct", 0.0)
        drawdown_pct = world_state.get("drawdown_pct", 0.0)
        open_positions = world_state.get("open_positions", [])
        positions_summary = (
            json.dumps(open_positions, indent=2) if open_positions else "none"
        )
        parts.append(
            f"## Portfolio\n"
            f"Capital: ${capital}\n"
            f"Cash available: ${cash_available}\n"
            f"Daily P&L: ${daily_pnl} ({daily_pnl_pct}%)\n"
            f"Drawdown: {drawdown_pct}%\n"
            f"Open positions: {positions_summary}"
        )

    parts.append(
        "## Constraints\n"
        + json.dumps(constraints.to_dict(), indent=2)
    )
    if patterns:
        lines = ["## Relevant patterns (from coach memory)"]
        for p in patterns:
            conf = p.get("weighted_confidence", p.get("confidence", 0))
            lines.append(
                f"- {p['pattern_type']} (confidence {conf:.2f}): {p.get('observation', '')}"
            )
        parts.append("\n".join(lines))
    if history:
        parts.append("## Prior rounds")
        for i, round_ in enumerate(history, 1):
            parts.append(f"### Round {i}")
            if "proposal" in round_:
                parts.append("**Proposal:**\n" + json.dumps(round_["proposal"], indent=2))
            if "evaluation" in round_:
                feedback = round_["evaluation"].get("feedback", "")
                if feedback:
                    parts.append("**Coach critique:**\n" + feedback)
    parts.append("Propose your trading actions now.")
    return "\n\n".join(parts)
