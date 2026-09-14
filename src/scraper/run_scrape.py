"""Scrape all configured routes → write to raw_flights table.

Usage:
    python -m src.scraper.run_scrape              # scrape all routes for today
    python -m src.scraper.run_scrape --date 2026-09-15
"""
import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from src.scraper.google_flights import GoogleFlightsScraper, _load_routes
from src.models.schemas import FlightRecord
from src.storage.database import get_connection, init_db

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _insert_records(records: list[FlightRecord], scrape_date: str, db_path: Path | str | None = None) -> int:
    """Batch-insert FlightRecords into raw_flights. Returns row count."""
    if not records:
        return 0

    conn = get_connection(db_path)
    try:
        sql = """
            INSERT INTO raw_flights
            (scrape_date, route, origin, dest, carrier, flight_no,
             depart_time, arrive_time, duration_mins, stops,
             base_fare, taxes, total_fare, currency, lead_window_days,
             scrape_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                scrape_date,
                r.route, r.origin, r.dest,
                r.carrier, r.flight_no,
                r.depart_time.isoformat(),
                r.arrive_time.isoformat(),
                r.duration_mins, r.stops,
                r.base_fare, r.taxes, r.total_fare,
                r.currency, r.lead_window_days,
                r.scrape_timestamp.isoformat(),
            )
            for r in records
        ]
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


async def run_scrape(target_date: date | None = None, db_path: Path | str | None = None) -> None:
    """Main scrape loop: every route × every configured lead window."""
    _setup_logging()
    init_db(db_path)

    cfg = _load_routes()
    routes = cfg["routes"]
    offsets = [int(w) for w in cfg.get("lead_windows", [1, 7, 30])]
    scrape_date_str = (target_date or date.today()).isoformat()

    log.info("=== Scrape run: %s ===", scrape_date_str)
    log.info("Routes: %d | Lead windows: %s", len(routes), offsets)

    scraper = GoogleFlightsScraper()
    total_inserted = 0
    total_failed = 0

    for route in routes:
        origin, dest = route["origin"], route["dest"]
        for lead in offsets:
            travel = (target_date or date.today()) + timedelta(days=lead)
            log.info("-- %s->%s  T+%d  (travel: %s) --", origin, dest, lead, travel)

            try:
                records = await scraper.fetch_flights(origin, dest, travel, lead)
                count = _insert_records(records, scrape_date_str, db_path)
                total_inserted += count
                log.info("  OK %d flights saved", count)
            except Exception as exc:
                total_failed += 1
                log.error("  FAILED: %s", exc)

    log.info(
        "=== Run complete: %d flights saved, %d routeXday failures ===",
        total_inserted, total_failed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run flight scrape")
    parser.add_argument("--date", type=str, default=None,
                        help="Scrape date as YYYY-MM-DD (default: today)")
    parser.add_argument("--db", type=str, default=None,
                        help="Path to SQLite db (default: data/apix.db)")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None
    asyncio.run(run_scrape(target, args.db))


if __name__ == "__main__":
    main()
