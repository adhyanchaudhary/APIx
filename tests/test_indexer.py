"""Test suites for src.indexer.api_index — the APIx weighted basket index.

All tests run offline using tests/fixtures/sample_cleaned.csv.
"""
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.indexer.api_index import (
    INDEX_COLUMNS,
    compute_daily_index,
    compute_rolling_index,
    load_route_weights,
    route_price_per_day,
    write_index,
)
from src.storage.database import get_connection, init_db

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CSV = FIXTURES / "sample_cleaned.csv"

WEIGHTS = {"DEL-BOM": 0.4, "DEL-BLR": 0.3, "BOM-BLR": 0.3}


@pytest.fixture
def cleaned_df() -> pd.DataFrame:
    return pd.read_csv(CSV)


@pytest.fixture
def prices(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    return route_price_per_day(cleaned_df)


@pytest.fixture
def daily(prices: pd.DataFrame) -> pd.DataFrame:
    return compute_daily_index(prices, WEIGHTS)


def _rows(daily: pd.DataFrame, window: int, date: str) -> pd.DataFrame:
    return daily[(daily["lead_window_days"] == window) & (daily["index_date"] == date)]


# ── Config ──────────────────────────────────────────────────────────────────

def test_route_weights_load_and_normalise():
    weights = load_route_weights()
    assert len(weights) == 12
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert weights["DEL-BOM"] > 0


# ── Price collapse ──────────────────────────────────────────────────────────

def test_price_per_day_excludes_outliers(cleaned_df: pd.DataFrame, prices: pd.DataFrame):
    assert len(cleaned_df) == 30
    assert cleaned_df[cleaned_df["is_outlier"] == 1].shape[0] == 1
    flagged = cleaned_df[cleaned_df["is_outlier"] == 1].iloc[0]
    assert flagged["route"] == "DEL-BOM"
    assert flagged["lead_window_days"] == 7
    assert flagged["scrape_date"] == "2026-09-04"
    combo = prices[
        (prices["route"] == "DEL-BOM")
        & (prices["lead_window_days"] == 7)
        & (prices["scrape_date"] == "2026-09-04")
    ]
    assert combo.empty, "Outlier fare must be excluded from route pricing"


def test_price_per_day_uses_min_fare():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 3,
            "lead_window_days": [1] * 3,
            "scrape_date": ["2026-09-01"] * 3,
            "total_fare": [5000.0, 4800.0, 5200.0],
            "is_outlier": [0, 0, 0],
        }
    )
    prices = route_price_per_day(df)
    assert prices.loc[0, "route_price"] == 4800.0


# ── Daily index ─────────────────────────────────────────────────────────────

def test_base_day_is_100_for_each_window(daily: pd.DataFrame):
    for window in (1, 7):
        d1 = _rows(daily, window, "2026-09-01")
        assert not d1.empty
        assert (d1["route_index"] == 100.0).all()
        assert (d1["aggregate_index"] == 100.0).all()


def test_weighted_index_math(daily: pd.DataFrame):
    # Window 1, day 3: DEL-BOM 4900/5000=98.0, DEL-BLR 6100/6000=101.67,
    # BOM-BLR 3700/3500=105.71 → agg = .4*98 + .3*101.67 + .3*105.71 = 101.41
    d3 = _rows(daily, 1, "2026-09-03").set_index("route")
    assert d3.loc["DEL-BOM", "route_index"] == pytest.approx(98.0, abs=0.01)
    assert d3.loc["DEL-BLR", "route_index"] == pytest.approx(101.67, abs=0.01)
    assert d3.loc["BOM-BLR", "route_index"] == pytest.approx(105.71, abs=0.01)
    assert d3.loc["DEL-BOM", "aggregate_index"] == pytest.approx(101.41, abs=0.01)


def test_missing_route_omitted_with_fixed_weights(daily: pd.DataFrame):
    # Window 7, day 4: DEL-BOM has no valid fare (outlier) → its weight stays
    # unclaimed. agg = .3*100.0 + .3*110.0 = 63.0, NOT re-normalised.
    d4 = _rows(daily, 7, "2026-09-04")
    assert "DEL-BOM" not in set(d4["route"])
    assert set(d4["route"]) == {"DEL-BLR", "BOM-BLR"}
    row = d4.iloc[0]
    assert row["aggregate_index"] == pytest.approx(63.0, abs=0.01)


