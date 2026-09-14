"""APIx index builder — composite headline via a 36-cell basket.

Core math (per cell = route × lead window):
    index(t, r, w) = P(t, r, w) / P(0, r, w) × 100
    APIx(t)        = Σ index(t, r, w) × w_r × w_win  over cells present on t

A single shared base date anchors every cell, so t+1 / t+7 / t+30 series are
directly comparable (there is no longer one base per window). Cell price is
the MEDIAN fare on each (route, window, date) — a single ultra-cheap fare no
longer drags a cell down. Routes that lose data are carried forward from the
last known fare. Weights are never re-normalised per day beyond re-balancing
over the cells that exist on each date (a late-starting window expands the
basket cleanly).

Design: the core functions operate on pandas DataFrames so they are trivially
unit-testable off-line; thin wrappers read from / write to SQLite.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.indexer.estimators import aggregate, weighted_trimmed_mean
from src.storage.database import get_connection

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "indexer.yaml"

INDEX_COLUMNS = [
    "index_date",
    "lead_window_days",
    "route",
    "weight",
    "route_price",
    "route_index",
    "aggregate_index",
    "base_period",
]

INDEX_TABLES = {"daily_index", "weekly_index", "monthly_index"}

INSERT_SQL = """
INSERT INTO {table}
(index_date, lead_window_days, route, weight, route_price, route_index,
 aggregate_index, base_period)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def load_index_config(cfg_path: Path | str | None = None) -> dict:
    """Read the ``index:`` section of config/indexer.yaml."""
    path = Path(cfg_path) if cfg_path else CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f).get("index", {})


def load_route_weights(cfg_path: Path | str | None = None) -> dict[str, float]:
    """Read route weights from yaml and normalise them to sum 1.0."""
    raw = load_index_config(cfg_path).get("weights", {})
    total = sum(raw.values())
    if not raw or total <= 0:
        raise ValueError("No route weights found in indexer.yaml under 'index.weights'")
    return {route: weight / total for route, weight in raw.items()}


def load_window_weights(cfg_path: Path | str | None = None) -> dict[int, float]:
    """Read booking lead-time (window) shares and normalise them to sum 1.0.

    These are the ``window_weights`` leg of the 36-cell basket: each cell's
    weight = route weight × window weight.
    """
    raw = load_index_config(cfg_path).get("window_weights", {1: 0.2, 7: 0.3, 30: 0.5})
    total = sum(raw.values())
    if not raw or total <= 0:
        raise ValueError("No window weights found in indexer.yaml under 'index.window_weights'")
    return {int(window): weight / total for window, weight in raw.items()}


def load_active_windows(cfg_path: Path | str | None = None) -> list[int]:
    """Read the lead windows the index is built for (default: t+1, t+7, t+30)."""
    windows = load_index_config(cfg_path).get("active_windows", [1, 7, 30])
    return [int(w) for w in windows]


def load_estimator_config(cfg_path: Path | str | None = None) -> dict:
    """Read the estimator settings from the ``index:`` section of indexer.yaml.

    Returns the aggregation estimator name + trim fraction (used for the daily
    headline), the rolling estimator name + trim fraction (used for the
    7/30-day weekly/monthly smoothing), and the route-price collapse method.
    """
    cfg = load_index_config(cfg_path)
    return {
        "aggregation_estimator": cfg.get("aggregation_estimator", "weighted_mean"),
        "aggregation_trim_frac": float(cfg.get("aggregation_trim_frac", 0.10)),
        "rolling_estimator": cfg.get("rolling_estimator", "mean"),
        "rolling_trim_frac": float(cfg.get("rolling_trim_frac", 0.10)),
        "route_price_method": cfg.get("route_price_method", "median"),
    }


