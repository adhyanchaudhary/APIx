"""Live APIx loop — scrape -> clean -> index -> diff -> emit, reusing the
existing pipeline components (no parallel index engine).

Startup:
    0. PRIME — scrape the FULL route pool once (skipped when today's basket
       is already complete) so every cell has a baseline. Only then does the
       rotating monitor begin, so the index never starts from a half-empty
       basket. Disable with --no-prime.

Each iteration:
    1. OPTIONALLY scrape a small rotating subset of routes (keeps us under
       the 60 req/h cap), else live on whatever raw data exists.
    2. clean_raw_data()  — incremental: only NEW raw rows become cleaned.
    3. run_index()       — recomputes daily/weekly/monthly from cleaned data
       (cell price = median of day x window x route, same as always).
    4. diff today's headline against the previous iteration, emit one
       IndexUpdate (biggest-mover cell as context) to the SubscriberHub.
    5. Subscribers persist the tick to live_index + log it to the terminal.

Usage:
    python -m src.live.run_live --no-scrape --interval 5      # offline demo
    python -m src.live.run_live --routes DEL-BOM,BOM-DEL --interval 300
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import logging
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path

from src.cleaner.clean import clean_raw_data
from src.indexer.api_index import load_estimator_config
from src.indexer.run_index import run_index
from src.scraper.run_scrape import run_scrape, _load_routes
from src.live.events import IndexUpdate, SubscriberHub
from src.storage.database import get_connection, init_db

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _all_route_keys() -> list[str]:
    routes = _load_routes()["routes"]
    return [f"{r['origin']}-{r['dest']}" for r in routes]


def _rotating_groups(pool: list[str], size: int) -> itertools.cycle:
    """Yield overlapping chunks of ``size`` routes, cycling forever."""
    chunked = [pool[i:i + size] for i in range(0, len(pool), size)] or [pool]
    return itertools.cycle(chunked)


def _daily_has_full_basket(db_path: Path, index_date: str, pool: list[str]) -> bool:
    """True when today's daily_index already covers every route in the pool,
    so a restart later in the day does not re-scrape everything."""
    conn = get_connection(db_path)
    try:
        present = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT route FROM daily_index WHERE index_date = ?",
                (index_date,),
            )
        }
        return set(pool).issubset(present)
    finally:
        conn.close()


def _prime_basket(db: Path, pool: list[str]) -> None:
    """Scrape the FULL route pool once so the 36-cell basket has a baseline
    before round-robin monitoring starts."""
    index_date = date.today().isoformat()
    if _daily_has_full_basket(db, index_date, pool):
        log.info("Full basket already primed for %s — recompute only.", index_date)
        clean_raw_data(db)
        run_index(db)
        return
    log.info("=== PRIME: scraping full basket (%d routes) ===", len(pool))
    asyncio.run(run_scrape(db_path=db, routes_subset=pool))
    stats = clean_raw_data(db)
    run_index(db)
    log.info("=== PRIME done (clean=%s) — entering round-robin ===",
             stats.get("cleaned", "-"))


# ── DB access helpers ──────────────────────────────────────────────────

def _read_today(db_path: Path, index_date: str) -> tuple[float | None, float | None, dict]:
    """(today's open, today's close, per-cell {route, window: (route_index,
    route_price)}). The daily table is the latest recompute (source of truth);
    the live tape only fills in when the indexer has not run for today yet."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT open_index, close_index FROM daily_index WHERE index_date = ? LIMIT 1",
            (index_date,),
        ).fetchone()
        open_idx = row[0] if row else None
        close_idx = row[1] if row else None
        if close_idx is None:
            row = conn.execute(
                "SELECT aggregate_index FROM live_index WHERE index_date = ?"
                " ORDER BY tick_timestamp DESC LIMIT 1",
                (index_date,),
            ).fetchone()
            close_idx = row[0] if row else None

        cells: dict = {}
        for r in conn.execute(
            "SELECT route, lead_window_days, route_index, route_price"
            " FROM daily_index WHERE index_date = ?",
            (index_date,),
        ):
            cells[(r[0], r[1])] = (float(r[2]), float(r[3]))
        return open_idx, close_idx, cells
    finally:
        conn.close()


# ── Subscribers ────────────────────────────────────────────────────────

def _make_db_writer(db_path: Path):
    """Subscriber: INSERT each tick into live_index."""
    def _write(update: IndexUpdate) -> None:
        d = update.to_dict()
        conn = get_connection(db_path)
        try:
            conn.execute(
                "INSERT INTO live_index (index_date, tick_timestamp, lead_window_days,"
                " route, route_price, route_index, aggregate_index, delta, estimator)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (d["index_date"], d["tick_timestamp"], d["lead_window_days"], d["route"],
                 d["route_price"], d["route_index"], d["aggregate_index"], d["delta"],
                 d["estimator"]),
            )
            conn.commit()
        finally:
            conn.close()
    return _write


def _make_cli_subscriber():
    """Subscriber: print a stock-tape style line to the terminal."""
    def _print(update: IndexUpdate) -> None:
        sign = "+" if update.delta >= 0 else ""
        o = f" O {update.open_index}" if update.open_index is not None else ""
        c = f" C {update.close_index}" if update.close_index is not None else ""
        print(f"  TICK {update.tick_timestamp:%H:%M:%S} | APIx {update.aggregate_index}"
              f" ({sign}{update.delta}){o}{c} | mover {update.route} T+{update.lead_window_days}"
              f" idx {update.route_index}")
    return _print


