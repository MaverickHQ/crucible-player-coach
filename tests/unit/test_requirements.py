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


# Note: a `test_python_version_pinned_for_streamlit_cloud` test used to live
# here, pinning `.python-version`. We discovered during the v2.0.0 verification
# cycle that Streamlit Cloud ignores `.python-version` (a pyenv convention) and
# only reads the per-app Settings dropdown at share.streamlit.io. The file was
# dropped in ee586d5 because its presence was actively misleading; the actual
# pin lives outside the repo. The deploy-mechanism docs are in CLAUDE.md's
# "Deploy environment" section.


@pytest.mark.parametrize("pkg", sorted(_REQUIRED))
def test_requirements_declares_package(pkg: str):
    assert pkg in _packages(), (
        f"{pkg!r} is missing from requirements.txt — the live Streamlit Cloud "
        "deploy will fail on imports the runner needs at backtest time."
    )
