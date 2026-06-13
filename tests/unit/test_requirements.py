"""Cloud-deploy parity: requirements.txt must declare everything the runner
imports at runtime, so the Streamlit Cloud build matches local. Keeps the
deploy from silently breaking when a new market dependency lands in pyproject.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REQ = Path("requirements.txt").read_text().splitlines()


def _packages() -> set[str]:
    out = set()
    for raw in _REQ:
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        out.add(s.split("[")[0].split(">=")[0].split("==")[0].split("<")[0].strip().lower())
    return out


# Each runtime import the dashboard / runner makes that isn't a stdlib module.
# A missing entry means the Streamlit Cloud deploy crashes at first use.
_REQUIRED = {
    # Existing.
    "streamlit",
    "anthropic",
    "yfinance",
    "requests",
    "ewm-core",
    # Phase 3A market layer + analytics + metrics — previously missing.
    "numpy",
    "pandas",
    "hmmlearn",
    "arch",
}


@pytest.mark.parametrize("pkg", sorted(_REQUIRED))
def test_requirements_declares_package(pkg: str):
    assert pkg in _packages(), (
        f"{pkg!r} is missing from requirements.txt — the live Streamlit Cloud "
        "deploy will fail on imports the runner needs at backtest time."
    )