# ── Core loop ──────────────────────────────────────────────────────────

def live_engine(
    db_path: Path | str | None = None,
    interval: int = 300,
    no_scrape: bool = False,
    routes: list[str] | None = None,
    rotate: int = 2,
    prime: bool = True,
    cycle_limit: int | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """Run live iterations until Ctrl-C (or ``cycle_limit`` iterations).

    ``prime`` scrapes the full route pool once at startup so the index always
    starts from a complete basket (no-op if scraping is disabled or today's
    basket already covers every route).

    ``stop_event`` lets a host process (e.g. the dashboard backend) halt the
    loop between cycles without killing the thread.
    """
    db = Path(db_path).resolve() if db_path else Path.cwd() / "data" / "apix.db"
    init_db(db)

    hub = SubscriberHub()
    hub.subscribe(_make_db_writer(db))
    hub.subscribe(_make_cli_subscriber())

    pool = routes or _all_route_keys()
    groups = _rotating_groups(pool, rotate)
    estimator = load_estimator_config().get("aggregation_estimator", "weighted_trimmed_mean")

    log.info("=== LIVE ENGINE START  db=%s  interval=%ds  mode=%s ===",
             db, interval, "reindex-only" if no_scrape else f"scrape subset({rotate})")
    log.info("Estimator: %s | pool: %d routes %s", estimator, len(pool), pool)

    if prime and not no_scrape:
        _prime_basket(db, pool)

    cycle = 0
    while (cycle_limit is None or cycle < cycle_limit) and not (stop_event and stop_event.is_set()):
        cycle += 1
        index_date = date.today().isoformat()
        started = datetime.now()
        try:
            prev_open, prev_close, prev_cells = _read_today(db, index_date)

            if not no_scrape:
                subset = next(groups)
                log.info("--- cycle %d scrape %s ---", cycle, subset)
                asyncio.run(run_scrape(db_path=db, routes_subset=subset))

            log.info("--- cycle %d clean ---", cycle)
            clean_stats = clean_raw_data(db)

            log.info("--- cycle %d index ---", cycle)
            run_index(db)

            new_open, new_close, new_cells = _read_today(db, index_date)
            if new_close is None:
                log.warning("No daily index for %s after run - skipping tick", index_date)
            else:
                delta = (new_close - prev_close) if prev_close is not None else 0.0
                mover_key, mover_val = _biggest_mover(prev_cells, new_cells)
                if mover_key is None:
                    log.warning("No cells present - nothing to emit")
                else:
                    update = IndexUpdate(
                        index_date=index_date,
                        tick_timestamp=datetime.now(),
                        route=mover_key[0],
                        lead_window_days=mover_key[1],
                        route_price=mover_val[1],
                        route_index=round(mover_val[0], 2),
                        aggregate_index=round(new_close, 2),
                        delta=round(delta, 2),
                        estimator=estimator,
                        open_index=round(new_open, 2) if new_open is not None else None,
                        close_index=round(new_close, 2),
                    )
                    hub.emit(update)

            elapsed = (datetime.now() - started).total_seconds()
            log.info("--- cycle %d done in %.1fs (clean=%s) ---",
                     cycle, elapsed, clean_stats.get("cleaned", "-"))
        except KeyboardInterrupt:
            raise
        except Exception:  # noqa: BLE001 - one bad cycle must not kill the loop
            log.exception("Cycle %d failed; continuing.", cycle)

        if cycle_limit is None or cycle < cycle_limit:
            if stop_event and stop_event.wait(interval):
                break
            time.sleep(interval)

    log.info("=== LIVE ENGINE STOP after %d cycles ===", cycle)


def _biggest_mover(prev_cells: dict, new_cells: dict) -> tuple[tuple | None, tuple | None]:
    """Cell with the largest |route_index| move; the aggregate delta is the
    headline move over the whole basket, this cell is just context."""
    moves = [
        (abs(new_cells[key][0] - prev_cells[key][0]), key)
        for key in set(prev_cells) & set(new_cells)
    ]
    if moves:
        _, key = max(moves)
        return key, new_cells[key]
    if new_cells:
        key = next(iter(new_cells))
        return key, new_cells[key]
    return None, None


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live APIx loop (scrape->clean->index->diff->emit).")
    parser.add_argument("--db", type=str, default=None, help="SQLite db (default: data/apix.db)")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between cycles (default: 300)")
    parser.add_argument("--no-scrape", action="store_true",
                        help="Skip live scraping; just clean + index + diff (offline demo)")
    parser.add_argument("--routes", type=str, default=None,
                        help="Route pool for scraping, comma-separated (default: all 12)")
    parser.add_argument("--rotate", type=int, default=2,
                        help="Scrape this many routes per cycle (default: 2)")
    parser.add_argument("--no-prime", action="store_true",
                        help="Skip the full-basket prime scrape on startup")
    parser.add_argument("--cycles", type=int, default=None,
                        help="Run N iterations then stop (default: run forever)")
    args = parser.parse_args()

    _setup_logging()
    routes = [r.strip() for r in args.routes.split(",") if r.strip()] if args.routes else None
    live_engine(
        db_path=args.db,
        interval=args.interval,
        no_scrape=args.no_scrape,
        routes=routes,
        rotate=args.rotate,
        prime=not args.no_prime,
        cycle_limit=args.cycles,
    )


if __name__ == "__main__":
    main()