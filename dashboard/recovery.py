"""Crash-safe recovery for the backtest page.

A Streamlit Cloud session can drop after a long backtest finishes but before
``save_backtest_result`` runs, taking the comparison record and ``st.session_state``
with it. We write a compact JSON snapshot to disk the instant each preset
completes; on the next page load we offer to rehydrate from the freshest one.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path("data/recovery")
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _normalise(strategy_id: str) -> str:
    return _SAFE_ID.sub("-", strategy_id).strip("-") or "snapshot"


def save_snapshot(
    payload: dict[str, Any],
    strategy_id: str,
    base_dir: str | Path = _DEFAULT_DIR,
) -> Path:
    """Write ``payload`` as a recovery snapshot named with the strategy id and
    a monotonically increasing timestamp. Returns the file path."""
    directory = Path(base_dir)
    directory.mkdir(parents=True, exist_ok=True)
    # Nanosecond timestamp keeps the ordering stable even when several
    # snapshots land in the same wall-clock millisecond.
    fname = f"{time.time_ns()}-{_normalise(strategy_id)}.json"
    path = directory / fname
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def load_snapshot(path: str | Path) -> dict[str, Any]:
    """Read a snapshot file. Raises ``FileNotFoundError`` on a missing path."""
    return json.loads(Path(path).read_text())


def list_recoverable(
    base_dir: str | Path = _DEFAULT_DIR,
    max_age_hours: float = 24.0,
) -> list[dict[str, Any]]:
    """Return recent recoverable snapshots, freshest first.

    Each entry: ``{"path": Path, "mtime": float, "payload": dict}``.
    Corrupt files are logged and silently skipped — a single bad snapshot
    must never block the recovery panel.
    """
    directory = Path(base_dir)
    if not directory.exists():
        return []
    cutoff = time.time() - max_age_hours * 3600.0

    items: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        try:
            payload = load_snapshot(path)
        except Exception:
            logger.warning("recovery: skipping corrupt snapshot %s", path)
            continue
        items.append({"path": path, "mtime": mtime, "payload": payload})

    items.sort(key=lambda i: i["mtime"], reverse=True)
    return items
