from __future__ import annotations

from player_coach.agents.coach import _SYSTEM_PROMPT


def test_coach_prompt_mentions_vwap_preference():
    assert "prefer_entry_below_vwap" in _SYSTEM_PROMPT
    assert "vwap" in _SYSTEM_PROMPT.lower()


def test_coach_prompt_marks_vwap_as_soft_not_blocking():
    lowered = _SYSTEM_PROMPT.lower()
    assert "never reject" in lowered or "advisory" in lowered or "soft" in lowered


def test_coach_vwap_compares_entry_price_not_close():
    # price_vs_vwap is derived from the latest CLOSE, so the rule must compare the
    # proposed entry_price to vwap directly and explicitly avoid price_vs_vwap.
    lowered = _SYSTEM_PROMPT.lower()
    assert "entry_price" in lowered
    assert "ignore price_vs_vwap" in lowered
