"""N6 — shared cache helpers in player_coach.agents._caching.

Pins the marker shape so every call site (PlayerAgent, CoachAgent,
ReasoningEvaluator, streaming/player_stream, streaming/coach_stream)
passes the identical structured block to the Anthropic SDK.
"""
from __future__ import annotations

from types import SimpleNamespace

from player_coach.agents._caching import build_cached_system, read_cache_tokens


def test_build_cached_system_returns_block_list() -> None:
    blocks = build_cached_system("hello")
    assert isinstance(blocks, list)
    assert len(blocks) == 1


def test_build_cached_system_carries_ephemeral_marker() -> None:
    blocks = build_cached_system("system prompt body")
    block = blocks[0]
    assert block["type"] == "text"
    assert block["text"] == "system prompt body"
    assert block["cache_control"] == {"type": "ephemeral"}


def test_read_cache_tokens_returns_field_value() -> None:
    usage = SimpleNamespace(cache_read_input_tokens=4200)
    assert read_cache_tokens(usage) == 4200


def test_read_cache_tokens_zero_when_field_missing() -> None:
    # Older SDK / responses without the field must default to 0, never raise.
    usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    assert read_cache_tokens(usage) == 0


def test_read_cache_tokens_zero_when_field_is_none() -> None:
    usage = SimpleNamespace(cache_read_input_tokens=None)
    assert read_cache_tokens(usage) == 0
