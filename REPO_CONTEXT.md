# APIx — Repository Context & Problem Description

> Read this file first. It describes what the project is, what problem it
> solves, and how the code is organised. Use it as an orientation map for any
> task in this repo.

---

## 1. What this project is

**APIx (Airfare Price Index)** is an automated pipeline that collects, cleans,
and indexes **real-time Indian domestic airfare data** and publishes a daily
**Airfare Price Index** (APIx). It is built for SIH-2026 on behalf of a
MoSPI/NSO + RBI use-case.

### The problem it solves

- Indian airfares swing **200–400% within a single day** due to dynamic pricing.
- The current CPI method collects airfares **manually** from a few ticketing
  outlets — this misses online-only deals, OTA coupons, dynamic surcharges, and
  is not representative (90%+ of fares are now sold online).
- RBI needs **high-frequency, accurate price data** for monetary policy.
- Goal: `|indexed price − DGCA reported price| < 5%` mean absolute deviation.

### MVP scope (per `docs/PRD.md`)

- Single data source: **Google Flights** (scraped via Playwright).
- 4 metro cities: `DEL`, `BOM`, `BLR`, `MAA` → **12 directional routes**
  (6 pairs × both directions).
- 3 advance-purchase (lead) windows: **T+1, T+7, T+30** days.
- Fares in INR only. Daily batch scraping (one scrape per route × day).
- Storage: **SQLite** (single-file, zero-infra). Dashboard: **Streamlit** (not
  yet implemented). FastAPI API is a Phase 2+ item (not implemented).

---

## 2. The pipeline (end-to-end flow)

```
scrape → clean → index → (dashboard / report)
  src/scraper    src/cleaner    src/indexer      docs + tests
```

1. **Scrape** (`src/scraper/`) — Playwright + headless Chromium drives Google
   Flights, parses the flight-card `aria-label` text, and writes validated rows
   to the `raw_flights` table.
2. **Clean** (`src/cleaner/clean.py`) — reads `raw_flights`, removes
   duplicates, drops/fills null fares, flags IQR outliers, computes a
   `quality_score`, and appends to `cleaned_flights`.
3. **Index** (`src/indexer/`) — collapses fares to one price per cell
   (route × window × date), builds the **36-cell weighted basket index**
   (Laspeyres-style, base = 100 on first date), then rolls daily values into
   `weekly_index` and `monthly_index` tables.
4. **Consumption** — estimator stability report (`report.py`), offline tests,
   and (future) Streamlit dashboard + FastAPI.

### Index formula in one line

```
index(t, r, w) = price(t, r, w) / price(base_date, r, w) × 100
APIx(t)        = Σ over present cells  index(t, r, w) × route_weight × window_weight
```

- Cell price = **median** fare on (route, window, date) by default (`min` also
  supported).
