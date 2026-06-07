from __future__ import annotations

from player_coach.agents.player import _SYSTEM_PROMPT


def test_player_prompt_mentions_kelly_fraction():
    assert "kelly_fraction" in _SYSTEM_PROMPT


def test_player_prompt_frames_kelly_as_reference_not_requirement():
    lowered = _SYSTEM_PROMPT.lower()
    assert "reference" in lowered or "suggest" in lowered or "guide" in lowered
