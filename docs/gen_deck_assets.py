"""Generate PNG assets for the SIH pitch deck (HLD, dashboard mock, charts).

Writes into docs/deck-images/ so python-pptx can embed them.
"""
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

OUT = Path(r"C:\Users\LENOVO\Desktop\SIH-2026\docs\deck-images")
OUT.mkdir(parents=True, exist_ok=True)

# ── palette (deck colours) ────────────────────────────────────────────────
BLUE = "#1565C0"
BLUE_D = "#0D47A1"
BLUE_L = "#E3F2FD"
GREEN = "#2E7D32"
GREEN_L = "#E8F5E9"
ORANGE = "#EF6C00"
ORANGE_L = "#FFF3E0"
PURPLE = "#6A1B9A"
PURPLE_L = "#F3E5F5"
TEAL = "#00695C"
TEAL_L = "#E0F2F1"
GREY = "#5F6368"
INK = "#1A1A2E"


def _box(ax, x, y, w, h, fc, ec, text, fs=15, tc="#111", lw=1.6, bold=True, style="round,pad=1.1,rounding_size=0.02"):
    box = FancyBboxPatch(
        (x, y), w, h, boxstyle=mpatches.BoxStyle(style),
        linewidth=lw, edgecolor=ec, facecolor=fc, mutation_aspect=1.0, zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text, ha="center", va="center",
        fontsize=fs, color=tc, fontweight="bold" if bold else "normal",
        linespacing=1.45, zorder=4,
    )
    return box


def _arrow(ax, x1, y1, x2, y2, color=GREY, lw=2.4, style="-|>", shrink=0.0, ms=22):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=ms,
        linewidth=lw, color=color, shrinkA=shrink, shrinkB=shrink, zorder=2,
    )
    ax.add_patch(a)


def _tag(ax, x, y, text, fc=PURPLE, fs=13, tc="#fff"):
    ax.text(
        x, y, text, ha="center", va="center", fontsize=fs, fontweight="bold",
        color=tc, bbox=dict(boxstyle="round,pad=0.28", fc=fc, ec="none"), zorder=5,
    )
    _ = Circle  # (keep import used marker)


# ═══════════════════════════════════════════════════════════════════════════
# 1) HLD architecture
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(16, 9), dpi=200)
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis("off")

# header band
ax.add_patch(plt.Rectangle((0, 8.35), 16, 0.65, color=BLUE_D, zorder=1))
ax.text(8, 8.67, "APIx — HIGH-LEVEL ARCHITECTURE (36-cell weighted price index)",
        ha="center", va="center", color="white", fontsize=17, fontweight="bold")

# source layer
_box(ax, 0.4, 7.25, 15.2, 0.85, BLUE_L, BLUE, "DATA SOURCES  ·  Google Flights  ·  Airline websites  ·  OTAs", fs=14, tc=BLUE_D)

# arrows sources -> scraper
_arrow(ax, 3.2, 7.25, 3.2, 6.4)
_arrow(ax, 8.0, 7.25, 8.0, 6.4)
_arrow(ax, 12.8, 7.25, 12.8, 6.4)

# ingestion row: 3 boxes
_box(ax, 0.4, 5.4, 4.6, 1.0, "#fff", BLUE, "SCRAPER", fs=14, tc=BLUE_D)
ax.text(2.7, 5.95, "Playwright (Python) · headless Chrome\nrate-limited 60 req/h · retries · APScheduler",
        ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.5)
_box(ax, 5.7, 5.4, 4.6, 1.0, "#fff", GREEN, "DATA CLEANING", fs=14, tc=GREEN)
ax.text(8.0, 5.95, "Pandas · dedup · null-fare handling\nIQR (1.5×) outlier flag · quality score",
        ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.5)
_box(ax, 11.0, 5.4, 4.6, 1.0, "#fff", ORANGE, "INDEX ENGINE — APIx", fs=14, tc=ORANGE)
ax.text(13.3, 5.95, "36 cells (12 routes × 3 windows)\nweighted trimmed mean · base = 100",
        ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.5)

