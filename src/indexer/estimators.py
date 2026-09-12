"""Robust aggregation estimators for the APIx headline index.

Three ways to combine route indices (and theirs weights) into a single daily
headline number, selectable by string name in config/indexer.yaml:

    weighted_mean            — current Laspeyres behaviour: Σ(v·w) / Σw.
    weighted_trimmed_mean    — shave ``trim_frac`` of weight from each tail,
                               then re-balance and average the survivors.
    weighted_median          — the value at which cumulative weight crosses 0.5.

Trimming is measured in WEIGHT MASS, not route count: cheap/costly extremes
are removed until the desired share of the basket is set aside, so a small
route is fully eaten while a big route is only partially shaved.

All functions take parallel ``values`` / ``weights`` array-likes and return a
float; a single surviving value (or NaN for degenerate input) is returned as-is.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

DEFAULT_TRIM_FRAC: float = 0.10


def _as_arrays(values: Sequence[float], weights: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Validate and convert inputs to aligned float arrays."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if v.ndim != 1 or w.ndim != 1:
        raise ValueError("values and weights must be 1-D arrays")
    if v.shape != w.shape:
        raise ValueError("values and weights must have the same length")
    return v, w


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    """Weighted arithmetic mean of values — the classic Laspeyres aggregate."""
    v, w = _as_arrays(values, weights)
    total = float(w.sum())
    if total <= 0:
        return float("nan")
    return float((v * w).sum() / total)


def weighted_trimmed_mean(
    values: Sequence[float],
    weights: Sequence[float],
    trim_frac: float = DEFAULT_TRIM_FRAC,
) -> float:
    """Weighted mean with ``trim_frac`` of weight cut from each tail.

    Values are sorted ascending; each element's weight is clipped so that the
    cumulative weight stays inside [trim_frac·total, (1-trim_frac)·total].
    Returns NaN if nothing survives the trim (e.g. trim_frac >= 0.5).
    """
    v, w = _as_arrays(values, weights)
    total = float(w.sum())
    if total <= 0:
        return float("nan")
    if len(v) == 1:
        return float(v[0])

    order = np.argsort(v)
    v = v[order]
    w = w[order]

    if trim_frac is None:
        trim_frac = DEFAULT_TRIM_FRAC
    trim_frac = max(0.0, min(float(trim_frac), 0.5))
    lower = trim_frac * total
    upper = total - lower

    cum = np.cumsum(w)
    # Overlap of each element's weight interval [cum-w, cum] with [lower, upper].
    w_kept = np.maximum(0.0, np.minimum(cum, upper) - np.maximum(cum - w, lower))
    kept_total = float(w_kept.sum())
    if kept_total <= 0:
        return weighted_median(v, w)
    return float((v * w_kept).sum() / kept_total)


def weighted_median(values: Sequence[float], weights: Sequence[float]) -> float:
    """Weighted median of values.

    Returns the value at which cumulative weight reaches 0.5·total; when the
    halfway point falls exactly on a boundary, averages the two neighbours.
    """
    v, w = _as_arrays(values, weights)
    total = float(w.sum())
    if total <= 0:
        return float("nan")
    if len(v) == 1:
        return float(v[0])

    order = np.argsort(v)
    v = v[order]
    w = w[order]

    half = 0.5 * total
    cum = np.cumsum(w)
    idx = int(np.searchsorted(cum, half, side="right"))
    if idx == 0:
        return float(v[0])
    if idx >= len(v):
        return float(v[-1])
    # Exact boundary: cumulative weight equals half exactly → average neighbours.
    if cum[idx - 1] == half:
        return float((v[idx - 1] + v[idx]) / 2.0)
    return float(v[idx])


ESTIMATORS: dict[str, Callable] = {
    "weighted_mean": weighted_mean,
    "weighted_trimmed_mean": weighted_trimmed_mean,
    "weighted_median": weighted_median,
}


def aggregate(
    values: Sequence[float],
    weights: Sequence[float],
    estimator: str = "weighted_mean",
    trim_frac: float = DEFAULT_TRIM_FRAC,
) -> float:
    """Dispatch to the named estimator with a uniform signature."""
    if estimator not in ESTIMATORS:
        raise ValueError(
            f"Unknown estimator '{estimator}'. Choose from {sorted(ESTIMATORS)}"
        )
    if estimator == "weighted_trimmed_mean":
        return weighted_trimmed_mean(values, weights, trim_frac)
    return ESTIMATORS[estimator](values, weights)