- Missing dates are **carried forward** from the last known fare (so coverage
  gaps don't distort the headline).
- A cell absent on the shared base date uses its **own first fare** and joins
  the basket at 100 on its start date.
- Aggregation estimator is pluggable: `weighted_mean` (Laspeyres),
  `weighted_trimmed_mean`, or `weighted_median`. Default (config):
  `weighted_trimmed_mean` with 10% trim.

---

## 3. Directory map

```
APIx/
├─ REPO_CONTEXT.md            ← this file (the problem + orientation map)
├─ problem statement.txt      ← currently EMPTY (placeholder — no content yet)
├─ requirements.txt           ← 11 pinned deps (playwright, pandas, numpy,
│                                pydantic, pyyaml, apscheduler, streamlit,
│                                plotly, python-dotenv, pytest, pytest-cov)
├─ .gitignore                 ← excludes .env, venv/, data/*.db, secrets, etc.
│
├─ config/
│  ├─ routes.yaml             ← cities, 12 routes, horizon_days, lead_windows
│  ├─ scraper.yaml            ← rate limit, retries, browser, timeouts
│  └─ indexer.yaml            ← index settings, weights, estimators, cleaning
│
├─ src/
│  ├─ walk_data_core.py       ← line-explanation data for docs (files 01-08)
│  ├─ walk_data_scraper.py    ← line-explanation data for docs (scraper files)
│  ├─ walk_data_cleaner.py    ← line-explanation data for docs (cleaner files)
│  ├─ walk_data_indexer.py    ← line-explanation data for docs (indexer files)
│  ├─ generate_walkthroughs.py← builds docs/walkthroughs/*.html from real code
│  ├─ test_scraper.py         ← dev-only single-route live scraper test
│  │
│  ├─ models/
│  │  ├─ schemas.py           ← Pydantic: FlightRecord, RouteConfig, CityConfig, IndexEntry
│  │  └─ price_predictor.py   ← Phase-2 TensorFlow fare classifier (NOT wired into MVP)
│  │
│  ├─ storage/
│  │  └─ database.py          ← SQLite: 5 table DDLs, init_db, get_connection
│  │                            DB file: data/apix.db
│  │
│  ├─ scraper/
│  │  ├─ base.py              ← abstract BaseScraper contract
│  │  ├─ driver.py            ← Playwright browser-context launcher (config-driven)
│  │  ├─ google_flights.py    ← the scraper: URL build, aria-label parse, retries
│  │  ├─ run_scrape.py        ← batch runner: 12 routes × horizon days → raw_flights
│  │  └─ run_smoke.py         ← one-route live smoke test (DEL→BOM)
│  │
│  ├─ cleaner/
│  │  ├─ clean.py             ← PRODUCTION cleaner: dedup → nulls → IQR outlier → quality
│  │  ├─ pipeline.py          ← modular cleaner functions + SQLAlchemy writer
│  │  ├─ mock_data.py         ← fake raw data with injected defects (for testing)
│  │  ├─ check_db.py          ← ad-hoc diagnostics: raw vs cleaned, outliers, nulls
│  │  ├─ test_run.py          ← runs pipeline on mock data, prints validation summary
│  │  └─ flights.db           ← scratch SQLite generated by mock tests (not tracked)
│  │
│  ├─ indexer/
│  │  ├─ api_index.py        ← core math: route_price_per_day, compute_daily/rolling_index, write_index
│  │  ├─ run_index.py        ← CLI: cleaned_flights → daily/weekly/monthly tables
│  │  ├─ estimators.py       ← weighted_mean / weighted_trimmed_mean / weighted_median
│  │  ├─ metrics.py          ← stability, route_sensitivity, weight_elasticity
│  │  ├─ synthetic.py        ← seeded synthetic cleaned data for estimator research
│  │  └─ report.py           ← empirical estimator-comparison report (CLI)
│  │
│  └─ dashboard/
│     └─ app.py              ← Streamlit app: T+1 / T+7 / T+30 tabs with pie
│                                charts, index trends, and data tables
│
├─ tests/
│  ├─ fixtures/sample_cleaned.csv  ← offline index-test fixture (3 routes × 2 windows)
│  ├─ test_indexer.py       ← main index-math + end-to-end suite
│  ├─ test_estimators.py    ← unit tests for the 3 aggregation estimators
│  └─ test_metrics.py       ← stability stats, synthetic data, sensitivity tests
│
└─ docs/
   ├─ PRD.md                ← Product Requirements Document
   ├─ CONSTRAINTS.md        ← technical / data / legal / perf / test constraints
   ├─ *.html                ← flowcharts, decks, quizzes (presentation material)
   └─ walkthroughs/         ← generated line-by-line code walkthroughs (29 files)
```

---

## 4. Database schema (SQLite: `data/apix.db`)

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `raw_flights` | scraped flights, one row per flight | route, origin, dest, carrier, flight_no, depart/arrive_time, duration_mins, stops, base_fare, taxes, total_fare, currency, lead_window_days, scrape_timestamp |
| `cleaned_flights` | cleaned + deduped + flagged | raw cols + `quality_score`, `is_outlier`, `dedup_hash`, `extraction_batch_id` |
| `daily_index` | daily cell + composite index | index_date, lead_window_days, route, weight, route_price, route_index, aggregate_index, base_period |
| `weekly_index` | 7-day rolling of daily | same shape as daily_index |
| `monthly_index` | 30-day rolling of daily | same shape as daily_index |

---

## 5. Config behaviour (what each YAML controls)

- **`config/routes.yaml`** — the city set, the 12 directional routes, `horizon_days`
  (30 — how many departure dates each scrape run covers), lead windows.
- **`config/scraper.yaml`** — `max_requests_per_hour` (60), random delay
  3–8 s, `max_retries` (3) with exponential backoff, headless flag,
  viewport, UA, timeouts.
- **`config/indexer.yaml`** — index formula knobs: `base_period`, `round_to`,
  `active_windows`, `aggregation_estimator` (+`trim_frac`), `rolling_estimator`
  (+`trim_frac`), `route_price_method` (median/min), `window_weights`
  (0.20 / 0.30 / 0.50 for t+1/t+7/t+30), route `weights` (DGCA share
  approximation, normalised to 1.0), and `cleaning` (IQR outlier method +
  null-fare action).

---

## 6. Commands (how to run things)

> Always run from the repo root. `.env` is expected to exist (see walkthrough
> 01) — it configures Playwright browser storage / logging; the code uses
> sensible defaults if missing.

```powershell
# init the DB (creates data/apix.db + tables)
python src/storage/database.py

# generate the 29 line-by-line HTML walkthroughs
python src/generate_walkthroughs.py

# scrape one route for a live smoke test (hits Google Flights)
python -m src.scraper.run_smoke

# full scrape of all 12 routes × 30-day horizon (slow, live)
python -m src.scraper.run_scrape
python -m src.scraper.run_scrape --date 2026-09-15

# clean raw_flights → cleaned_flights
python src/cleaner/clean.py

# build daily/weekly/monthly indices from cleaned_flights
python -m src.indexer.run_index
python -m src.indexer.run_index --db data/custom.db

# estimator stability report (real data, falls back to synthetic)
python -m src.indexer.report
python -m src.indexer.report --synthetic

# launch the Streamlit dashboard (T+1 / T+7 / T+30 tabs)
streamlit run src/dashboard/app.py

# run the offline test suite
python -m pytest tests/ -q
python -m pytest tests/ -q --cov=src --cov-report=term-missing
```

---

## 7. Testing strategy (offline-first)

- Tests never hit the live network — index tests use
  `tests/fixtures/sample_cleaned.csv`; synthetic data comes from
  `src/indexer/synthetic.py`.
- Coverage is expected on core logic (`cleaner`, `indexer`, `models`) —
  target ≥ 80% per `CONSTRAINTS.md`.
- The scraper is tested via manual smoke runs / recorded fixtures only.

---

## 8. Current status and known gaps (as of the last commit)

**Implemented (Phases 0–3, mostly complete):**

- [x] Config layer (routes / scraper / indexer YAML) + Pydantic schemas.
- [x] SQLite storage layer (5 tables).
- [x] Playwright Google Flights scraper (aria-label parsing, retries, rate limit).
- [x] Production cleaning pipeline (`clean.py`) + modular variant (`pipeline.py`).
- [x] Index builder with pluggable estimators, 36-cell basket, carry-forward,
      rolling week/month indices.
- [x] 29-file HTML code walkthrough generator (`src/generate_walkthroughs.py`).
- [x] Offline test suites for indexer, estimators, metrics.
- [x] Streamlit dashboard (`src/dashboard/app.py`) — per-window tabs (T+1 / T+7 /
      T+30) with carrier/route pie charts, daily·weekly·monthly APIx and
      route-level index trend graphs, avg-fare bar chart, and index + cleaned
      data tables; sidebar can load a 30-day synthetic demo dataset.

**Not yet done / gaps:**

- [ ] `problem statement.txt` is empty — the problem write-up has not been
      pasted in yet.
- [ ] **FastAPI REST endpoint** for NSO/RBI consumption (FR6).
- [ ] **Scheduler** (APScheduler / cron) for the daily run (FR1.1, PRD P5).
- [ ] `.env` file — not present in the repo (intentionally gitignored); expected
      by the walkthrough docs and `python-dotenv` usage.
- [ ] DGCA back-test (≥ 30 days of validated results, G4) — no comparison code yet.
- [ ] `price_predictor.py` imports `tensorflow`, which is NOT in
      `requirements.txt`; it is Phase-2-only and intentionally unwired.
- [ ] Dashboard needs live scraped data to be meaningful — currently demoed via
      the synthetic seed; a real scrape (`python -m src.scraper.run_scrape`)
      fills it for real.

---

## 9. Quick reference — key files the problem-solving lives in

| Concern | File |
|---------|------|
| Index math (bread-and-butter) | `src/indexer/api_index.py` |
| Estimators | `src/indexer/estimators.py` |
| Index entry point | `src/indexer/run_index.py` |
| Cleaning (production) | `src/cleaner/clean.py` |
| Cleaner modular | `src/cleaner/pipeline.py` |
| Scraper | `src/scraper/google_flights.py` |
| Scraper runner | `src/scraper/run_scrape.py` |
| DB layer + schema | `src/storage/database.py` |
| Pydantic models | `src/models/schemas.py` |
| Tests | `tests/test_indexer.py`, `tests/test_estimators.py`, `tests/test_metrics.py` |
| Docs | `docs/PRD.md`, `docs/CONSTRAINTS.md` |

---

*Keep this file updated as the codebase evolves. If a task changes the schema,
the index formula, the pipeline stages, or adds major modules, update the
sections above.*