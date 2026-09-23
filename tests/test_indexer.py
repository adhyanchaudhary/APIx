"""Test suites for src.indexer.api_index — the APIx weighted basket index.

All tests run offline using tests/fixtures/sample_cleaned.csv.
"""
from pathlib import Path

import pandas as pd
import pytest
import sqlite3
import yaml

from src.indexer.api_index import (
    CONFIG_PATH,
    INDEX_COLUMNS,
    cell_staleness_days,
    compute_daily_index,
    compute_rolling_index,
    load_estimator_config,
    load_route_weights,
    load_stale_cap,
    load_window_weights,
    route_price_per_day,
    write_index,
)
from src.storage.database import get_connection, init_db

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CSV = FIXTURES / "sample_cleaned.csv"

WEIGHTS = {"DEL-BOM": 0.4, "DEL-BLR": 0.3, "BOM-BLR": 0.3}
# Equal booking-lead-time shares for the 3-route × 2-window fixture: every
# cell weight = route weight × 0.5, so the fixture blends both windows 50/50.
WINDOW_WEIGHTS = {1: 0.5, 7: 0.5}


@pytest.fixture
def cleaned_df() -> pd.DataFrame:
    return pd.read_csv(CSV)


@pytest.fixture
def prices(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    return route_price_per_day(cleaned_df)


@pytest.fixture
def daily(prices: pd.DataFrame) -> pd.DataFrame:
    return compute_daily_index(prices, WEIGHTS, WINDOW_WEIGHTS)


def _rows(daily: pd.DataFrame, window: int, date: str) -> pd.DataFrame:
    return daily[(daily["lead_window_days"] == window) & (daily["index_date"] == date)]


# ── Config ──────────────────────────────────────────────────────────────────

def test_route_weights_load_and_normalise():
    weights = load_route_weights()
    assert len(weights) == 12
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert weights["DEL-BOM"] > 0


def test_estimator_config_loads_expected_keys():
    est = load_estimator_config()
    assert set(est) == {
        "aggregation_estimator",
        "aggregation_trim_frac",
        "rolling_estimator",
        "rolling_trim_frac",
        "route_price_method",
    }
    assert est["aggregation_estimator"] == "weighted_trimmed_mean"
    assert est["aggregation_trim_frac"] == pytest.approx(0.10)
    assert est["rolling_estimator"] == "mean"
    assert est["rolling_trim_frac"] == pytest.approx(0.10)
    assert est["route_price_method"] == "median"


def test_window_weights_load_and_normalise():
    window_weights = load_window_weights()
    assert set(window_weights) == {1, 7, 30}
    assert sum(window_weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert window_weights[30] > window_weights[1]


def test_stale_cap_loads_from_config():
    cap = load_stale_cap()
    assert cap == 7
    cfg = {"index": {"stale_cap_days": None}}
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as d:
        p = _P(d) / "indexer.yaml"
        p.write_text("index:\n  stale_cap_days: null\n")
        assert load_stale_cap(p) is None


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
    assert len(combo) == 1
    # Outlier fare 4200 excluded; 9/3's price carried forward instead.
    assert combo.iloc[0]["route_price"] == 4050.0


def test_price_per_day_uses_median_fare_by_default():
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
    assert prices.loc[0, "route_price"] == 5000.0  # median, not the cheapest 4800


def test_price_per_day_uses_min_fare_when_specified():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 3,
            "lead_window_days": [1] * 3,
            "scrape_date": ["2026-09-01"] * 3,
            "total_fare": [5000.0, 4800.0, 5200.0],
            "is_outlier": [0, 0, 0],
        }
    )
    prices = route_price_per_day(df, method="min")
    assert prices.loc[0, "route_price"] == 4800.0


