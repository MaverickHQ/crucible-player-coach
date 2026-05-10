from __future__ import annotations
import json
import os
import re
from typing import Any

from player_coach.constraints.schema import ConstraintSchema


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
    ) -> dict[str, Any]:
        user_content = _build_user_prompt(world_state, constraints, history)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
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

Respond with valid JSON only — no markdown, no explanation outside the JSON:
{
  "actions": [
    {
      "symbol": "<ticker>",
      "side": "buy" | "sell",
      "size_pct": <float, fraction of portfolio>,
      "entry_price": <float>,
      "stop_loss": <float>,
      "take_profit": <float>
    }
  ],
  "reasoning": "<one paragraph explaining the rationale>"
}

Rules:
- Only propose symbols from the allowed list.
- Each action's size_pct must not exceed max_single_trade_pct.
- Total open positions must not exceed max_open_positions.
- Risk/reward (|take_profit - entry| / |entry - stop_loss|) must meet min_risk_reward.
- Do not exceed max_leverage.
- If revising, address every critique raised by the Coach.\
"""


def _build_user_prompt(
    world_state: dict[str, Any],
    constraints: ConstraintSchema,
    history: list[dict[str, Any]] | None,
) -> str:
    parts: list[str] = []
    parts.append("## World state\n" + json.dumps(world_state, indent=2))
    parts.append(
        "## Constraints\n"
        + json.dumps(constraints.to_dict(), indent=2)
    )
    if history:
        parts.append("## Prior rounds")
        for i, round_ in enumerate(history, 1):
            parts.append(f"### Round {i}")
            if "proposal" in round_:
                parts.append("**Proposal:**\n" + json.dumps(round_["proposal"], indent=2))
            if "critique" in round_:
                parts.append("**Coach critique:**\n" + json.dumps(round_["critique"], indent=2))
    parts.append("Propose your trading actions now.")
    return "\n\n".join(parts)
