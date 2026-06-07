from __future__ import annotations
import json
import os
from typing import Any

from player_coach.constraints.schema import ConstraintSchema


def _extract_json(text: str) -> str:
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
    return text


class CoachAgent:
    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "Install player-coach-core[llm] to use CoachAgent"
            ) from e
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = "claude-haiku-4-5-20251001"

    def evaluate(
        self,
        proposal: dict[str, Any],
        constraints: ConstraintSchema,
        world_state: dict[str, Any],
    ) -> dict[str, Any]:
        user_content = _build_user_prompt(proposal, constraints, world_state)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as e:
            raise RuntimeError(f"CoachAgent API call failed: {e}") from e
        if not response.content:
            raise ValueError("CoachAgent received empty response from API")
        text = response.content[0].text.strip()
        text = _extract_json(text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"verdict": "REJECT", "violations": [], "critique": text}

        violations: list[str] = parsed.get("violations", [])
        verdict = parsed.get("verdict", "REJECT")

        # Python is authoritative on ABORT — upgrade REJECT if a hard violation found
        if verdict != "APPROVE" and any(
            v in constraints.abort_on_violations for v in violations
        ):
            verdict = "ABORT"

        return {
            "verdict": verdict,
            "violations": violations,
            "critique": parsed.get("critique"),
            "tokens_used": {
                "coach": response.usage.input_tokens + response.usage.output_tokens
            },
        }


_SYSTEM_PROMPT = """\
You are a trading risk auditor. Check every proposed action against the constraints exactly.

Respond with valid JSON only — no markdown, no code fences, no explanation outside the JSON. Keep the critique field as a single line with no line breaks:
{
  "verdict": "APPROVE" | "REJECT",
  "violations": ["<constraint_name>", ...],
  "critique": "<one line per constraint checked: constraint_name: actual X vs limit Y — PASS or FAIL. Always populate this field, even on APPROVE.>"
}

Action types and checks:

For entry actions (action_type is "enter_long" or "enter_short"):
- allowed_symbols: action.symbol must be in constraints.allowed_symbols
- max_single_trade_pct: action.size_pct must be <= constraints.max_single_trade_pct
- max_open_positions: total number of entry actions must be <= constraints.max_open_positions
- max_position_pct: sum of all entry size_pct must be <= constraints.max_position_pct
- min_risk_reward: |take_profit - entry_price| / |entry_price - stop_loss| >= constraints.min_risk_reward
- min_stop_atr_multiple: the stop must sit at least this many ATRs from entry —
  |entry_price - stop_loss| >= constraints.min_stop_atr_multiple * world_state.atr.
  Only check this when world_state.atr is present (non-null); if atr is null, skip it.

For exit actions (action_type is "exit_position"):
- position_id must be present (non-null)
- action.symbol must match a symbol in world_state open_positions

For hold actions (action_type is "hold"):
- Always APPROVE, no constraint checks needed.

REJECT if any constraint is violated. List only breached constraint names in violations.
APPROVE only when every constraint is satisfied.\
"""


def _build_user_prompt(
    proposal: dict[str, Any],
    constraints: ConstraintSchema,
    world_state: dict[str, Any],
) -> str:
    parts: list[str] = []
    parts.append("## Proposal\n" + json.dumps(proposal, indent=2))
    parts.append("## Constraints\n" + json.dumps(constraints.to_dict(), indent=2))
    parts.append("## World state\n" + json.dumps(world_state, indent=2))
    parts.append("Evaluate this proposal now.")
    return "\n\n".join(parts)