def test_price_per_day_rejects_unknown_method():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 2,
            "lead_window_days": [1] * 2,
            "scrape_date": ["2026-09-01"] * 2,
            "total_fare": [5000.0, 4800.0],
            "is_outlier": [0, 0],
        }
    )
    with pytest.raises(ValueError):
        route_price_per_day(df, method="avg")


def test_price_per_day_carries_forward_across_gap():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 3,
            "lead_window_days": [1] * 3,
            "scrape_date": ["2026-09-01", "2026-09-03", "2026-09-04"],
            "total_fare": [5000.0, 5200.0, 5400.0],
            "is_outlier": [0, 0, 0],
        }
    )
    prices = route_price_per_day(df)
    gap = prices[prices["scrape_date"] == "2026-09-02"]
    assert len(gap) == 1
    assert gap.iloc[0]["route_price"] == 5000.0


def test_price_per_day_no_phantom_dates_before_first_observation():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 2,
            "lead_window_days": [1] * 2,
            "scrape_date": ["2026-09-03", "2026-09-04"],
            "total_fare": [5200.0, 5400.0],
            "is_outlier": [0, 0],
        }
    )
    prices = route_price_per_day(df)
    assert set(prices["scrape_date"]) == {"2026-09-03", "2026-09-04"}


def test_cell_carries_forward_to_global_max_not_cell_max():
    # A-B is observed 09-01..09-02 only, but C-D runs to 09-05: the global
    # span ends at 09-05, so A-B's last fare must carry forward to that date
    # (previously it stopped at its own max of 09-02 and dropped out).
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 2 + ["C-D"] * 3,
            "lead_window_days": [1] * 5,
            "scrape_date": ["2026-09-01", "2026-09-02",
                            "2026-09-01", "2026-09-02", "2026-09-05"],
            "total_fare": [5000.0, 5200.0, 3000.0, 3100.0, 3200.0],
            "is_outlier": [0, 0, 0, 0, 0],
        }
    )
    prices = route_price_per_day(df)
    ab = prices[prices["route"] == "A-B"].sort_values("scrape_date")
    assert ab["scrape_date"].max() == "2026-09-05"

    last = ab[ab["scrape_date"] == "2026-09-05"].iloc[0]
    assert last["route_price"] == 5200.0  # last known fare carried forward
    assert last["price_obs_date"] == "2026-09-02"  # imputed row identifiable

    real = ab[ab["scrape_date"] == "2026-09-02"].iloc[0]
    assert real["price_obs_date"] == "2026-09-02"  # real obs stamped as-is


def test_price_obs_date_stamped_on_real_observations(prices: pd.DataFrame):
    assert "price_obs_date" in prices.columns
    # Observation date never lies in the future.
    assert (prices["price_obs_date"] <= prices["scrape_date"]).all()
    # The fixture's one gap: DEL-BOM w=7 on 09-04 has no real fare (outlier),
    # so its 4050.0 was carried forward from 09-03 — identifiable via the stamp.
    carried = prices[
        (prices["route"] == "DEL-BOM")
        & (prices["lead_window_days"] == 7)
        & (prices["scrape_date"] == "2026-09-04")
    ].iloc[0]
    assert carried["route_price"] == 4050.0
    assert carried["price_obs_date"] == "2026-09-03"


# ── Daily index ─────────────────────────────────────────────────────────────

def test_base_day_is_100_for_each_window(daily: pd.DataFrame):
    for window in (1, 7):
        d1 = _rows(daily, window, "2026-09-01")
        assert not d1.empty
        assert (d1["route_index"] == 100.0).all()
        assert (d1["aggregate_index"] == 100.0).all()


