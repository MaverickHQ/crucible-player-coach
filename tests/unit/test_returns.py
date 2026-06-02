from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from player_coach.market.returns import compute_log_returns, validate_returns


# ----------------------------------------------------------------- correctness

def test_log_returns_correctness():
    # 100 → 110 → 121 is two consecutive +10% steps; each log return = ln(1.1).
    r = compute_log_returns([100.0, 110.0, 121.0])
    assert len(r) == 2
    assert math.isclose(r[0], math.log(1.1), rel_tol=1e-9)
    assert math.isclose(r[1], math.log(1.1), rel_tol=1e-9)


def test_log_returns_length_is_n_minus_one():
    assert len(compute_log_returns([1.0, 2.0, 3.0, 4.0])) == 3


def test_empty_and_single_price_yield_empty():
    assert len(compute_log_returns([])) == 0
    assert len(compute_log_returns([100.0])) == 0


# ------------------------------------------------------- graceful degradation

def test_handles_nan_price_without_propagating():
    r = compute_log_returns([100.0, float("nan"), 110.0])
    assert np.all(np.isfinite(r)), "NaN price must not leak into returns"


def test_handles_zero_price_without_inf():
    r = compute_log_returns([100.0, 0.0, 110.0])
    assert np.all(np.isfinite(r)), "zero price must not produce inf"


def test_handles_negative_price_without_nan():
    r = compute_log_returns([100.0, -5.0, 110.0])
    assert np.all(np.isfinite(r))


def test_forward_fill_preserves_move_across_gap():
    # A bad bar should not erase the real move when good data resumes:
    # [100, NaN, 110] forward-fills to [100, 100, 110] → [0, ln(1.1)].
    r = compute_log_returns([100.0, float("nan"), 110.0])
    assert r[0] == 0.0
    assert math.isclose(r[1], math.log(1.1), rel_tol=1e-9)


def test_forward_fill_zero_price_preserves_move():
    r = compute_log_returns([100.0, 0.0, 110.0])
    assert math.isclose(r[1], math.log(1.1), rel_tol=1e-9)


def test_leading_bad_price_is_safe():
    r = compute_log_returns([float("nan"), 100.0, 110.0])
    assert np.all(np.isfinite(r))


# ----------------------------------------------------------- input flexibility

def test_accepts_pandas_series():
    r = compute_log_returns(pd.Series([100.0, 110.0, 121.0]))
    assert isinstance(r, np.ndarray)
    assert len(r) == 2


def test_accepts_numpy_array():
    r = compute_log_returns(np.array([100.0, 110.0]))
    assert isinstance(r, np.ndarray)
    assert len(r) == 1


# -------------------------------------------------------------- validation

def test_validate_raises_below_min_obs():
    with pytest.raises(ValueError):
        validate_returns(np.zeros(29), min_obs=30)


def test_validate_passes_at_min_obs():
    validate_returns(np.zeros(30), min_obs=30)  # must not raise


def test_validate_default_min_obs_is_30():
    with pytest.raises(ValueError):
        validate_returns(np.zeros(29))
    validate_returns(np.zeros(30))  # must not raise
