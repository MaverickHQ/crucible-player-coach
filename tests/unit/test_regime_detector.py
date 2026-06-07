from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from player_coach.market.regime_detector import RegimeDetector


def _returns(scale: float, n: int = 240, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, scale, size=n)


def _two_regime_series(seed: int = 0) -> np.ndarray:
    """A calm block followed by a volatile block — clearly two variance states."""
    rng = np.random.default_rng(seed)
    calm = rng.normal(0.0, 0.005, size=120)
    wild = rng.normal(0.0, 0.04, size=120)
    return np.concatenate([calm, wild])


# --------------------------------------------------------------- label validity

def test_fit_predict_returns_valid_label():
    label, _ = RegimeDetector().fit_predict(_two_regime_series())
    assert label in {"low_vol", "high_vol"}


def test_fit_predict_returns_valid_probability():
    _, prob = RegimeDetector().fit_predict(_two_regime_series())
    assert 0.0 <= prob <= 1.0


# ------------------------------------------------------------ insufficient data

def test_fit_raises_on_insufficient_data():
    with pytest.raises(ValueError):
        RegimeDetector().fit(_returns(0.01, n=29))


def test_fit_accepts_minimum_data():
    RegimeDetector().fit(_returns(0.01, n=30))  # must not raise


# ----------------------------------------------------- stable variance ordering

def test_low_vol_block_predicts_low_vol():
    # Ends in the calm block → most recent obs is low-vol.
    rng = np.random.default_rng(1)
    series = np.concatenate([
        rng.normal(0.0, 0.04, size=120),   # wild first
        rng.normal(0.0, 0.005, size=120),  # calm last
    ])
    label, _ = RegimeDetector().fit_predict(series)
    assert label == "low_vol"


def test_high_vol_block_predicts_high_vol():
    # Ends in the volatile block → most recent obs is high-vol.
    label, _ = RegimeDetector().fit_predict(_two_regime_series(seed=2))
    assert label == "high_vol"


def test_state_ordering_is_deterministic_across_fits():
    series = _two_regime_series(seed=3)
    labels = {RegimeDetector().fit_predict(series)[0] for _ in range(5)}
    assert len(labels) == 1, "label must be stable across repeated fits"


# ------------------------------------------------------------------ multi-restart

def test_multi_restart_matches_or_beats_single_fit():
    series = _two_regime_series(seed=4)
    one = RegimeDetector(n_fits=1).fit(series).score(series)
    many = RegimeDetector(n_fits=10).fit(series).score(series)
    assert many >= one - 1e-6, "more restarts must not yield a worse log-likelihood"


# ----------------------------------------------------------------- three-state

def test_three_state_uses_full_label_vocab():
    rng = np.random.default_rng(5)
    series = np.concatenate([
        rng.normal(0.0, 0.005, size=80),
        rng.normal(0.0, 0.02, size=80),
        rng.normal(0.0, 0.05, size=80),
    ])
    label, _ = RegimeDetector(n_states=3).fit_predict(series)
    assert label in {"low_vol", "medium_vol", "high_vol"}


# ----------------------------------------------------- persistence (anti-flicker)

def test_first_confirm_sets_baseline():
    d = RegimeDetector(min_duration=3)
    assert d.confirm_regime("high_vol") == "high_vol"


def test_persistence_blocks_single_flip():
    d = RegimeDetector(min_duration=3)
    d.confirm_regime("low_vol")
    assert d.confirm_regime("high_vol") == "low_vol"  # one outlier day ignored
    assert d.confirm_regime("low_vol") == "low_vol"


def test_persistence_allows_sustained_change():
    d = RegimeDetector(min_duration=3)
    d.confirm_regime("low_vol")
    assert d.confirm_regime("high_vol") == "low_vol"
    assert d.confirm_regime("high_vol") == "low_vol"
    assert d.confirm_regime("high_vol") == "high_vol"  # 3rd consecutive confirms


def test_persistence_resets_on_reversal():
    d = RegimeDetector(min_duration=3)
    d.confirm_regime("low_vol")
    d.confirm_regime("high_vol")  # pending count 1
    d.confirm_regime("high_vol")  # pending count 2
    d.confirm_regime("low_vol")   # reversal resets the pending run
    assert d.confirm_regime("high_vol") == "low_vol"  # back to count 1, no switch


def test_min_duration_one_switches_immediately():
    d = RegimeDetector(min_duration=1)
    d.confirm_regime("low_vol")
    assert d.confirm_regime("high_vol") == "high_vol"


def test_reset_clears_fitted_model():
    d = RegimeDetector().fit(_two_regime_series(seed=9))
    d.reset()
    with pytest.raises(RuntimeError):
        d.predict(_two_regime_series(seed=9))  # model gone, must not reuse stale fit


# ------------------------------------------------------------- serialization

def test_save_load_roundtrip_predicts_identically(tmp_path: Path):
    series = _two_regime_series(seed=7)
    detector = RegimeDetector().fit(series)
    expected = detector.predict(series)

    path = tmp_path / "regime.pkl"
    detector.save(path)
    restored = RegimeDetector.load(path)

    assert restored.predict(series) == expected


def test_save_before_fit_raises(tmp_path: Path):
    with pytest.raises(RuntimeError):
        RegimeDetector().save(tmp_path / "regime.pkl")


def test_load_nonexistent_raises():
    with pytest.raises(FileNotFoundError):
        RegimeDetector.load("/nonexistent/regime.pkl")


def test_load_corrupt_raises(tmp_path: Path):
    bad = tmp_path / "corrupt.pkl"
    bad.write_bytes(b"not a pickle")
    with pytest.raises(ValueError):
        RegimeDetector.load(bad)