def read_cleaned_flights(db_path: Path | str | None = None) -> pd.DataFrame:
    """Load the full cleaned_flights table as a DataFrame."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql("SELECT * FROM cleaned_flights", conn)
    finally:
        conn.close()


ROUTE_PRICE_METHODS = {"min", "median"}


def route_price_per_day(cleaned: pd.DataFrame, method: str = "median") -> pd.DataFrame:
    """Collapse cleaned rows to one fare per (route, window, date) cell.

    ``method`` picks how the multiple scraped fares in a cell are combined:
        "min"    — classic lowest-fare cell price
        "median" — robust centre (default); a single ultra-cheap fare no longer
                   drags the cell down.

    Rows flagged as outliers (is_outlier == 1) are excluded from the price.
    Missing dates within a (route, window) observation span are carried
    forward from the last known fare, so a coverage gap no longer drags the
    aggregate index down for no economic reason.
    """
    if method not in ROUTE_PRICE_METHODS:
        raise ValueError(
            f"Unknown route price method '{method}'. Choose from {sorted(ROUTE_PRICE_METHODS)}"
        )

    df = cleaned.copy()
    df = df[df["total_fare"].notna()]
    if "is_outlier" in df.columns:
        df = df[df["is_outlier"] != 1]

    prices = (
        df.groupby(["route", "lead_window_days", "scrape_date"])["total_fare"]
        .agg(method)
        .reset_index()
        .rename(columns={"total_fare": "route_price"})
    )
    prices = prices.sort_values(["route", "lead_window_days", "scrape_date"])
    return _carry_forward_missing_dates(prices)


def _carry_forward_missing_dates(prices: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill route prices across gaps in each (route, window) span.

    Fills every calendar day between a group's first and last observed date;
    dates before the first observation stay missing (nothing to carry from).
    """
    if prices is None or prices.empty:
        return prices

    chunks: list[pd.DataFrame] = []
    for (_, _), g in prices.groupby(["route", "lead_window_days"]):
        g = g.set_index("scrape_date")
        calendar = pd.date_range(
            start=g.index.min(), end=g.index.max(), freq="D"
        ).strftime("%Y-%m-%d")
        g = g.reindex(calendar).ffill()
        g = g.reset_index().rename(columns={"index": "scrape_date"})
        chunks.append(g)

    out = pd.concat(chunks, ignore_index=True)
    return out[prices.columns]


def compute_daily_index(
    prices: pd.DataFrame,
    route_weights: dict[str, float],
    window_weights: dict[int, float] | None = None,
    round_to: int = 2,
    estimator: str = "weighted_mean",
    trim_frac: float | None = None,
) -> pd.DataFrame:
    """Compute cell-level and composite daily index over the 36-cell basket.

    Each cell (route × lead window) is priced against its OWN base fare — the
    fare on the shared base date (the first date with ANY data) when the cell
    existed then. A cell absent on the shared base date uses its first observed
    fare instead and joins the basket at 100 on its own start date (so a
    window added mid-scrape expands the basket without jerking the headline).

    Cell weight = route weight × window weight; when ``window_weights`` is
    None the active windows share equal weight, and the aggregate re-balances
    over the cells present on each date (so today's headline always blends to
    exactly the cells that exist). ``aggregate_index`` is the single composite
    headline, identical for every row of a given date.

    The aggregate uses the named ``estimator`` (see estimators module):
    weighted_mean is the classic Laspeyres; weighted_trimmed_mean and
    weighted_median are robust alternatives selected via config.
    """
    if prices is None or prices.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    if window_weights is None:
        active = sorted(int(w) for w in prices["lead_window_days"].unique())
        window_weights = {w: 1.0 / len(active) for w in active} if active else {}

    cell_weight = {
        (route, int(window)): rw * ww
        for route, rw in route_weights.items()
        for window, ww in window_weights.items()
    }

    base_date = prices["scrape_date"].min()
    base = prices[prices["scrape_date"] == base_date].set_index(
        ["route", "lead_window_days"]
    )["route_price"]
    # Fallback base for cells absent on the shared base date: their own first
    # observation (and its date). Such cells join the basket at 100 later.
    first_price = (
        prices.sort_values("scrape_date")
        .groupby(["route", "lead_window_days"])["route_price"]
        .first()
    )
    first_date = (
        prices.groupby(["route", "lead_window_days"])["scrape_date"].min()
    )

    rows: list[dict] = []
    for day_date in sorted(prices["scrape_date"].unique()):
        day_data = prices[prices["scrape_date"] == day_date].set_index(
            ["route", "lead_window_days"]
        )["route_price"]

        route_indices: list[float] = []
        cells: list[float] = []
        date_rows: list[dict] = []
        for (route, window), cw in cell_weight.items():
            if (route, window) not in day_data.index:
                continue
            cell_base_date = base_date
            key = (route, window)
            p_base = base.get(key)
            if p_base is None:
                if key not in first_price.index:
                    continue
                p_base = first_price[key]
                cell_base_date = first_date[key]
            if p_base <= 0:
                continue
            route_index = (day_data[key] / p_base) * 100.0
            route_indices.append(route_index)
            cells.append(cw)
            date_rows.append(
                {
                    "index_date": day_date,
                    "lead_window_days": window,
                    "route": route,
                    "weight": cw,
                    "route_price": float(day_data[key]),
                    "route_index": round(route_index, round_to),
                    "aggregate_index": None,
                    "base_period": cell_base_date,
                }
            )
        agg_value = round(aggregate(route_indices, cells, estimator, trim_frac), round_to)
        for r in date_rows:
            r["aggregate_index"] = agg_value
        rows.extend(date_rows)

    return pd.DataFrame(rows, columns=INDEX_COLUMNS)


