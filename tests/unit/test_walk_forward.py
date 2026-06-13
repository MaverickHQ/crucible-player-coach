from __future__ import annotations

import math

from player_coach.backtest.walk_forward import oos_returns, walk_forward_windows


def test_windows_anchored_slicing():
    w = walk_forward_windows(150, fit_days=60, eval_days=30)
    assert [(f.start, f.stop, e.start, e.stop) for f, e in w] == [
        (0, 60, 60, 90),
        (0, 90, 90, 120),
        (0, 120, 120, 150),
    ]


def test_no_look_ahead_eval_strictly_after_fit():
    for fit, ev in walk_forward_windows(200, 50, 25):
        assert ev.start == fit.stop  # eval begins exactly where fit ends


def test_eval_windows_are_contiguous_and_non_overlapping():
    evals = [ev for _, ev in walk_forward_windows(150, 60, 30)]
    for a, b in zip(evals, evals[1:]):
        assert b.start == a.stop


def test_insufficient_data_yields_no_windows():
    assert walk_forward_windows(50, 60, 30) == []
    assert walk_forward_windows(100, 0, 30) == []


def test_oos_returns_concatenate_within_fold():
    fold_a = [("d1", 100.0), ("d2", 110.0)]   # +0.10
    fold_b = [("d3", 200.0), ("d4", 220.0)]   # +0.10 (no cross-fold jump)
    r = oos_returns([fold_a, fold_b])
    assert len(r) == 2
    assert all(math.isclose(x, 0.10) for x in r)
