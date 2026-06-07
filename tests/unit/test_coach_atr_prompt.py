from __future__ import annotations

from player_coach.agents.coach import _SYSTEM_PROMPT


def test_coach_prompt_enforces_atr_stop_rule():
    assert "min_stop_atr_multiple" in _SYSTEM_PROMPT
    assert "atr" in _SYSTEM_PROMPT.lower()


def test_coach_prompt_skips_atr_check_when_absent():
    # The check must be conditional — degraded bars report atr=null and the
    # rule should be skipped rather than failing every entry.
    lowered = _SYSTEM_PROMPT.lower()
    assert "null" in lowered or "present" in lowered
