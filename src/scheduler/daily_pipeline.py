"""Automated daily E2E pipeline: scrape -> clean -> index -> data/e2e_real.db.

Runs the full APIx pipeline once per day in the background and stores results
in the *real* end-to-end database (``data/e2e_real.db``), which the Streamlit
dashboard auto-detects as "Benchmark Dataset (data/e2e_real.db)".

Modes
-----
Windows Task Scheduler (recommended — true background, survives reboot,
no console kept open). Registers a daily task that invokes ``--run-now``:

    python -m src.scheduler.daily_pipeline --install-task            # daily 06:00
    python -m src.scheduler.daily_pipeline --install-task --time 05:30
    python -m src.scheduler.daily_pipeline --uninstall-task

Persistent APScheduler loop (keeps the console open):

    python -m src.scheduler.daily_pipeline --schedule                # daily 06:00
    python -m src.scheduler.daily_pipeline --schedule --run-now      # run once, then keep scheduling
    python -m src.scheduler.daily_pipeline --schedule --time 05:30

One-shot manual run (what the scheduled task executes):

    python -m src.scheduler.daily_pipeline --run-now
    python -m src.scheduler.daily_pipeline --run-now --db data/custom.db
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _REPO_ROOT / "logs"
E2E_DB_PATH = _REPO_ROOT / "data" / "e2e_real.db"
TASK_NAME = "SIH-APIx-Daily"
DEFAULT_TIME = "06:00"


def _setup_logging() -> logging.Logger:
    log = logging.getLogger("daily_pipeline")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    _LOG_DIR.mkdir(exist_ok=True)
    fileh = RotatingFileHandler(
        _LOG_DIR / "daily_pipeline.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    fileh.setFormatter(fmt)
    # Attach to both this logger and root so submodule logs land in the same file.
    log.addHandler(stream)
    log.addHandler(fileh)
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(stream)
        root.addHandler(fileh)
    return log


def run_daily_pipeline(db_path: Path | str | None = None, scrape_date: date | None = None) -> dict:
    """Execute the full day's pipeline into the E2E database and return stats."""
    from src.scraper.run_scrape import run_scrape
    from src.cleaner.clean import clean_raw_data
    from src.indexer.run_index import run_index

    db = Path(db_path).resolve() if db_path else E2E_DB_PATH
    target: date = scrape_date or date.today()
    log = _setup_logging()

    log.info("=== DAILY E2E PIPELINE START  db=%s  date=%s ===", db, target.isoformat())
    started = datetime.now()

    # 1. Scrape every route x lead window for the target date.
    log.info("--- STAGE 1/3: SCRAPE ---")
    asyncio.run(run_scrape(target, db))

    # 2. Clean raw rows into cleaned_flights (dedup, IQR outliers, quality).
    log.info("--- STAGE 2/3: CLEAN ---")
    clean_stats = clean_raw_data(db, scrape_date=target.isoformat())

    # 3. Rebuild daily / weekly (7-day) / monthly (30-day) rolling indices.
    log.info("--- STAGE 3/3: INDEX ---")
    index_stats = run_index(db)

    stats = {
        "db": str(db),
        "date": target.isoformat(),
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now().isoformat(timespec="seconds"),
        "clean": clean_stats,
        "index": index_stats,
    }
    log.info("=== DAILY E2E PIPELINE DONE  %s ===", stats)
    return stats


# ── Persistent APScheduler loop ──────────────────────────────────────────────

def _schedule_loop(time_str: str, run_now: bool) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    hour, minute = (int(x) for x in time_str.split(":"))
    log = _setup_logging()
    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_daily_pipeline,
        trigger,
        id="daily_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    from datetime import datetime, timezone

    next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    log.info("Scheduled: daily at %s | next run %s | db %s", time_str, next_run, E2E_DB_PATH)
    if run_now:
        try:
            run_daily_pipeline()
        except Exception:
            log.exception("Immediate run failed; continuing schedule.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


# ── Windows Task Scheduler (true background) ────────────────────────────────

def _install_task(time_str: str, db: Path) -> None:
    script = sys.executable
    task_cmd = f'"{script}" -m src.scheduler.daily_pipeline --run-now --db "{db}"'
    schtasks = (
        f'schtasks /Create /F /TN "{TASK_NAME}" /SC DAILY /ST {time_str} '
        f'/TR "{task_cmd}" /RL LIMITED'
    )
    print(f"Registering scheduled task '{TASK_NAME}' ...")
    print(f"  Runs daily at {time_str}")
    print(f"  Command: {task_cmd}")
    print(f"  Working dir: {_REPO_ROOT}")
    subprocess.run(schtasks, shell=True, cwd=str(_REPO_ROOT), check=True)
    print(f"\nTask '{TASK_NAME}' installed. Verify with:\n  schtasks /Query /TN {TASK_NAME}")


def _uninstall_task() -> None:
    schtasks = f'schtasks /Delete /F /TN "{TASK_NAME}"'
    print(f"Removing scheduled task '{TASK_NAME}' ...")
    subprocess.run(schtasks, shell=True, cwd=str(_REPO_ROOT), check=True)
    print(f"Task '{TASK_NAME}' removed.")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated daily APIx E2E pipeline (scrape -> clean -> index)."
    )
    parser.add_argument("--db", type=str, default=None,
                        help=f"Target SQLite db (default: {E2E_DB_PATH})")
    parser.add_argument("--date", type=str, default=None,
                        help="Scrape date YYYY-MM-DD (default: today; for back-fill runs)")
    parser.add_argument("--run-now", action="store_true",
                        help="Run the pipeline once immediately")
    parser.add_argument("--schedule", action="store_true",
                        help="Keep an APScheduler loop and run daily (console stays open)")
    parser.add_argument("--time", type=str, default=DEFAULT_TIME,
                        help="Daily run time HH:MM (default: %(default)s)")
    parser.add_argument("--install-task", action="store_true",
                        help="Register a Windows daily scheduled task (true background)")
    parser.add_argument("--uninstall-task", action="store_true",
                        help="Remove the Windows scheduled task")
    args = parser.parse_args()

    db = Path(args.db).resolve() if args.db else E2E_DB_PATH

    if args.install_task:
        _install_task(args.time, db)
        return
    if args.uninstall_task:
        _uninstall_task()
        return
    if args.schedule:
        _schedule_loop(args.time, args.run_now)
        return

    # Default: one-shot run (this is what the scheduled task executes).
    scrape_date = date.fromisoformat(args.date) if args.date else None
    stats = run_daily_pipeline(db, scrape_date)
    print("\nPipeline finished. Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()