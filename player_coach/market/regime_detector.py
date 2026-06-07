from __future__ import annotations

import logging
import pickle
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from player_coach.market.returns import validate_returns

logger = logging.getLogger(__name__)

# Label vocab by state count. States are ordered by ascending emission variance,
# so index 0 is always the calmest regime and index n-1 the most volatile.
_LABELS: dict[int, list[str]] = {
    2: ["low_vol", "high_vol"],
    3: ["low_vol", "medium_vol", "high_vol"],
}

UNKNOWN = "unknown"


class RegimeDetector:
    """N-state Gaussian HMM over daily log returns, with deterministic labels.

    State assignment convention: states are sorted by emission variance
    (ascending) after fitting, so the label is stable across fits regardless of
    the random initialisation hmmlearn happens to land on:

      - 2 states → ["low_vol", "high_vol"]
      - 3 states → ["low_vol", "medium_vol", "high_vol"]

    ``n_fits`` random restarts are run and the fit with the best log-likelihood
    is kept, which is what makes the result reproducible in practice.
    """

    def __init__(
        self,
        n_states: int = 2,
        n_fits: int = 10,
        n_iter: int = 100,
        random_state: int = 42,
        min_duration: int = 3,
    ) -> None:
        if n_states not in _LABELS:
            raise ValueError(f"n_states must be one of {sorted(_LABELS)}")
        self.n_states = n_states
        self.n_fits = n_fits
        self.n_iter = n_iter
        self.random_state = random_state
        self.min_duration = max(1, min_duration)
        self._model: Any | None = None
        # state index (by ascending variance) → label
        self._labels: list[str] = list(_LABELS[n_states])
        # permutation mapping raw hmm state index → variance-rank index
        self._rank_of_state: dict[int, int] = {}
        # persistence-smoothing state (live anti-flicker)
        self._confirmed_label: str | None = None
        self._pending_label: str | None = None
        self._pending_count: int = 0

    # ------------------------------------------------------------------- fit

    def fit(self, returns: np.ndarray) -> RegimeDetector:
        """Fit the HMM on a 1-D array of log returns (>= 30 observations)."""
        from hmmlearn.hmm import GaussianHMM

        validate_returns(returns, min_obs=30)
        x = np.asarray(returns, dtype=float).reshape(-1, 1)

        best_model = None
        best_score = -np.inf
        for fit_idx in range(self.n_fits):
            model = GaussianHMM(
                n_components=self.n_states,
                covariance_type="full",
                n_iter=self.n_iter,
                random_state=self.random_state + fit_idx,
            )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(x)
                    score = model.score(x)
            except Exception:  # a restart failed to converge — skip it
                continue
            if np.isfinite(score) and score > best_score:
                best_score = score
                best_model = model

        if best_model is None:
            raise RuntimeError("HMM failed to converge on any restart")

        self._model = best_model
        self._order_states_by_variance(best_model)
        return self

    def _order_states_by_variance(self, model: Any) -> None:
        # covars_ shape: (n_states, 1, 1) for full covariance on 1-D data.
        variances = model.covars_.reshape(self.n_states)
        order = np.argsort(variances)  # ascending: calmest first
        self._rank_of_state = {int(state): rank for rank, state in enumerate(order)}

    # --------------------------------------------------------------- predict

    def predict(self, returns: np.ndarray) -> tuple[str, float]:
        """Return ``(label, probability)`` for the most recent observation."""
        if self._model is None:
            raise RuntimeError("call fit() before predict()")
        x = np.asarray(returns, dtype=float).reshape(-1, 1)
        posteriors = self._model.predict_proba(x)
        last = posteriors[-1]
        raw_state = int(np.argmax(last))
        rank = self._rank_of_state[raw_state]
        return self._labels[rank], float(last[raw_state])

    def fit_predict(self, returns: np.ndarray) -> tuple[str, float]:
        """Convenience: fit then predict on the same series."""
        return self.fit(returns).predict(returns)

    def score(self, returns: np.ndarray) -> float:
        """Log-likelihood of the series under the fitted model."""
        if self._model is None:
            raise RuntimeError("call fit() before score()")
        x = np.asarray(returns, dtype=float).reshape(-1, 1)
        return float(self._model.score(x))

    # ----------------------------------------------------- persistence smoothing

    def reset(self) -> None:
        """Clear the fitted model and persistence-smoothing state, so a reused
        detector cannot leak a prior run's fit or regime into the next run."""
        self._model = None
        self._rank_of_state = {}
        self._confirmed_label = None
        self._pending_label = None
        self._pending_count = 0

    def confirm_regime(self, raw_label: str) -> str:
        """Smooth a stream of raw daily labels into a flicker-resistant regime.

        A new raw label must persist for ``min_duration`` consecutive
        observations before the confirmed regime switches; a single outlier day
        is ignored, and a reversal back to the confirmed regime resets the
        pending run. ``min_duration=1`` disables smoothing (switch immediately).

        Stateful across calls — intended for the live per-day path, not the
        one-shot ``fit_predict``.
        """
        if self._confirmed_label is None:
            self._confirmed_label = raw_label
            return self._confirmed_label

        if raw_label == self._confirmed_label:
            self._pending_label = None
            self._pending_count = 0
            return self._confirmed_label

        if raw_label == self._pending_label:
            self._pending_count += 1
        else:
            self._pending_label = raw_label
            self._pending_count = 1

        if self._pending_count >= self.min_duration:
            self._confirmed_label = raw_label
            self._pending_label = None
            self._pending_count = 0

        return self._confirmed_label

    # ------------------------------------------------------------- persistence io

    def save(self, path: str | Path) -> None:
        """Pickle the fitted model + metadata so live trading can reload it
        between sessions rather than refitting on every start."""
        if self._model is None:
            raise RuntimeError("nothing to save: call fit() first")
        payload = {
            "model": self._model,
            "n_states": self.n_states,
            "n_fits": self.n_fits,
            "n_iter": self.n_iter,
            "random_state": self.random_state,
            "min_duration": self.min_duration,
            "labels": self._labels,
            "rank_of_state": self._rank_of_state,
        }
        Path(path).write_bytes(pickle.dumps(payload))

    @classmethod
    def load(cls, path: str | Path) -> RegimeDetector:
        """Restore a detector saved with :meth:`save`."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"no regime model at {path}")
        try:
            payload = pickle.loads(p.read_bytes())
        except Exception as e:  # truncated / non-pickle / wrong format
            raise ValueError(f"corrupt regime model at {path}") from e

        detector = cls(
            n_states=payload["n_states"],
            n_fits=payload["n_fits"],
            n_iter=payload["n_iter"],
            random_state=payload["random_state"],
            min_duration=payload["min_duration"],
        )
        detector._model = payload["model"]
        detector._labels = payload["labels"]
        detector._rank_of_state = payload["rank_of_state"]
        return detector
