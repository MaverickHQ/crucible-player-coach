from __future__ import annotations

import json
from collections.abc import Generator

import anthropic

from player_coach.agents.player import _SYSTEM_PROMPT, _build_user_prompt, _extract_json
from player_coach.constraints.schema import ConstraintSchema


def stream_player_decision(
    world_state: dict,
    constraints: ConstraintSchema,
    history: list[dict] | None,
    api_key: str,
) -> Generator[str | dict, None, None]:
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(world_state, constraints, history)

    accumulated = ""
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            accumulated += chunk
            yield chunk
        usage = stream.get_final_usage()

    extracted = _extract_json(accumulated)
    try:
        result = json.loads(extracted)
    except json.JSONDecodeError:
        result = {"actions": [], "reasoning": accumulated}
    yield {"__done__": True, "result": result,
           "tokens": usage.input_tokens + usage.output_tokens}