ROLLING_ESTIMATORS = {"mean", "trimmed_mean", "median"}


def _rolling_agg(series: pd.Series, window_days: int, estimator: str, trim_frac: float) -> pd.Series:
    """Apply an unweighted rolling estimator over a Series (min_periods=1)."""
    if estimator == "mean":
        return series.rolling(window_days, min_periods=1).mean()
    if estimator == "median":
        return series.rolling(window_days, min_periods=1).median()
    if estimator == "trimmed_mean":
        def _trim(values: np.ndarray) -> float:
            v = np.asarray(values, dtype=float)
            v = v[~np.isnan(v)]
            if v.size == 0:
                return float("nan")
            return weighted_trimmed_mean(v, np.ones(v.size), trim_frac)

        return series.rolling(window_days, min_periods=1).apply(_trim, raw=True)
    raise ValueError(f"Unknown rolling estimator '{estimator}'. Choose from {sorted(ROLLING_ESTIMATORS)}")


def compute_rolling_index(
    daily: pd.DataFrame,
    window_days: int,
    round_to: int = 2,
    estimator: str = "mean",
    trim_frac: float = 0.10,
) -> pd.DataFrame:
    """Weekly / monthly rollups of daily values per route and per aggregate.

    Anchored at each index_date (min_periods=1 so early data still yields a
    value). The rolling ``estimator`` is ``mean`` (default), ``median``, or
    ``trimmed_mean`` over the trailing window.
    """
    if daily is None or daily.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    df = daily.sort_values(["lead_window_days", "route", "index_date"])
    df["route_price_roll"] = (
        df.groupby(["lead_window_days", "route"])["route_price"]
        .transform(lambda s: _rolling_agg(s, window_days, estimator, trim_frac))
    )
    df["route_index_roll"] = (
        df.groupby(["lead_window_days", "route"])["route_index"]
        .transform(lambda s: _rolling_agg(s, window_days, estimator, trim_frac))
    )
    # The composite headline is ONE value per date (identical across routes and
    # windows), so the rolling aggregate must run over date-deduped values.
    # Rolling over the route-major frame would sweep across route blocks.
    unique_agg = (
        df.drop_duplicates(["lead_window_days", "index_date"])
        [["lead_window_days", "index_date", "aggregate_index"]]
        .copy()
    )
    unique_agg["agg_roll"] = (
        unique_agg.groupby("lead_window_days")["aggregate_index"]
        .transform(lambda s: _rolling_agg(s, window_days, estimator, trim_frac))
    )
    df = df.merge(
        unique_agg[["lead_window_days", "index_date", "agg_roll"]],
        on=["lead_window_days", "index_date"],
        how="left",
    )

    out = pd.DataFrame(
        {
            "index_date": df["index_date"],
            "lead_window_days": df["lead_window_days"],
            "route": df["route"],
            "weight": df["weight"],
            "route_price": df["route_price_roll"].round(round_to),
            "route_index": df["route_index_roll"].round(round_to),
            "aggregate_index": df["agg_roll"].round(round_to),
            "base_period": df["base_period"],
        }
    )
    return out.reset_index(drop=True)


def write_index(
    index_df: pd.DataFrame, table: str, db_path: Path | str | None = None
) -> int:
    """Overwrite *_index rows for each (index_date, lead_window_days).

    Re-running for the same date re-computes rather than duplicating rows.
    """
    if table not in INDEX_TABLES:
        raise ValueError(f"Unknown index table: {table}")

    if index_df is None or index_df.empty:
        log.info("No rows to write to %s", table)
        return 0

    index_df = index_df[INDEX_COLUMNS]
    conn = get_connection(db_path)
    try:
        for (day, window), _ in index_df.groupby(["index_date", "lead_window_days"]):
            conn.execute(
                f"DELETE FROM {table} WHERE index_date = ? AND lead_window_days = ?",
                (day, int(window)),
            )
        rows = [tuple(r) for r in index_df.itertuples(index=False, name=None)]
        conn.executemany(INSERT_SQL.format(table=table), rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()