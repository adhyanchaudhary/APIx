"""Tests for the live pipeline: events payloads, today-session reads, movers."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.live.events import IndexUpdate, SubscriberHub
from src.live.run_live import (
    _biggest_mover,
    _daily_has_full_basket,
    _prime_basket,
    _read_today,
)
from src.storage.database import get_connection, init_db

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CSV = FIXTURES / "sample_cleaned.csv"
WEIGHTS = {"DEL-BOM": 0.4, "DEL-BLR": 0.3, "BOM-BLR": 0.3}
WINDOW_WEIGHTS = {1: 0.5, 7: 0.5}


def _make_update(**kw) -> IndexUpdate:
    defaults = dict(
        index_date="2026-09-18",
        tick_timestamp=datetime(2026, 9, 18, 10, 30, 0),
        route="DEL-BOM",
        lead_window_days=7,
        route_price=12000.0,
        route_index=105.0,
        aggregate_index=102.5,
        delta=2.5,
        estimator="weighted_trimmed_mean",
    )
    defaults.update(kw)
    return IndexUpdate(**defaults)


def test_index_update_to_dict_has_open_close():
    d = _make_update(open_index=100.0, close_index=102.5).to_dict()
    assert d["index_date"] == "2026-09-18"
    assert d["tick_timestamp"] == datetime(2026, 9, 18, 10, 30, 0).isoformat()
    assert d["open_index"] == 100.0
    assert d["close_index"] == 102.5


def test_index_update_open_close_default_none():
    d = _make_update().to_dict()
    assert d["open_index"] is None
    assert d["close_index"] is None


def test_subscriber_hub_stores_and_preserves_order():
    got = []
    hub = SubscriberHub()
    cb1 = lambda u: got.append(("a", u))
    cb2 = lambda u: got.append(("b", u))
    hub.subscribe(cb1)
    hub.subscribe(cb2)
    hub.emit(_make_update())
    assert [tag for tag, _ in got] == ["a", "b"]


def test_subscriber_hub_unsubscribe():
    got = []
    hub = SubscriberHub()
    cb = lambda u: got.append(u)
    hub.subscribe(cb)
    hub.unsubscribe(cb)
    hub.emit(_make_update())
    assert got == []


def test_init_db_migrates_legacy_index_schema(tmp_path):
    """A pre-open/close database gets the new columns ALTERed in and its rows
    back-filled from aggregate_index (legacy rows read as completed days)."""
    db = tmp_path / "legacy.db"
    conn = get_connection(db)
    conn.execute(
        "CREATE TABLE daily_index (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " index_date TEXT NOT NULL, lead_window_days INTEGER NOT NULL,"
        " route TEXT NOT NULL, weight REAL, route_price REAL, route_index REAL,"
        " aggregate_index REAL, base_period TEXT)"
    )
    conn.execute(
        "INSERT INTO daily_index (index_date, lead_window_days, route, aggregate_index)"
        " VALUES ('2026-09-01', 7, 'DEL-BOM', 100.0)"
    )
    conn.commit()
    conn.close()

    init_db(db)

    conn = get_connection(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_index)").fetchall()}
        assert {"open_index", "close_index"}.issubset(cols)
        row = conn.execute(
            "SELECT aggregate_index, open_index, close_index FROM daily_index"
        ).fetchone()
        assert row[0] == 100.0
        assert row[1] == 100.0  # back-filled: open == old close
        assert row[2] == 100.0
    finally:
        conn.close()


def test_read_today_returns_open_close_from_daily(tmp_path):
    from src.indexer.api_index import compute_daily_index, route_price_per_day, write_index

    db = tmp_path / "apix.db"
    init_db(db)
    prices = route_price_per_day(pd.read_csv(CSV))
    daily = compute_daily_index(prices, WEIGHTS, WINDOW_WEIGHTS)
    write_index(daily, "daily_index", db)

    day = daily["index_date"].iloc[0]
    open_idx, close_idx, cells = _read_today(db, day)
    assert open_idx == close_idx  # single recompute: open == close for the day
    assert open_idx is not None
    assert ("DEL-BOM", 7) in cells


def test_read_today_falls_back_to_live_tape(tmp_path):
    db = tmp_path / "apix.db"
    init_db(db)
    conn = get_connection(db)
    try:
        conn.execute(
            "INSERT INTO live_index (index_date, tick_timestamp, lead_window_days, route,"
            " route_price, route_index, aggregate_index, delta, estimator)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-09-18", "10:00", 7, "DEL-BOM", 12000.0, 105.0, 103.5, 0.0, "x"),
        )
        conn.commit()
    finally:
        conn.close()

    open_idx, close_idx, cells = _read_today(db, "2026-09-18")
    assert open_idx is None
    assert close_idx == pytest.approx(103.5, abs=0.01)
    assert cells == {}


def test_read_today_returns_nones_when_empty(tmp_path):
    db = tmp_path / "apix.db"
    init_db(db)
    open_idx, close_idx, cells = _read_today(db, "2026-09-18")
    assert open_idx is None and close_idx is None and cells == {}


def test_biggest_mover_marks_largest_delta():
    prev_cells = {("DEL-BOM", 1): (100.0, 12_000.0), ("BOM-BLR", 1): (100.0, 6_000.0)}
    new_cells = {("DEL-BOM", 1): (103.0, 12_360.0), ("BOM-BLR", 1): (111.0, 6_600.0)}
    key, (idx, price) = _biggest_mover(prev_cells, new_cells)
    assert key == ("BOM-BLR", 1)
    assert idx == pytest.approx(111.0, abs=0.01)
    assert price == pytest.approx(6_600.0, abs=0.01)


def test_biggest_mover_new_cell_treated_as_mover():
    key, val = _biggest_mover({}, {("DEL-BOM", 1): (101.0, 1.0)})
    assert key == ("DEL-BOM", 1)
    assert val == (101.0, 1.0)


def test_biggest_mover_none_when_nothing_new():
    assert _biggest_mover({("DEL-BOM", 1): (100.0, 1.0)}, {}) == (None, None)
    assert _biggest_mover({}, {}) == (None, None)


def test_daily_has_full_basket_true_when_all_routes_present(tmp_path):
    db = tmp_path / "apix.db"
    init_db(db)
    conn = get_connection(db)
    try:
        for route, val in (("DEL-BOM", 101.0), ("BOM-DEL", 102.0), ("DEL-BLR", 99.0)):
            conn.execute(
                "INSERT INTO daily_index (index_date, lead_window_days, route, route_price,"
                " route_index, aggregate_index)"
                " VALUES ('2026-09-18', 7, ?, ?, ?, ?)",
                (route, val, 100.0, 100.0),
            )
        conn.commit()
    finally:
        conn.close()

    assert _daily_has_full_basket(db, "2026-09-18", ["DEL-BOM", "BOM-DEL", "DEL-BLR"])
    assert not _daily_has_full_basket(db, "2026-09-18", ["DEL-BOM", "BOM-DEL", "MAA-BOM"])
    assert not _daily_has_full_basket(db, "2026-09-17", ["DEL-BOM"])


def test_prime_basket_scrapes_full_pool_once_then_round_robin(tmp_path, monkeypatch):
    """Prime scrapes every route BEFORE the rotating subset cycle starts."""
    from src.live import run_live as rl

    db = tmp_path / "apix.db"
    init_db(db)

    scraped: list[list[str]] = []

    async def _fake_scrape(**kw):
        scraped.append(kw.get("routes_subset", []))

    def _conn(_p):
        class FakeConn:
            def execute(self, *a, **k):
                return []
            def close(self):
                pass
        return FakeConn()

    monkeypatch.setattr(rl, "run_scrape", _fake_scrape)
    monkeypatch.setattr(rl, "clean_raw_data", lambda _db: {"cleaned": 0})
    monkeypatch.setattr(rl, "run_index", lambda _db: None)
    monkeypatch.setattr(rl, "get_connection", _conn)
    monkeypatch.setattr(rl, "_read_today",
                        lambda *a, **k: (None, 100.0, {("DEL-BOM", 1): (100.0, 1.0)}))
    monkeypatch.setattr(rl, "SubscriberHub",
                        lambda: type("H", (), {"subscribe": lambda s, cb: None,
                                               "emit": lambda s, u: None})())

    rl.live_engine(db_path=db, interval=0, routes=["DEL-BOM", "BOM-DEL"],
                   rotate=2, prime=True, cycle_limit=2)

    assert scraped, "prime full-basket scrape should run before any rotation"
    assert scraped[0] == ["DEL-BOM", "BOM-DEL"]  # first scrape is the FULL pool prime