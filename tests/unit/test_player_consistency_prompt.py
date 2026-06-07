from __future__ import annotations

from player_coach.agents.player import _SYSTEM_PROMPT


def test_player_prompt_mentions_consistency_status():
    assert "consistency_status" in _SYSTEM_PROMPT


def test_player_prompt_advises_throttle_when_approaching():
    assert "approaching" in _SYSTEM_PROMPT.lower()
