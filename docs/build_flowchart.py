"""Build a fully-native PowerPoint flowchart of the APIx pipeline.

Stages: SCRAPER -> CLEANER -> INDEXER (rolling index) -> DASHBOARD.
All shapes/text are native PowerPoint objects (no image files), matching the
SIH deck style.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

OUT = r"C:\Users\LENOVO\Downloads\airindex_pipeline_flowchart.pptx"

BLUE_D = RGBColor(0x0D, 0x47, 0xA1)
BLUE_M = RGBColor(0x15, 0x65, 0xC0)
BLUE_L = RGBColor(0xE3, 0xF2, 0xFD)
GREEN_D = RGBColor(0x1B, 0x5E, 0x20)
GREEN_M = RGBColor(0x2E, 0x7D, 0x32)
GREEN_L = RGBColor(0xE8, 0xF5, 0xE9)
ORANGE_D = RGBColor(0xE6, 0x51, 0x00)
ORANGE_M = RGBColor(0xEF, 0x6C, 0x00)
ORANGE_L = RGBColor(0xFF, 0xF3, 0xE0)
PURPLE_D = RGBColor(0x6A, 0x1B, 0x9A)
PURPLE_M = RGBColor(0x8E, 0x24, 0xAA)
PURPLE_L = RGBColor(0xF3, 0xE5, 0xF5)
TEAL_M = RGBColor(0x00, 0x69, 0x5C)
GREY = RGBColor(0x5F, 0x63, 0x68)
INK = RGBColor(0x1A, 0x1A, 0x2E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Segoe UI"


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


def _round(slide, x, y, w, h, fill, line=None, lw=1.0, rad=0.08):
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


def _arrow(slide, kind, x, y, w, h, fill):
    sp = slide.shapes.add_shape(kind, Emu(x), Emu(y), Emu(w), Emu(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    sp.line.fill.background(); sp.shadow.inherit = False
    return sp


prs = Presentation()
prs.slide_width = Emu(12192000)
prs.slide_height = Emu(6858000)
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

# background
_round(slide, 0, 0, 12192000, 6858000, WHITE, RGBColor(0xE2, 0xE8, 0xF0), lw=1.5, rad=0.01)

_txt(slide, 250000, 180000, 11692000, 420000,
     [([("APIx PIPELINE — ", 24, True, BLUE_D),
         ("SCRAPER  →  CLEANER  →  INDEXER (rolling)  →  DASHBOARD", 24, True, INK)], 0)],
     align=PP_ALIGN.CENTER)
_line2 = _round(slide, 300000, 700000, 11592000, 50000, PURPLE_M, rad=0.5)

STAGES = [
    {
        "num": "01", "accent_d": BLUE_D, "accent_m": BLUE_M, "bg": BLUE_L,
        "title": "1 · SCRAPER  —  src/scraper/run_scrape.py",
        "rows": [
            ("Playwright + headless Chrome", "12 routes (4 metro cities both directions) × 3 windows (T+1 / T+7 / T+30)"),
            ("Rate-limited 60 req/h · retries · APScheduler daily job", "stores every result, nothing dropped at this stage"),
        ],
        "out": "OUT →  raw_flights table",
    },
    {
        "num": "02", "accent_d": GREEN_D, "accent_m": GREEN_M, "bg": GREEN_L,
        "title": "2 · CLEANER  —  src/cleaner/clean.py",
        "rows": [
            ("dedup via _compute_hash (scrape / route / flight / fare)", "_flag_outliers_iqr → IQR 1.5× bands, is_outlier=1"),
            ("_compute_quality_score · null-fare handling", "non-influential rows dropped, rest flagged not deleted"),
        ],
        "out": "OUT →  cleaned_flights table",
    },
    {
        "num": "03", "accent_d": ORANGE_D, "accent_m": ORANGE_M, "bg": ORANGE_L,
        "title": "3 · INDEXER — ROLLING INDEX  —  src/indexer/run_index.py",
        "rows": [
            ("route_price_per_day → median fare per (route × window × date)", "price/0 weight basket = weighted trimmed mean, base day = 100"),
            ("compute_daily_index → 36 cells + aggregate headline", "compute_rolling_index(7) and compute_rolling_index(30)"),
        ],
        "out": "OUT →  daily_index · weekly_index · monthly_index",
    },
    {
        "num": "04", "accent_d": PURPLE_D, "accent_m": PURPLE_M, "bg": PURPLE_L,
        "title": "4 · DASHBOARD  —  src/dashboard/app.py  (Streamlit + Plotly)",
        "rows": [
            ("Composite APIx headline + trend (daily / weekly / monthly)", "route map of all 12 corridors · KPI cards"),
            ("Window tabs T+1 / T+7 / T+30 · city flight search", "route-level index trend · carrier & route pies · raw tables"),
        ],
        "out": "OUT →  MoSPI / NSO · RBI · policy research",
    },
]

BAND_Y = 950000
BAND_H = 1320000
BAND_W = 11692000
X = 250000
BANDS = []

for st in STAGES:
    y = BAND_Y + len(BANDS) * (BAND_H + 120000)
    _round(slide, X, y, BAND_W, BAND_H, st["bg"], st["accent_m"], lw=1.3, rad=0.035)
    # stage number badge
    badge = _round(slide, X + 120000, y + 120000, 240000, 240000, st["accent_d"], rad=0.3)
    _txt(slide, X + 120000, y + 120000, 240000, 240000,
         [([(st["num"], 15, True, WHITE)], 0)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    # title
    _txt(slide, X + 520000, y + 130000, BAND_W - 700000, 240000,
         [([(st["title"], 16, True, st["accent_d"])], 0)])
    # two detail rows (left label / right value)
    for i, (label, value) in enumerate(st["rows"]):
        row_y = y + 420000 + i * 280000
        _round(slide, X + 520000, row_y, 5600000, 240000, st["accent_d"] if i == 0 else WHITE,
               None if i == 0 else st["accent_m"], lw=1.0, rad=0.12)
        _txt(slide, X + 560000, row_y, 5560000, 240000,
             [([(label, 11.5, True, WHITE if i == 0 else st["accent_d"])], 0)],
             anchor=MSO_ANCHOR.MIDDLE)
        _txt(slide, X + 6300000, row_y, 5350000, 240000,
             [([(value, 11, False, INK)], 0)], anchor=MSO_ANCHOR.MIDDLE)
    # output chip
    _round(slide, X + 520000, y + BAND_H - 230000, 6400000, 160000, st["accent_d"], rad=0.5)
    _txt(slide, X + 540000, y + BAND_H - 230000, 6380000, 160000,
         [([(st["out"], 10.5, True, WHITE)], 0)], anchor=MSO_ANCHOR.MIDDLE)
    BANDS.append((X + BAND_W // 2, y + BAND_H))

# connectors between bands
prev = None
for cx, cy in BANDS:
    if prev is not None:
        _arrow(slide, MSO_SHAPE.DOWN_ARROW, prev - 110000, cy + 10000, 220000, 100000, GREY)
    prev = cx

prs.save(OUT)
print("SAVED:", OUT)