# arrows to storage
_arrow(ax, 2.7, 5.4, 2.7, 4.55)
_arrow(ax, 8.0, 5.4, 8.0, 4.55)
_arrow(ax, 13.3, 5.4, 13.3, 4.55)

# storage layer
_box(ax, 0.4, 3.35, 7.3, 1.2, TEAL_L, TEAL, "SQLite  ·  data/apix.db", fs=14, tc=TEAL)
ax.text(4.05, 3.9, "raw_flights · cleaned_flights\ndaily_index · weekly_index · monthly_index",
        ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.5)
_box(ax, 8.3, 3.35, 7.3, 1.2, GREEN_L, GREEN, "CACHE LAYER", fs=14, tc=GREEN)
ax.text(11.95, 3.9, "TTL in-memory cache (60 s) · aggregated materialised views\ncuts repeat SN/moM requests & dashboard cold loads",
        ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.5)

# arrows storage -> consumer
_arrow(ax, 2.7, 3.35, 2.7, 2.35)
_arrow(ax, 7.5, 3.95, 8.3, 3.95, color=GREY, lw=1.8)   # cache reads DB
_arrow(ax, 11.95, 3.35, 11.95, 2.35)

# consumer layer
_box(ax, 0.4, 1.15, 4.6, 1.2, BLUE_L, BLUE, "STREAMLIT DASHBOARD", fs=14, tc=BLUE_D)
ax.text(2.7, 1.7, "Plotly charts: composite trend · route trends\npie & bar · raw explorer (FR4)",
        ha="center", va="center", fontsize=11, color=INK, linespacing=1.5)
_box(ax, 5.7, 1.15, 4.6, 1.2, ORANGE_L, ORANGE, "REST API  (FastAPI)", fs=14, tc=ORANGE)
ax.text(8.0, 1.7, "CSV / JSON export of index series\nfor RBI & NSO consumption (FR6)",
        ha="center", va="center", fontsize=11, color=INK, linespacing=1.5)
_box(ax, 11.0, 1.15, 4.6, 1.2, PURPLE_L, PURPLE, "NN — FARE DIRECTION MODEL", fs=14, tc=PURPLE)
ax.text(13.3, 1.7, "TensorFlow classifier 20 features\n2×[64,32] ReLU+Dropout → surging/steady/dipping",
        ha="center", va="center", fontsize=11, color=INK, linespacing=1.5)

# NN tag
_tag(ax, 13.3, 3.1, "NN ON CONSUMER LAYER", fc=PURPLE, fs=12)

# consumers downstream
ax.add_patch(plt.Rectangle((0.4, 0.12), 15.2, 0.62, color=BLUE_D, zorder=1))
ax.text(8.0, 0.43, "CONSUMERS  ·  MoSPI / NSO inflation statistics  ·  RBI monetary policy  ·  Policy research",
        ha="center", va="center", color="white", fontsize=13.5, fontweight="bold")
_arrow(ax, 2.7, 1.15, 2.7, 0.74, color=GREY, lw=1.8)
_arrow(ax, 8.0, 1.15, 8.0, 0.74, color=GREY, lw=1.8)
_arrow(ax, 13.3, 1.15, 13.3, 0.74, color=GREY, lw=1.8)

plt.tight_layout(pad=0.3)
plt.savefig(OUT / "hld-architecture.png", dpi=200, bbox_inches="tight", facecolor="white")
plt.close()
print("wrote hld-architecture.png")

# ═══════════════════════════════════════════════════════════════════════════
# 2) Dashboard mock (frontend image)
# ═══════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(16, 9), dpi=180)
gs = fig.add_gridspec(12, 16, hspace=0.5, wspace=0.5, top=0.93, bottom=0.05, left=0.04, right=0.99)

