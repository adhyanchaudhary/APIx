import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "apix.db"

RAW_FLIGHTS = """
CREATE TABLE IF NOT EXISTS raw_flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_date TEXT NOT NULL,
    route TEXT NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    carrier TEXT,
    flight_no TEXT,
    depart_time TEXT,
    arrive_time TEXT,
    duration_mins INTEGER,
    stops INTEGER,
    base_fare REAL,
    taxes REAL,
    total_fare REAL,
    currency TEXT DEFAULT 'INR',
    lead_window_days INTEGER NOT NULL,
    scrape_timestamp TEXT NOT NULL
);
"""

CLEANED_FLIGHTS = """
CREATE TABLE IF NOT EXISTS cleaned_flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_date TEXT NOT NULL,
    route TEXT NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    carrier TEXT,
    flight_no TEXT,
    depart_time TEXT,
    arrive_time TEXT,
    duration_mins INTEGER,
    stops INTEGER,
    base_fare REAL,
    taxes REAL,
    total_fare REAL,
    currency TEXT DEFAULT 'INR',
    lead_window_days INTEGER NOT NULL,
    scrape_timestamp TEXT NOT NULL,
    quality_score REAL,
    is_outlier INTEGER DEFAULT 0,
    dedup_hash TEXT,
    extraction_batch_id TEXT
);
"""

DAILY_INDEX = """
CREATE TABLE IF NOT EXISTS daily_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_date TEXT NOT NULL,
    lead_window_days INTEGER NOT NULL,
    route TEXT NOT NULL,
    weight REAL,
    route_price REAL,
    route_index REAL,
    open_index REAL,
    close_index REAL,
    aggregate_index REAL,
    base_period TEXT,
    price_obs_date TEXT
);
"""

WEEKLY_INDEX = """
CREATE TABLE IF NOT EXISTS weekly_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_date TEXT NOT NULL,
    lead_window_days INTEGER NOT NULL,
    route TEXT NOT NULL,
    weight REAL,
    route_price REAL,
    route_index REAL,
    open_index REAL,
    close_index REAL,
    aggregate_index REAL,
    base_period TEXT,
    price_obs_date TEXT
);
"""

MONTHLY_INDEX = """
CREATE TABLE IF NOT EXISTS monthly_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_date TEXT NOT NULL,
    lead_window_days INTEGER NOT NULL,
    route TEXT NOT NULL,
    weight REAL,
    route_price REAL,
    route_index REAL,
    open_index REAL,
    close_index REAL,
    aggregate_index REAL,
    base_period TEXT,
    price_obs_date TEXT
);
"""

LIVE_INDEX = """
CREATE TABLE IF NOT EXISTS live_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_date TEXT NOT NULL,
    tick_timestamp TEXT NOT NULL,
    lead_window_days INTEGER NOT NULL,
    route TEXT NOT NULL,
    route_price REAL,
    route_index REAL,
    aggregate_index REAL,
    delta REAL,
    estimator TEXT
);
"""


_INDEX_TABLES_WITH_OPEN_CLOSE = ("daily_index", "weekly_index", "monthly_index")


def _ensure_index_columns(conn: sqlite3.Connection) -> None:
    """Add ``open_index`` / ``close_index`` / ``price_obs_date`` to existing
    index tables (migration).

    BEFORE this schema change the daily/weekly/monthly tables stored a single
    ``aggregate_index`` per date.  Older databases need the columns added via
    ALTER TABLE, and every pre-existing row is back-filled with its own
    ``aggregate_index`` so the dashboard never sees NULL session brackets —
    those rows simply read as "the day opened AND closed at the same level"
    (which is exactly what a completed day looks like).
    """
    for table in _INDEX_TABLES_WITH_OPEN_CLOSE:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, dtype in (("open_index", "REAL"), ("close_index", "REAL"), ("price_obs_date", "TEXT")):
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
        conn.execute(
            f"UPDATE {table} SET open_index = COALESCE(open_index, aggregate_index),"
            f" close_index = COALESCE(close_index, aggregate_index)"
            f" WHERE open_index IS NULL OR close_index IS NULL"
        )


def init_db(db_path: Path | str | None = None) -> None:
    """Create all tables if they don't exist."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        for ddl in [RAW_FLIGHTS, CLEANED_FLIGHTS, DAILY_INDEX, WEEKLY_INDEX, MONTHLY_INDEX, LIVE_INDEX]:
            conn.execute(ddl)
        _ensure_index_columns(conn)
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return a live connection to the database."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


if __name__ == "__main__":
    init_db()
    print(f"Database created at: {DB_PATH}")
