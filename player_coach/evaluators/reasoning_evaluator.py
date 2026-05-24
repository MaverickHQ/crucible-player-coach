from __future__ import annotations
import json
import os
from typing import Any


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


_FALLBACK: dict[str, Any] = {
    "reasoning_score": None,
    "reasoning_critique": "evaluation unavailable",
}

_SYSTEM_PROMPT = """\
You are a reasoning auditor for a trading agent. Evaluate the quality of the
Player's stated reasoning on three dimensions and return a single JSON object.
No markdown, no code fences, no text outside the JSON.

Dimensions:
1. market_grounded  — Does the reasoning cite specific data values from the
   world state (prices, volumes, indicators)? Score 0.0 (pure assertion) to 1.0.
2. internally_coherent — Does the conclusion follow logically from the stated
   premises? Score 0.0 (contradictory) to 1.0 (fully consistent).
3. proportionate — Is the conviction level proportionate to the proposed action
   size (e.g. a 5% position should not claim "extremely high confidence" without
   strong evidence)? Score 0.0 (wildly disproportionate) to 1.0 (well-matched).

Return exactly:
{
  "market_grounded": <float 0.0-1.0>,
  "internally_coherent": <float 0.0-1.0>,
  "proportionate": <float 0.0-1.0>,
  "critique": "<one concise sentence per dimension, comma-separated>"
}\
"""


def _build_user_prompt(
    reasoning: str,
    actions: list[dict[str, Any]],
    world_state: dict[str, Any],
) -> str:
    parts = [
        "## Player reasoning\n" + (reasoning or "(none provided)"),
        "## Proposed actions\n" + json.dumps(actions, indent=2),
        "## World state\n" + json.dumps(world_state, indent=2),
        "Evaluate the reasoning quality now.",
    ]
    return "\n\n".join(parts)


class ReasoningEvaluator:
    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "Install player-coach-core[llm] to use ReasoningEvaluator"
            ) from e
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = "claude-haiku-4-5-20251001"

    def evaluate(
        self,
        reasoning: str,
        actions: list[dict[str, Any]],
        world_state: dict[str, Any],
    ) -> dict[str, Any]:
        user_content = _build_user_prompt(reasoning, actions, world_state)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=256,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception:
            return dict(_FALLBACK)

        if not response.content:
            return dict(_FALLBACK)

        text = _extract_json(response.content[0].text.strip())
        try:
            parsed = json.loads(text)
            scores = [
                float(parsed["market_grounded"]),
                float(parsed["internally_coherent"]),
                float(parsed["proportionate"]),
            ]
            score = round(sum(scores) / len(scores), 3)
            score = max(0.0, min(1.0, score))
            critique = str(parsed.get("critique", ""))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return dict(_FALLBACK)

        return {"reasoning_score": score, "reasoning_critique": critique}
