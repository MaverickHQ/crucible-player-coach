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


def test_python_version_pinned_for_streamlit_cloud():
    # Streamlit Cloud's default Python (currently 3.14) may not have wheels for
    # our numerical deps (hmmlearn, arch, scipy). Pin to a version with full
    # wheel coverage — keeping the deploy on the interpreter our tests pass on.
    pin = Path(".python-version")
    assert pin.exists(), (
        "Missing .python-version: Streamlit Cloud will use its default "
        "(currently Python 3.14) and the deploy will fail importing native deps."
    )
    version = pin.read_text().strip()
    major_minor = ".".join(version.split(".")[:2])
    assert major_minor in {"3.11", "3.12", "3.13"}, (
        f"Pin {version} is outside the range with reliable wheel coverage."
    )


@pytest.mark.parametrize("pkg", sorted(_REQUIRED))
def test_requirements_declares_package(pkg: str):
    assert pkg in _packages(), (
        f"{pkg!r} is missing from requirements.txt — the live Streamlit Cloud "
        "deploy will fail on imports the runner needs at backtest time."
    )