def test_weighted_index_math(daily: pd.DataFrame):
    # Day 3, 36-cell basket (route weight × 0.5 window share each):
    #   t+1: DEL-BOM 4900/5000=98.0, DEL-BLR 6100/6000=101.67,
    #        BOM-BLR 3700/3500=105.71
    #   t+7: DEL-BOM 4050/4000=101.25, DEL-BLR 5050/5000=101.0,
    #        BOM-BLR 3200/3000=106.67
    # Composite = Σ cell_index × route_w × 0.5 = 102.11, one headline per date.
    d3 = _rows(daily, 1, "2026-09-03").set_index("route")
    assert d3.loc["DEL-BOM", "route_index"] == pytest.approx(98.0, abs=0.1)
    assert d3.loc["DEL-BLR", "route_index"] == pytest.approx(101.67, abs=0.01)
    assert d3.loc["BOM-BLR", "route_index"] == pytest.approx(105.71, abs=0.01)
    assert d3.loc["DEL-BOM", "aggregate_index"] == pytest.approx(102.11, abs=0.01)
    # The composite headline is identical for every row of the same date.
    assert d3["aggregate_index"].nunique() == 1
    assert _rows(daily, 7, "2026-09-03")["aggregate_index"].nunique() == 1


def test_daily_index_aggregate_median_estimator(prices: pd.DataFrame):
    # Day 3, 6 cell indices sorted 98(.2), 101(.15), 101.25(.2), 101.67(.15),
    # 105.71(.15), 106.67(.15): cumulative weight crosses 0.5 at 101.25.
    daily = compute_daily_index(prices, WEIGHTS, WINDOW_WEIGHTS, estimator="weighted_median")
    d3 = _rows(daily, 1, "2026-09-03").set_index("route")
    assert d3.loc["DEL-BOM", "aggregate_index"] == pytest.approx(101.25, abs=0.01)


def test_daily_index_aggregate_trimmed_estimator(prices: pd.DataFrame):
    # 10% weight-trim over the 6 sorted cells (cum 0.2/0.35/0.55/0.7/0.85/1.0):
    # kept weights 0.10/0.15/0.20/0.15/0.15/0.05 → or 102.05.
    daily = compute_daily_index(prices, WEIGHTS, WINDOW_WEIGHTS, estimator="weighted_trimmed_mean")
    d3 = _rows(daily, 1, "2026-09-03").set_index("route")
    assert d3.loc["DEL-BOM", "aggregate_index"] == pytest.approx(102.05, abs=0.01)


def test_missing_route_carries_forward_last_fare(daily: pd.DataFrame):
    # Window 7, day 4: DEL-BOM's 9/4 fare is an outlier → the last good fare
    # (9/3 = 4050) is carried forward, so the route is NOT missing and the
    # composite = .2·(106+101.25) + .15·(100.83+100+108.57+110)... = 104.36.
    d4 = _rows(daily, 7, "2026-09-04")
    by_route = d4.set_index("route")
    assert set(by_route.index) == {"DEL-BOM", "DEL-BLR", "BOM-BLR"}
    assert by_route.loc["DEL-BOM", "route_price"] == 4050.0
    assert by_route.loc["DEL-BOM", "route_index"] == pytest.approx(101.25, abs=0.01)
    assert by_route.loc["DEL-BOM", "aggregate_index"] == pytest.approx(104.36, abs=0.01)


