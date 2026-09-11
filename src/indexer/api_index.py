"""APIx index builder — Laspeyres-style weighted basket index.

Core math (per lead window):
    APIx(t) = Σ [ P_i(t) / P_i(0) × w_i ] × 100

Where P_i(t) = lowest fare on route i on date t, P_i(0) = lowest fare on the
base date, and w_i are route weights (sum ≈ 1.0). Missing routes are omitted
and their weight contributes 0 (weights are never re-normalised per day).

Design: the core functions operate on pandas DataFrames so they are trivially
unit-testable off-line; thin wrappers read from / write to SQLite.
"""
import logging
from pathlib import Path

import pandas as pd
import yaml

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


def read_cleaned_flights(db_path: Path | str | None = None) -> pd.DataFrame:
    """Load the full cleaned_flights table as a DataFrame."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql("SELECT * FROM cleaned_flights", conn)
    finally:
        conn.close()


def route_price_per_day(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Collapse cleaned rows to one min fare per (route, window, date).

    Rows flagged as outliers (is_outlier == 1) are excluded from the price.
    """
    df = cleaned.copy()
    df = df[df["total_fare"].notna()]
    if "is_outlier" in df.columns:
        df = df[df["is_outlier"] != 1]

    prices = (
        df.groupby(["route", "lead_window_days", "scrape_date"])["total_fare"]
        .min()
        .reset_index()
        .rename(columns={"total_fare": "route_price"})
    )
    return prices


def compute_daily_index(
    prices: pd.DataFrame, weights: dict[str, float], round_to: int = 2
) -> pd.DataFrame:
    """Compute route-level and aggregate daily index per lead window.

    Base period is the first date with data, independently per lead window.
    Routes without data on a given day are omitted (weights stay fixed).
    """
    if prices is None or prices.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    rows: list[dict] = []
    for window, wg in prices.groupby("lead_window_days"):
        wg = wg.sort_values("scrape_date")
        base_date = wg["scrape_date"].iloc[0]
        base_prices = wg.loc[wg["scrape_date"] == base_date].set_index("route")["route_price"]

        for day_date, day in wg.groupby("scrape_date"):
            by_route = day.set_index("route")["route_price"]
            agg = 0.0
            date_rows: list[dict] = []
            for route, weight in weights.items():
                if route not in by_route.index or route not in base_prices.index:
                    continue
                p_base = base_prices[route]
                if p_base <= 0:
                    continue
                route_index = (by_route[route] / p_base) * 100.0
                agg += route_index * weight
                date_rows.append(
                    {
                        "index_date": day_date,
                        "lead_window_days": int(window),
                        "route": route,
                        "weight": weight,
                        "route_price": float(by_route[route]),
                        "route_index": round(route_index, round_to),
                        "aggregate_index": None,
                        "base_period": base_date,
                    }
                )
            agg_value = round(agg, round_to)
            for r in date_rows:
                r["aggregate_index"] = agg_value
            rows.extend(date_rows)

    return pd.DataFrame(rows, columns=INDEX_COLUMNS)


def compute_rolling_index(
    daily: pd.DataFrame, window_days: int, round_to: int = 2
) -> pd.DataFrame:
    """Weekly / monthly rollups: rolling mean of daily values per route and
    per aggregate, anchored at each index_date (min_periods=1 so early data
    still yields a value)."""
    if daily is None or daily.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    df = daily.sort_values(["lead_window_days", "route", "index_date"])
    df["route_price_roll"] = (
        df.groupby(["lead_window_days", "route"])["route_price"]
        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())
    )
    df["route_index_roll"] = (
        df.groupby(["lead_window_days", "route"])["route_index"]
        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())
    )
    df["agg_roll"] = (
        df.groupby("lead_window_days")["aggregate_index"]
        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())
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