def test_route_price_in_daily(daily: pd.DataFrame):
    d2 = _rows(daily, 1, "2026-09-02").set_index("route")
    assert d2.loc["DEL-BLR", "route_price"] == 6000.0
    assert d2.loc["BOM-BLR", "route_price"] == 3600.0


def test_empty_prices_gives_empty(daily):
    prices = pd.DataFrame(columns=["route", "lead_window_days", "scrape_date", "route_price"])
    assert compute_daily_index(prices, WEIGHTS).empty
    assert compute_rolling_index(daily if False else pd.DataFrame(columns=INDEX_COLUMNS), 7).empty


# ── Rolling (weekly/monthly) ───────────────────────────────────────────────

def test_rolling_route_index():
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    weekly = compute_rolling_index(daily, 3)
    w1 = weekly[weekly["lead_window_days"] == 1].set_index(["index_date", "route"])
    # DEL-BOM route_index: 100, 104, 98, 106, 102 → 3-day mean at d3 = 100.67
    assert w1.loc[("2026-09-03", "DEL-BOM"), "route_index"] == pytest.approx(100.67, abs=0.01)
    # d1 has min_periods=1 → equals the daily value
    assert w1.loc[("2026-09-01", "DEL-BOM"), "route_index"] == pytest.approx(100.0, abs=0.01)


def test_weekly_aggregate_is_rolling_mean_of_daily_aggregate():
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    weekly = compute_rolling_index(daily, 7)
    w1_daily = daily[daily["lead_window_days"] == 1].drop_duplicates("index_date")["aggregate_index"]
    expected = w1_daily.mean()
    w1 = weekly[weekly["lead_window_days"] == 1]
    last = w1.drop_duplicates("index_date").iloc[-1]["aggregate_index"]
    assert last == pytest.approx(expected, abs=0.01)


def test_rolling_writes_all_index_columns():
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    weekly = compute_rolling_index(daily, 7)
    assert list(weekly.columns) == INDEX_COLUMNS
    assert not weekly.empty


# ── Write / idempotency ────────────────────────────────────────────────────

def test_write_index_overwrites_same_date(tmp_path):
    db = tmp_path / "apix.db"
    init_db(db)
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)

    n1 = write_index(daily, "daily_index", db)
    n2 = write_index(daily, "daily_index", db)

    conn = get_connection(db)
    try:
        count = conn.execute("SELECT COUNT(*) FROM daily_index").fetchone()[0]
        dup = conn.execute(
            "SELECT COUNT(*) FROM daily_index WHERE index_date = '2026-09-01' AND lead_window_days = 1"
        ).fetchone()[0]
    finally:
        conn.close()

    assert n1 == n2 == count
    assert dup == 3  # 3 routes, same date/window, no duplicates


def test_write_index_rejects_unknown_table(tmp_path):
    daily = pd.DataFrame(columns=INDEX_COLUMNS)
    with pytest.raises(ValueError):
        write_index(daily, "hack_index", tmp_path / "apix.db")


# ── End-to-end ─────────────────────────────────────────────────────────────

def test_run_index_end_to_end(tmp_path):
    from src.indexer.run_index import run_index

    db = tmp_path / "apix.db"
    init_db(db)
    cleaned = pd.read_csv(CSV)
    conn = get_connection(db)
    try:
        cleaned.to_sql("cleaned_flights", conn, if_exists="append", index=False)
    finally:
        conn.close()

    result = run_index(db_path=db)

    # 5 dates × (2 windows − 1 missing day) × 3 routes
    daily_expected = 5 * 2 * 3 - 1  # 29
    assert result["daily"] == daily_expected
    assert result["weekly"] == daily_expected
    assert result["monthly"] == daily_expected

    conn = get_connection(db)
    try:
        agg = conn.execute("SELECT DISTINCT aggregate_index, lead_window_days, index_date FROM daily_index ORDER BY index_date, lead_window_days").fetchall()
    finally:
        conn.close()
    assert agg, "daily_index must be populated"