def test_cells_without_a_shared_base_join_at_bridge_level(prices: pd.DataFrame):
    # A window that starts after the shared base day is chain-linked, on its
    # debut day, to a bridge anchor already on the shared base: same route's
    # closest other window first. DEL-BOM t+30 debuts 09-03 at 6000; DEL-BOM
    # t+7 (base 4000) priced 4050 on 09-03 → anchor level 4050/4000·100 = 101.25.
    df = pd.concat(
        [
            prices,
            pd.DataFrame(
                {
                    "route": ["DEL-BOM"],
                    "lead_window_days": [30],
                    "scrape_date": ["2026-09-03"],
                    "route_price": [6000.0],
                    "price_obs_date": ["2026-09-03"],
                }
            ),
        ],
        ignore_index=True,
    )
    daily = compute_daily_index(df, WEIGHTS, {1: 0.5, 7: 0.1, 30: 0.4})
    late = _rows(daily, 30, "2026-09-03").set_index("route")
    # Not 100: joins at the bridge anchor's level on the shared base date.
    assert late.loc["DEL-BOM", "route_index"] == pytest.approx(101.25, abs=0.01)
    assert late.loc["DEL-BOM", "base_period"] == "2026-09-01"
    assert late.loc["DEL-BOM", "price_obs_date"] == "2026-09-03"
    # Cells on the shared base keep the global anchor.
    assert _rows(daily, 1, "2026-09-03").set_index("route").loc["DEL-BOM", "base_period"] == "2026-09-01"
    assert daily[daily["lead_window_days"] == 30]["index_date"].min() == "2026-09-03"
    # The late cell joins at the bridge LEVEL, so the debut-day composite is
    # consistent across windows of that date.
    window30_agg = daily[daily["lead_window_days"] == 30]["aggregate_index"].iloc[0]
    assert late.loc["DEL-BOM", "aggregate_index"] == pytest.approx(window30_agg, abs=0.01)
    # The late cell's subsequent moves are measured against its virtual base:
    # price 6300 on 09-05 → route_index = 6300/6000·100/101.25·100 ≈ 106.31
    late30 = pd.concat(
        [
            df,
            pd.DataFrame(
                {
                    "route": ["DEL-BOM"],
                    "lead_window_days": [30],
                    "scrape_date": ["2026-09-05"],
                    "route_price": [6300.0],
                    "price_obs_date": ["2026-09-05"],
                }
            ),
        ],
        ignore_index=True,
    )
    daily2 = compute_daily_index(late30, WEIGHTS, {1: 0.5, 7: 0.1, 30: 0.4})
    v = _rows(daily2, 30, "2026-09-05").set_index("route")
    assert v.loc["DEL-BOM", "route_index"] == pytest.approx(6300 / 6000 * 101.25, abs=0.01)


def test_late_cell_bridge_anchor_prefers_closest_same_route_window(prices: pd.DataFrame):
    # BOM-BLR debuts t+30 on 09-03. Same route has t+1 (base 3500, 09-03 = 3700)
    # and t+7 (base 3000, 09-03 = 3200). t+7 is closer to 30, so it anchors:
    # 3200/3000·100 = 106.67.
    df = pd.concat(
        [
            prices,
            pd.DataFrame(
                {
                    "route": ["BOM-BLR"],
                    "lead_window_days": [30],
                    "scrape_date": ["2026-09-03"],
                    "route_price": [3400.0],
                }
            ),
        ],
        ignore_index=True,
    )
    daily = compute_daily_index(df, WEIGHTS, {1: 0.5, 7: 0.3, 30: 0.2})
    late = _rows(daily, 30, "2026-09-03").set_index("route")
    assert late.loc["BOM-BLR", "route_index"] == pytest.approx(106.67, abs=0.01)
    assert late.loc["BOM-BLR", "base_period"] == "2026-09-01"


def test_late_cell_bridge_falls_back_to_same_window_nearest_route():
    # Route C-W has NO other window on the shared base, so it anchors to the
    # nearest route (by price on debut day) IN ITS OWN window (t+7): A-B t+7.
    df = pd.DataFrame(
        {
            "route": ["A-B", "A-B", "C-W"],
            "lead_window_days": [7, 7, 7],
            "scrape_date": ["2026-09-01", "2026-09-03", "2026-09-05"],
            "total_fare": [4000.0, 4800.0, 4400.0],
            "is_outlier": [0, 0, 0],
        }
    )
    prices = route_price_per_day(df)
    daily = compute_daily_index(prices, {"A-B": 0.5, "C-W": 0.5}, {7: 1.0})
    late = _rows(daily, 7, "2026-09-05").set_index("route")
    # A-B t+7: base 4000 → level on 09-05 = 4800/4000·100 = 120.
    assert late.loc["A-B", "route_index"] == pytest.approx(120.0, abs=0.01)
    # C-W (no same-route window) chains onto A-B's debut-day level → 120, NOT 100.
    assert late.loc["C-W", "route_index"] == pytest.approx(120.0, abs=0.01)
    assert late.loc["C-W", "base_period"] == "2026-09-01"


