"""APIx Real-Time Airfare Price Index Dashboard.

Scientific / Institutional Light-Theme Dashboard:
- Formulation for Ministry of Statistics (MoSPI), NSO, and Reserve Bank of India (RBI)
- Original draft layout with long Teal top navigation bar
- Self-explanatory table column names across all datasets
- 3D Globe with geodesic curved flight arcs and Route Inspector Pop-up Card as DEFAULT tab
- Dedicated "Flight Search by City" tab
- Preserved brand typography (Eurostile Extended + Pacifico)
- Professional scientific presentation without generic emojis

Data source:
    - cleaned_flights      (cleaned flight rows, one per flight)
    - daily_index          (per-date cell + composite headline index)
    - weekly_index         (7-day rolling of the daily composite)
    - monthly_index        (30-day rolling of the daily composite)

Run from the repo root:
    streamlit run src/dashboard/app.py
"""
from __future__ import annotations

import math
import sys
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.storage.database import DB_PATH, get_connection, init_db
from src.indexer.api_index import cell_staleness_days, load_stale_cap
from src.live.run_live import live_engine

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="APIx — Airfare Price Index Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants & Route Metadata ───────────────────────────────────────────────
WINDOWS = (1, 7, 30)
WINDOW_LABELS = {
    1: "T+1 (last-minute)",
    7: "T+7 (one week out)",
    30: "T+30 (one month out)",
}

INDEX_TABLES = ("daily_index", "weekly_index", "monthly_index")
INDEX_TABLE_LABELS = {
    "daily_index": "Daily APIx",
    "weekly_index": "Weekly (7-day rolling)",
    "monthly_index": "Monthly (30-day rolling)",
}

ROUTE_COLORS = [
    "#6C5CE7",  # violet
    "#00CEC9",  # teal
    "#FD9644",  # orange
    "#0984E3",  # blue
    "#E84393",  # pink
    "#00B894",  # green
    "#FDCB6E",  # yellow
    "#D63031",  # red
    "#A29BFE",  # lavender
    "#55EFC4",  # mint
    "#E17055",  # terracotta
    "#74B9FF",  # sky
]

ACCENT = "#6C5CE7"

TOTAL_BASKET_CELLS = 12 * 3  # 12 directional routes × 3 lead windows

CITY_COORDS = {
    "DEL": {"lat": 28.5562, "lon": 77.1000, "name": "New Delhi", "airport": "Indira Gandhi International (DEL)"},
    "BOM": {"lat": 19.0896, "lon": 72.8656, "name": "Mumbai", "airport": "Chhatrapati Shivaji Maharaj Intl (BOM)"},
    "BLR": {"lat": 13.1986, "lon": 77.7066, "name": "Bengaluru", "airport": "Kempegowda International (BLR)"},
    "MAA": {"lat": 12.9941, "lon": 80.1709, "name": "Chennai", "airport": "Chennai International (MAA)"},
}

ROUTE_METADATA = {
    "DEL-BOM": {"distance": "1,148 km", "flight_time": "2h 10m", "corridor": "New Delhi — Mumbai", "weight": "10.0%"},
    "BOM-DEL": {"distance": "1,148 km", "flight_time": "2h 15m", "corridor": "Mumbai — New Delhi", "weight": "10.0%"},
    "DEL-BLR": {"distance": "1,740 km", "flight_time": "2h 45m", "corridor": "New Delhi — Bengaluru", "weight": "9.0%"},
    "BLR-DEL": {"distance": "1,740 km", "flight_time": "2h 50m", "corridor": "Bengaluru — New Delhi", "weight": "9.0%"},
    "DEL-MAA": {"distance": "1,760 km", "flight_time": "2h 45m", "corridor": "New Delhi — Chennai", "weight": "6.0%"},
    "MAA-DEL": {"distance": "1,760 km", "flight_time": "2h 50m", "corridor": "Chennai — New Delhi", "weight": "6.0%"},
    "BOM-BLR": {"distance": "840 km", "flight_time": "1h 40m", "corridor": "Mumbai — Bengaluru", "weight": "10.0%"},
    "BLR-BOM": {"distance": "840 km", "flight_time": "1h 45m", "corridor": "Bengaluru — Mumbai", "weight": "10.0%"},
    "BOM-MAA": {"distance": "1,030 km", "flight_time": "2h 00m", "corridor": "Mumbai — Chennai", "weight": "8.0%"},
    "MAA-BOM": {"distance": "1,030 km", "flight_time": "2h 05m", "corridor": "Chennai — Mumbai", "weight": "8.0%"},
    "BLR-MAA": {"distance": "290 km", "flight_time": "1h 00m", "corridor": "Bengaluru — Chennai", "weight": "7.0%"},
    "MAA-BLR": {"distance": "290 km", "flight_time": "1h 05m", "corridor": "Chennai — Bengaluru", "weight": "7.0%"},
}

TEAL_PALETTE = [
    "#0D9488",  # Primary Teal
    "#0F766E",  # Deep Teal
    "#14B8A6",  # Light Teal
    "#0284C7",  # Sky
    "#3B82F6",  # Blue
    "#6366F1",  # Indigo
    "#D97706",  # Amber
    "#475569",  # Slate
    "#059669",  # Emerald
    "#6D28D9",  # Purple
    "#BE185D",  # Rose
    "#0369A1",  # Ocean
]

DATA_DB_OPTIONS: dict[str, str] = {}
_e2e = _REPO_ROOT / "data" / "e2e_real.db"
if _e2e.exists():
    DATA_DB_OPTIONS["Real Scraped Database (data/e2e_real.db)"] = str(_e2e)
DATA_DB_OPTIONS["Synthetic Demo Database (data/apix.db)"] = str(DB_PATH)


DARK_CSS = """
<style>
  /* ── Dark theme overrides ───────────────────────────────────────── */
  [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0f1420 0%, #0a0e17 100%);
    color: #e8edf5;
  }
  [data-testid="stSidebar"][data-testid="stSidebar"] {
    background: linear-gradient(180deg, #141a29 0%, #10141f 100%);
  }
  [data-testid="stAppViewContainer"] h1,
  [data-testid="stAppViewContainer"] h2,
  [data-testid="stAppViewContainer"] h3,
  [data-testid="stAppViewContainer"] [data-testid="stHeading"] > * {
    color: #e8edf5 !important;
  }
  [data-testid="stAppViewContainer"] [data-testid="stMetricValue"],
  [data-testid="stAppViewContainer"] [data-testid="stMetricLabel"] {
    color: #e8edf5;
  }
  .topbar {
    background: #10151f;
    border-bottom: 1px solid #263044;
    box-shadow: 0 3px 12px rgba(0, 0, 0, .5);
  }
  .topbar .rnav-title { color: #93a1b5; border-right-color: #263044; }
  .topbar a { color: #cbd5e1; }
  .topbar a:hover { background: #1e2a41; color: #a5a6ff; }
  .topbar .rnav-dot { background: #3a4a63; }
  .topbar a:hover .rnav-dot { background: #a5a6ff; }
  [data-testid="stTabs"] { background: rgba(20, 26, 41, 0.6); }
  [data-testid="stTabs"] button[data-baseweb="tab"] {
    color: #a9b4c4;
    background: #181e2d;
    border-color: #2a3346;
    box-shadow: 0 1px 4px rgba(0, 0, 0, .3);
  }
  [data-testid="stTabs"] button[data-baseweb="tab"]:hover {
    border-color: #6C5CE7;
    color: #a5a6ff;
  }
  details[data-testid="stExpander"] {
    background: #141a29;
    border-color: #263044;
    box-shadow: 0 2px 12px rgba(0, 0, 0, .4);
  }
  details[data-testid="stExpander"] summary { color: #cbd5e1; }
  details[data-testid="stExpander"][open] summary {
    color: #a5a6ff;
    border-bottom-color: #263044;
  }
  [data-testid="stDataFrame"] {
    background: #141a29;
    border-color: #263044;
    box-shadow: 0 3px 14px rgba(0, 0, 0, .4);
  }
  [data-testid="stHeading"] h2,
  [data-testid="stHeading"] h3 {
    color: #e8edf5 !important;
  }
  .stMultiSelect [data-baseweb="select"] > div {
    background: #181e2d;
    border-color: #6C5CE7;
    box-shadow: 0 2px 10px rgba(0, 0, 0, .4);
    color: #e8edf5;
  }
  [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #cbd5e1;
  }
</style>
"""

