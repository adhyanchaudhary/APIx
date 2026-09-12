"""Stability metrics for picking the most robust headline estimator.

Given the same underlying price data we can re-run the index under several
aggregation estimators and score how *stable* each daily headline is:

    mean_abs_change   average index-point move day-to-day      (lower = calmer)
    std_change        volatility σ of those moves              (lower = calmer)
    max_abs_change    worst single-day move                    (lower = calmer)
    extreme_move_days count of days with |move| > threshold    (lower = calmer)

"Stable" is not the same as "smooth-for-its-own-sake" — the report also prints
a route-sensitivity table so we can see whether stability comes from ignoring
a genuinely informative route rather than just trimming noise.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from src.indexer.api_index import compute_daily_index

DEFAULT_THRESHOLD = 5.0

AGGREGATION_ESTIMATORS = ("weighted_mean", "weighted_trimmed_mean", "weighted_median")

STABILITY_COLUMNS = (
    "mean_abs_change",
    "std_change",
    "max_abs_change",
    "extreme_move_days",
)


def stability_stats(values: Sequence[float], threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Point-change stability statistics for a daily aggregate series."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    diff = np.diff(v)
    if diff.size == 0:
        return {
            "mean_abs_change": float("nan"),
            "std_change": float("nan"),
            "max_abs_change": float("nan"),
            "extreme_move_days": 0,
        }
    return {
        "mean_abs_change": float(np.mean(np.abs(diff))),
        "std_change": float(np.std(diff, ddof=1)) if diff.size > 1 else float("nan"),
        "max_abs_change": float(np.max(np.abs(diff))),
        "extreme_move_days": int(np.sum(np.abs(diff) > threshold)),
    }


def aggregate_by_day(daily: pd.DataFrame, window: int) -> pd.Series:
    """The unique daily aggregate index series for one lead window."""
    sub = daily[
        (daily["lead_window_days"] == window) & (daily["aggregate_index"].notna())
    ]
    return (
        sub.drop_duplicates("index_date")
        .set_index("index_date")["aggregate_index"]
        .sort_index()
    )


def compare_aggregation_estimators(
    prices: pd.DataFrame,
    weights: dict[str, float],
    estimators: Sequence[str] = AGGREGATION_ESTIMATORS,
    trim_frac: float = 0.10,
    windows: Sequence[int] | None = None,
    window_weights: dict[int, float] | None = None,
) -> dict[str, pd.DataFrame]:
    """Per estimator × window stability table.

    Returns ``estimator -> DataFrame`` with one row per window and the four
    stability columns. With the 36-cell basket the headline is a single
    composite number per date, so every window row shows the same composite
    stability (the window dimension is kept for reporting compatibility).
    """
    active = list(windows) if windows is not None else sorted(prices["lead_window_days"].unique())
    result: dict[str, pd.DataFrame] = {}
    for name in estimators:
        daily = compute_daily_index(
            prices, weights, window_weights, round_to=4, estimator=name, trim_frac=trim_frac
        )
        rows: dict[int, dict] = {}
        for window in active:
            series = aggregate_by_day(daily, window)
            rows[window] = stability_stats(series.values)
        result[name] = pd.DataFrame(rows).T
        result[name].index.name = "lead_window_days"
    return result


def route_sensitivity(
    prices: pd.DataFrame,
    weights: dict[str, float],
    estimator: str = "weighted_mean",
    trim_frac: float = 0.10,
    window: int = 1,
    window_weights: dict[int, float] | None = None,
) -> pd.Series:
    """Mean |headline move| when a route loses all data (weights re-normalised).

    Because the aggregation estimator already re-normalises (and missing fares
    are carried forward), losing one route's data moves the headline very
    little — SMALLER is better. This is a robustness stat, not a weight stat.
    """
    full = compute_daily_index(
        prices, weights, window_weights, round_to=4, estimator=estimator, trim_frac=trim_frac
    )
    base = aggregate_by_day(full, window)

    sensitivity: dict[str, float] = {}
    for route in weights:
        reduced_weights = {r: w for r, w in weights.items() if r != route}
        reduced = compute_daily_index(
            prices, reduced_weights, window_weights, round_to=4,
            estimator=estimator, trim_frac=trim_frac,
        )
        abridged = aggregate_by_day(reduced, window)
        joined = pd.concat([base, abridged], axis=1).ffill()
        sensitivity[route] = float((joined.iloc[:, 1] - joined.iloc[:, 0]).abs().mean())
    return pd.Series(sensitivity).sort_values(ascending=False)


def weight_elasticity(
    prices: pd.DataFrame,
    weights: dict[str, float],
    estimator: str = "weighted_mean",
    trim_frac: float = 0.10,
    window: int = 1,
    delta: float = 0.01,
    window_weights: dict[int, float] | None = None,
) -> pd.Series:
    """Mean |headline move| when one route's weight is bumped by ``delta``.

    Each route's weight is increased by ``delta`` and the whole weight vector
    re-normalised, so everything else scales down to compensate. Routes whose
    DGCA traffic-share estimate is decoupled from their price behaviour stand
    out — these are the weights that need attention.
    """
    full = compute_daily_index(
        prices, weights, window_weights, round_to=4, estimator=estimator, trim_frac=trim_frac
    )
    base = aggregate_by_day(full, window)
    total = float(sum(weights.values()))

    leverage: dict[str, float] = {}
    for route in weights:
        bumped = {r: w for r, w in weights.items()}
        bumped[route] += delta
        renormalised = {r: w / (total + delta) for r, w in bumped.items()}
        moved = compute_daily_index(
            prices, renormalised, window_weights, round_to=4,
            estimator=estimator, trim_frac=trim_frac,
        )
        shifted = aggregate_by_day(moved, window)
        joined = pd.concat([base, shifted], axis=1).ffill()
        leverage[route] = float((joined.iloc[:, 1] - joined.iloc[:, 0]).abs().mean())
    return pd.Series(leverage).sort_values(ascending=False)


def best_estimator_per_window(
    comparison: dict[str, pd.DataFrame],
) -> dict[int, str]:
    """Window → estimator name with the lowest mean_abs_change."""
    best: dict[int, tuple[float, str]] = {}
    for name, table in comparison.items():
        for window in table.index:
            value = float(table.loc[window, "mean_abs_change"])
            if np.isnan(value):
                continue
            if window not in best or value < best[window][0]:
                best[window] = (value, name)
    return {window: name for window, (_, name) in sorted(best.items())}