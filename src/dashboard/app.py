"""APIx Streamlit dashboard.

Renders pie charts, trend graphs, and tables from the SQLite database
(``data/apix.db``) for each advance-purchase window — T+1, T+7, T+30 — in its
own tab.

Data source:
    - cleaned_flights      (cleaned flight rows, one per flight)
    - daily_index          (per-date cell + composite headline index)
    - weekly_index         (7-day rolling of the daily composite)
    - monthly_index        (30-day rolling of the daily composite)

Run from the repo root:
    streamlit run src/dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.storage.database import DB_PATH, get_connection, init_db  # noqa: E402

WINDOWS = (1, 7, 30)
WINDOW_LABELS = {1: "T+1 (last-minute)", 7: "T+7 (one week out)", 30: "T+30 (one month out)"}

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

CITY_COORDS = {
    "DEL": {"lat": 28.57, "lon": 77.09, "name": "New Delhi"},
    "BOM": {"lat": 19.09, "lon": 72.87, "name": "Mumbai"},
    "BLR": {"lat": 13.20, "lon": 77.71, "name": "Bengaluru"},
    "MAA": {"lat": 12.99, "lon": 80.17, "name": "Chennai"},
}

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


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_cleaned() -> pd.DataFrame:
    conn = get_connection()
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
def load_index(table: str) -> pd.DataFrame:
    conn = get_connection()
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
        "No data yet. Run the pipeline first: scrape → clean → index "
        "(`python -m src.scraper.run_scrape`, `python src/cleaner/clean.py`, "
        "`python -m src.indexer.run_index`), or use **Load synthetic demo data** "
        "in the sidebar to populate a sample dataset."
    )


def seed_demo_data() -> None:
    """Write a synthetic cleaned dataset + build indices in data/apix.db."""
    from src.indexer.run_index import run_index
    from src.indexer.synthetic import make_synthetic_cleaned

    init_db()
    conn = get_connection()
    try:
        df = make_synthetic_cleaned(days=30)
        conn.execute("DELETE FROM cleaned_flights")
        df.to_sql("cleaned_flights", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()
    run_index(db_path=DB_PATH)


# ── Theme ─────────────────────────────────────────────────────────────────────

def is_dark() -> bool:
    return st.session_state.get("dark_mode", False)


def fig_name() -> str:
    return "plotly_dark" if is_dark() else "plotly_white"


# ── Shared chart builders ────────────────────────────────────────────────────

def fig_base(fig) -> None:
    fig.update_layout(
        template=fig_name(),
        height=360,
<<<<<<< Updated upstream
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
=======
        margin=dict(l=10, r=10, t=50, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, font=dict(size=11)),
        title_font_size=15,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
>>>>>>> Stashed changes
    )


def carrier_pie(cleaned_w: pd.DataFrame, key: str) -> None:
    counts = (
        cleaned_w["carrier"].fillna("UNKNOWN")
        .value_counts()
        .rename_axis("carrier")
        .reset_index(name="count")
    )
    fig = px.pie(
        counts,
        names="carrier",
        values="count",
        title="Flight share by carrier",
        hole=0.35,
    )
    fig.update_traces(textinfo="percent+label", textposition="auto")
    fig_base(fig)
    st.plotly_chart(fig, key=key, width="stretch", config={"displayModeBar": False})


def route_fare_pie(cleaned_w: pd.DataFrame, key: str) -> None:
    fares = cleaned_w.groupby("route", as_index=False)["total_fare"].sum()
    fig = px.pie(
        fares,
        names="route",
        values="total_fare",
        title="Fare value share by route",
        hole=0.35,
    )
    fig.update_traces(textinfo="percent+label", textposition="auto")
    fig_base(fig)
    st.plotly_chart(fig, key=key, width="stretch", config={"displayModeBar": False})


def route_fare_bar(cleaned_w: pd.DataFrame, key: str) -> None:
    avg = cleaned_w.groupby("route", as_index=False)["total_fare"].mean()
    avg = avg.sort_values("total_fare", ascending=False)
    fig = px.bar(
        avg,
        x="route",
        y="total_fare",
        title="Average fare by route (INR)",
        text="total_fare",
        color="route",
        color_discrete_sequence=ROUTE_COLORS,
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig_base(fig)
    st.plotly_chart(fig, key=key, width="stretch", config={"displayModeBar": False})


<<<<<<< Updated upstream
def aggregate_trend(window: int) -> None:
=======
def route_map(cleaned: pd.DataFrame) -> None:
    """Render an India map with all 12 flight routes and city markers."""
    import plotly.graph_objects as go

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


def aggregate_trend() -> None:
    """Composite headline is ONE number per date (window-independent).

    Deduplicate the per-route rows (aggregate_index is identical on a date),
    then plot the daily headline alongside its 7-day and 30-day rolling means.
    """
>>>>>>> Stashed changes
    frames = []
    for table in INDEX_TABLES:
        df = load_index(table)
        df = df[df["lead_window_days"] == window] if not df.empty else df
        if df.empty:
            continue
        series = (
            df.drop_duplicates("index_date")[["index_date", "aggregate_index"]]
            .copy()
            .sort_values("index_date")
        )
        series["series"] = INDEX_TABLE_LABELS[table]
        frames.append(series)
    if not frames:
        return
    trend = pd.concat(frames, ignore_index=True)
    fig = px.line(
        trend,
        x="index_date",
        y="aggregate_index",
        color="series",
        title="APIx composite headline over time",
        markers=True,
        color_discrete_sequence=ROUTE_COLORS,
    )
    fig_base(fig)
    st.plotly_chart(fig, key=f"agg_trend_{window}", width="stretch", config={"displayModeBar": False})


def route_index_trend(window: int) -> None:
    daily = load_index("daily_index")
    daily = daily[daily["lead_window_days"] == window] if not daily.empty else daily
    if daily.empty:
        return

    all_routes = sorted(daily["route"].dropna().unique())
    if not all_routes:
        return

    focus = st.multiselect(
        "Filter routes",
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
        title="Route-level index trend (base = 100)",
        color_discrete_sequence=ROUTE_COLORS,
        markers=True,
    )
    fig.update_xaxes(title_text="index_date")
    fig.update_yaxes(title_text="route_index")
<<<<<<< Updated upstream
    fig_base(fig)
    fig.update_layout(height=420)
=======
    fig.update_layout(
        template=fig_name(),
        legend=dict(orientation="v", yanchor="top", y=1, x=1.02, font=dict(size=10)),
        margin=dict(l=10, r=10, t=60, b=10),
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
>>>>>>> Stashed changes
    st.plotly_chart(fig, key=f"route_trend_{window}", width="stretch", config={"displayModeBar": False})


# ── Tables ────────────────────────────────────────────────────────────────────

def index_table(window: int, table: str) -> pd.DataFrame:
    df = load_index(table)
    df = df[df["lead_window_days"] == window] if not df.empty else df
    if df.empty:
        return df
<<<<<<< Updated upstream
    return df[["index_date", "route", "weight", "route_price", "route_index", "aggregate_index", "base_period"]]
=======
    out = df[["index_date", "route", "weight", "route_price", "route_index", "base_period"]].copy()
    out["flight_date"] = (
        pd.to_datetime(out["index_date"]) + pd.to_timedelta(int(window), unit="D")
    ).dt.strftime("%Y-%m-%d")
    out = out.rename(columns={"index_date": "scrape_date"})
    out["route_price"] = out["route_price"].apply(lambda v: f"₹{v:,.0f}")
    return out[["scrape_date", "flight_date", "route", "weight", "route_price", "route_index", "base_period"]]
>>>>>>> Stashed changes


def cleaned_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scrape_date", "route", "carrier", "flight_no",
        "depart_time", "arrive_time", "stops", "duration_mins",
        "total_fare", "quality_score", "is_outlier",
    ]
    cols = [c for c in cols if c in cleaned_w.columns]
<<<<<<< Updated upstream
    return cleaned_w[cols]


def route_price_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    agg = cleaned_w.groupby("route", as_index=False).agg(
        flights=("total_fare", "size"),
        min_fare=("total_fare", "min"),
        median_fare=("total_fare", "median"),
        avg_fare=("total_fare", "mean"),
        max_fare=("total_fare", "max"),
    )
    return agg.round(2)
=======
    out = cleaned_w.sort_values("scrape_date", ascending=False)[cols]
    if "total_fare" in out.columns:
        out["total_fare"] = out["total_fare"].apply(lambda v: f"₹{v:,.2f}")
    return out


def route_price_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    """Per-route median fare on each route's single most recent scrape date.

    Four plain columns only: route, flight count on that date, the cell
    median fare, and the date itself. The median fare equals the last
    ``route_price`` row for that route in the matching Route detail
    (Daily APIx) table.
    """
    latest_date = cleaned_w.groupby("route")["scrape_date"].transform("max")
    latest = cleaned_w[cleaned_w["scrape_date"] == latest_date]
    out = (
        latest.groupby("route", as_index=False)
        .agg(
            flights=("total_fare", "size"),
            **{"Median fare (INR)": ("total_fare", "median")},
            **{"Date": ("scrape_date", "max")},
        )
        .round({"Median fare (INR)": 2})
    )
    out["Median fare (INR)"] = out["Median fare (INR)"].apply(lambda v: f"₹{v:,.2f}")
    return out
>>>>>>> Stashed changes


# ── One window tab ────────────────────────────────────────────────────────────

def render_window_tab(cleaned: pd.DataFrame, window: int) -> None:
    st.header(WINDOW_LABELS[window])
    cleaned_w = cleaned[cleaned["lead_window_days"] == window]

    daily = load_index("daily_index")
    daily_w = daily[daily["lead_window_days"] == window] if not daily.empty else daily

    # KPIs
    latest_date = None
    latest_api = None
    if not daily_w.empty:
        latest = daily_w.drop_duplicates("index_date").sort_values("index_date").iloc[-1]
        latest_date = latest["index_date"]
        latest_api = float(latest["aggregate_index"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest composite APIx", f"{latest_api:.2f}" if latest_api is not None else "—")
    c2.metric("Latest index date", str(latest_date) if latest_date else "—")
    c3.metric("Cleaned flights", f"{len(cleaned_w):,}")
    c4.metric("Routes in data", f"{cleaned_w['route'].nunique() if not cleaned_w.empty else 0}")

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
    aggregate_trend(window)
    route_index_trend(window)

    st.subheader("Average fare by route")
    route_fare_bar(cleaned_w, key=f"route_fare_bar_{window}")

    # Tables
    st.subheader("Tables")
    with st.expander("Cleaned flights (sample)", expanded=False):
        df = cleaned_table(cleaned_w)
        if df.empty:
            _empty_state()
        else:
            st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Route price summary", expanded=False):
        df = route_price_table(cleaned_w)
        if df.empty:
            _empty_state()
        else:
            st.dataframe(df, width="stretch", hide_index=True)

    for table in INDEX_TABLES:
        with st.expander(f"{INDEX_TABLE_LABELS[table]} — rows for {WINDOW_LABELS[window]}", expanded=False):
            df = index_table(window, table)
            if df.empty:
                _empty_state()
            else:
                st.dataframe(df.sort_values(["index_date", "route"]), width="stretch", hide_index=True)


# ── App ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="APIx Dashboard", page_icon="✈", layout="wide")
init_db()

<<<<<<< Updated upstream
with st.sidebar:
    st.title("APIx Dashboard")
    st.caption("Real-time Airfare Price Index — MoSPI / NSO / RBI")
    st.divider()
    st.subheader("Data source")
    st.code(str(DB_PATH))
=======
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700&display=swap');
      [id] { scroll-margin-top: 7.5rem; }
      .topbar {
        position: fixed; top: 3.5rem; left: 0; right: 0; z-index: 1000;
        display: flex; align-items: center; gap: 4px;
        background: #f4f8fcee; border-bottom: 1px solid #c7d2e0;
        box-shadow: 0 3px 12px rgba(15, 40, 80, .08);
        padding: 6px 16px;
        font-family: 'Poppins', 'Segoe UI', system-ui, sans-serif;
      }
      [data-testid="stHeading"] {
        transition: color 0.15s ease;
        cursor: default;
      }
      [data-testid="stHeading"]:hover {
        color: #6C5CE7;
      }
      .topbar .rnav-title {
        font-size: 0.65rem; font-weight: 700; letter-spacing: 1.2px;
        color: #52606d; text-transform: uppercase;
        margin-right: 10px; padding-right: 12px;
        border-right: 1px solid #e3e8ef; white-space: nowrap;
      }
      .topbar a {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 0.78rem; font-weight: 500;
        color: #1f2933; text-decoration: none;
        padding: 7px 12px; border-radius: 8px; margin: 2px 0;
        transition: background 0.15s, color 0.15s;
      }
      .topbar a:hover { background: #ECE9FF; color: #6C5CE7; }
      .topbar .rnav-dot {
        display: inline-block; width: 6px; height: 6px;
        border-radius: 50%; background: #c3cfd9;
        transition: background 0.15s;
      }
      .topbar a:hover .rnav-dot { background: #6C5CE7; }
      @media (max-width: 1100px) { .topbar { display: none; } }
      .stMultiSelect [data-baseweb="select"] > div {
        border: 1.5px solid #6C5CE7;
        border-radius: 10px;
        background: linear-gradient(180deg, #ffffff 0%, #f7f5ff 100%);
        box-shadow: 0 2px 10px rgba(108, 92, 231, 0.12);
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
      }
      .stMultiSelect [data-baseweb="select"] > div:focus-within {
        border-color: #00CEC9;
        box-shadow: 0 0 0 3px rgba(0, 206, 201, 0.20);
      }
      .stMultiSelect [data-baseweb="tag"] {
        background: linear-gradient(90deg, #6C5CE7, #0984E3);
        color: #ffffff;
        border-radius: 999px;
        font-weight: 600;
      }
      .stMultiSelect [data-baseweb="tag"] span[aria-hidden="true"] {
        color: #ffffff;
      }

      /* ── Window tabs ─────────────────────────────────────────────────── */
      [data-testid="stTabs"] {
        background: rgba(255, 255, 255, 0.55);
        padding: 8px 10px;
        border-radius: 16px;
        box-shadow: inset 0 1px 3px rgba(15, 40, 80, .06);
      }
      [data-testid="stTabs"] [data-baseweb="tab-highlight"],
      [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none;
      }
      [data-testid="stTabs"] button[data-baseweb="tab"] {
        border: 1.5px solid #d4dcea;
        border-radius: 12px;
        padding: 10px 22px;
        font-weight: 600;
        letter-spacing: 0.3px;
        color: #475569;
        background: #ffffff;
        margin: 0 6px;
        box-shadow: 0 1px 4px rgba(15, 40, 80, .05);
        transition: all 0.2s ease;
      }
      [data-testid="stTabs"] button[data-baseweb="tab"]:hover {
        border-color: #6C5CE7;
        color: #6C5CE7;
        box-shadow: 0 2px 10px rgba(108, 92, 231, .15);
      }
      [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #6C5CE7, #0984E3);
        color: #ffffff !important;
        border-color: transparent;
        box-shadow: 0 4px 16px rgba(108, 92, 231, .35);
        position: relative;
      }
      [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]::after {
        content: "";
        position: absolute;
        bottom: -2px;
        left: 25%;
        width: 50%;
        height: 3px;
        border-radius: 2px;
        background: rgba(255, 255, 255, .7);
      }

      /* ── Expanders (table containers) ────────────────────────────────── */
      details[data-testid="stExpander"] {
        border: 1px solid #d0daea;
        border-radius: 14px;
        background: #ffffff;
        box-shadow: 0 2px 12px rgba(15, 40, 80, .05);
        margin-bottom: 0.6rem;
        overflow: hidden;
      }
      details[data-testid="stExpander"] summary {
        font-weight: 600;
        color: #1e3a5f;
        padding: 0.5rem 0.3rem;
      }
      details[data-testid="stExpander"][open] summary {
        color: #6C5CE7;
        border-bottom: 1px solid #e8ecf3;
      }

      /* ── Dataframe tables ─────────────────────────────────────────────── */
      [data-testid="stDataFrame"] {
        border: 1px solid #d5dce6;
        border-radius: 12px;
        box-shadow: 0 3px 14px rgba(15, 40, 80, .07);
        overflow: hidden;
        background: #ffffff;
      }

      /* ── Section subheadings ──────────────────────────────────────────── */
      [data-testid="stHeading"] h3,
      [data-testid="stHeading"] h2 {
        color: #1e3a5f;
        border-left: 4px solid #6C5CE7;
        padding-left: 10px;
        border-radius: 0 4px 4px 0;
        margin-bottom: 0.3rem;
      }
    </style>
    <nav class="topbar">
      <span class="rnav-title">Navigate</span>
      <a href="#sec-headline"><span class="rnav-dot"></span>Headline</a>
      <a href="#sec-search"><span class="rnav-dot"></span>Search</a>
      <a href="#sec-trend"><span class="rnav-dot"></span>Trend</a>
      <a href="#sec-composite-tables"><span class="rnav-dot"></span>Composite tables</a>
      <a href="#sec-tabs"><span class="rnav-dot"></span>Windows</a>
    </nav>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<h1 style="font-family:\'Eurostile Extended\', \'Poppins\', \'Segoe UI\', system-ui, sans-serif;'
        ' font-weight:700; letter-spacing:1px;">'
        '<em style="font-family:\'Pacifico\', \'Segoe Script\', cursive;'
        ' font-style:italic; color:#6C5CE7;">APIx</em> Dashboard</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Real-time Airfare Price Index — MoSPI / NSO / RBI")
    st.divider()
    dark_mode = st.toggle(
        "Dark theme",
        value=st.session_state.get("dark_mode", False),
        help="Switch the dashboard to a dark color scheme.",
    )
    st.session_state["dark_mode"] = dark_mode
    st.divider()
    st.subheader("Database")
    _db_label = st.radio(
        "Which dataset to view",
        list(DATA_DB_OPTIONS.keys()),
        index=0,
        help="Demo = synthetic 30-day series. Live = today's real scraped fares."
    )
    st.session_state["db_path"] = DATA_DB_OPTIONS[_db_label]
    st.caption(str(DATA_DB_OPTIONS[_db_label]))
>>>>>>> Stashed changes
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("Demo data")
    st.caption("Populate the DB with 30 days of seeded synthetic fares + built indices.")
    if st.button("Load synthetic demo data", use_container_width=True):
        with st.spinner("Seeding demo data and building indices..."):
            seed_demo_data()
        st.cache_data.clear()
        st.success("Demo data ready!")
        st.rerun()

<<<<<<< Updated upstream
st.title("APIx — Airfare Price Index Dashboard")
=======
if is_dark():
    st.markdown(DARK_CSS, unsafe_allow_html=True)

st.markdown('<div style="height:2.9rem"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;700&family=Pacifico&display=swap');
      @import url('https://fonts.cdnfonts.com/css/eurostile-extended');
      h1.apihead {
        font-family: 'Eurostile Extended', 'Poppins', 'Segoe UI', system-ui, sans-serif;
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 0;
      }
      h1.apihead em {
        font-family: 'Pacifico', 'Segoe Script', cursive;
        font-style: italic;
        color: #6C5CE7;
      }
    </style>
    <h1 class="apihead"><em>APIx</em> — Airfare Price Index Dashboard</h1>
    """,
    unsafe_allow_html=True,
)
>>>>>>> Stashed changes
st.caption(
    "Each tab isolates one advance-purchase window. Charts use cleaned flight "
    "data for distribution views and the index tables for trend views."
)

