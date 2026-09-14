"""APIx Streamlit dashboard.

Renders the composite headline trend plus pie charts, trend graphs, and tables
from the SQLite database (``data/apix.db``). The composite APIx is a single
number per date (window-independent) and is shown once above the tabs; each
advance-purchase window — T+1, T+7, T+30 — then gets its own tab for
window-specific views.

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

DATA_DB_OPTIONS = {
    "Demo (synthetic 30-day)": DB_PATH,
    "Live scrape (real fares today)": _REPO_ROOT / "data" / "e2e_real.db",
}

WINDOWS = (1, 7, 30)
WINDOW_LABELS = {1: "T+1 (last-minute)", 7: "T+7 (one week out)", 30: "T+30 (one month out)"}

INDEX_TABLES = ("daily_index", "weekly_index", "monthly_index")
INDEX_TABLE_LABELS = {
    "daily_index": "Daily APIx (no smoothing)",
    "weekly_index": "Weekly APIx (rolling average over past scrape dates)",
    "monthly_index": "Monthly APIx (rolling average over past scrape dates)",
}

ROUTE_COLORS = px.colors.qualitative.Safe

INDEX_HELP = """
**How the APIx index is calculated**

1. **Basket** — 12 routes × 3 advance-purchase windows (T+1, T+7, T+30)
   = **36 cells** (route × how many days before departure you buy).

2. **Cell price** — for each (route, window, *day*) we take the **median**
   fare of all scrapped flights (outlier rows are excluded). A single
   ultra-cheap fare doesn't drag the cell down.

3. **Route index** — `cell_price ÷ base_period_cell_price × 100`.
   Every route starts at **100** on the base day (first day with data),
   then moves up/down as fares change.

4. **Daily APIx (composite headline)** — a **weighted trimmed mean** of that
   day's route indexes, where each cell's weight = route traffic share ×
   booking-lead share. Weights re-balance over the cells that exist that day.
   The composite is a **single number per date** (same for every window).

5. **Weekly / Monthly APIx** — the **average of the last 7 (or 30) daily
   values**, a smooth rolling line of the same index.

