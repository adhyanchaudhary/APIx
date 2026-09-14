"""Rebuild SIH deck slides 2-4 using ONLY native PowerPoint shapes/charts (no image files).

All diagrams + charts are drawn programmatically so nothing depends on external
image files — visuals are guaranteed to render in PowerPoint/WPS.
Data for charts is computed from the actual repo code (synthetic generator + indexer).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

ROOT = Path(r"C:\Users\LENOVO\Desktop\SIH-2026")
SRC = r"C:\Users\LENOVO\Downloads\_Real_ Time_ Airfare.pptx"
OUT = r"C:\Users\LENOVO\Downloads\Real_Time_Airfare_SIH_pitch_deck_DeepTrek.pptx"

# ---------- compute real chart data from the repo code ----------
import sys as _sys
_sys.path.insert(0, str(ROOT))
from src.indexer.synthetic import make_synthetic_cleaned
from src.indexer.api_index import (
    route_price_per_day, compute_daily_index, compute_rolling_index,
    load_route_weights, load_window_weights, load_estimator_config,
)
from src.indexer.estimators import aggregate

_df = make_synthetic_cleaned(days=30)
_cfg = load_estimator_config()
_prices = route_price_per_day(_df, method=_cfg["route_price_method"])
_daily = compute_daily_index(_prices, load_route_weights(), load_window_weights(),
                             estimator=_cfg["aggregation_estimator"],
                             trim_frac=_cfg["aggregation_trim_frac"])
_weekly = compute_rolling_index(_daily, 7, estimator=_cfg["rolling_estimator"],
                                trim_frac=_cfg["rolling_trim_frac"])
_monthly = compute_rolling_index(_daily, 30, estimator=_cfg["rolling_estimator"],
                                 trim_frac=_cfg["rolling_trim_frac"])

COMP_DAILY = _daily.groupby("index_date")["aggregate_index"].first()
COMP_WEEKLY = _weekly.groupby("index_date")["aggregate_index"].first()
DATES = list(COMP_DAILY.index)

_elasticity = _df.groupby("lead_window_days")["total_fare"].median().sort_index()
WINDOW_LABELS = {1: "T+1", 7: "T+7", 30: "T+30"}

_carriers = _df["carrier"].fillna("UNKNOWN").value_counts()
CARRIER_NAMES = list(_carriers.index[:5])
CARRIER_VALS = [int(v) for v in _carriers.values[:5]]

ROUTES_ALL = list(load_route_weights().keys())
ROUTE_W = load_route_weights()
_TREND_ROUTES = ["DEL-BOM", "BOM-BLR", "BLR-MAA"]

def _route_series(route):
    sub = _daily[_daily["route"] == route]
    s = sub.groupby("index_date")["route_index"].mean()
    return [round(float(v), 1) for v in s.reindex(DATES, method="ffill").fillna(100.0)]


# ---------- palette ----------
BLUE_D = RGBColor(0x0D, 0x47, 0xA1)
BLUE_M = RGBColor(0x15, 0x65, 0xC0)
BLUE_L = RGBColor(0xE3, 0xF2, 0xFD)
SKY = RGBColor(0x42, 0xA5, 0xF5)
GREEN_D = RGBColor(0x1B, 0x5E, 0x20)
GREEN_M = RGBColor(0x2E, 0x7D, 0x32)
GREEN_L = RGBColor(0xE8, 0xF5, 0xE9)
ORANGE_D = RGBColor(0xE6, 0x51, 0x00)
ORANGE_M = RGBColor(0xEF, 0x6C, 0x00)
ORANGE_L = RGBColor(0xFF, 0xF3, 0xE0)
PURPLE_D = RGBColor(0x6A, 0x1B, 0x9A)
PURPLE_L = RGBColor(0xF3, 0xE5, 0xF5)
TEAL_M = RGBColor(0x00, 0x69, 0x5C)
TEAL_L = RGBColor(0xE0, 0xF2, 0xF1)
GREY = RGBColor(0x5F, 0x63, 0x68)
INK = RGBColor(0x1A, 0x1A, 0x2E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Segoe UI"


# ---------- helpers ----------
def _txt(slide, x, y, w, h, runslist, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, sp_after=2):
    box = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    first = True
    for runs, level in runslist:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.level = level
        p.space_after = Pt(sp_after)
        for text, size, bold, color in runs:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.name = FONT
            r.font.color.rgb = color
    return box


def _line(slide, x, y, w, h, text, size=13, color=INK, bold=True, align=PP_ALIGN.LEFT):
    return _txt(slide, x, y, w, h, [([(text, size, bold, color)], 0)], align=align)


def _c(color):
    if isinstance(color, str):
        return RGBColor.from_string(color.lstrip("#"))
    return color


def _shape(slide, kind, x, y, w, h, fill, line=None, lw=1.0):
    fill, line = _c(fill), _c(line) if line else None
    sp = slide.shapes.add_shape(kind, Emu(x), Emu(y), Emu(w), Emu(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    return sp


def _round(slide, x, y, w, h, fill, line=None, lw=1.0, rad=0.12):
    fill, line = _c(fill), _c(line) if line else None
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(x), Emu(y), Emu(w), Emu(h))
    try:
        sp.adjustments[0] = rad
    except Exception:
        pass
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    return sp


def _pill(slide, x, y, w, h, text, fill, tcolor=WHITE, size=16):
    r = _round(slide, x, y, w, h, fill, rad=0.5)
    tf = r.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Emu(20000)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run = p.add_run(); run.text = text
    run.font.size = Pt(size); run.font.bold = True; run.font.name = FONT; run.font.color.rgb = tcolor
    return r


def _card(slide, x, y, w, h, accent, title, lines, tsize=14, dsize=10.5):
    r = _round(slide, x, y, w, h, WHITE, accent, lw=1.1, rad=0.06)
    _round(slide, x + 40000, y + 60000, 90000, h - 120000, accent, rad=0.5)
    _line(slide, x + 320000, y + 70000, w - 400000, 200000, title, size=tsize, color=accent)
    pl = []
    for ln in lines:
        pl.append(([(ln, dsize, False, INK)], 0))
    _txt(slide, x + 320000, y + 310000, w - 380000, h - 380000, pl)
    return r


def _chip(slide, x, y, w, h, num, label, accent, size=11.5):
    r = _round(slide, x, y, w, h, WHITE, accent, lw=1.0, rad=0.18)
    d = 110000
    cx = x + 95000
    cy = y + (h - d) // 2
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(cx), Emu(cy), Emu(d), Emu(d))
    c.fill.solid(); c.fill.fore_color.rgb = accent
    c.line.fill.background(); c.shadow.inherit = False
    tfc = c.text_frame; tfc.vertical_anchor = MSO_ANCHOR.MIDDLE
    pc = tfc.paragraphs[0]; pc.alignment = PP_ALIGN.CENTER
    rc = pc.add_run(); rc.text = num
    rc.font.size = Pt(11); rc.font.bold = True; rc.font.name = FONT; rc.font.color.rgb = WHITE
    tx = cx + d + 20000
    _txt(slide, tx, y, x + w - tx - 15000, h, [([(label, size, True, INK)], 0)],
         anchor=MSO_ANCHOR.MIDDLE)
    return r


def _flowbox(slide, x, y, w, h, fill, line, title, sub, tsize=11.5, ssize=8.5):
    _round(slide, x, y, w, h, fill, line, lw=1.1, rad=0.10)
    lines = [([(title, tsize, True, line)], 0)]
    if sub:
        lines.append(([(sub, ssize, False, INK)], 0))
    _txt(slide, x + 40000, y + 30000, w - 80000, h - 60000, lines,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def _arrow(slide, kind, x, y, w, h, fill):
    sp = slide.shapes.add_shape(kind, Emu(x), Emu(y), Emu(w), Emu(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    sp.line.fill.background(); sp.shadow.inherit = False
    return sp


def _chart(slide, chart_type, x, y, cx, cy, cats, series, title=None, legend=False, font=8.5):
    cd = CategoryChartData()
    cd.categories = cats
    for name, values in series:
        cd.add_series(name, tuple(values))
    gf = slide.shapes.add_chart(chart_type, Emu(x), Emu(y), Emu(cx), Emu(cy), cd)
    chart = gf.chart
    if title:
        chart.has_title = True
        chart.chart_title.text_frame.text = title
        try:
            chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(font + 1)
            chart.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
            chart.chart_title.text_frame.paragraphs[0].runs[0].font.name = FONT
            chart.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = INK
        except Exception:
            pass
    else:
        chart.has_title = False
    chart.has_legend = legend
    try:
        chart.font.size = Pt(font)
        chart.font.name = FONT
    except Exception:
        pass
    return chart


# ---------- load deck ----------
prs = Presentation(SRC)
slides = list(prs.slides)


def delete_except(slide, keep):
    for shape in list(slide.shapes):
        if shape.name not in keep:
            shape._element.getparent().remove(shape._element)


# ═════════════════════════════════════════════════════════════════════
# SLIDE 2  — Problem (left)  |  Solution + native flowcharts (right)
# ═════════════════════════════════════════════════════════════════════
s2 = slides[1]
delete_except(s2, {"object 2", "object 5", "object 6", "object 7", "object 8", "object 11"})

_shape(s2, MSO_SHAPE.RECTANGLE, 6096000, 1450000, 26000, 4650000, RGBColor(0xB0, 0xBE, 0xC5))

_pill(s2, 250000, 1500000, 5700000, 330000, "THE PROBLEM", BLUE_D, size=17)
_line(s2, 250000, 1920000, 5600000, 260000,
      "Airlines change fares dynamically; India has no official airfare price index.",
      size=12.5, bold=False)

_challs = [
    ("1", "Fragmented Sources", "Airfares scattered across airlines, OTAs & GDS feeds — no single trustworthy source.", BLUE_M),
    ("2", "Dynamic Pricing", "Fares swing 200–400% within a single day; manual sampling can't track rapid movement.", ORANGE_D),
    ("3", "Non-Standardized Data", "Fare components, taxes & formats differ across every platform.", GREEN_M),
    ("4", "Limited High-Frequency Measurement", "Current CPI model can't capture route & lead-time price behaviour.", PURPLE_D),
]
for (num, title, desc, accent), (x, y) in zip(_challs, [(250000, 2350000), (3090000, 2350000), (250000, 3450000), (3090000, 3450000)]):
    _card(s2, x, y, 2690000, 990000, accent, title, [desc], tsize=15.5, dsize=11.5)

_line(s2, 250000, 4530000, 5600000, 300000,
      "Unlike CPI/WPI, no published index measures how the cost of domestic air travel moves.",
      size=12, color=GREY, bold=False)

_pill(s2, 6250000, 1500000, 5700000, 330000, "OUR SOLUTION — AIRINDEX", GREEN_D, size=17)
_line(s2, 6250000, 1920000, 5700000, 260000,
      "A transparent, reproducible price index over a fixed basket of metro routes — for MoSPI / NSO / RBI.",
      size=12.5, bold=False)

# flowchart 1 (native)
_pill(s2, 6250000, 2270000, 2800000, 200000, "1 · AUTOMATED COLLECTION", BLUE_M, size=10.5)
_flowbox(s2, 6250000, 2550000, 1500000, 520000, BLUE_L, BLUE_M, "Google Flights", "12 routes × 3 windows")
_arrow(s2, MSO_SHAPE.RIGHT_ARROW, 7830000, 2650000, 190000, 300000, BLUE_M)
_flowbox(s2, 8070000, 2550000, 1500000, 520000, BLUE_L, BLUE_M, "Playwright scraper", "Python · headless Chrome · 60 req/h")
_arrow(s2, MSO_SHAPE.RIGHT_ARROW, 9650000, 2650000, 190000, 300000, BLUE_M)
_flowbox(s2, 9880000, 2550000, 1500000, 520000, BLUE_L, BLUE_M, "raw_flights", "SQLite staging table")

# flowchart 2 (native)
_pill(s2, 6250000, 3350000, 2800000, 200000, "2 · CLEANING & VALIDATION", GREEN_M, size=10.5)
_flowbox(s2, 6250000, 3630000, 1500000, 520000, GREEN_L, GREEN_M, "raw_flights", "source rows")
_arrow(s2, MSO_SHAPE.RIGHT_ARROW, 7830000, 3730000, 190000, 300000, GREEN_M)
_flowbox(s2, 8070000, 3630000, 1500000, 520000, GREEN_L, GREEN_M, "Pandas cleaner", "dedup · null-fare · IQR(1.5×) outliers · quality score")
_arrow(s2, MSO_SHAPE.RIGHT_ARROW, 9650000, 3730000, 190000, 300000, GREEN_M)
_flowbox(s2, 9880000, 3630000, 1500000, 520000, GREEN_L, GREEN_M, "cleaned_flights", "validated fares")

_line(s2, 6250000, 4270000, 5700000, 250000,
      "Both stages mirror config/ — route basket, windows (T+1/T+7/T+30) and rate limits live in YAML.",
      size=10.5, color=GREY, bold=False)

_steps = [
    ("01", "Automated Collection", BLUE_M),
    ("02", "Data Cleaning & Validation", GREEN_M),
    ("03", "Fare Normalization", ORANGE_D),
    ("04", "Statistical Index Engine", PURPLE_D),
    ("05", "Real-Time Airfare Price Index", TEAL_M),
    ("06", "Dashboard + API", BLUE_D),
]
for i, (num, label, accent) in enumerate(_steps):
    _chip(s2, [6250000, 8160000, 10070000][i % 3], [4720000, 5320000][i // 3],
          1810000, 470000, num, label, accent, size=11)

# ═════════════════════════════════════════════════════════════════════
# SLIDE 3  — Tech stack + APIx formula (left) | native HLD (right)
# ═════════════════════════════════════════════════════════════════════
s3 = slides[2]
delete_except(s3, {"object 2", "object 5", "object 6", "object 7", "object 8", "object 36"})

_shape(s3, MSO_SHAPE.RECTANGLE, 6096000, 1450000, 26000, 4650000, RGBColor(0xB0, 0xBE, 0xC5))

_pill(s3, 250000, 1500000, 5700000, 330000, "TECH STACK — 4 LAYERS", BLUE_D, size=17)
_stack = [
    ("DATA COLLECTION", "Playwright (Python) · headless Chrome", "rate-limited 60 req/h · retries · APScheduler daily jobs", BLUE_M),
    ("DATA PROCESSING", "Pandas · NumPy · Python", "dedup · null-fare handling · IQR (1.5x) outlier flag · quality score", GREEN_M),
    ("FRONTEND", "Streamlit + Plotly", "composite trend · route analytics · heatmap · raw explorer", ORANGE_D),
    ("DATABASE", "SQLite (data/apix.db)", "raw_flights · cleaned_flights · daily / weekly / monthly index", PURPLE_D),
]
for (title, sub, desc, accent), (x, y) in zip(_stack, [(250000, 1960000), (3090000, 1960000), (250000, 2860000), (3090000, 2860000)]):
    _card(s3, x, y, 2690000, 790000, accent, title, [sub, desc], tsize=14, dsize=10)

# APIx formula card (native text)
fcard = _round(s3, 250000, 3790000, 5650000, 1380000, GREEN_L, GREEN_M, lw=1.2, rad=0.045)
_line(s3, 350000, 3880000, 5300000, 200000, "HOW APIx IS CALCULATED", size=13, color=GREEN_D)
_line(s3, 350000, 4130000, 5300000, 300000,
      "APIx(t) = \u2211 [ P_cell(t) / P_cell(0) \u00d7 w_route \u00d7 w_window ] \u00d7 100",
      size=14, color=BLUE_D)
_txt(s3, 350000, 4470000, 5300000, 660000, [
    ([("\u25AA  36-cell basket = 12 routes × 3 booking windows (T+1 / T+7 / T+30)", 9.5, False, INK)], 0),
    ([("\u25AA  P_cell(t) = median fare per (route, window, day); outliers dropped, gaps carried forward", 9.5, False, INK)], 0),
    ([("\u25AA  w = DGCA route share × booking-lead share (20 : 30 : 50); base day = 100", 9.5, False, INK)], 0),
    ([("\u25AA  headline = weighted trimmed mean  \u2192  daily / weekly / monthly", 9.5, False, INK)], 0),
])

_line(s3, 250000, 5270000, 5600000, 250000,
      "Weights are config-driven: swap official DGCA traffic shares in config/indexer.yaml — no code change.",
      size=10.5, color=GREY, bold=False)

# HLD (native)
_pill(s3, 6250000, 1500000, 5700000, 330000, "ARCHITECTURE — HIGH-LEVEL DESIGN (HLD)", GREEN_D, size=15)
_line(s3, 6250000, 1910000, 5700000, 200000,
      "SQLite storage with cache layer · neural net on the consumer layer", size=11.5, color=INK, bold=False)

# sources band
_flowbox(s3, 6250000, 2250000, 5700000, 450000, BLUE_L, BLUE_M,
         "DATA SOURCES  —  Google Flights · Airline websites · OTAs", "", tsize=12)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 8990000, 2720000, 220000, 190000, BLUE_M)

# pipeline row
_flowbox(s3, 6250000, 2960000, 1550000, 600000, "#FFFFFF", BLUE_M, "SCRAPER", "Playwright · headless Chrome\n60 req/h · APScheduler")
_arrow(s3, MSO_SHAPE.RIGHT_ARROW, 7920000, 3110000, 140000, 300000, BLUE_M)
_flowbox(s3, 8120000, 2960000, 1550000, 600000, "#FFFFFF", GREEN_M, "DATA CLEANING", "Pandas · dedup · nulls\nIQR (1.5×) outliers")
_arrow(s3, MSO_SHAPE.RIGHT_ARROW, 9790000, 3110000, 140000, 300000, GREEN_M)
_flowbox(s3, 9990000, 2960000, 1730000, 600000, "#FFFFFF", ORANGE_M, "INDEX ENGINE — APIx", "36 cells · weighted\ntrimmed mean · base=100")
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 7025000, 3620000, 140000, 190000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 8895000, 3620000, 140000, 190000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 10860000, 3620000, 140000, 190000, GREY)

# storage + cache row
_sqlite = _round(s3, 6250000, 3860000, 2750000, 560000, TEAL_L, TEAL_M, lw=1.2, rad=0.06)
_line(s3, 6450000, 3930000, 2550000, 200000, "SQLite · data/apix.db", size=11.5, color=TEAL_M)
_line(s3, 6450000, 4170000, 2550000, 200000, "raw / cleaned / daily / weekly / monthly", size=8.5, color=INK, bold=False)
_cache = _round(s3, 9250000, 3860000, 2700000, 560000, GREEN_L, GREEN_D, lw=1.2, rad=0.06)
_line(s3, 9450000, 3930000, 2500000, 200000, "CACHE LAYER", size=11.5, color=GREEN_D)
_line(s3, 9450000, 4170000, 2500000, 200000, "TTL 60 s · materialised views\ncuts repeat reads · <1 s dashboard load", size=8.5, color=INK, bold=False)
_arrow(s3, MSO_SHAPE.RIGHT_ARROW, 9020000, 4090000, 210000, 150000, GREEN_D)   # sqlite -> cache
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 7025000, 4480000, 140000, 170000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 8895000, 4480000, 140000, 170000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 10860000, 4480000, 140000, 170000, GREY)

# consumer row (NN on consumer layer)
_flowbox(s3, 6250000, 4700000, 1550000, 580000, BLUE_L, BLUE_M, "STREAMLIT DASHBOARD", "Plotly charts\ncomposite + route trends")
_flowbox(s3, 8120000, 4700000, 1550000, 580000, ORANGE_L, ORANGE_M, "REST API", "FastAPI · CSV/JSON\nexport for NSO / RBI")
_flowbox(s3, 9990000, 4700000, 1730000, 580000, PURPLE_L, PURPLE_D, "NN FARE-DIRECTION MODEL", "TensorFlow · 20 features\n2×[64,32] ReLU+Dropout\nDOWN / STABLE / UP")
_badge = _round(s3, 11150000, 4620000, 800000, 160000, PURPLE_D, rad=0.5)
_txt(s3, 11150000, 4620000, 800000, 160000,
     [([("NN ON CONSUMER LAYER", 7.5, True, WHITE)], 0)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# final consumers band
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 7025000, 5340000, 140000, 150000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 8895000, 5340000, 140000, 150000, GREY)
_arrow(s3, MSO_SHAPE.DOWN_ARROW, 10860000, 5340000, 140000, 150000, GREY)
_final = _round(s3, 6250000, 5540000, 5630000, 300000, BLUE_D, rad=0.12)
_txt(s3, 6200000, 5540000, 5730000, 300000,
     [([("CONSUMERS — MoSPI / NSO inflation statistics · RBI monetary policy · policy research", 10.5, True, WHITE)], 0)],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# ═════════════════════════════════════════════════════════════════════
# SLIDE 4  — Phases (native chips) · Future scope (native previews + charts)
# ═════════════════════════════════════════════════════════════════════
s4 = slides[3]

# phase 1 -> 4 metro cities; remove blank original icon pictures
for shape in list(s4.shapes):
    if shape.name == "Text 3":
        shape.text_frame.text = "4 Metro Cities · 12 Routes\n-> Automated data pipeline -> Fare normalization -> Airfare Index -> Interactive dashboard"
    if shape.name in ("Image 0", "Image 1", "Image 2", "Picture 38", "Text 9"):
        shape._element.getparent().remove(shape._element)

# native phase chips where the blank icons were
for pn, (x, y) in {1: (486282, 1055829), 2: (4199963, 1055829), 3: (8001801, 1055829)}.items():
    _round(s4, x + 200000, y + 120000, 260000, 260000, [BLUE_M, GREEN_M, ORANGE_M][pn - 1], rad=0.3)
_txt(s4, x + 200000, y + 120000, 260000, 260000,
     [([(f"P{pn}", 14, True, WHITE)], 0)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# future scope chips
_futs = [
    ("AI/ML", "Anomaly detection + fare-direction forecasting", PURPLE_D),
    ("DATA", "More OTA sources · 50+ routes · DGCA back-test", ORANGE_D),
    ("SERVE", "FastAPI for NSO / RBI · auto-refresh scheduler", TEAL_M),
]
for (tag, desc, accent), x in zip(_futs, [577032, 4500000, 8420000]):
    ch = _round(s4, x, 3970000, 3300000, 440000, WHITE, accent, lw=1.0, rad=0.16)
    _txt(s4, x + 70000, 4040000, 3150000, 440000,
         [([(tag, 10, True, accent)], 0), ([("  " + desc, 11, False, INK)], 0)],
         anchor=MSO_ANCHOR.MIDDLE)

# ---- preview cards (native, no images) ----
def _metric_cell(slide, x, y, w, h, accent_bg, label, value):
    _round(slide, x, y, w, h, accent_bg, None, rad=0.12)
    _line(slide, x + 80000, y + 20000, w - 160000, 60000, label, size=8, color=INK, bold=False)
    _line(slide, x + 80000, y + 85000, w - 160000, 60000, value, size=13, color=BLUE_D)

CARD_Y = 4620000
CARD_H = 1510000

# LEFT CARD — frontend preview
lx, lw_ = 577032, 5620000
_round(s4, lx, CARD_Y, lw_, CARD_H, WHITE, BLUE_M, lw=1.2, rad=0.05)
_round(s4, lx + 60000, CARD_Y + 60000, lw_ - 120000, 130000, BLUE_D, rad=0.1)
_txt(s4, lx + 60000, CARD_Y + 60000, lw_ - 120000, 130000,
     [([("FRONTEND PREVIEW — STREAMLIT DASHBOARD  (streamlit run src/dashboard/app.py)", 11, True, WHITE)], 0)],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
_metric_cell(s4, lx + 100000, CARD_Y + 230000, 2600000, 150000, GREEN_L, "Latest composite APIx",
             f"{round(float(COMP_DAILY.iloc[-1]), 2)}")
_metric_cell(s4, lx + 2920000, CARD_Y + 230000, 2580000, 150000, BLUE_L, "Latest index date",
             str(DATES[-1]))
_chart(s4, XL_CHART_TYPE.LINE_MARKERS, lx + 120000, CARD_Y + 420000, 2720000, 1000000,
       [str(d)[5:] for d in DATES],
       [("Daily", [round(float(v), 2) for v in COMP_DAILY.values]),
        ("Weekly", [round(float(v), 2) for v in COMP_WEEKLY.values])],
       title="Composite APIx trend (base = 100)", legend=False, font=7.5)
_chart(s4, XL_CHART_TYPE.PIE, lx + 2950000, CARD_Y + 420000, 2550000, 1000000,
       CARRIER_NAMES, [("Share", CARRIER_VALS)],
       title="Flight share by carrier", legend=False, font=7.5)

# RIGHT CARD — upcoming analytics previews
rx, rw = 6420000, 5620000
_round(s4, rx, CARD_Y, rw, CARD_H, WHITE, ORANGE_D, lw=1.2, rad=0.05)
_round(s4, rx + 60000, CARD_Y + 60000, rw - 120000, 130000, ORANGE_D, rad=0.1)
_txt(s4, rx + 60000, CARD_Y + 60000, rw - 120000, 130000,
     [([("UPCOMING ANALYTICS — CHARTS & BENCHMARKS", 11, True, WHITE)], 0)],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
_metric_cell(s4, rx + 100000, CARD_Y + 230000, 2600000, 150000, ORANGE_L, "36-cell basket",
             "12 routes × 3 windows")
_metric_cell(s4, rx + 2920000, CARD_Y + 230000, 2580000, 150000, TEAL_L, "Aggregation",
             "weighted trimmed mean")
_chart(s4, XL_CHART_TYPE.BAR_CLUSTERED, rx + 120000, CARD_Y + 420000, 2650000, 1000000,
       [WINDOW_LABELS[w] for w in _elasticity.index],
       [("Median fare (INR)", [int(v) for v in _elasticity.values])],
       title="Lead-time elasticity (median fare vs window)", legend=False, font=7.5)
_chart(s4, XL_CHART_TYPE.LINE, rx + 2920000, CARD_Y + 420000, 2580000, 1000000,
       [str(d)[5:] for d in DATES],
       [(r, _route_series(r)) for r in _TREND_ROUTES],
       title="Route-level index trend (base = 100)", legend=False, font=7.5)

prs.save(OUT)
print("SAVED:", OUT)
print("slides:", len(prs.slides))