"""Deterministic synthetic cleaned-flights generator for estimator research.

Produces a realistic multi-route multi-window scrape: several flights per
(route, window, day) cell, real carrier names, varied depart/arrive times,
occasional 1-stop itineraries, an upward price drift, weekly seasonality
(weekends cost more), route-level wobble, occasional sharp spikes, occasional
deep-discount promo fares, and deliberate coverage gaps so the carry-forward
and median-robustness logic get exercised. Output uses the ``cleaned_flights``
column schema.

Seeded, so re-running yields identical data — the mean-vs-trimmed-vs-median
comparison in ``report.py`` is reproducible.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Sequence

import pandas as pd

ROUTES = [
    "DEL-BOM", "BOM-DEL", "DEL-BLR", "BLR-DEL", "DEL-MAA", "MAA-DEL",
    "BOM-BLR", "BLR-BOM", "BOM-MAA", "MAA-BOM", "BLR-MAA", "MAA-BLR",
]

BASE_PRICES = {
    "DEL-BOM": 5200, "BOM-DEL": 5100, "DEL-BLR": 4600, "BLR-DEL": 4500,
    "DEL-MAA": 4800, "MAA-DEL": 4700, "BOM-BLR": 4200, "BLR-BOM": 4100,
    "BOM-MAA": 4400, "MAA-BOM": 4300, "BLR-MAA": 3900, "MAA-BLR": 3800,
}

WINDOWS = [1, 7, 30]

# Real domestic carriers so the demo reads like an actual Google Flights scrape.
CARRIERS = [
    ("IndiGo", "6E"),
    ("Air India", "AI"),
    ("Vistara", "UK"),
    ("Akasa Air", "QP"),
    ("SpiceJet", "SG"),
    ("Air India Express", "IX"),
]

# Median block-time per directional route; 1-stop itineraries get +~2 hr.
BASE_DURATION_MINS = {
    "DEL-BOM": 145, "BOM-DEL": 145,
    "DEL-BLR": 185, "BLR-DEL": 185,
    "DEL-MAA": 170, "MAA-DEL": 170,
    "BOM-BLR": 135, "BLR-BOM": 135,
    "BOM-MAA": 105, "MAA-BOM": 105,
    "BLR-MAA": 75, "MAA-BLR": 75,
}

# Economy fare tiers for one cell. The median tier sits at the cell reference
# price; cheap promos push the MIN well below it, so median-vs-min robustness
# is visible in the dashboard.
TIER_FRACTIONS = [0.88, 0.94, 1.00, 1.06, 1.12, 1.19, 1.30]
PROMO_FRACTION = 0.62   # deep-discount "flash sale" fare
DEPARTURE_HOURS = [6, 7, 8, 9, 10, 11, 13, 15, 17, 19]
STOP_PROB = 0.18        # share of itineraries with 1 stop
SPIKE_OUTLIER_PROB = 0.35  # share of spiked cells flagged as outliers


def _base_date() -> date:
    return date(2026, 8, 1)


def _add_days(base: date, n: int) -> date:
    return base + timedelta(days=n)


def _format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def make_synthetic_cleaned(
    seed: int = 7,
    days: int = 15,
    windows: Sequence[int] = WINDOWS,
    spike_prob: float = 0.03,
    flights_per_cell: int = 7,
    promo_prob: float = 0.25,
) -> pd.DataFrame:
    """Build a seeded cleaned_flights DataFrame with realistic cell spreads.

    Price model per (route, window, day):
        drift (slow rise) × weekend bump × small wobble,
    plus ``spike_prob`` chance of a sharp cell spike, and ``promo_prob`` chance
    of one deep-discount fare inside the cell. Each cell holds
    ``flights_per_cell`` fares spread across economy tiers (occasionally a
    cheap promo on top), flights are tagged with real carriers, varied times
    and some 1-stop itineraries. One deliberate coverage-gap day per
    route+window exercises the carry-forward logic.
    """
    rng = random.Random(seed)
    start = _base_date()
    rows: list[dict] = []

    for window in windows:
        for gap_offset, route in enumerate(ROUTES):
            # Coverage gap mid-series (never day 0 — that would orphan the
            # route from the base period — and never the last day).
            gap_day = 1 + (gap_offset % max(days - 3, 1))
            for d in range(days):
                if d == gap_day:
                    continue

                scrape = _add_days(start, d)
                travel = _add_days(scrape, int(window))
                date_str = scrape.strftime("%Y-%m-%d")

                base = BASE_PRICES[route]
                drift = 1.0 + 0.015 * d
                weekend = 1.08 if d % 7 in (5, 6) else 1.0
                wobble = 1.0 + (rng.random() - 0.5) * 0.06
                cell_ref = base * drift * weekend * wobble
                spiked = rng.random() < spike_prob
                if spiked:
                    cell_ref *= 1.6

                use_promo = rng.random() < promo_prob
                tier_count = flights_per_cell

                for f in range(tier_count):
                    tier = TIER_FRACTIONS[f % len(TIER_FRACTIONS)]
                    fwob = 1.0 + (rng.random() - 0.5) * 0.04
                    total = cell_ref * tier * fwob
                    rows.append(
                        _make_flight(rng, route, date_str, travel, window, total,
                                     spiked, f)
                    )

                if use_promo:
                    promo = cell_ref * PROMO_FRACTION
                    rows.append(
                        _make_flight(rng, route, date_str, travel, window, promo,
                                     spiked, tier_count, is_promo=True)
                    )

    return pd.DataFrame(rows)


def _make_flight(
    rng: random.Random,
    route: str,
    date_str: str,
    travel: date,
    window: int,
    total_fare: float,
    spiked: bool,
    seq: int,
    is_promo: bool = False,
) -> dict:
    """Build one cleaned_flights row with realistic carrier / time / stops."""
    origin, dest = route.split("-")
    carrier, code = CARRIERS[rng.randrange(len(CARRIERS))]

    stops = 1 if rng.random() < STOP_PROB else 0
    duration = BASE_DURATION_MINS[route] + (120 if stops else 0) + rng.randint(-12, 12)
    hour = DEPARTURE_HOURS[rng.randrange(len(DEPARTURE_HOURS))]
    minute = rng.randrange(0, 60, 5)
    dep = datetime.combine(travel, datetime.min.time()) + timedelta(
        hours=hour, minutes=minute
    )
    arr = dep + timedelta(minutes=duration)

    flight_no = f"{code}-{1000 + seq:04d}"

    if spiked and rng.random() < SPIKE_OUTLIER_PROB:
        is_outlier = 1
    else:
        is_outlier = 0

    return {
        "scrape_date": date_str,
        "route": route,
        "origin": origin,
        "dest": dest,
        "carrier": carrier,
        "flight_no": flight_no,
        "depart_time": _format_dt(dep),
        "arrive_time": _format_dt(arr),
        "duration_mins": duration,
        "stops": stops,
        "base_fare": round(total_fare * 0.85, 2),
        "taxes": round(total_fare * 0.15, 2),
        "total_fare": round(total_fare, 2),
        "currency": "INR",
        "lead_window_days": int(window),
        "scrape_timestamp": f"{date_str} 06:00:00",
        "quality_score": 1.0,
        "is_outlier": is_outlier,
        "dedup_hash": f"{route}|{window}|{date_str}|{flight_no}",
    }