def test_late_cell_without_any_anchor_still_joins_at_100():
    # Route C-D debuts t+7 on 09-05 but has no t+7 sibling and C-D never had
    # another window; A-B t+1 sets the shared base date only. No anchor exists
    # → the orphan keeps its own first fare and joins at 100.
    df = pd.DataFrame(
        {
            "route": ["A-B", "C-D"],
            "lead_window_days": [1, 7],
            "scrape_date": ["2026-09-01", "2026-09-05"],
            "route_price": [8000.0, 8800.0],
        }
    )
    daily = compute_daily_index(df, {"A-B": 0.5, "C-D": 0.5}, {1: 0.5, 7: 0.5})
    late = _rows(daily, 7, "2026-09-05").set_index("route")
    assert late.loc["C-D", "route_index"] == pytest.approx(100.0, abs=0.01)
    assert late.loc["C-D", "base_period"] == "2026-09-05"


def test_never_observed_route_stays_omitted(prices: pd.DataFrame):
    weights = {"DEL-BOM": 0.4, "DEL-BLR": 0.3, "BOM-BLR": 0.3, "GHOST-RTE": 0.0}
    daily = compute_daily_index(prices, weights)
    assert "GHOST-RTE" not in set(daily["route"])


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


def test_rolling_route_index_median_estimator():
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    weekly = compute_rolling_index(daily, 3, estimator="median")
    w1 = weekly[weekly["lead_window_days"] == 1].set_index(["index_date", "route"])
    # DEL-BOM route_index 100, 104, 98 → median(100, 104) = 102 at d2.
    assert w1.loc[("2026-09-02", "DEL-BOM"), "route_index"] == pytest.approx(102.0, abs=0.01)
    # median(100, 104, 98) = 100 at d3.
    assert w1.loc[("2026-09-03", "DEL-BOM"), "route_index"] == pytest.approx(100.0, abs=0.01)


def test_rolling_route_index_trimmed_estimator():
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    weekly = compute_rolling_index(daily, 3, estimator="trimmed_mean", trim_frac=0.10)
    w1 = weekly[weekly["lead_window_days"] == 1].set_index(["index_date", "route"])
    # 10% weight-trim over [98, 100, 104] → kept 0.7/1.0/0.7 → (98·.7+100+104·.7)/2.4 = 100.58
    assert w1.loc[("2026-09-03", "DEL-BOM"), "route_index"] == pytest.approx(100.58, abs=0.01)


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


