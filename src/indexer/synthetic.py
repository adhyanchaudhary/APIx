"""Deterministic synthetic cleaned-flights generator for estimator research.

Produces a realistic-ish multi-route multi-window scrape: an upward price
drift, weekly seasonality (weekends cost more), small route-level wobble,
occasional sharp spikes, and deliberate coverage gaps so the carry-forward
logic gets exercised. Output uses the ``cleaned_flights`` column schema.

Seeded, so re-running yields identical data — the mean-vs-trimmed-vs-median
comparison in ``report.py`` is reproducible.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
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


def _base_date() -> date:
    return date(2026, 8, 1)


def make_synthetic_cleaned(
    seed: int = 7,
    days: int = 15,
    windows: Sequence[int] = WINDOWS,
    spike_prob: float = 0.03,
) -> pd.DataFrame:
    """Build a seeded cleaned_flights DataFrame.

    Price model per (route, window, day):
        drift (slow rise) × weekend bump × small wobble,
    plus a ~``spike_prob`` chance of a sharp spike (a promo/fare glitch),
    and one deliberate coverage gap day per route+window.
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
                # Deliberate coverage gap: one missing day per route+window.
                if d == gap_day:
                    continue

                year, month, day = _add_days(start, d).timetuple()[:3]
                date_str = f"{year:04d}-{month:02d}-{day:02d}"

                base = BASE_PRICES[route]
                drift = 1.0 + 0.015 * d
                weekend = 1.08 if d % 7 in (5, 6) else 1.0
                wobble = 1.0 + (rng.random() - 0.5) * 0.06
                fare = base * drift * weekend * wobble
                if rng.random() < spike_prob:
                    fare *= 1.6

                rows.append(
                    {
                        "scrape_date": date_str,
                        "route": route,
                        "origin": route.split("-")[0],
                        "dest": route.split("-")[1],
                        "carrier": "SyntheticAir",
                        "flight_no": f"SA-{rng.randint(1000, 9999)}",
                        "depart_time": f"{date_str} 08:00:00",
                        "arrive_time": f"{date_str} 10:30:00",
                        "duration_mins": 150,
                        "stops": 0,
                        "base_fare": round(fare * 0.85, 2),
                        "taxes": round(fare * 0.15, 2),
                        "total_fare": round(fare, 2),
                        "currency": "INR",
                        "lead_window_days": int(window),
                        "scrape_timestamp": f"{date_str} 06:00:00",
                        "quality_score": 1.0,
                        "is_outlier": 0,
                        "dedup_hash": f"{route}|{window}|{date_str}",
                    }
                )

    return pd.DataFrame(rows)


def _add_days(base: date, n: int) -> date:
    return base + timedelta(days=n)