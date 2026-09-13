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

ROUTE_COLORS = px.colors.qualitative.Safe


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


# ── Shared chart builders ────────────────────────────────────────────────────

def fig_base(fig) -> None:
    fig.update_layout(
        template="plotly_white",
        height=360,
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
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


def aggregate_trend(window: int) -> None:
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
    pivot = daily.pivot_table(
        index="index_date", columns="route", values="route_index"
    ).sort_index()
    fig = px.line(
        pivot,
        x=pivot.index,
        y=pivot.columns,
        title="Route-level index trend (base = 100)",
        color_discrete_sequence=ROUTE_COLORS,
    )
    fig.update_xaxes(title_text="index_date")
    fig.update_yaxes(title_text="route_index")
    fig_base(fig)
    fig.update_layout(height=420)
    st.plotly_chart(fig, key=f"route_trend_{window}", width="stretch", config={"displayModeBar": False})


# ── Tables ────────────────────────────────────────────────────────────────────

def index_table(window: int, table: str) -> pd.DataFrame:
    df = load_index(table)
    df = df[df["lead_window_days"] == window] if not df.empty else df
    if df.empty:
        return df
    return df[["index_date", "route", "weight", "route_price", "route_index", "aggregate_index", "base_period"]]


def cleaned_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scrape_date", "route", "carrier", "flight_no",
        "depart_time", "arrive_time", "stops", "duration_mins",
        "total_fare", "quality_score", "is_outlier",
    ]
    cols = [c for c in cols if c in cleaned_w.columns]
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

with st.sidebar:
    st.title("APIx Dashboard")
    st.caption("Real-time Airfare Price Index — MoSPI / NSO / RBI")
    st.divider()
    st.subheader("Data source")
    st.code(str(DB_PATH))
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

st.title("APIx — Airfare Price Index Dashboard")
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
    tab1, tab7, tab30 = st.tabs([WINDOW_LABELS[1], WINDOW_LABELS[7], WINDOW_LABELS[30]])
    with tab1:
        render_window_tab(cleaned, 1)
    with tab7:
        render_window_tab(cleaned, 7)
    with tab30:
        render_window_tab(cleaned, 30)