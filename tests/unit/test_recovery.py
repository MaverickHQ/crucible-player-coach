from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dashboard.recovery import (
    list_recoverable,
    load_snapshot,
    save_snapshot,
)


def _sample() -> dict:
    return {
        "preset": "conservative", "symbol": "AMZN",
        "start_date": "2024-01-01", "end_date": "2024-06-30",
        "metrics": {"sharpe": 1.2, "mc_success_prob": 0.55},
        "equity_curve": [["2024-01-02", 100_000.0], ["2024-01-03", 100_120.0]],
        "exchanges": [],
    }


# ----------------------------------------------------------------- round-trip

def test_write_then_read_snapshot_round_trip(tmp_path: Path):
    path = save_snapshot(_sample(), strategy_id="s-abc", base_dir=tmp_path)
    assert path.exists()
    assert load_snapshot(path) == _sample()


def test_snapshot_filename_carries_strategy_id(tmp_path: Path):
    path = save_snapshot(_sample(), strategy_id="bt-conservative-AMZN", base_dir=tmp_path)
    assert "bt-conservative-AMZN" in path.name
    assert path.suffix == ".json"


# ---------------------------------------------------------------- listing

def test_list_recoverable_returns_recent_first(tmp_path: Path):
    p1 = save_snapshot(_sample(), strategy_id="old", base_dir=tmp_path)
    time.sleep(0.01)
    p2 = save_snapshot(_sample(), strategy_id="new", base_dir=tmp_path)
    items = list_recoverable(tmp_path)
    assert [i["path"] for i in items[:2]] == [p2, p1]


def test_ignores_snapshots_older_than_max_age(tmp_path: Path):
    old = save_snapshot(_sample(), strategy_id="ancient", base_dir=tmp_path)
    # Backdate the file 25 hours.
    backdated = time.time() - 25 * 3600
    os.utime(old, (backdated, backdated))
    fresh = save_snapshot(_sample(), strategy_id="fresh", base_dir=tmp_path)
    paths = [i["path"] for i in list_recoverable(tmp_path, max_age_hours=24)]
    assert old not in paths
    assert fresh in paths


def test_corrupt_snapshot_skipped_not_raised(tmp_path: Path):
    bad = tmp_path / "broken.json"
    bad.write_text("{not json")
    good = save_snapshot(_sample(), strategy_id="good", base_dir=tmp_path)
    items = list_recoverable(tmp_path)
    paths = [i["path"] for i in items]
    assert good in paths
    assert bad not in paths  # corrupt entry silently skipped


def test_list_recoverable_empty_when_dir_missing(tmp_path: Path):
    assert list_recoverable(tmp_path / "does-not-exist") == []


def test_load_snapshot_missing_raises(tmp_path: Path):
    # A direct load of a missing path is a programmer error and should raise.
    import pytest
    with pytest.raises(FileNotFoundError):
        load_snapshot(tmp_path / "no-such-file.json")