# ── Scientific Light Theme CSS with Teal Long Bar ────────────────────────────
SCIENTIFIC_LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Pacifico&display=swap');
@import url('https://fonts.cdnfonts.com/css/eurostile-extended');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Global Layout & Canvas */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
}

.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 95% !important;
}

/* Long Teal Navigation Bar */
.topbar {
    position: fixed;
    top: 3.5rem;
    left: 0;
    right: 0;
    z-index: 10000;
    display: flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(90deg, #0F766E 0%, #0D9488 100%);
    border-bottom: 2px solid #115E59;
    box-shadow: 0 3px 12px rgba(13, 148, 136, 0.20);
    padding: 8px 18px;
    border-radius: 8px;
    margin-bottom: 1.4rem;
    font-family: 'Poppins', 'Segoe UI', system-ui, sans-serif;
}
.topbar .rnav-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: #CCFBF1;
    text-transform: uppercase;
    margin-right: 12px;
    padding-right: 14px;
    border-right: 1px solid rgba(255, 255, 255, 0.25);
    white-space: nowrap;
}
.topbar a {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    font-weight: 500;
    color: #FFFFFF;
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 6px;
    transition: background 0.15s ease, color 0.15s ease;
}
.topbar a:hover {
    background: rgba(255, 255, 255, 0.18);
    color: #FFFFFF;
}
.topbar .rnav-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #99F6E4;
}

/* Brand Typography */
h1.apihead {
    font-family: 'Eurostile Extended', 'Poppins', 'Segoe UI', system-ui, sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    color: #0F172A !important;
    margin-bottom: 0.1rem !important;
}
h1.apihead em {
    font-family: 'Pacifico', cursive !important;
    font-style: italic !important;
    color: #0D9488 !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #0F172A !important;
}

/* Metric Display Cards */
[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.65rem !important;
    font-weight: 700 !important;
}

/* Window & Navigation Tabs */
div[data-testid="stTabs"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 4px 6px !important;
    margin-bottom: 1.2rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px !important;
    background-color: transparent !important;
}
div[data-testid="stTabs"] [data-baseweb="tab"] {
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    padding: 8px 18px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #475569 !important;
    background-color: transparent !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #0D9488 !important;
    background-color: #F0FDFA !important;
}
div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background-color: #0D9488 !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(13, 148, 136, 0.3) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
div[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* Route Inspector Pop-up Card */
.route-inspector-card {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-top: 4px solid #0D9488;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 1rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}
.inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #F1F5F9;
    padding-bottom: 8px;
    margin-bottom: 12px;
}
.inspector-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0F172A;
}
.inspector-weight-tag {
    background-color: #F0FDFA;
    border: 1px solid #99F6E4;
    color: #0F766E;
    font-size: 0.74rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
}
.inspector-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 10px;
}
.inspector-stat {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 8px 12px;
}
.inspector-stat-label {
    font-size: 0.70rem;
    color: #64748B;
    text-transform: uppercase;
    font-weight: 600;
}
.inspector-stat-value {
    font-size: 1.15rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #0F172A;
}

/* Dataframe and Tables */
[data-testid="stDataFrame"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
}

/* Section Headings — standard font for every st.header/st.subheader */
[data-testid="stHeading"] h2,
[data-testid="stHeading"] h3 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    border-left: 3px solid #0D9488;
    padding-left: 10px;
    border-radius: 0 4px 4px 0;
    margin-bottom: 0.35rem !important;
}
[data-testid="stHeading"] h2 { font-size: 1.4rem !important; }
[data-testid="stHeading"] h3 { font-size: 1.1rem !important; }

/* Globe / Network feature heading — different font */
.feature-heading {
    font-family: 'Poppins', -apple-system, sans-serif;
    font-weight: 700;
    font-size: 1.45rem;
    color: #0F172A;
    border-bottom: 2px solid #0D9488;
    padding-bottom: 6px;
    margin-bottom: 0.4rem;
}
.feature-subheading {
    font-family: 'Poppins', -apple-system, sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
    color: #0F766E;
    margin-bottom: 0.3rem;
}