def test_daily_rows_carry_price_obs_date_rolling_rows_null(tmp_path):
    """Daily rows stamp the last real observation; weekly/monthly leave NULL."""
    db = tmp_path / "apix.db"
    init_db(db)
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)
    assert "price_obs_date" in daily.columns
    assert daily["price_obs_date"].notna().all()

    write_index(daily, "daily_index", db)
    write_index(compute_rolling_index(daily, 7), "weekly_index", db)
    write_index(compute_rolling_index(daily, 30), "monthly_index", db)

    conn = get_connection(db)
    try:
        daily_obs = conn.execute(
            "SELECT COUNT(*) FROM daily_index WHERE price_obs_date IS NOT NULL"
        ).fetchone()[0]
        weekly_null = conn.execute(
            "SELECT COUNT(*) FROM weekly_index WHERE price_obs_date IS NOT NULL"
        ).fetchone()[0]
        monthly_null = conn.execute(
            "SELECT COUNT(*) FROM monthly_index WHERE price_obs_date IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    assert daily_obs == 30  # every daily cell stamped
    assert weekly_null == 0
    assert monthly_null == 0


def test_cell_staleness_days_measures_carry_forward():
    df = pd.DataFrame(
        {
            "route": ["A-B"] * 2 + ["C-D"] * 3,
            "lead_window_days": [1] * 5,
            "scrape_date": ["2026-09-01", "2026-09-02",
                            "2026-09-01", "2026-09-02", "2026-09-05"],
            "total_fare": [5000.0, 5200.0, 3000.0, 3100.0, 3200.0],
            "is_outlier": [0, 0, 0, 0, 0],
        }
    )
    prices = route_price_per_day(df)
    daily = compute_daily_index(prices, {"A-B": 0.5, "C-D": 0.5})
    last = daily[daily["index_date"] == "2026-09-05"].set_index("route")
    # A-B was really observed 09-02 (3 days stale); C-D observed 09-05 (fresh).
    assert last.loc["A-B", "price_obs_date"] == "2026-09-02"
    assert last.loc["C-D", "price_obs_date"] == "2026-09-05"
    stale = cell_staleness_days(daily[daily["index_date"] == "2026-09-05"]).reset_index(drop=True)
    assert stale.max() == 3
    assert stale.min() == 0


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


def test_write_index_preserves_open_advances_close(tmp_path):
    db = tmp_path / "apix.db"
    init_db(db)
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS)

    morning = daily.copy()
    morning["close_index"] = daily["aggregate_index"] * 1.05
    morning["aggregate_index"] = morning["close_index"]
    write_index(morning, "daily_index", db)

    afternoon = daily.copy()
    afternoon["open_index"] = daily["aggregate_index"] * 1.10
    afternoon["close_index"] = daily["aggregate_index"] * 1.10
    afternoon["aggregate_index"] = afternoon["close_index"]
    write_index(afternoon, "daily_index", db)

    conn = get_connection(db)
    try:
        rows = conn.execute(
            "SELECT index_date, route, lead_window_days, open_index, close_index"
            " FROM daily_index"
        ).fetchall()
    finally:
        conn.close()

    by_cell = {(r[0], r[1], r[2]): (r[3], r[4]) for r in rows}
    assert len(by_cell) == len(daily)
    cols = ["index_date", "route", "lead_window_days", "aggregate_index"]
    for row in daily.reset_index()[cols].itertuples(index=False):
        key = (row.index_date, row.route, row.lead_window_days)
        op, cl = by_cell[key]
        assert op == pytest.approx(row.aggregate_index, abs=0.01)  # open stays frozen
        assert cl == pytest.approx(1.10 * row.aggregate_index, abs=0.01)  # close advances