**Reading the tabs** — T+1/T+7/T+30 = how far in advance the flight is
booked. The *Daily / Weekly / Monthly* tables in each tab are the *same*
index smoothed over the last 7/30 **scrape days**, always using that tab's
lead window only.
"""


def _active_db() -> Path:
    return st.session_state.get("db_path", DB_PATH)


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def load_cleaned(db_path: Path) -> pd.DataFrame:
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
def load_index(table: str, db_path: Path) -> pd.DataFrame:
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
        for table in INDEX_TABLES:
            conn.execute(f"DELETE FROM {table}")
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
        margin=dict(l=10, r=10, t=50, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, font=dict(size=11)),
        title_font_size=15,
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
    fig.update_layout(showlegend=False)
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
    fig.update_layout(showlegend=False)
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
    fig.update_layout(showlegend=False)
    fig_base(fig)
    st.plotly_chart(fig, key=key, width="stretch", config={"displayModeBar": False})


def aggregate_trend() -> None:
    """Composite headline is ONE number per date (window-independent).

    Deduplicate the per-route rows (aggregate_index is identical on a date),
    then plot the daily headline alongside its 7-day and 30-day rolling means.
    """
    frames = []
    for table in INDEX_TABLES:
        df = load_index(table, _active_db())
        if df.empty:
            continue
        series = (
            df.groupby("index_date", as_index=False)["aggregate_index"]
            .first()
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
    st.plotly_chart(fig, key="agg_trend", width="stretch", config={"displayModeBar": False})


def route_index_trend(window: int) -> None:
    daily = load_index("daily_index", _active_db())
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
    fig.update_layout(
        legend=dict(orientation="v", yanchor="top", y=1, x=1.02, font=dict(size=10)),
        margin=dict(l=10, r=10, t=60, b=10),
        height=420,
    )
    st.plotly_chart(fig, key=f"route_trend_{window}", width="stretch", config={"displayModeBar": False})


# ── Tables ────────────────────────────────────────────────────────────────────

def composite_table(table: str) -> pd.DataFrame:
    """One row per index_date — the aggregate composite (window-independent)."""
    df = load_index(table, _active_db())
    if df.empty:
        return df
    return (
        df.groupby("index_date", as_index=False)["aggregate_index"]
        .first()
        .sort_values("index_date", ascending=False)
    )


def index_table(window: int, table: str) -> pd.DataFrame:
    df = load_index(table, _active_db())
    df = df[df["lead_window_days"] == window] if not df.empty else df
    if df.empty:
        return df
    out = df[["index_date", "route", "weight", "route_price", "route_index", "base_period"]].copy()
    out["flight_date"] = (
        pd.to_datetime(out["index_date"]) + pd.to_timedelta(int(window), unit="D")
    ).dt.strftime("%Y-%m-%d")
    out = out.rename(columns={"index_date": "scrape_date"})
    return out[["scrape_date", "flight_date", "route", "weight", "route_price", "route_index", "base_period"]]


def cleaned_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scrape_date", "route", "carrier", "flight_no",
        "depart_time", "arrive_time", "stops", "duration_mins",
        "total_fare", "quality_score", "is_outlier",
    ]
    cols = [c for c in cols if c in cleaned_w.columns]
    return cleaned_w.sort_values("scrape_date", ascending=False)[cols]


def route_price_table(cleaned_w: pd.DataFrame) -> pd.DataFrame:
    """Per-route median fare on each route's single most recent scrape date.

    Four plain columns only: route, flight count on that date, the cell
    median fare, and the date itself. The median fare equals the last
    ``route_price`` row for that route in the matching Route detail
    (Daily APIx) table.
    """
    latest_date = cleaned_w.groupby("route")["scrape_date"].transform("max")
    latest = cleaned_w[cleaned_w["scrape_date"] == latest_date]
    return (
        latest.groupby("route", as_index=False)
        .agg(
            flights=("total_fare", "size"),
            **{"Median fare (INR)": ("total_fare", "median")},
            **{"Date": ("scrape_date", "max")},
        )
        .round({"Median fare (INR)": 2})
    )


# ── One window tab ────────────────────────────────────────────────────────────

def render_window_tab(cleaned: pd.DataFrame, window: int) -> None:
    st.header(WINDOW_LABELS[window])
    cleaned_w = cleaned[cleaned["lead_window_days"] == window]

    # Drop outlier-flagged rows for anything that aggregates fares, so the
    # dashboard's numbers match the indexer (which excludes is_outlier == 1).
    cleaned_valid = (
        cleaned_w[cleaned_w["is_outlier"] != 1]
        if "is_outlier" in cleaned_w.columns
        else cleaned_w
    )

    c1, c2 = st.columns(2)
    c1.metric("Cleaned flights", f"{len(cleaned_w):,}")
    c2.metric("Routes in data", f"{cleaned_w['route'].nunique() if not cleaned_w.empty else 0}")

    # Pie charts
    st.subheader("Distribution")
    if cleaned_valid.empty:
        _empty_state()
        return
    left, right = st.columns(2)
    with left:
        carrier_pie(cleaned_valid, key=f"carrier_pie_{window}")
    with right:
        route_fare_pie(cleaned_valid, key=f"route_fare_pie_{window}")

    # Graphs
    st.subheader("Trends")
    route_index_trend(window)

    st.subheader("Average fare by route")
    route_fare_bar(cleaned_valid, key=f"route_fare_bar_{window}")

    # Tables
    st.subheader("Tables")
    with st.expander("Cleaned flights (sample)", expanded=False):
        df = cleaned_table(cleaned_w)
        if df.empty:
            _empty_state()
        else:
            st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Latest median fare by route", expanded=False):
        st.caption(
            "Median fare = median of scraped fares on Date; matches that "
            "route's last row in Route detail (Daily APIx)."
        )
        df = route_price_table(cleaned_valid)
        if df.empty:
            _empty_state()
        else:
            st.dataframe(df, width="stretch", hide_index=True)

    for table in INDEX_TABLES:
        with st.expander(
            f"Route detail ({INDEX_TABLE_LABELS[table]} — {WINDOW_LABELS[window]})",
            expanded=False,
        ):
            df = index_table(window, table)
            if df.empty:
                _empty_state()
            else:
                caption = {
                    "daily_index": (
                        f"Daily APIx = the day's aggregate index, built only from "
                        f"{WINDOW_LABELS[window]} flights. `route_price` is each "
                        f"route's median fare for the `flight_date`."
                    ),
                    "weekly_index": (
                        f"Each `scrape_date` = average of the LAST 7 daily APIx "
                        f"values, computed only from {WINDOW_LABELS[window]} "
                        f"flights (rolling average)."
                    ),
                    "monthly_index": (
                        f"Each `scrape_date` = average of the LAST 30 daily APIx "
                        f"values, computed only from {WINDOW_LABELS[window]} "
                        f"flights (rolling average)."
                    ),
                }[table]
                st.caption(caption)
                st.dataframe(
                    df.sort_values(["scrape_date", "route"], ascending=[False, True]),
                    width="stretch",
                    hide_index=True,
                )


# ── App ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="APIx Dashboard", page_icon="✈", layout="wide")
init_db()

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700&display=swap');
      [id] { scroll-margin-top: 7.5rem; }
      .topbar {
        position: fixed; top: 3.5rem; left: 0; right: 0; z-index: 1000;
        display: flex; align-items: center; gap: 4px;
        background: #ffffffee; border-bottom: 1px solid #d3dce6;
        box-shadow: 0 3px 12px rgba(0,0,0,.06);
        padding: 6px 16px;
        font-family: 'Poppins', 'Segoe UI', system-ui, sans-serif;
      }
      [data-testid="stHeading"] {
        transition: color 0.15s ease;
        cursor: default;
      }
      [data-testid="stHeading"]:hover {
        color: #0b7285;
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
      .topbar a:hover { background: #e0f4f5; color: #0b7285; }
      .topbar .rnav-dot {
        display: inline-block; width: 6px; height: 6px;
        border-radius: 50%; background: #c3cfd9;
        transition: background 0.15s;
      }
      .topbar a:hover .rnav-dot { background: #0b7285; }
      @media (max-width: 1100px) { .topbar { display: none; } }
    </style>
    <nav class="topbar">
      <span class="rnav-title">Navigate</span>
      <a href="#sec-headline"><span class="rnav-dot"></span>Headline</a>
      <a href="#sec-trend"><span class="rnav-dot"></span>Trend</a>
      <a href="#sec-composite-tables"><span class="rnav-dot"></span>Composite tables</a>
      <a href="#sec-tabs"><span class="rnav-dot"></span>Windows</a>
    </nav>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<h1 style="font-family:\'Poppins\', \'Segoe UI\', system-ui, sans-serif;'
        ' font-weight:700; letter-spacing:0.4px;">'
        '<em style="font-family:\'Pacifico\', \'Segoe Script\', cursive;'
        ' font-style:italic; color:#0b7285;">APIx</em> Dashboard</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Real-time Airfare Price Index — MoSPI / NSO / RBI")
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
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("Demo data")
    st.caption("Populate the demo DB with 30 days of seeded synthetic fares + built indices.")
    if st.button("Load synthetic demo data", use_container_width=True):
        with st.spinner("Seeding demo data and building indices..."):
            seed_demo_data()
        st.cache_data.clear()
        st.success("Demo data ready!")
        st.rerun()

st.markdown('<div style="height:2.9rem"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;700&family=Pacifico&display=swap');
      h1.apihead {
        font-family: 'Poppins', 'Segoe UI', system-ui, sans-serif;
        font-weight: 700;
        letter-spacing: 0.4px;
        margin-bottom: 0;
      }
      h1.apihead em {
        font-family: 'Pacifico', 'Segoe Script', cursive;
        font-style: italic;
        color: #0b7285;
      }
    </style>
    <h1 class="apihead"><em>APIx</em> — Airfare Price Index Dashboard</h1>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Each tab isolates one advance-purchase window. Charts use cleaned flight "
    "data for distribution views and the index tables for trend views."
)

with st.popover("ℹ️ How is APIx calculated?"):
    st.markdown(INDEX_HELP)

init_db(_active_db())
cleaned = load_cleaned(_active_db())
if cleaned.empty:
    _empty_state()
    with st.expander("What each tab will show once data exists", expanded=True):
        st.markdown(
            "- **Pie charts** — flight share by carrier + fare-value share by route\n"
            "- **Graphs** — daily/weekly/monthly composite APIx trend, route-level index trend, avg fare by route\n"
            "- **Tables** — cleaned flight sample, route price summary, daily/weekly/monthly index rows"
        )
else:
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
    tab1, tab7, tab30 = st.tabs([WINDOW_LABELS[1], WINDOW_LABELS[7], WINDOW_LABELS[30]])
    st.caption(
        "Tabs = how many days BEFORE DEPARTURE the ticket is bought "
        "(about the flight). Inside each tab, Daily/Weekly/Monthly = smoothing "
        "over PAST SCRAPE DATES (about when we collected the prices)."
    )
    with tab1:
        render_window_tab(cleaned, 1)
    with tab7:
        render_window_tab(cleaned, 7)
    with tab30:
        render_window_tab(cleaned, 30)