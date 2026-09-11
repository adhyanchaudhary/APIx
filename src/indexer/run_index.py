"""Compute daily / weekly / monthly APIx from cleaned_flights.

Reads the full cleaned_flights table, builds the weighted basket index, and
writes the result to daily_index, weekly_index, and monthly_index.

Usage:
    python -m src.indexer.run_index                  # rebuild all indices
    python -m src.indexer.run_index --db data/custom.db
"""
import argparse
import logging
import sys
from pathlib import Path

from src.indexer.api_index import (
    compute_daily_index,
    compute_rolling_index,
    load_index_config,
    load_route_weights,
    read_cleaned_flights,
    route_price_per_day,
    write_index,
)
from src.storage.database import get_connection, init_db

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_index(db_path: Path | str | None = None, cfg_path: Path | str | None = None) -> dict:
    init_db(db_path)

    cleaned = read_cleaned_flights(db_path)
    if cleaned.empty:
        log.warning("cleaned_flights is empty — nothing to index")
        return {"daily": 0, "weekly": 0, "monthly": 0}

    weights = load_route_weights(cfg_path)
    round_to = load_index_config(cfg_path).get("round_to", 2)

    log.info("═══ Index run ═══")
    log.info("Weights: %d routes (normalised to %s)", len(weights), round(sum(weights.values()), 4))

    prices = route_price_per_day(cleaned)
    if prices.empty:
        log.warning("No price rows after cleaning filter — nothing to index")
        return {"daily": 0, "weekly": 0, "monthly": 0}
    log.info("Price rows: %d (route × window × date)", len(prices))

    daily = compute_daily_index(prices, weights, round_to)
    weekly = compute_rolling_index(daily, 7, round_to)
    monthly = compute_rolling_index(daily, 30, round_to)

    n_daily = write_index(daily, "daily_index", db_path)
    n_weekly = write_index(weekly, "weekly_index", db_path)
    n_monthly = write_index(monthly, "monthly_index", db_path)

    log.info("═══ Complete: daily=%d | weekly=%d | monthly=%d ═══", n_daily, n_weekly, n_monthly)
    return {"daily": n_daily, "weekly": n_weekly, "monthly": n_monthly}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build APIx indices from cleaned_flights")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite db (default: data/apix.db)")
    args = parser.parse_args()

    _setup_logging()
    run_index(db_path=args.db)


if __name__ == "__main__":
    main()