"""Tests for src.indexer.estimators — the pluggable aggregation estimators.

All cases use small hand-computed arrays (see the module docstrings / the
worked examples in the design discussion) so failures are easy to eyeball.
"""
import math

import pytest

from src.indexer.estimators import (
    DEFAULT_TRIM_FRAC,
    ESTIMATORS,
    aggregate,
    weighted_mean,
    weighted_median,
    weighted_trimmed_mean,
)

# The 4-route day from the design discussion:
#   A=95 (0.40), B=100 (0.30), C=130 (0.20), D=240 (0.10)
VALUES = [95.0, 100.0, 130.0, 240.0]
WEIGHTS = [0.40, 0.30, 0.20, 0.10]


def test_weighted_mean_matches_laspeyres():
    assert weighted_mean(VALUES, WEIGHTS) == pytest.approx(118.0)


def test_weighted_trimmed_mean_example():
    # 10% weight trimmed off each tail: D removed entirely, A shaved to 0.30.
    assert weighted_trimmed_mean(VALUES, WEIGHTS, 0.10) == pytest.approx(105.625)


def test_weighted_median_example():
    # Cumulative weight at 95=0.40, 100=0.70 → crosses 0.5 at 100.
    assert weighted_median(VALUES, WEIGHTS) == pytest.approx(100.0)


def test_trim_frac_zero_equals_weighted_mean():
    assert weighted_trimmed_mean(VALUES, WEIGHTS, 0.0) == pytest.approx(118.0)


def test_equal_weight_ten_percent_trim():
    equal = [0.25] * 4
    # Only 0.10 of weight is shaved per end, so the extreme routes are
    # partially kept: remaining weights 0.15, 0.25, 0.25, 0.15 → mean 134.6875.
    assert weighted_trimmed_mean([95, 100, 130, 240], equal, 0.10) == pytest.approx(
        134.6875
    )


def test_small_route_fully_removed_by_trim():
    # A tiny 0.06-weight route at the extreme is eaten entirely by a 0.10 trim.
    # Effective trimmed weights: 95→0.27, 100→0.38, 130→0.15, 240→0.00
    # mean = (95·0.27 + 100·0.38 + 130·0.15) / 0.80 = 103.9375
    v = [95.0, 100.0, 130.0, 240.0]
    w = [0.37, 0.38, 0.19, 0.06]
    assert weighted_trimmed_mean(v, w, 0.10) == pytest.approx(103.9375)


def test_single_value_passes_through():
    assert weighted_mean([120], [1.0]) == pytest.approx(120.0)
    assert weighted_trimmed_mean([120], [1.0], 0.10) == pytest.approx(120.0)
    assert weighted_median([120], [1.0]) == pytest.approx(120.0)


def test_all_zero_weights_gives_nan():
    assert math.isnan(weighted_mean([100, 200], [0.0, 0.0]))
    assert math.isnan(weighted_trimmed_mean([100, 200], [0.0, 0.0]))
    assert math.isnan(weighted_median([100, 200], [0.0, 0.0]))


def test_empty_input_gives_nan():
    assert math.isnan(weighted_mean([], []))
    assert math.isnan(weighted_trimmed_mean([], []))
    assert math.isnan(weighted_median([], []))


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        weighted_mean([1, 2], [1.0])
    with pytest.raises(ValueError):
        weighted_trimmed_mean([1, 2], [1.0])


def test_median_exact_boundary_averages_neighbours():
    # Cumulative weight hits 0.5 exactly at the boundary → midpoint.
    assert weighted_median([1, 2, 3], [0.5, 0.25, 0.25]) == pytest.approx(1.5)


def test_registry_contains_all_estimators():
    assert set(ESTIMATORS) == {"weighted_mean", "weighted_trimmed_mean", "weighted_median"}


def test_aggregate_dispatches_by_name():
    assert aggregate(VALUES, WEIGHTS, "weighted_mean") == pytest.approx(118.0)
    assert aggregate(VALUES, WEIGHTS, "weighted_median") == pytest.approx(100.0)
    assert aggregate(VALUES, WEIGHTS, "weighted_trimmed_mean") == pytest.approx(105.625)


def test_aggregate_unknown_estimator_raises():
    with pytest.raises(ValueError, match="estimator"):
        aggregate(VALUES, WEIGHTS, "harmonic_mean")


def test_default_trim_frac_is_10_percent():
    assert DEFAULT_TRIM_FRAC == 0.10
    assert aggregate(VALUES, WEIGHTS, "weighted_trimmed_mean") == pytest.approx(105.625)


def test_trim_frac_over_half_falls_back_to_median():
    assert weighted_trimmed_mean(VALUES, WEIGHTS, 0.9) == pytest.approx(
        weighted_median(VALUES, WEIGHTS)
    )