from __future__ import annotations

from player_coach.agents.coach import _SYSTEM_PROMPT


def test_coach_prompt_mentions_vwap_preference():
    assert "prefer_entry_below_vwap" in _SYSTEM_PROMPT
    assert "vwap" in _SYSTEM_PROMPT.lower()


def test_coach_prompt_marks_vwap_as_soft_not_blocking():
    lowered = _SYSTEM_PROMPT.lower()
    assert "never reject" in lowered or "advisory" in lowered or "soft" in lowered
