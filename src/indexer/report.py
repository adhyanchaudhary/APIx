"""Run the estimator stability comparison and print a plain-text report.

Usage:
    python -m src.indexer.report                 # real db, falls back to synthetic
    python -m src.indexer.report --db data/x.db  # specific database
    python -m src.indexer.report --synthetic     # force synthetic data

The report answers the mentor's "which estimator is more stable" question:
  - aggregation estimator comparison  (weighted mean / trimmed / median)
  - rolling estimator comparison      (mean / trimmed / median, on weekly)
  - route sensitivity                 (which routes lever the headline)
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from src.indexer.api_index import (
    compute_daily_index,
    compute_rolling_index,
    load_estimator_config,
    load_route_weights,
    load_window_weights,
    read_cleaned_flights,
    route_price_per_day,
)
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
from src.indexer.synthetic import make_synthetic_cleaned

log = logging.getLogger(__name__)

MIN_ROUTES = 3
MIN_DATES = 5


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-7s | %(message)s",
        stream=sys.stdout,
    )


def _load_cleaned(db_path: Path | str | None, force_synthetic: bool) -> tuple[pd.DataFrame, str]:
    """Return (cleaned, source_label); falls back to synthetic when too sparse."""
    if not force_synthetic:
        cleaned = read_cleaned_flights(db_path)
        if (
            not cleaned.empty
            and cleaned["route"].nunique() >= MIN_ROUTES
            and cleaned["scrape_date"].nunique() >= MIN_DATES
        ):
            return cleaned, "REAL"
    return make_synthetic_cleaned(), "SYNTHETIC"


def _print_stability_table(label: str, table: pd.DataFrame) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    cols = [c for c in STABILITY_COLUMNS if c in table.columns] or list(table.columns)
    print(table[cols].round(3).to_string(float_format=lambda x: f"{x:.3f}"))


def _rolling_comparison(daily: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    rows: dict[int, dict] = {}
    for window in windows:
        for estimator in ("mean", "trimmed_mean", "median"):
            roll = compute_rolling_index(daily, 7, estimator=estimator, round_to=4)
            series = aggregate_by_day(roll, window)
            key = f"{estimator}"
            stats = stability_stats(series.values)
            row = rows.setdefault(window, {})
            for col in STABILITY_COLUMNS:
                row[f"{key}.{col}"] = stats[col]
    return pd.DataFrame(rows).T.rename_axis("lead_window_days").round(3)


def run_report(db_path: Path | str | None = None, *, force_synthetic: bool = False) -> None:
    cleaned, source = _load_cleaned(db_path, force_synthetic)
    print(f"Data source: {source} ({len(cleaned)} cleaned rows, "
          f"{cleaned['route'].nunique()} routes, {cleaned['scrape_date'].nunique()} dates)")

    weights = load_route_weights()
    window_weights = load_window_weights()
    est = load_estimator_config()
    prices = route_price_per_day(cleaned, method=est["route_price_method"])
    windows = sorted(int(w) for w in prices["lead_window_days"].unique())
    print(f"Window weights (booking lead-time shares): {window_weights}")
    print(f"Route price method: {est['route_price_method']}")
    print(f"Lead windows present: {windows}")

    # 1 ── Aggregation estimator comparison (daily composite headline)
    comparison = compare_aggregation_estimators(
        prices, weights, AGGREGATION_ESTIMATORS,
        est["aggregation_trim_frac"], windows, window_weights,
    )
    for name, table in comparison.items():
        _print_stability_table(f"Aggregation estimator: {name}", table)
    best = best_estimator_per_window(comparison)
    print(f"\nCalmest aggregation estimator: {best}")
    print("(One composite headline per date, so every window row is the same series.)")

    # 2 ── Rolling estimator comparison (7-day composite headline)
    daily = compute_daily_index(
        prices, weights, window_weights, round_to=4,
        estimator=est["aggregation_estimator"], trim_frac=est["aggregation_trim_frac"],
    )
    _print_stability_table("Rolling estimator (7-day) comparison", _rolling_comparison(daily, windows))

    # 3 ── Route sensitivity + weight elasticity (DGCA weight attention)
    sens = route_sensitivity(
        prices, weights, est["aggregation_estimator"], est["aggregation_trim_frac"], window_weights=window_weights
    )
    print("\nRoute data-loss robustness (mean |move| if a route loses data; LOWER is better)")
    print("-" * 76)
    print(sens.round(3).to_string(float_format=lambda x: f"{x:.3f}"))

    elas = weight_elasticity(
        prices, weights, est["aggregation_estimator"], est["aggregation_trim_frac"], window_weights=window_weights
    )
    print("\nWeight leverage (mean |headline move| per +0.01 weight; DGCA accuracy matters)")
    print("-" * 76)
    print(elas.round(3).to_string(float_format=lambda x: f"{x:.3f}"))


def main() -> None:
    parser = argparse.ArgumentParser(description="APIx estimator stability report")
    parser.add_argument("--db", type=str, default=None)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    _setup_logging()
    run_report(args.db, force_synthetic=args.synthetic)


if __name__ == "__main__":
    main()