# sidebar panel
sb = fig.add_axes([0.02, 0.05, 0.13, 0.86], xticks=[], yticks=[])
sb.add_patch(plt.Rectangle((0, 0), 1, 1, fc="#0F2537", ec="none", transform=sb.transAxes, zorder=0))
sb.text(0.06, 0.9, "APIx", color="#5BC8E8", fontsize=16, fontweight="bold")
sb.text(0.06, 0.82, "Real-time Airfare Price Index — MoSPI / NSO / RBI", color="#9FB4C7", fontsize=7.5)
sb.text(0.06, 0.70, "Database", color="#CFE2EE", fontsize=9, fontweight="bold")
for i, lbl in enumerate(["◉ Demo (synthetic 30-day)", "○ Live scrape (real fares)"]):
    sb.text(0.07, 0.60 - i * 0.07, lbl, color="#B9CCDA", fontsize=7.5)
sb.text(0.06, 0.42, "⊕ Load synthetic demo data", color="#B9CCDA", fontsize=7.5)
sb.text(0.06, 0.14, "Tabs: T+1 / T+7 / T+30", color="#B9CCDA", fontsize=7)

# top metric cards
for i, (label, val) in enumerate([("Latest composite APIx", "107.42"), ("Latest index date", "2026-09-14"), ("Cleaned flights", "1,248"), ("Routes in data", "12 / 12")]):
    axm = fig.add_subplot(gs[0:1, 3 + i * 3:6 + i * 3], xticks=[], yticks=[])
    axm.add_patch(plt.Rectangle((0, 0), 1, 1, fc="#F4F7FA", ec="#D5DEE8", lw=1.2, transform=axm.transAxes))
    axm.text(0.5, 0.55, val, ha="center", va="center", fontsize=20, fontweight="bold", color="#0B7285")
    axm.text(0.5, 0.18, label, ha="center", va="center", fontsize=8, color="#5F6368")

import numpy as np

# composite trend chart
axt = fig.add_subplot(gs[1:5, 3:11], xticks=[], yticks=[])
days = np.arange(1, 31)
daily = 100 + 3.2 * np.sin(days / 5.2) + 0.18 * days
weekly = np.convolve(daily, np.ones(7) / 7, "same")
monthly = np.convolve(daily, np.ones(30) / 30, "same")
axt.plot(days, daily, "-o", ms=3, color="#1565C0", lw=1.6, label="Daily APIx")
axt.plot(days, weekly, "-", color="#2E7D32", lw=2.2, label="Weekly APIx")
axt.plot(days, monthly, "--", color="#EF6C00", lw=2.2, label="Monthly APIx")
axt.axhline(100, color="#9E9E9E", lw=0.8, ls=":")
axt.set_title("APIx composite headline over time (base = 100)", fontsize=10.5, fontweight="bold", color="#202124")
axt.legend(fontsize=8, loc="upper left", frameon=False)
axt.tick_params(labelsize=7)
axt.grid(alpha=0.25)
axt.set_ylim(90, 130)

# carrier pie
axp = fig.add_subplot(gs[1:5, 11:16], xticks=[], yticks=[] , aspect="equal")
sizes = [38, 26, 18, 12, 6]
labels = ["IndiGo", "Air India", "Akasa", "SpiceJet", "Vistara"]
cols = ["#1565C0", "#2E7D32", "#EF6C00", "#6A1B9A", "#00838F"]
wedges, _, autot = axp.pie(
    sizes, colors=cols, autopct="%1.0f%%", startangle=120,
    textprops=dict(fontsize=7.5, color="white", fontweight="bold"), wedgeprops=dict(width=0.42),
)
axp.set_title("Flight share by carrier", fontsize=10.5, fontweight="bold", color="#202124", pad=8)
axp.legend(wedges, labels, loc="center left", fontsize=7, bbox_to_anchor=(0.98, 0.5), frameon=False)

# route bar chart
axb = fig.add_subplot(gs[5:9, 3:11], xticks=[], yticks=[])
routes = ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-MAA", "BOM-MAA", "BLR-MAA", "BLR-BOM", "MAA-BLR", "BOM-DEL", "MAA-DEL", "BLR-DEL", "MAA-BOM"]
weights = [0.10, 0.09, 0.10, 0.06, 0.08, 0.07, 0.10, 0.07, 0.10, 0.06, 0.09, 0.08]
bars = axb.bar(routes, weights, color="#42A5F5", edgecolor="#1565C0", lw=0.5)
axb.set_title("Average fare by route (INR, latest scrape)", fontsize=10.5, fontweight="bold", color="#202124")
axb.tick_params(labelsize=7, rotation=45)
axb.grid(axis="y", alpha=0.25)
axb.set_ylim(0, max(weights) * 1.5)