cleaned = load_cleaned()
if cleaned.empty:
    _empty_state()
    with st.expander("What each tab will show once data exists", expanded=True):
        st.markdown(
            "- **Pie charts** — flight share by carrier + fare-value share by route\n"
            "- **Graphs** — daily/weekly/monthly composite APIx trend, route-level index trend, avg fare by route\n"
            "- **Tables** — cleaned flight sample, route price summary, daily/weekly/monthly index rows"
        )
else:
<<<<<<< Updated upstream
    tab1, tab7, tab30 = st.tabs([WINDOW_LABELS[1], WINDOW_LABELS[7], WINDOW_LABELS[30]])
=======
    # Composite APIx is a SINGLE headline number per date (identical across
    # windows), so it is shown once above the tabs rather than per window.
    composite = load_index("daily_index", _active_db())
    latest_date = None
    latest_api = None
    if not composite.empty:
        latest_composite = composite.sort_values("index_date").iloc[-1]
        latest_date = latest_composite["index_date"]
        latest_api = float(latest_composite["aggregate_index"])

    st.markdown('<div id="sec-headline"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Latest composite APIx", f"{latest_api:.2f}" if latest_api is not None else "—")
    c2.metric("Latest index date", str(latest_date) if latest_date else "—")

# ── City-based flight search (only highlighted cities) ──────────────
    st.subheader("Search flights by city")
    st.markdown('<div id="sec-search"></div>', unsafe_allow_html=True)

    city_order = [c for c in CITY_COORDS]
    city_names = {c: CITY_COORDS[c]["name"] for c in CITY_COORDS}

    s1, s2, s3 = st.columns([1.2, 1.2, 1])
    origin_code = s1.selectbox(
        "Origin city",
        options=city_order,
        format_func=lambda c: f"{c} — {city_names[c]}",
        key="city_search_origin",
    )
    dest_code = s2.selectbox(
        "Destination city",
        options=city_order,
        index=1,
        format_func=lambda c: f"{c} — {city_names[c]}",
        key="city_search_dest",
    )
    flat = s3.toggle(
        "Both directions",
        value=True,
        help="Also show flights on the reverse route (dest → origin).",
    )

    window_filter = st.selectbox(
        "Lead window",
        options=["All"] + [f"T+{w}" for w in WINDOWS],
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
        ]

        if window_filter != "All":
            lead = int(window_filter.replace("T+", ""))
            region = region[region["lead_window_days"] == lead]

        st.caption(
            f"{len(region):,} flight{'s' if len(region) != 1 else ''} on the "
            f"{origin_code} ⇄ {dest_code} corridor of {len(cleaned):,} total."
        )

        if region.empty:
            _empty_state()
        else:
            carrier_sel = st.pills(
                "Carrier",
                options=["All"] + sorted(region["carrier"].dropna().unique().tolist()),
                default="All",
                key="city_search_carrier",
            )
            show = region.sort_values("scrape_date", ascending=False)
            if carrier_sel != "All":
                show = show[show["carrier"] == carrier_sel]
            cols = [
                "scrape_date", "origin", "dest", "route", "carrier", "flight_no",
                "depart_time", "arrive_time", "duration_mins", "stops",
                "total_fare", "lead_window_days", "quality_score",
            ]
            cols = [c for c in cols if c in show.columns]
            show = show[cols]
            if "total_fare" in show.columns:
                show = show.copy()
                show["total_fare"] = show["total_fare"].apply(lambda v: f"₹{v:,.2f}")
            st.dataframe(show.head(500), width="stretch", hide_index=True)

    st.subheader("Composite trend")
    st.markdown('<div id="sec-trend"></div>', unsafe_allow_html=True)
    aggregate_trend()

    st.subheader("Composite index tables")
    st.markdown('<div id="sec-composite-tables"></div>', unsafe_allow_html=True)
    for table in INDEX_TABLES:
        with st.expander(f"{INDEX_TABLE_LABELS[table]}", expanded=False):
            df = composite_table(table)
            if df.empty:
                _empty_state()
            else:
                st.dataframe(df, width="stretch", hide_index=True)

    st.markdown('<div id="sec-tabs"></div>', unsafe_allow_html=True)
    tab1, tab7, tab30, tab_map = st.tabs(
        [WINDOW_LABELS[1], WINDOW_LABELS[7], WINDOW_LABELS[30], "🗺️ Route Map"]
    )
    st.caption(
        "Tabs = how many days BEFORE DEPARTURE the ticket is bought "
        "(about the flight). Inside each tab, Daily/Weekly/Monthly = smoothing "
        "over PAST SCRAPE DATES (about when we collected the prices)."
    )
>>>>>>> Stashed changes
    with tab1:
        render_window_tab(cleaned, 1)
    with tab7:
        render_window_tab(cleaned, 7)
    with tab30:
        render_window_tab(cleaned, 30)
    with tab_map:
        st.header("Flight routes across India")
        c1, c2, c3 = st.columns(3)
        c1.metric("Cities served", f"{len(CITY_COORDS)}")
        c2.metric("Routes tracked", "12")
        c3.metric(
            "Flights in latest scrape",
            f"{len(cleaned):,}" if not cleaned.empty else "0",
        )
        st.caption(
            "Each line shows a directional route (origin → destination). Line "
            "thickness reflects the number of flights scraped; hover a city "
            "marker or route for details. Landing on the map is fixed to India."
        )
        route_map(cleaned)