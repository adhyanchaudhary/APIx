"""Tests for Phase E: metrics, synthetic data, and the report smoke."""
import numpy as np
import pandas as pd
import pytest

from src.indexer.metrics import (
    AGGREGATION_ESTIMATORS,
    STABILITY_COLUMNS,
    aggregate_by_day,
    best_estimator_per_window,
    compare_aggregation_estimators,
    route_sensitivity,
    stability_stats,
    weight_elasticity,
)
from src.indexer.synthetic import make_synthetic_cleaned, ROUTES, WINDOWS


# ── Stability stats ──────────────────────────────────────────────────────────

def test_stability_stats_basic():
    # series [100, 105, 95, 100] → diffs [5, -10, 5]
    stats = stability_stats([100, 105, 95, 100], threshold=5.0)
    assert stats["mean_abs_change"] == pytest.approx(20 / 3, abs=0.01)
    assert stats["std_change"] == pytest.approx(8.660, abs=0.01)
    assert stats["max_abs_change"] == pytest.approx(10.0)
    assert stats["extreme_move_days"] == 1


def test_stability_stats_single_value():
    stats = stability_stats([100])
    assert np.isnan(stats["mean_abs_change"])
    assert stats["extreme_move_days"] == 0


def test_stability_stats_with_nan_fills():
    stats = stability_stats([100, np.nan, 100])
    assert stats["mean_abs_change"] == pytest.approx(0.0)


# ── Synthetic data ───────────────────────────────────────────────────────────

def test_make_synthetic_shape_and_uniques():
    df = make_synthetic_cleaned()
    assert set(df["route"]) == set(ROUTES)
    assert set(df["lead_window_days"]) == set(WINDOWS)
    assert df["scrape_date"].nunique() == 15  # all dates present across routes
    # 12 routes × 14 dates × 3 windows × 7 flights per cell (plus promos).
    assert len(df) >= 12 * 14 * 3 * 7
    # Every cell carries a realistic bucket of fares, not a single one.
    per_cell = df.groupby(["route", "lead_window_days", "scrape_date"])["total_fare"]
    assert per_cell.count().min() >= 7
    # Median of each cell is strictly above the minimum → median-vs-min visible.
    assert (per_cell.median() > per_cell.min()).mean() > 0.5
    assert df["total_fare"].min() > 0
    assert df["dedup_hash"].is_unique


# ── Aggregate by day ─────────────────────────────────────────────────────────

def test_aggregate_by_day_series():
    from src.indexer.api_index import compute_daily_index, route_price_per_day
    from src.indexer.api_index import load_route_weights

    cleaned = make_synthetic_cleaned()
    prices = route_price_per_day(cleaned)
    weights = load_route_weights()
    daily = compute_daily_index(prices, weights, round_to=4)
    series = aggregate_by_day(daily, window=1)
    assert len(series) > 0
    assert series.index.is_monotonic_increasing


# ── Compare aggregation estimators ───────────────────────────────────────────

def test_compare_aggregation_estimators_keys_and_columns():
    cleaned = make_synthetic_cleaned()
    from src.indexer.api_index import load_route_weights, route_price_per_day

    prices = route_price_per_day(cleaned)
    weights = load_route_weights()
    comp = compare_aggregation_estimators(prices, weights)
    assert set(comp.keys()) == set(AGGREGATION_ESTIMATORS)
    for name, table in comp.items():
        assert all(col in table.columns for col in STABILITY_COLUMNS)


def test_best_estimator_per_window_returns_all_windows():
    cleaned = make_synthetic_cleaned()
    from src.indexer.api_index import load_route_weights, route_price_per_day

    prices = route_price_per_day(cleaned)
    weights = load_route_weights()
    comp = compare_aggregation_estimators(prices, weights)
    best = best_estimator_per_window(comp)
    assert set(best.keys()) == set(WINDOWS)
    for window, name in best.items():
        assert name in AGGREGATION_ESTIMATORS


# ── Route sensitivity ────────────────────────────────────────────────────────

def test_route_sensitivity_all_routes_and_robust():
    cleaned = make_synthetic_cleaned()
    from src.indexer.api_index import load_route_weights, route_price_per_day

    prices = route_price_per_day(cleaned)
    weights = load_route_weights()
    sens = route_sensitivity(prices, weights, window=1)
    assert set(sens.index) == set(weights)
    # Losing one route's data moves the headline by well under 2 index points.
    assert sens.max() < 2.0
    # Sorted descending.
    assert list(sens.values) == sorted(sens.values, reverse=True)


def test_weight_elasticity_positive_and_ranked():
    cleaned = make_synthetic_cleaned()
    from src.indexer.api_index import load_route_weights, route_price_per_day

    prices = route_price_per_day(cleaned)
    weights = load_route_weights()
    elas = weight_elasticity(prices, weights, window=1)
    assert set(elas.index) == set(weights)
    assert (elas > 0).all()
    # Sorted descending, so the first route has the most leverage.
    assert list(elas.values) == sorted(elas.values, reverse=True)