# weights sub-bar inside? simpler: bar shows weights
axb.set_title("Route basket weights (DGCA traffic share)", fontsize=10.5, fontweight="bold", color="#202124")

# heatmap/table
hx = np.arange(1, 31)
hm = fig.add_subplot(gs[5:9, 11:16], xticks=[], yticks=[])
data = np.random.RandomState(7).rand(12, 30) * 40 + 80
hm.imshow(data, aspect="auto", cmap="YlGnBu", interpolation="nearest")
hm.set_title("Route index heatmap — last 30 days (base = 100)", fontsize=10.5, fontweight="bold", color="#202124")
hm.set_yticks(range(12), routes, fontsize=6.5)
hm.set_xticks(range(0, 30, 5), [f"D-{30-c}" for c in range(0, 30, 5)], fontsize=6.5)

# bottom strip: NN + cache chips
axn = fig.add_subplot(gs[9:12, 3:16], xticks=[], yticks=[])
axn.axis("off")
axn.add_patch(plt.Rectangle((0, 0.45), 0.24, 0.42, fc="#F3E5F5", ec="#6A1B9A", lw=1.4, transform=axn.transAxes))
axn.text(0.12, 0.66, "NN FORECAST", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#6A1B9A", transform=axn.transAxes)
axn.text(0.12, 0.52, "fare direction classifier\n(Down / Stable / Up)", ha="center", va="center", fontsize=6.8, color="#4A148C", transform=axn.transAxes, linespacing=1.4)
axn.add_patch(plt.Rectangle((0.27, 0.45), 0.24, 0.42, fc="#E8F5E9", ec="#2E7D32", lw=1.4, transform=axn.transAxes))
axn.text(0.39, 0.66, "CACHE LAYER", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#2E7D32", transform=axn.transAxes)
axn.text(0.39, 0.52, "60 s TTL · materialised views\n<1 s cached dashboard load", ha="center", va="center", fontsize=6.8, color="#1B5E20", transform=axn.transAxes, linespacing=1.4)
for i, c in enumerate(["Pie charts", "Route trends", "Composite tables", "Raw explorer", "CSV/JSON export"]):
    axn.text(0.56 + i * 0.09, 0.66, c, ha="center", va="center", fontsize=7.5, fontweight="bold", color="#1565C0", transform=axn.transAxes)
    axn.text(0.56 + i * 0.09, 0.5, "in-app", ha="center", va="center", fontsize=6.5, color="#5F6368", transform=axn.transAxes)

plt.savefig(OUT / "dashboard-mock.png", dpi=180, facecolor="white")
plt.close()
print("wrote dashboard-mock.png")

# ═══════════════════════════════════════════════════════════════════════════
# 3) Trend charts for upcoming features (lead-time elasticity + route trend)
# ═══════════════════════════════════════════════════════════════════════════
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.4), dpi=180)

windows = ["T+1", "T+7", "T+30"]
prices = [12450, 9210, 6840]
colors = ["#1565C0", "#2E7D32", "#EF6C00"]
bars = ax1.bar(windows, prices, color=colors, width=0.55, edgecolor="#222", lw=0.6)
for b, v in zip(bars, prices):
    ax1.text(b.get_x() + b.get_width() / 2, v + 250, f"₹{v:,}", ha="center", fontsize=12, fontweight="bold", color="#202124")
ax1.set_title("Lead-time elasticity — median fare vs booking window", fontsize=13, fontweight="bold", color="#202124")
ax1.set_ylabel("Median one-way fare (INR)", fontsize=10.5)
ax1.grid(axis="y", alpha=0.25)
ax1.text(0.02, -0.18, "Booking earlier = cheaper (50% of bookings are T+30)", transform=ax1.transAxes, fontsize=9, color="#5F6368")

