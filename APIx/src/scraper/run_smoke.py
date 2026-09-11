"""Manual smoke test for the Google Flights scraper on one route.

Run interactively (hits the live site and writes to the DB):
    python -m src.scraper.run_smoke
"""
import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.scraper.google_flights import GoogleFlightsScraper
from src.scraper.run_scrape import _insert_records
from src.storage.database import init_db


async def test():
    init_db()
    scraper = GoogleFlightsScraper()
    travel = date.today() + timedelta(days=7)
    print(f"Testing DEL -> BOM, travel: {travel}")

    records = await scraper.fetch_flights("DEL", "BOM", travel, 7)
    print(f"\nGot {len(records)} flights\n")

    for i, r in enumerate(records[:5], 1):
        print(
            f"  {i}. {r.carrier:20s} | Rs.{r.total_fare:>8.0f} "
            f"| {r.duration_mins:>3d}min | {r.stops} stops "
            f"| dep {r.depart_time.strftime('%H:%M')} "
            f"| arr {r.arrive_time.strftime('%H:%M')}"
        )

    if records:
        count = _insert_records(records, date.today().isoformat())
        print(f"\nInserted {count} rows into raw_flights")


if __name__ == "__main__":
    asyncio.run(test())
