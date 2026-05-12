from __future__ import annotations

import json
from collections.abc import Generator

import anthropic

from player_coach.agents.coach import _SYSTEM_PROMPT, _build_user_prompt, _extract_json
from player_coach.constraints.schema import ConstraintSchema


def stream_coach_evaluation(
    proposal: dict,
    constraints: ConstraintSchema,
    world_state: dict,
    api_key: str,
) -> Generator[str | dict, None, None]:
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(proposal, constraints, world_state)

    accumulated = ""
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            accumulated += chunk
            yield chunk

    import re as _pre_re
    pre_cleaned = _pre_re.sub(
        r"```(?:json)?\s*|\s*```", "", accumulated
    ).strip()
    extracted = _extract_json(pre_cleaned)
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError:
        parsed = {}
    import re as _re
    critique = parsed.get("critique", "")
    if not critique or "{" in str(critique):
        cleaned_acc = _re.sub(
            r"```(?:json)?\s*|\s*```", "", accumulated
        ).strip()
        m = _re.search(
            r'"critique"\s*:\s*"((?:[^"\\]|\\.)*)"',
            cleaned_acc,
        )
        critique = m.group(1).replace('\\"', '"') if m else ""
    result = {
        "verdict": parsed.get("verdict", "REJECT"),
        "violations": parsed.get("violations", []),
        "critique": critique,
    }
    yield {"__done__": True, "result": result}