days = np.arange(1, 41)
rng = np.random.RandomState(3)
for r, c in zip(["DEL-BOM", "BOM-BLR", "BLR-MAA"], ["#1565C0", "#2E7D32", "#EF6C00"]):
    base = 100 + rng.randn(1)[0] * 8
    series = base + 0.25 * np.cumsum(rng.randn(40)) * 0.6 + np.sin(days / 5) * 2
    ax2.plot(days, series, label=r, lw=2)
ax2.axhline(100, color="#9E9E9E", lw=0.8, ls=":")
ax2.set_title("Route-level index trend (base = 100)", fontsize=13, fontweight="bold", color="#202124")
ax2.set_xlabel("Index date (days)", fontsize=10.5)
ax2.legend(fontsize=10, frameon=False, loc="upper left")
ax2.grid(alpha=0.25)

plt.savefig(OUT / "trend-charts.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close()
print("wrote trend-charts.png")

# ═══════════════════════════════════════════════════════════════════════════
# 4) Route weight / benchmark bar chart
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(16, 6.2), dpi=180)
routes = ["DEL-\nBOM", "BOM-\nDEL", "DEL-\nBLR", "BLR-\nDEL", "BOM-\nBLR", "BLR-\nBOM",
          "DEL-\nMAA", "MAA-\nDEL", "BOM-\nMAA", "MAA-\nBOM", "BLR-\nMAA", "MAA-\nBLR"]
weights = [0.10, 0.10, 0.09, 0.09, 0.10, 0.10, 0.06, 0.06, 0.08, 0.08, 0.07, 0.07]
cmap = plt.cm.viridis(np.linspace(0.15, 0.9, 12))
bars = ax.bar(routes, weights, color=cmap, edgecolor="#222", lw=0.7, width=0.62)
for b, v in zip(bars, weights):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.0015, f"{v:.2f}", ha="center", fontsize=10.5, fontweight="bold", color="#202124")
ax.set_title("12-route DGCA basket weights — sum = 1.00 (config-driven)", fontsize=14, fontweight="bold", color="#202124")
ax.set_ylabel("Traffic share weight", fontsize=11)
ax.grid(axis="y", alpha=0.25)
ax.set_ylim(0, 0.125)
plt.savefig(OUT / "route-weights-bar.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close()
print("wrote route-weights-bar.png")

# ═══════════════════════════════════════════════════════════════════════════
# 5) APIx formula card image
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(15, 3.4), dpi=180)
ax.axis("off")
ax.add_patch(FancyBboxPatch((0.02, 0.05), 0.96, 0.9, boxstyle="round,pad=0.01,rounding_size=0.03",
                            fc="#E8F5E9", ec="#2E7D32", lw=1.6, transform=ax.transAxes))
ax.text(0.05, 0.86, "How APIx is calculated", transform=ax.transAxes, fontsize=13, fontweight="bold", color="#1B5E20")
ax.text(0.05, 0.62, "APIx(t) = \u2211 [ P_cell(t) / P_cell(0) × w_route × w_window ] × 100", transform=ax.transAxes,
        fontsize=16, fontweight="bold", color="#0D47A1", family="DejaVu Sans")
ax.text(0.05, 0.32, "1) 36-cell basket  =  12 routes × 3 booking windows (T+1 / T+7 / T+30)",
        transform=ax.transAxes, fontsize=10.5, color="#202124")
ax.text(0.05, 0.16, "2)  P_cell(t)  =  median fare per (route, window, day), outliers excluded · carry-forward fills gaps",
        transform=ax.transAxes, fontsize=10.5, color="#202124")
ax.text(0.05, 0.03, "3)  weights  =  DGCA route share × booking-lead share (20 : 30 : 50)  →  headline = weighted trimmed mean, base day = 100",
        transform=ax.transAxes, fontsize=10.5, color="#202124")
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
plt.savefig(OUT / "api-formula.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close()
print("wrote api-formula.png")

print("ALL ASSETS DONE")