/* Expanders */
details[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    margin-bottom: 0.6rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}
details[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #1E293B !important;
}
details[data-testid="stExpander"][open] summary {
    color: #0D9488 !important;
    border-bottom: 1px solid #F1F5F9 !important;
}
</style>
"""
st.markdown(SCIENTIFIC_LIGHT_CSS, unsafe_allow_html=True)


# ── Theme ─────────────────────────────────────────────────────────────────────

def is_dark() -> bool:
    return st.session_state.get("dark_mode", False)


def fig_name() -> str:
    return "plotly_dark" if is_dark() else "plotly_white"


# ── Data Loading Functions ────────────────────────────────────────────────────
def _active_db() -> str:
    return st.session_state.get("db_path", str(DB_PATH))


@st.cache_data(ttl=60, show_spinner=False)
def load_cleaned(db_path: str | None = None) -> pd.DataFrame:
    conn = get_connection(db_path)
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "cleaned_flights" not in tables:
            return pd.DataFrame()
        return pd.read_sql("SELECT * FROM cleaned_flights", conn)
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_index(table: str, db_path: str | None = None) -> pd.DataFrame:
    conn = get_connection(db_path)
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if table not in tables:
            return pd.DataFrame()
        return pd.read_sql(f"SELECT * FROM {table}", conn)
    finally:
        conn.close()


def _empty_state() -> None:
    st.info(
        "No data available yet. Run the scraping pipeline: "
        "(`python -m src.scraper.run_scrape`, `python src/cleaner/clean.py`, `python -m src.indexer.run_index`), "
        "or click 'Load Synthetic Demo Data' in the sidebar to populate sample data."
    )


def seed_demo_data() -> None:
    """Generate 30 days of seeded synthetic flight data and build index tables."""
    from src.indexer.run_index import run_index
    from src.indexer.synthetic import make_synthetic_cleaned

    db = _active_db()
    init_db(db)
    conn = get_connection(db)
    try:
        df = make_synthetic_cleaned(days=30)
        conn.execute("DELETE FROM cleaned_flights")
        df.to_sql("cleaned_flights", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()
    run_index(db_path=db)


# ── Live Scrape Engine (background thread) ───────────────────────────────────
# One daemon thread drives the live_engine loop; the dashboard only reads the
# resulting tables, so the UI never blocks on Google Flights.
_LIVE = {"stop": None, "thread": None, "started_at": None, "error": None}


def _live_thread_target(db: str, interval: int, rotate: int) -> None:
    _LIVE["error"] = None
    try:
        live_engine(
            db_path=Path(db),
            interval=interval,
            no_scrape=False,
            rotate=rotate,
            stop_event=_LIVE["stop"],
        )
    except Exception as exc:  # noqa: BLE001 - surface, never crash the app
        _LIVE["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _LIVE["thread"] = None


def _live_is_running() -> bool:
    return _LIVE["thread"] is not None and _LIVE["thread"].is_alive()


def _start_live(interval: int, rotate: int) -> None:
    if _live_is_running():
        return
    if _LIVE["stop"] is None:
        _LIVE["stop"] = threading.Event()
    else:
        _LIVE["stop"].clear()
    _LIVE["started_at"] = datetime.now()
    _LIVE["thread"] = threading.Thread(
        target=_live_thread_target,
        args=(_active_db(), interval, rotate),
        daemon=True,
        name="api-live-engine",
    )
    _LIVE["thread"].start()


def _stop_live() -> None:
    if _LIVE["stop"] is not None:
        _LIVE["stop"].set()


def _load_live_tape(limit: int = 500) -> pd.DataFrame:
    conn = get_connection(_active_db())
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "live_index" not in tables:
            return pd.DataFrame()
        df = pd.read_sql(
            "SELECT * FROM live_index ORDER BY id DESC LIMIT ?",
            conn,
            params=(limit,),
        )
        return df.sort_values("id").reset_index(drop=True)
    finally:
        conn.close()


# ── Chart Theming Helpers (Scientific Light Palette) ──────────────────────────
def fig_base(fig: go.Figure, height: int = 360) -> None:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=15, r=15, t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            x=0,
            font=dict(size=11, family="Inter", color="#475569"),
        ),
        title_font=dict(size=13, family="Inter", color="#0F172A"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#475569"),
        xaxis=dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
        yaxis=dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
    )


def compute_curved_arc(
    lon1: float, lat1: float, lon2: float, lat2: float, n_points: int = 35, bend: float = 0.16
) -> tuple[list[float], list[float]]:
    """Calculates smooth curved parabolic flight arc points between two coordinates."""
    t = np.linspace(0, 1, n_points)
    lons = (1 - t) * lon1 + t * lon2
    lats = (1 - t) * lat1 + t * lat2
    dx = lon2 - lon1
    dy = lat2 - lat1
    dist = math.hypot(dx, dy)
    norm_x = -dy / (dist + 1e-7)
    norm_y = dx / (dist + 1e-7)
    curvature = np.sin(np.pi * t) * dist * bend
    return (lons + norm_x * curvature).tolist(), (lats + norm_y * curvature).tolist()


# ── Self-Explanatory Table Builders ───────────────────────────────────────────
def composite_table(table: str) -> pd.DataFrame:
    """Composite headline rows with self-explanatory column names (daily shows
    the Open/Close session bracket; weekly/monthly show the rolling-from-close)."""
    df = load_index(table, _active_db())
    if df.empty:
        return df
    uniq = df.drop_duplicates("index_date")
    has_oc = {"open_index", "close_index"}.issubset(df.columns)
    cols = ["index_date", "base_period"]
    if has_oc:
        cols += ["open_index", "close_index", "aggregate_index"]
    else:
        cols += ["aggregate_index"]
    out = uniq[cols].copy().sort_values("index_date", ascending=False)
    out["aggregate_index"] = pd.to_numeric(out["aggregate_index"], errors="coerce").round(2)
    if has_oc:
        out["open_index"] = pd.to_numeric(out["open_index"], errors="coerce").round(2)
        out["close_index"] = pd.to_numeric(out["close_index"], errors="coerce").round(2)
        out["day_movement"] = out["close_index"] - out["open_index"]
    out["inflation_change"] = out["aggregate_index"].apply(
        lambda v: f"+{v - 100.0:.2f}%" if v >= 100.0 else f"{v - 100.0:.2f}%"
    )
    rename_map = {
        "index_date": "Index Date",
        "aggregate_index": "APIx Level (Base = 100.00)",
        "inflation_change": "Inflation vs Base Period (%)",
        "base_period": "Reference Base Date",
    }
    if has_oc:
        rename_map["open_index"] = "APIx Open (session start)"
        rename_map["close_index"] = "APIx Close (session end)"
        rename_map["day_movement"] = "Day Movement (Close − Open)"
    return out.rename(columns=rename_map)


def route_price_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    """Per-route median fare summary with self-explanatory column names."""
    latest_date = cleaned_w.groupby("route")["scrape_date"].transform("max")
    latest = cleaned_w[cleaned_w["scrape_date"] == latest_date]
    out = (
        latest.groupby("route", as_index=False)
        .agg(
            flights=("total_fare", "size"),
            min_fare=("total_fare", "min"),
            median_fare=("total_fare", "median"),
            max_fare=("total_fare", "max"),
            scrape_date=("scrape_date", "max"),
        )
        .round({"min_fare": 2, "median_fare": 2, "max_fare": 2})
    )
    out["min_fare"] = out["min_fare"].apply(lambda v: f"INR {v:,.2f}")
    out["median_fare"] = out["median_fare"].apply(lambda v: f"INR {v:,.2f}")
    out["max_fare"] = out["max_fare"].apply(lambda v: f"INR {v:,.2f}")
    return out.rename(columns={
        "route": "Route Corridor",
        "flights": "Sampled Flights Count",
        "min_fare": "Minimum Observed Fare (INR)",
        "median_fare": "Typical Median Fare (INR)",
        "max_fare": "Maximum Observed Fare (INR)",
        "scrape_date": "Observation Date",
    })


def index_table(window: int, table: str) -> pd.DataFrame:
    """Per-route index progression table with self-explanatory column names."""
    df = load_index(table, _active_db())
    df = df[df["lead_window_days"] == window] if not df.empty else df
    if df.empty:
        return df
    out = df[["index_date", "route", "weight", "route_price", "route_index", "base_period"]].copy()
    out["flight_date"] = (
        pd.to_datetime(out["index_date"]) + pd.to_timedelta(int(window), unit="D")
    ).dt.strftime("%Y-%m-%d")
    out["weight"] = out["weight"].apply(lambda w: f"{w * 100:.1f}%")
    out["route_price"] = out["route_price"].apply(lambda v: f"INR {v:,.2f}")
    out["route_index"] = out["route_index"].round(2)
    out["pct_change"] = out["route_index"].apply(
        lambda v: f"+{v - 100.0:.2f}%" if v >= 100.0 else f"{v - 100.0:.2f}%"
    )
    ordered = out[[
        "index_date", "flight_date", "route", "weight",
        "route_price", "route_index", "pct_change", "base_period"
    ]].sort_values(["index_date", "route"], ascending=[False, True])
    return ordered.rename(columns={
        "index_date": "Scrape Date",
        "flight_date": "Flight Departure Date",
        "route": "Route Corridor",
        "weight": "DGCA Basket Weight (%)",
        "route_price": "Typical Median Fare (INR)",
        "route_index": "Route Index Level (Base = 100.00)",
        "pct_change": "Inflation vs Base Period (%)",
        "base_period": "Reference Base Date",
    })


def cleaned_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    """Sample of validated cleaned flights with self-explanatory column names."""
    cols = [
        "scrape_date", "route", "carrier", "flight_no",
        "depart_time", "arrive_time", "stops", "duration_mins",
        "total_fare", "quality_score", "is_outlier",
    ]
    cols = [c for c in cols if c in cleaned_w.columns]
    out = cleaned_w.sort_values("scrape_date", ascending=False)[cols].copy()
    if "total_fare" in out.columns:
        out["total_fare"] = out["total_fare"].apply(lambda v: f"INR {v:,.2f}")
    if "quality_score" in out.columns:
        out["quality_score"] = out["quality_score"].apply(lambda q: f"{q * 100:.0f}%")
    if "is_outlier" in out.columns:
        out["is_outlier"] = out["is_outlier"].apply(lambda o: "Flagged Outlier" if o == 1 else "Normal")
    return out.rename(columns={
        "scrape_date": "Scrape Date",
        "route": "Route Corridor",
        "carrier": "Operating Carrier",
        "flight_no": "Flight Number",
        "depart_time": "Scheduled Departure",
        "arrive_time": "Scheduled Arrival",
        "stops": "Stops Count",
        "duration_mins": "Duration (Minutes)",
        "total_fare": "Total Fare (INR)",
        "quality_score": "Data Quality Score",
        "is_outlier": "Outlier Status",
    })


# ── Chart Builders ────────────────────────────────────────────────────────────
def route_map(cleaned: pd.DataFrame) -> None:
    """Render an India map with all 12 flight routes and city markers."""
    fig = go.Figure()

    route_srcs = [
        ("DEL", "BOM"), ("BOM", "DEL"),
        ("DEL", "BLR"), ("BLR", "DEL"),
        ("DEL", "MAA"), ("MAA", "DEL"),
        ("BOM", "BLR"), ("BLR", "BOM"),
        ("BOM", "MAA"), ("MAA", "BOM"),
        ("BLR", "MAA"), ("MAA", "BLR"),
    ]

    cleaned_valid = (
        cleaned[cleaned["is_outlier"] != 1]
        if "is_outlier" in cleaned.columns
        else cleaned
    )
    flight_counts = (
        cleaned_valid.groupby(["origin", "dest"], as_index=False)
        .size()
        .rename(columns={"size": "flights"})
    )
    count_map = {
        (r["origin"], r["dest"]): r["flights"]
        for _, r in flight_counts.iterrows()
    } if not flight_counts.empty else {}
    max_flights = int(flight_counts["flights"].max()) if not flight_counts.empty else 1

    for idx, (src, dst) in enumerate(route_srcs):
        c = CITY_COORDS[src]
        d = CITY_COORDS[dst]
        flights = count_map.get((src, dst), 0)
        width = max(1.5, min(4.5, flights / max_flights * 4.5))
        color = ROUTE_COLORS[idx % len(ROUTE_COLORS)]

        fig.add_trace(go.Scattergeo(
            lon=[c["lon"], d["lon"]],
            lat=[c["lat"], d["lat"]],
            mode="lines",
            line=dict(width=width, color=color, dash="solid"),
            opacity=0.7,
            hoverinfo="text",
            text=f"{src} → {dst}  ({flights} flights)" if flights else f"{src} → {dst}",
            showlegend=False,
        ))

    city_lons = [CITY_COORDS[c]["lon"] for c in CITY_COORDS]
    city_lats = [CITY_COORDS[c]["lat"] for c in CITY_COORDS]
    city_labels = [f"✈ {c} — {CITY_COORDS[c]['name']}" for c in CITY_COORDS]

    fig.add_trace(go.Scattergeo(
        lon=city_lons,
        lat=city_lats,
        mode="markers+text",
        marker=dict(size=14, color=ACCENT, symbol="circle",
                    line=dict(width=2, color="#ffffff")),
        text=list(CITY_COORDS.keys()),
        textposition="top center",
        textfont=dict(size=12, color="#ffffff", family="Poppins, sans-serif"),
        hovertext=city_labels,
        hoverinfo="text",
        showlegend=False,
    ))

    geo_config = dict(
        scope="asia",
        projection_type="mercator",
        center=dict(lat=22, lon=79),
        lonaxis=dict(range=[66, 92]),
        lataxis=dict(range=[6, 37]),
        showland=True,
        landcolor="#f0f2f5" if not is_dark() else "#1a2035",
        showocean=True,
        oceancolor="#dce8f5" if not is_dark() else "#0f1520",
        showlakes=False,
        showcountries=True,
        countrycolor="#c7d2e0" if not is_dark() else "#263044",
        coastlinecolor="#a0aec0" if not is_dark() else "#3a4a63",
        coastlinewidth=1,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        geo=geo_config,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=10),
        height=520,
    )

    st.plotly_chart(fig, key="route_map", width="stretch", config={"displayModeBar": False})


def aggregate_trend(key: str = "main_composite_trend") -> None:
    """Composite headline: daily Open + Close lines, weekly/monthly rolling
    averages computed from the daily CLOSES (stock-index style)."""
    frames = []
    for tbl in INDEX_TABLES:
        df = load_index(tbl, _active_db())
        if df.empty:
            continue
        uniq = df.drop_duplicates("index_date").sort_values("index_date")
        if tbl == "daily_index" and {"open_index", "close_index"}.issubset(df.columns):
            op = uniq[["index_date", "open_index"]].copy()
            op = op.rename(columns={"open_index": "value"})
            op["value"] = pd.to_numeric(op["value"], errors="coerce")
            op["Series"] = "Daily Open (session start)"
            cl = uniq[["index_date", "close_index"]].copy()
            cl = cl.rename(columns={"close_index": "value"})
            cl["value"] = pd.to_numeric(cl["value"], errors="coerce")
            cl["Series"] = "Daily Close (session end)"
            frames.append(op)
            frames.append(cl)
        else:
            series = (
                uniq[["index_date", "aggregate_index"]]
                .rename(columns={"aggregate_index": "value"})
                .copy()
            )
            series["Series"] = INDEX_TABLE_LABELS[tbl]
            frames.append(series)
    if not frames:
        return
    trend = pd.concat(frames, ignore_index=True)
    fig = px.line(
        trend,
        x="index_date",
        y="value",
        color="Series",
        title="National APIx Headline (Base = 100.00) — Daily Open/Close & Rolling-from-Close",
        markers=True,
        color_discrete_sequence=["#94A3B8", "#0D9488", "#0284C7", "#D97706"],
    )
    fig.update_layout(xaxis_title="Calculation Date", yaxis_title="Index Level")
    fig_base(fig, height=360)
    st.plotly_chart(fig, key=key, use_container_width=True, config={"displayModeBar": False})


def carrier_pie(cleaned_w: pd.DataFrame, key: str) -> None:
    counts = (
        cleaned_w["carrier"].fillna("Unknown")
        .value_counts()
        .rename_axis("Carrier")
        .reset_index(name="Flight Count")
    )
    fig = px.pie(
        counts,
        names="Carrier",
        values="Flight Count",
        title="Flight Share by Carrier",
        hole=0.35,
        color_discrete_sequence=TEAL_PALETTE,
    )
    fig.update_traces(textinfo="percent+label", textposition="auto")
    fig_base(fig, height=320)
    st.plotly_chart(fig, key=key, use_container_width=True, config={"displayModeBar": False})


def route_fare_pie(cleaned_w: pd.DataFrame, key: str) -> None:
    fares = cleaned_w.groupby("route", as_index=False)["total_fare"].sum()
    fig = px.pie(
        fares,
        names="route",
        values="total_fare",
        title="Fare Value Share by Route",
        hole=0.35,
        color_discrete_sequence=TEAL_PALETTE,
    )
    fig.update_traces(textinfo="percent+label", textposition="auto")
    fig_base(fig, height=320)
    st.plotly_chart(fig, key=key, use_container_width=True, config={"displayModeBar": False})


def route_fare_bar(cleaned_w: pd.DataFrame, key: str) -> None:
    avg = cleaned_w.groupby("route", as_index=False)["total_fare"].mean().sort_values("total_fare", ascending=False)
    fig = px.bar(
        avg,
        x="route",
        y="total_fare",
        title="Average Fare by Route (INR)",
        text="total_fare",
        color="total_fare",
        color_continuous_scale=[[0, "#99F6E4"], [0.5, "#0D9488"], [1, "#0F766E"]],
    )
    fig.update_traces(texttemplate="INR %{text:.0f}", textposition="outside")
    fig.update_layout(xaxis_title="Route Corridor", yaxis_title="Average Fare (INR)", coloraxis_showscale=False)
    fig_base(fig, height=340)
    st.plotly_chart(fig, key=key, use_container_width=True, config={"displayModeBar": False})


def route_index_trend(window: int) -> None:
    daily = load_index("daily_index", _active_db())
    daily = daily[daily["lead_window_days"] == window] if not daily.empty else daily
    if daily.empty:
        return

    all_routes = sorted(daily["route"].dropna().unique())
    if not all_routes:
        return

    focus = st.multiselect(
        "Filter Routes",
        options=all_routes,
        default=all_routes[:3],
        key=f"route_filter_{window}",
        placeholder="Select routes to display",
    )
    if not focus:
        st.caption("Select at least one route to see the trend.")
        return

    pivot = daily[daily["route"].isin(focus)].pivot_table(
        index="index_date", columns="route", values="route_index"
    ).sort_index()
    fig = px.line(
        pivot,
        x=pivot.index,
        y=pivot.columns,
        title="Route-Level Index Trend (Base = 100.00)",
        color_discrete_sequence=TEAL_PALETTE,
        markers=True,
    )
    fig.update_layout(xaxis_title="Index Date", yaxis_title="Route Index")
    fig_base(fig, height=360)
    st.plotly_chart(fig, key=f"route_trend_{window}", use_container_width=True, config={"displayModeBar": False})


# ── Render One Window Tab ─────────────────────────────────────────────────────
def render_window_tab(cleaned_data: pd.DataFrame, window: int) -> None:
    st.header(WINDOW_LABELS[window])
    cleaned_w = cleaned_data[cleaned_data["lead_window_days"] == window]

    daily = load_index("daily_index", _active_db())
    daily_w = daily[daily["lead_window_days"] == window] if not daily.empty else daily

    # KPIs
    latest_d = None
    latest_a = None
    if not daily_w.empty:
        latest_r = daily_w.drop_duplicates("index_date").sort_values("index_date").iloc[-1]
        latest_d = latest_r["index_date"]
        latest_a = float(latest_r["aggregate_index"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest Composite APIx", f"{latest_a:.2f}" if latest_a is not None else "—")
    c2.metric("Latest Index Date", str(latest_d) if latest_d else "—")
    c3.metric("Cleaned Flights", f"{len(cleaned_w):,}")
    c4.metric("Routes in Basket", f"{cleaned_w['route'].nunique() if not cleaned_w.empty else 0}")

    # Pie charts
    st.subheader("Distribution")
    if cleaned_w.empty:
        _empty_state()
        return
    left, right = st.columns(2)
    with left:
        carrier_pie(cleaned_w, key=f"carrier_pie_{window}")
    with right:
        route_fare_pie(cleaned_w, key=f"route_fare_pie_{window}")

    # Graphs
    st.subheader("Trends")
    aggregate_trend(key=f"window_composite_trend_{window}")
    route_index_trend(window)

    st.subheader("Average Fare by Route")
    route_fare_bar(cleaned_w, key=f"route_fare_bar_{window}")

    # Tables with self-explanatory column names
    st.subheader("Tables")
    with st.expander("Cleaned Flights Sample", expanded=False):
        df_cl = cleaned_table(cleaned_w)
        if df_cl.empty:
            _empty_state()
        else:
            st.dataframe(df_cl.head(250), use_container_width=True, hide_index=True)

    with st.expander("Route Price Summary (Latest Observation Day)", expanded=False):
        df_rp = route_price_table(cleaned_w)
        if df_rp.empty:
            _empty_state()
        else:
            st.dataframe(df_rp, use_container_width=True, hide_index=True)

    for tbl in INDEX_TABLES:
        with st.expander(f"{INDEX_TABLE_LABELS[tbl]} — Rows for {WINDOW_LABELS[window]}", expanded=False):
            df_idx = index_table(window, tbl)
            if df_idx.empty:
                _empty_state()
            else:
                st.dataframe(df_idx.head(250), use_container_width=True, hide_index=True)


# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <h1 style="font-family:'Eurostile Extended', 'Poppins', sans-serif; font-weight:700; letter-spacing:1px; font-size:1.35rem; margin-bottom:0.1rem;">
            <em style="font-family:'Pacifico', cursive; font-style:italic; color:#0D9488;">APIx</em> Dashboard
        </h1>
        <div style="font-size: 0.78rem; color: #64748B; margin-bottom: 0.8rem;">
            Ministry of Statistics (MoSPI) · NSO · RBI
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Real-Time Airfare Price Index Platform for Domestic Aviation.")
    st.divider()

    st.subheader("Database")
    _db_label = st.radio(
        "Which Dataset to View",
        list(DATA_DB_OPTIONS.keys()),
        index=0,
        help="Production database contains scraped and indexed data; benchmark contains reference validation data.",
        key="sidebar_db_radio",
    )
    st.session_state["db_path"] = DATA_DB_OPTIONS[_db_label]
    st.caption(f"Path: `{DATA_DB_OPTIONS[_db_label]}`")
    init_db(st.session_state["db_path"])

    if st.button("Refresh Data", key="sidebar_refresh_btn", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Demo Data")
    st.caption("Populate the database with 30 days of seeded synthetic fares and built index tables.")
    if st.button("Load Synthetic Demo Data", key="sidebar_seed_btn", use_container_width=True):
        with st.spinner("Seeding demo data and building indices..."):
            seed_demo_data()
        st.cache_data.clear()
        st.success("Demo data ready.")
        st.rerun()

    st.divider()
    st.subheader("Live Scrape Engine")
    st.caption(
        "Runs the real Google Flights scrape loop in a background thread. Each "
        "cycle scrapes a rotating route subset, cleans, recomputes the index, and "
        "writes a tick — the tape below refreshes automatically."
    )
    if _live_is_running():
        since = _LIVE.get("started_at")
        st.success(f"RUNNING since {since:%H:%M:%S}" if since else "RUNNING")
    elif _LIVE.get("started_at"):
        st.info("engine stopped")
    if _LIVE.get("error"):
        st.error(_LIVE["error"])
    st.number_input(
        "Cycle interval (seconds)",
        min_value=30,
        max_value=3600,
        value=180,
        step=30,
        key="live_interval",
    )
    st.slider(
        "Routes scraped per cycle",
        min_value=1,
        max_value=12,
        value=2,
        key="live_rotate",
    )
    c_start, c_stop = st.columns(2)
    c_start.button(
        "Start Live",
        key="live_start_btn",
        use_container_width=True,
        disabled=_live_is_running(),
    )
    c_stop.button(
        "Stop",
        key="live_stop_btn",
        use_container_width=True,
        disabled=not _live_is_running(),
    )
    if st.session_state.get("live_start_btn"):
        _start_live(int(st.session_state.get("live_interval", 180)),
                    int(st.session_state.get("live_rotate", 2)))
        st.rerun()
    if st.session_state.get("live_stop_btn"):
        _stop_live()
        st.rerun()

    st.divider()
    st.subheader("Index Specification")
    st.markdown(
        """
        - **Formula:** 36-Cell Laspeyres Basket
        - **Cell Aggregation:** Median Fare (Robust)
        - **Macro Smoothing:** 10% Trimmed Mean
        - **Weights:** DGCA Traffic Share
        """
    )
    st.divider()
    st.caption("SIH-2026 Innovation Project · Institutional Release")


@st.fragment(run_every=10)
def live_tape_fragment() -> None:
    """Auto-refreshing live tick tape: engine status, session bracket, and the
    most recent scraped ticks straight from live_index."""
    db = _active_db()
    tape = _load_live_tape()
    today = datetime.now().date().isoformat()

    conn = get_connection(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_index)").fetchall()}
        has_oc = {"open_index", "close_index"}.issubset(cols)
        if has_oc:
            row = conn.execute(
                "SELECT open_index, close_index FROM daily_index"
                " WHERE index_date = ? ORDER BY id LIMIT 1",
                (today,),
            ).fetchone()
            open_today = float(row[0]) if row and row[0] is not None else None
            close_today = float(row[1]) if row and row[1] is not None else None
        else:
            row = conn.execute(
                "SELECT aggregate_index FROM daily_index"
                " WHERE index_date = ? ORDER BY id LIMIT 1",
                (today,),
            ).fetchone()
            open_today = None
            close_today = float(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()

    running = _live_is_running()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Engine", "LIVE scraping" if running else "Idle")
    c2.metric("Ticks Recorded", f"{len(tape)}")
    c3.metric("Session Open", f"{open_today:.2f}" if open_today is not None else "—")
    c4.metric("Latest Headline", f"{close_today:.2f}" if close_today is not None else "—")

    # ── Basket coverage & staleness (data freshness) ─────────────────────────
    # Coverage % = cells with a price today / full 36-cell basket. With
    # carry-forward, every ever-observed cell is present; coverage then measures
    # basket completeness. Max staleness = oldest price_obs_date among today's
    # cells; turns orange when it exceeds indexer's stale_cap_days (keep-but-flag).
    coverage = None
    max_stale = None
    present_cells = 0
    daily_today = pd.DataFrame()
    if today:
        daily_today = load_index("daily_index", db)
    if not daily_today.empty:
        today_rows = daily_today[daily_today["index_date"] == today]
        present = today_rows.drop_duplicates(["route", "lead_window_days"])
        present_cells = len(present)
        coverage = present_cells / TOTAL_BASKET_CELLS
        stale = cell_staleness_days(present.reset_index(drop=True))
        max_stale = int(stale.max()) if not stale.empty else 0
    cap = load_stale_cap()
    stale_over = cap is not None and max_stale is not None and max_stale > cap

    c5, c6 = st.columns(2)
    c5.metric(
        "Basket Coverage",
        f"{coverage:.0%}" if coverage is not None else "—",
        delta=f"{present_cells}/{TOTAL_BASKET_CELLS} cells",
    )
    c6.metric(
        "Max Staleness",
        f"{max_stale}d" if max_stale is not None else "—",
        delta=f"cap {cap}d" if cap is not None else "no cap",
        delta_color="inverse" if stale_over else "off",
    )
    if stale_over:
        st.warning(
            f"The freshest cell in today's basket is {max_stale} days old — above "
            f"the {cap}-day stale_cap_days. Prices are carried forward; consider "
            f"a scrape pass for the lagging routes."
        )

    if open_today is not None and close_today is not None:
        move = close_today - open_today
        st.caption(
            f"Intraday move {move:+.2f} pts since the day opened at 100.00 · "
            "tape refreshes every 10 s"
        )

    if tape.empty:
        if not running:
            st.info("No live ticks recorded yet — press **Start Live** in the sidebar, or run "
                    "`python -m src.live.run_live --interval 180` from a terminal.")
        else:
            st.info("Engine warming up — awaiting the first completed scrape cycle…")
        return

    t = tape.copy()
    t["t"] = pd.to_datetime(t["tick_timestamp"], errors="coerce")
    t["t"] = t["t"].fillna(pd.to_datetime(t["index_date"], errors="coerce"))
    t = t[t["t"].notna()]
    chart = px.line(
        t,
        x="t",
        y="aggregate_index",
        markers=True,
        title="Live Headline — Last Recorded Ticks",
        color_discrete_sequence=["#0D9488"],
    )
    if open_today is not None:
        chart.add_hline(y=open_today, line_dash="dot", line_color="#94A3B8",
                        annotation_text="day open", annotation_position="top left")
    chart.update_layout(xaxis_title="Tick Time", yaxis_title="APIx Level")
    fig_base(chart, height=300)
    st.plotly_chart(chart, key="live_tape_chart", use_container_width=True, config={"displayModeBar": False})

    last = t.tail(12).iloc[::-1][["t", "route", "lead_window_days", "route_price", "route_index", "delta"]].copy()
    last["t"] = last["t"].dt.strftime("%H:%M:%S")
    st.dataframe(
        last.rename(columns={
            "t": "Tick",
            "route": "Mover Route",
            "lead_window_days": "Window (T+)",
            "route_price": "Route Fare (INR)",
            "route_index": "Route Index",
            "delta": "Headline Δ",
        }).round({"route_price": 0, "route_index": 2, "delta": 2}),
        use_container_width=True,
        hide_index=True,
    )


# ── Long Teal Top Navigation Bar ──────────────────────────────────────────────
st.markdown('<div style="height:3.5rem"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <nav class="topbar">
        <span class="rnav-title">Navigation</span>
        <a href="#sec-headline"><span class="rnav-dot"></span>Headline</a>
        <a href="#sec-live"><span class="rnav-dot"></span>Live Tape</a>
        <a href="#sec-trend"><span class="rnav-dot"></span>Trend</a>
        <a href="#sec-composite-tables"><span class="rnav-dot"></span>Composite Tables</a>
        <a href="#sec-tabs"><span class="rnav-dot"></span>Globe, Windows & Search</a>
    </nav>
    """,
    unsafe_allow_html=True,
)