def test_write_index_preserves_open_per_date_not_route(tmp_path):
    """A date's open is ONE frozen value shared by every row - even rows whose
    route joined the basket after the day opened."""
    db = tmp_path / "apix.db"
    init_db(db)

    def frame(routes, agg=100.0, day="2026-09-01", open_v=None):
        rows = []
        for w in (1, 7):
            for r in routes:
                rows.append(
                    [
                        day,
                        w,
                        r,
                        1.0 / len(routes),
                        5000.0,
                        agg,
                        agg if open_v is None else open_v,
                        agg,
                        agg,
                        day,
                        day,  # price_obs_date
                    ]
                )
        return pd.DataFrame(rows, columns=INDEX_COLUMNS)

    # Morning: the basket opens at 100.0.
    write_index(frame(["A-B", "A-C"]), "daily_index", db)
    # Afternoon: the composite moves to 108.0 and a NEW route joins mid-day.
    write_index(frame(["A-B", "A-C", "D-E"], agg=108.0), "daily_index", db)

    conn = get_connection(db)
    try:
        rows = conn.execute(
            "SELECT index_date, route, lead_window_days, open_index, close_index"
            " FROM daily_index WHERE index_date = '2026-09-01'"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 3 * 2  # 3 routes x 2 windows
    opens = {r[3] for r in rows}
    assert opens == {100.0}  # one frozen day-open shared by every row
    by_cell = {(r[1], r[2]): r[4] for r in rows}
    for key, close in by_cell.items():
        assert close == pytest.approx(108.0, abs=0.01)  # close advanced for all


def test_write_index_rejects_unknown_table(tmp_path):
    daily = pd.DataFrame(columns=INDEX_COLUMNS)
    with pytest.raises(ValueError):
        write_index(daily, "hack_index", tmp_path / "apix.db")


def test_init_db_migrates_legacy_index_tables_adds_price_obs_date(tmp_path):
    """A pre-existing DB without price_obs_date gains it via ALTER TABLE."""
    db = tmp_path / "legacy.apix.db"
    conn = sqlite3.connect(str(db))
    try:
        # Old schema: no open/close/price_obs_date columns.
        conn.execute(
            """
            CREATE TABLE daily_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_date TEXT NOT NULL,
                lead_window_days INTEGER NOT NULL,
                route TEXT NOT NULL,
                weight REAL,
                route_price REAL,
                route_index REAL,
                aggregate_index REAL,
                base_period TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO daily_index (index_date, lead_window_days, route, weight,"
            " route_price, route_index, aggregate_index, base_period)"
            " VALUES ('2026-09-01', 1, 'A-B', 0.5, 100.0, 100.0, 100.0, '2026-09-01')"
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db)

    conn = get_connection(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_index)").fetchall()}
        row = conn.execute(
            "SELECT open_index, close_index, price_obs_date FROM daily_index LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert {"open_index", "close_index", "price_obs_date"} <= cols
    assert row[0] == pytest.approx(100.0)  # open back-filled from aggregate
    assert row[1] == pytest.approx(100.0)  # close back-filled
    assert row[2] is None  # legacy rows have no observation stamp


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

    # 5 dates × 2 windows × 3 routes; carry-forward fills the one gap.
    daily_expected = 5 * 2 * 3  # 30
    assert result["daily"] == daily_expected
    assert result["weekly"] == daily_expected
    assert result["monthly"] == daily_expected

    conn = get_connection(db)
    try:
        agg = conn.execute("SELECT DISTINCT aggregate_index, lead_window_days, index_date FROM daily_index ORDER BY index_date, lead_window_days").fetchall()
    finally:
        conn.close()
    assert agg, "daily_index must be populated"


def test_run_index_respects_estimator_config(tmp_path):
    from src.indexer.run_index import run_index

    db = tmp_path / "apix.db"
    init_db(db)
    cleaned = pd.read_csv(CSV)
    conn = get_connection(db)
    try:
        cleaned.to_sql("cleaned_flights", conn, if_exists="append", index=False)
    finally:
        conn.close()

    cfg = tmp_path / "indexer.yaml"
    base_cfg = yaml.safe_load(open(CONFIG_PATH))
    base_cfg["index"]["aggregation_estimator"] = "weighted_median"
    base_cfg["index"]["rolling_estimator"] = "median"
    cfg.write_text(yaml.safe_dump(base_cfg))

    result = run_index(db_path=db, cfg_path=cfg)
    assert result["daily"] == 30

    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT aggregate_index FROM daily_index "
            "WHERE index_date = '2026-09-03' AND lead_window_days = 1 LIMIT 1"
        ).fetchone()
        weekly = conn.execute(
            "SELECT COUNT(*) FROM weekly_index WHERE lead_window_days = 1"
        ).fetchone()[0]
    finally:
        conn.close()

    # Day 3, weighted median over the 6 fixture cells configured with
    # window_weights {1:0.2, 7:0.3, 30:0.5} (window 30 absent from data):
    # cum 0.08/0.17/0.29/0.35/0.41/0.50 crosses 0.25 at 101.25.
    assert row[0] == pytest.approx(101.25, abs=0.01)
    assert weekly == 15  # 3 routes × 5 dates, rolling median ran fine