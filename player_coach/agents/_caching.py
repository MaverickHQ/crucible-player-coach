"""Shared prompt-caching helpers for the Anthropic SDK.

N6 — T1 originally wrapped only PlayerAgent and CoachAgent in the structured
``system=[{type: text, text, cache_control}]`` block. The same large static
system prompt also drives ReasoningEvaluator and both streaming clones
(dashboard/streaming/{player,coach}_stream.py). Without the marker, those
sites pay full input cost on every call — half of T1's projected savings
evaporate on Standard backtests, all of them on streaming.

This module owns the two-line marker so every caller passes the SAME shape
to ``messages.create`` / ``messages.stream``: change the marker (e.g. switch
to a persistent cache tier) in one place, every site updates with it.
"""
from __future__ import annotations

from typing import Any


def build_cached_system(prompt: str) -> list[dict[str, Any]]:
    """Wrap a system prompt in the Anthropic structured block that the SDK
    needs to attach a 5-minute ephemeral cache marker. Caller passes the
    return value as ``system=...`` to ``messages.create`` / ``messages.stream``.
    """
    return [{
        "type": "text",
        "text": prompt,
        "cache_control": {"type": "ephemeral"},
    }]


def read_cache_tokens(usage: Any) -> int:
    """Read ``cache_read_input_tokens`` from an Anthropic Usage object, falling
    back to 0 if the field is absent (older SDKs, non-cached responses, or
    the SDK shape changing). N5 wires this through CoachLoop to the artifact
    so the dashboard's token panel can report real cache-hit %.
    """
    return int(getattr(usage, "cache_read_input_tokens", 0) or 0)
