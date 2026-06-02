from __future__ import annotations

import numpy as np
import pytest

from player_coach.market.volatility_model import VolatilityModel


def _calm(n: int = 200, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 0.005, size=n)


def _ends_in_shock(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.concatenate([
        rng.normal(0.0, 0.005, size=180),
        rng.normal(0.0, 0.05, size=20),  # recent volatility spike
    ])


# ----------------------------------------------------------------- forecast > 0

def test_forecast_is_positive():
    assert VolatilityModel().fit(_calm()).forecast_vol() > 0.0


def test_fit_forecast_convenience_is_positive():
    assert VolatilityModel().fit_forecast(_calm(seed=1)) > 0.0


def test_forecast_in_plausible_daily_range():
    # A daily-return vol forecast should be a small fraction, not blow up.
    vol = VolatilityModel().fit_forecast(_calm(seed=2))
    assert 0.0 < vol < 1.0


# ----------------------------------------------------- monotonic vol response

def test_recent_vol_shock_raises_forecast():
    calm = VolatilityModel().fit_forecast(_calm(seed=3))
    shocked = VolatilityModel().fit_forecast(_ends_in_shock(seed=3))
    assert shocked > calm


# ------------------------------------------------------------ insufficient data

def test_fit_raises_on_insufficient_data():
    with pytest.raises(ValueError):
        VolatilityModel().fit(_calm(n=29))


def test_fit_accepts_minimum_data():
    VolatilityModel().fit(_calm(n=30))  # must not raise


# ------------------------------------------------------------- usage guard

def test_forecast_before_fit_raises():
    with pytest.raises(RuntimeError):
        VolatilityModel().forecast_vol()


# ----------------------------------------- forecast on new data, cached params

def test_forecast_vol_on_uses_cached_params():
    model = VolatilityModel().fit(_calm(seed=10))
    vol = model.forecast_vol_on(_calm(n=60, seed=11))
    assert vol > 0.0


def test_forecast_vol_on_before_fit_raises():
    with pytest.raises(RuntimeError):
        VolatilityModel().forecast_vol_on(_calm(n=60))