if is_dark():
    st.markdown(DARK_CSS, unsafe_allow_html=True)

st.markdown('<div style="height:2.9rem"></div>', unsafe_allow_html=True)

# ── Main Header (Preserved Typography) ────────────────────────────────────────
st.markdown(
    """
    <h1 class="apihead"><em style="font-family:'Pacifico', cursive; color:#0D9488;">APIx</em> — Airfare Price Index Dashboard</h1>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Automated high-frequency airfare inflation measurement across major Indian domestic corridors."
)

# ── Live Tick Tape Section (auto-refreshing, visible even on an empty DB) ────
st.markdown('<div id="sec-live"></div>', unsafe_allow_html=True)
st.subheader("Live Tick Tape")
live_tape_fragment()

cleaned = load_cleaned(_active_db())

if cleaned.empty:
    _empty_state()
else:
    # Composite headline metrics (stock-market day session: open → close)
    composite = load_index("daily_index", _active_db())
    latest_date = None
    latest_open = None
    latest_close = None
    day_move = None
    if not composite.empty:
        latest_composite = composite.drop_duplicates("index_date").sort_values("index_date").iloc[-1]
        latest_date = latest_composite["index_date"]
        latest_close = float(latest_composite["aggregate_index"])
        if "open_index" in composite.columns and pd.notna(latest_composite["open_index"]):
            latest_open = float(latest_composite["open_index"])
        else:
            latest_open = latest_close
        day_move = latest_close - latest_open

    st.markdown('<div id="sec-headline"></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's Open", f"{latest_open:.2f}" if latest_open is not None else "—")
    c2.metric("Latest Close", f"{latest_close:.2f}" if latest_close is not None else "—")
    c3.metric("Day Movement", f"{'+' if day_move and day_move >= 0 else ''}{day_move:.2f}" if day_move is not None else "—")
    c4.metric("Latest Index Date", str(latest_date) if latest_date else "—")

    # ── Composite Trend Section (Macro Headline) ──────────────────────────────
    st.subheader("Composite Trend")
    st.markdown('<div id="sec-trend"></div>', unsafe_allow_html=True)
    aggregate_trend()

    # ── Composite Index Tables Section ────────────────────────────────────────
    st.subheader("Composite Index Tables")
    st.markdown('<div id="sec-composite-tables"></div>', unsafe_allow_html=True)
    for table in INDEX_TABLES:
        with st.expander(f"{INDEX_TABLE_LABELS[table]}", expanded=False):
            df_comp = composite_table(table)
            if df_comp.empty:
                _empty_state()
            else:
                st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # ── Tabs Section: Globe (Default), Windows, and Dedicated Search ──────────
    st.markdown('<div id="sec-tabs"></div>', unsafe_allow_html=True)
    tab_globe, tab1, tab7, tab30, tab_search, tab_docs = st.tabs([
        "Air Corridor Globe & Network",
        WINDOW_LABELS[1],
        WINDOW_LABELS[7],
        WINDOW_LABELS[30],
        "Flight Search by City",
        "Docs / Methodology",
    ])
    st.caption(
        "Tabs = Air corridor network on interactive globe (default), advance purchase lead windows (T+1, T+7, T+30), city-pair search, and methodology documentation."
    )

    # ── TAB 1: 3D Globe Feature with Curved Flight Arcs (DEFAULT TAB) ─────────
    with tab_globe:
        st.markdown(
            '<h2 class="feature-heading">Air Corridor Network &amp; Globe</h2>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Airports Tracked", f"{len(CITY_COORDS)}")
        c2.metric("Corridors in Basket", "12")
        c3.metric("Quotes in Latest Scrape", f"{len(cleaned):,}" if not cleaned.empty else "0")
        st.caption(
            "Each curved line represents an active directional flight corridor (origin to destination). "
            "Inspect individual corridors below to view traffic weight, median fare, and route progression."
        )

        map_left, map_right = st.columns([1.3, 0.7])

        with map_right:
            st.markdown(
                '<div class="feature-subheading">Route Corridor Inspector</div>',
                unsafe_allow_html=True,
            )
            all_directional_routes = list(ROUTE_METADATA.keys())
            inspected_route = st.selectbox(
                "Select Corridor to Inspect",
                options=all_directional_routes,
                format_func=lambda r: f"{r} ({ROUTE_METADATA[r]['corridor']})",
                key="globe_inspected_route",
            )
            projection_choice = st.radio(
                "Projection Geometry",
                options=["3D Spherical Globe (Orthographic)", "Subcontinent Radar (Natural Earth)"],
                index=0,
                horizontal=True,
                key="globe_projection_choice",
            )

            r_meta = ROUTE_METADATA[inspected_route]
            r_src, r_dst = inspected_route.split("-")
            r_flights = cleaned[cleaned["route"] == inspected_route]

            r_daily = composite[composite["route"] == inspected_route]
            current_route_index = 100.0
            if not r_daily.empty:
                current_route_index = float(r_daily.sort_values("index_date").iloc[-1]["route_index"])

            med_price = r_flights["total_fare"].median() if not r_flights.empty else 0.0
            min_price = r_flights["total_fare"].min() if not r_flights.empty else 0.0
            idx_move = current_route_index - 100.0
            diff_str = f"+{idx_move:.2f}%" if idx_move >= 0 else f"{idx_move:.2f}%"

            # Scientific Pop-up Card
            st.markdown(
                f"""
                <div class="route-inspector-card">
                    <div class="inspector-header">
                        <div>
                            <div class="inspector-title">{inspected_route} Corridor</div>
                            <div style="font-size: 0.78rem; color: #64748B;">{r_meta['corridor']}</div>
                        </div>
                        <span class="inspector-weight-tag">{r_meta['weight']} Basket Weight</span>
                    </div>
                    <div class="inspector-grid">
                        <div class="inspector-stat">
                            <div class="inspector-stat-label">Route Index</div>
                            <div class="inspector-stat-value">{current_route_index:.2f}</div>
                            <div style="font-size: 0.72rem; color: #0D9488; font-weight: 600;">{diff_str} vs Base</div>
                        </div>
                        <div class="inspector-stat">
                            <div class="inspector-stat-label">Median Fare</div>
                            <div class="inspector-stat-value">INR {med_price:,.0f}</div>
                            <div style="font-size: 0.72rem; color: #64748B;">Min: INR {min_price:,.0f}</div>
                        </div>
                        <div class="inspector-stat">
                            <div class="inspector-stat-label">Block Flight Time</div>
                            <div class="inspector-stat-value">{r_meta['flight_time']}</div>
                            <div style="font-size: 0.72rem; color: #64748B;">Distance: {r_meta['distance']}</div>
                        </div>
                        <div class="inspector-stat">
                            <div class="inspector-stat-label">Sampled Quotes</div>
                            <div class="inspector-stat-value">{len(r_flights):,}</div>
                            <div style="font-size: 0.72rem; color: #0D9488;">Active in Basket</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Mini Route Trend inside inspector
            if not r_daily.empty:
                mini_trend_df = r_daily[r_daily["lead_window_days"] == 7].sort_values("index_date")
                if not mini_trend_df.empty:
                    fig_mini = px.line(
                        mini_trend_df,
                        x="index_date",
                        y="route_index",
                        title=f"{inspected_route} (7-Day Lead Trend)",
                        markers=True,
                        color_discrete_sequence=["#0D9488"],
                    )
                    fig_mini.update_layout(
                        height=180,
                        margin=dict(l=10, r=10, t=30, b=20),
                        yaxis_title=None,
                        xaxis_title=None,
                        paper_bgcolor="#FFFFFF",
                        plot_bgcolor="#F8FAFC",
                        font=dict(size=10, family="Inter", color="#475569"),
                    )
                    st.plotly_chart(fig_mini, key=f"globe_mini_{inspected_route}", use_container_width=True, config={"displayModeBar": False})

        with map_left:
            # Build 3D Curved Globe
            fig_globe = go.Figure()

            # Add curved flight lines for all corridors
            for idx, r_key in enumerate(all_directional_routes):
                src, dst = r_key.split("-")
                p1 = CITY_COORDS[src]
                p2 = CITY_COORDS[dst]

                is_active = (r_key == inspected_route)
                arc_bend = 0.18 if (src, dst) in [("DEL", "BLR"), ("BLR", "DEL"), ("DEL", "MAA")] else 0.14
                if src > dst:
                    arc_bend = -arc_bend

                arc_lons, arc_lats = compute_curved_arc(p1["lon"], p1["lat"], p2["lon"], p2["lat"], bend=arc_bend)

                arc_color = "#0D9488" if is_active else "#94A3B8"
                arc_width = 4.2 if is_active else 1.8
                arc_opacity = 1.0 if is_active else 0.45

                fig_globe.add_trace(go.Scattergeo(
                    lon=arc_lons,
                    lat=arc_lats,
                    mode="lines",
                    line=dict(width=arc_width, color=arc_color),
                    opacity=arc_opacity,
                    hoverinfo="text",
                    text=f"Air Corridor: {src} — {dst}<br>DGCA Weight: {ROUTE_METADATA[r_key]['weight']}<br>Duration: {ROUTE_METADATA[r_key]['flight_time']}",
                    name=f"{src}-{dst}",
                    showlegend=False,
                ))

            # Airport Nodes
            city_lons = [c["lon"] for c in CITY_COORDS.values()]
            city_lats = [c["lat"] for c in CITY_COORDS.values()]
            city_texts = [f"<b>{code}</b><br>{c['name']}<br>{c['airport']}" for code, c in CITY_COORDS.items()]

            fig_globe.add_trace(go.Scattergeo(
                lon=city_lons,
                lat=city_lats,
                mode="markers+text",
                marker=dict(
                    size=11,
                    color="#0D9488",
                    line=dict(width=2, color="#FFFFFF"),
                    symbol="circle",
                ),
                text=list(CITY_COORDS.keys()),
                textposition="top center",
                textfont=dict(size=11, color="#0F172A", family="Inter", weight="bold"),
                hovertext=city_texts,
                hoverinfo="text",
                name="Airports",
                showlegend=False,
            ))

            proj = "orthographic" if "3D" in projection_choice else "natural earth"
            fig_globe.update_geos(
                projection_type=proj,
                center=dict(lat=20.59, lon=78.96),
                projection_rotation=dict(lon=78.96, lat=20.59, roll=0) if proj == "orthographic" else None,
                showland=True,
                landcolor="#E2E8F0",
                showocean=True,
                oceancolor="#F1F5F9",
                showcountries=True,
                countrycolor="#CBD5E1",
                showcoastlines=True,
                coastlinecolor="#94A3B8",
                showframe=False,
                bgcolor="#FFFFFF",
            )
            fig_globe.update_layout(
                paper_bgcolor="#FFFFFF",
                margin=dict(l=0, r=0, t=10, b=10),
                height=540,
            )
            st.plotly_chart(fig_globe, key="globe_map_chart", use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "modeBarButtonsToAdd": ["zoomIn", "zoomOut"], "displaylogo": False})

    # ── TAB 2: T+1 (Last-Minute Booking) ───────────────────────────────────────
    with tab1:
        render_window_tab(cleaned, 1)

    # ── TAB 3: T+7 (1-Week Advance) ────────────────────────────────────────────
    with tab7:
        render_window_tab(cleaned, 7)

    # ── TAB 4: T+30 (1-Month Advance) ──────────────────────────────────────────
    with tab30:
        render_window_tab(cleaned, 30)

    # ── TAB 5: Dedicated Flight Search by City ─────────────────────────────────
    with tab_search:
        st.header("Search Flights by City")
        st.caption("Filter and inspect raw flight quotes across tracked Indian metro corridors.")

        city_order = list(CITY_COORDS.keys())
        city_names = {c: CITY_COORDS[c]["name"] for c in CITY_COORDS}

        s1, s2, s3 = st.columns([1.2, 1.2, 1])
        origin_code = s1.selectbox(
            "Origin City",
            options=city_order,
            format_func=lambda c: f"{c} — {city_names[c]}",
            key="city_search_origin",
        )
        dest_code = s2.selectbox(
            "Destination City",
            options=city_order,
            index=1,
            format_func=lambda c: f"{c} — {city_names[c]}",
            key="city_search_dest",
        )
        flat = s3.toggle(
            "Both Directions",
            value=True,
            help="Also show flights on the reverse corridor (destination to origin).",
            key="city_search_flat",
        )

        window_filter = st.selectbox(
            "Lead Window",
            options=["All Windows"] + [f"T+{w}" for w in WINDOWS],
            key="city_search_window",
        )

        if origin_code == dest_code:
            st.warning("Origin and destination are the same city. Pick two different cities.")
        else:
            region = cleaned[
                ((cleaned["origin"] == origin_code) & (cleaned["dest"] == dest_code))
                | (
                    flat
                    & (cleaned["origin"] == dest_code)
                    & (cleaned["dest"] == origin_code)
                )
            ].copy()

            if window_filter != "All Windows":
                lead = int(window_filter.replace("T+", ""))
                region = region[region["lead_window_days"] == lead]

            st.caption(
                f"{len(region):,} flight{'s' if len(region) != 1 else ''} on the "
                f"{origin_code} ⇄ {dest_code} corridor of {len(cleaned):,} total."
            )

            if region.empty:
                _empty_state()
            else:
                carrier_options = ["All Carriers"] + sorted(region["carrier"].dropna().unique().tolist())
                carrier_sel = st.selectbox(
                    "Filter Operating Carrier",
                    options=carrier_options,
                    index=0,
                    key="city_search_carrier",
                )
                show = region.sort_values("scrape_date", ascending=False).copy()
                if carrier_sel != "All Carriers":
                    show = show[show["carrier"] == carrier_sel]

                # Format search table columns self-explanatory
                show["Total Fare (INR)"] = show["total_fare"].apply(lambda v: f"INR {v:,.2f}")
                show["Duration"] = show["duration_mins"].apply(
                    lambda m: f"{int(m // 60)}h {int(m % 60):02d}m" if pd.notna(m) else "—"
                )
                show["Stops Category"] = show["stops"].apply(lambda s: "Non-stop" if s == 0 else f"{s} Stop")
                show["Quality Score"] = show["quality_score"].apply(lambda q: f"{q * 100:.0f}%")
                show["Horizon"] = show["lead_window_days"].apply(lambda w: f"T+{w} days")

                rename_search = {
                    "scrape_date": "Scrape Date",
                    "origin": "Origin",
                    "dest": "Destination",
                    "route": "Route Corridor",
                    "carrier": "Operating Carrier",
                    "flight_no": "Flight Number",
                    "depart_time": "Scheduled Departure",
                    "arrive_time": "Scheduled Arrival",
                }
                show = show.rename(columns=rename_search)
                search_cols = [
                    "Scrape Date", "Origin", "Destination", "Route Corridor", "Operating Carrier",
                    "Flight Number", "Scheduled Departure", "Scheduled Arrival", "Duration",
                    "Stops Category", "Total Fare (INR)", "Horizon", "Quality Score"
                ]
                search_cols = [c for c in search_cols if c in show.columns]
                st.dataframe(show[search_cols].head(350), use_container_width=True, hide_index=True)

    # ── TAB 6: Docs / Methodology ─────────────────────────────────────────────
    with tab_docs:
        st.markdown(
            '<h2 class="feature-heading">APIx — Methodology &amp; Formula Reference</h2>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Formulation basis for the Ministry of Statistics (MoSPI), NSO, and Reserve Bank of India (RBI). "
            "Documentation mirrors the live index builders in src/indexer/api_index.py, src/indexer/estimators.py "
            "and the stabilisation benchmark in src/indexer/metrics.py."
        )

        # ── 1. Index Formula ──────────────────────────────────────────────────
        st.subheader("Index Definition")
        st.markdown(
            """
            APIx is a **36-cell Laspeyres-type price basket** over leading Indian domestic corridors.
            Each **cell** is a route × booking-lead window combination (12 routes × 3 windows = 36 cells).

            **Step 1 — Cell price.** Every scraped fare on a given day collapses to a single robust cell price
            using the **median** (not the mean), so one ultra-cheap or ultra-costly fare cannot distort a cell:

            ```
            P(t, r, w) = median fare observed on date t  for route r at lead window w
            ```

            **Step 2 — Cell index.** Each cell is priced against its own base-period fare on the shared
            reference date (base = 100.00):

            ```
            index(t, r, w) = [ P(t, r, w) / P(0, r, w) ] × 100
            ```

            where `P(0, r, w)` is the base fare of cell `(r, w)`. Cells with no observation on the shared base
            date join the basket at 100 on their own first observation date.

            **Step 3 — Cell weight.** Each cell carries the product of its route and booking-horizon shares:

            ```
            w(r, w) = w_route(r) × w_window(w)
            ```

            Route weights are the DGCA traffic-share approximation (normalised to sum 1.0); window weights
            reflect booking mix — 0.20 last-minute, 0.30 one-week, 0.50 one-month.

            **Step 4 — Composite headline.** All cells present on date `t` are blended into a single national
            headline using a robust aggregation estimator `E`:

            ```
            APIx(t) = E( index(t, r, w) · w(r, w) )   for every cell present on t
            ```

            Missing dates are **carried forward** from the last known fare, so a coverage gap never drags the
            headline down artificially.

            **Step 5 — Day session (open / close).** Within a given day the headline is recomputed on every
            scrape cycle. The **open** is the first headline observed for the day (frozen once set); the **close**
            is the latest headline, updated until the market day ends. The daily headline shown below is the
            day's closing value.

            **Step 6 — Rolling (weekly / monthly).** Exactly like a stock index moving average, the weekly and
            monthly rollups are computed from the daily **closing** headlines, never from intraday values.
            """
        )

        # ── 2. Estimator Benchmarking ─────────────────────────────────────────
        st.subheader("Estimator Benchmarking — Stable Index Selection")
        st.markdown(
            """
            The headline estimator **has been benchmarked** so that the daily index is the most *stable*
            (calmest) yet still economically honest. Three aggregation estimators were compared over the same
            underlying price data:
            """
        )

        est_data = pd.DataFrame([
            {
                "Estimator": "Weighted Mean",
                "Formula": "Σ (v · w) / Σ w",
                "Role": "Classic Laspeyres aggregate; every cell contributes in proportion to its basket weight.",
                "Behaviour": "Sensitive to extreme cells; skips up/down when one big route spikes.",
            },
            {
                "Estimator": "Weighted Median",
                "Formula": "value at cumulative weight = 0.5",
                "Role": "Fully robust; the level at which half the basket weight lies on each side.",
                "Behaviour": "Most resistant to outliers, but can underreact to genuine broad-based moves.",
            },
            {
                "Estimator": "Trimmed Weighted Mean (10%)",
                "Formula": "weighted mean after shaving 10% weight off each tail",
                "Role": "Compromise; CPI-style. Removes cheap/costly extremes by WEIGHT MASS (not route count), re-balances and averages the survivors.",
                "Behaviour": "Keeps the tail reactions of the mean while muting single-route noise. **Selected default.**",
            },
        ])
        st.dataframe(
            est_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Estimator": st.column_config.TextColumn("Estimator", width="medium"),
                "Formula": st.column_config.TextColumn("Formula", width="medium"),
                "Role": st.column_config.TextColumn("Role", width="large"),
                "Behaviour": st.column_config.TextColumn("Benchmark Finding", width="large"),
            },
        )

        st.markdown(
            """
            **Stability scoring.** Each candidate was scored on how the CONSTANT-COMPOSITION daily aggregate
            moves day-to-day (lower = calmer):

            - `mean_abs_change` — average index-point move between consecutive days
            - `std_change` — volatility σ of those day-to-day moves
            - `max_abs_change` — worst single-day move
            - `extreme_move_days` — count of days moving more than ±5.0 index points

            The **10% trimmed weighted mean** was selected because, across the 36-cell basket, it consistently
            delivered the lowest volatility while preserving genuine trend signal — it avoids the weighted
            mean's single-route spike sensitivity without the weighted median's sluggishness. The comparison is
            reproducible: `compare_aggregation_estimators()` in `src/indexer/metrics.py` re-runs the index under
            all three estimators and prints the per-window stability tables.

            > **Current configuration** (config/indexer.yaml): `aggregation_estimator: "weighted_trimmed_mean"`,
            > `aggregation_trim_frac: 0.10`, `route_price_method: "median"`.
            """
        )