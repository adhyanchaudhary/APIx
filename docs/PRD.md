# Product Requirements Document (PRD)

## Real-time Airfare Price Index (APIx) Platform

**Project:** SIH-2026 | **Status:** Draft v1.0 | **Date:** 2026-09-04

---

## 1. Executive Summary

The Ministry of Statistics and Programme Implementation (MoSPI) currently measures airfare inflation through **manual price collection** from a limited set of ticketing outlets. Over 90% of domestic airfares are now sold online through airline websites and OTAs, making the current CPI method **unrepresentative** of actual consumer fares.

This platform automates the collection, cleaning, and indexing of real-time airfare data for major Indian city-pairs, producing a **Real-time Airfare Price Index (APIx)** for use by NSO and RBI.

**MVP Scope:** Google Flights as the sole data source, 4 Indian metro cities, 3 advance-purchase windows.

---

## 2. Problem Statement (Recap)

- Airfares in India vary **200-400%** within a single day due to dynamic pricing.
- Manual CPI collection cannot capture route-specific, time-sensitive, dynamic pricing.
- Current model misses online-only deals, dynamic surcharges, and OTA-stack coupons.
- RBI needs **high-frequency, accurate** price data to set monetary policy.

---

## 3. Goals

### 3.1 Business Goals
| ID | Goal | Metric |
|----|------|--------|
| G1 | Mirror real consumer airfare prices | Mean absolute deviation < 5% vs DGCA monthly data |
| G2 | Automate data collection end-to-end | Zero manual data entry |
| G3 | Power daily/weekly/monthly index | APIx computed at 3 frequencies |
| G4 | Back-test against DGCA data | ≥ 30 days of validated results |

### 3.2 Non-Goals (MVP)
- ❌ Multi-source scraping (airlines + OTAs) — deferred to Phase 2
- ❌ All 42+ DGCA routes — limited to 6 city-pairs for MVP
- ❌ Mobile app — web dashboard only
- ❌ Live streaming — daily batch only

---

## 4. Scope

### 4.1 Data Sources (MVP)
- **Google Flights** (aggregates most IndiGo, Air India, Akasa, SpiceJet, etc. pricing)
- Future: MakeMyTrip, Ixigo, EaseMyTrip, Cleartrip, Goibibo

### 4.2 City Coverage (MVP)
| City | Code |
|------|------|
| New Delhi | DEL |
| Mumbai | BOM |
| Bengaluru | BLR |
| Chennai | MAA |

### 4.3 City-Pair Basket
| Route | Direction |
|-------|-----------|
| DEL ↔ BOM | both |
| DEL ↔ BLR | both |
| DEL ↔ MAA | both |
| BOM ↔ BLR | both |
| BOM ↔ MAA | both |
| BLR ↔ MAA | both |

### 4.4 Advance-Purchase Windows (Lead Time)
| Window | Label |
|--------|-------|
| T + 1 day | 1-day lead |
| T + 7 days | 1-week lead |
| T + 15 days | 2-week lead |
| T + 30 days | 1-month lead |
| T + 45 days | 45-day lead |

*(MVP may start with T+1, T+7, T+30 only; full set in Phase 2.)*

---

## 5. Functional Requirements

### FR1 — Web Scraping Engine (Playwright + Python)
- **FR1.1** Schedule daily extraction from Google Flights for each city-pair × lead-time window.
- **FR1.2** Handle JavaScript-rendered SPA pages.
- **FR1.3** Capture per-flight: origin, destination, carrier, dep/arr time, base fare, taxes, total fare, flight number, stops, duration.
- **FR1.4** Select **lowest fare per route** and per carrier.
- **FR1.5** Rate-limiting: max N requests/hour, respectful delays between requests.
- **FR1.6** Robots.txt compliance and Terms of Service awareness.

### FR2 — Data Cleaning Pipeline (Pandas)
- **FR2.1** Remove outliers (IQR / Z-score based, configurable threshold).
- **FR2.2** Handle missing values (dropping + forward-fill strategies).
- **FR2.3** Flag and exclude sold-out/cancelled flights.
- **FR2.4** Normalise currency, strip text, cast types.
- **FR2.5** De-duplicate identical (route, date, flight) entries.
- **FR2.6** Separate base fare vs taxes/fees.

### FR3 — Index Construction (APIx)
- **FR3.1** Compute daily, weekly, monthly airfare indices.
- **FR3.2** Weight city-pairs per DGCA passenger traffic data.
- **FR3.3** Produce both **route-level** and **aggregate** indices.
- **FR3.4** Basket-based construction (Laspeyres-style base-period index).

### FR4 — Dashboard (Streamlit)
- **FR4.1** Live daily Airfare Price Index display.
- **FR4.2** Price trend line charts by route.
- **FR4.3** Sector-wise heatmap.
- **FR4.4** Lead-time elasticity curve (price vs advance window).
- **FR4.5** Carrier-wise comparison charts.
- **FR4.6** Raw-data explorer table with filters.

### FR5 — Data Storage
- **FR5.1** SQLite for MVP (0-dependency, portable).
- **FR5.2** Schema: `raw_flights`, `cleaned_flights`, `daily_index`, `weekly_index`, `monthly_index`.

### FR6 — API (For NSO / RBI Consumption)
- **FR6.1** REST endpoints (Future / FastAPI) to serve index data.
- **FR6.2** Export to CSV / JSON.

---

## 6. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|-------------|-----------|
| US1 | Data Analyst | scrape flight prices daily | I have up-to-date fare data |
| US2 | Data Scientist | automatically clean scraped data | I don't hand-edit raw quotes |
| US3 | Economist | compute APIx | I can study inflation trends |
| US4 | Dashboard User | view price trends graphically | I can spot spikes/surges |
| US5 | RBI Official | consume index via API | I can feed it into monetary models |
| US6 | Administrator | schedule runs and view logs | I know the pipeline is healthy |

---

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Performance — scrape cycle | ≤ 45 min for full basket/day |
| NFR2 | Performance — dashboard load | < 3s startup, < 1s chart render |
| NFR3 | Availability of data | ≥ 99% of scheduled runs succeed |
| NFR4 | Data accuracy vs DGCA | MAE < 5% |
| NFR5 | Maintainability | Modular packages, typed, documented |
| NFR6 | Testability | ≥ 80% coverage on core logic |
| NFR7 | Security | No secrets in repo, .env for keys |
| NFR8 | Portability | Run on Windows/macOS/Linux (Docker-ready) |

---

## 8. System Architecture (MVP)

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Playwright  │   │   Pandas     │   │   APIx       │   │  Streamlit  │
│  Scraper     │──▶│  Cleaner     │──▶│  Builder     │──▶│  Dashboard  │
│  (python)    │   │  (pandas)    │   │  (numpy)     │   │  (frontend) │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
        │                 │                │                  │
        ▼                 ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                               SQLite                                │
│         raw_flights │ cleaned_flights │ *_index tables              │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown
1. **Scraper** (`src/scraper/`) — Playwright, headless Chromium, per-route crawler, schedule via scheduler.
2. **Cleaner** (`src/cleaner/`) — Pandas transforms, outlier detection, dedup, standardisation.
3. **Index builder** (`src/indexer/`) — Weighted basket index math.
4. **Dashboard** (`src/dashboard/`) — Streamlit app reading from SQLite.
5. **Scheduler** (`src/scheduler.py`) — APScheduler or cron for daily runs.
6. **Config** (`config/`) — YAML/JSON for routes, windows, weights, thresholds.

---

## 9. Data Model

### `raw_flights`
```
id, scrape_date, route, origin, dest,
carrier, flight_no, depart_time, arrive_time,
duration_mins, stops, base_fare, taxes, total_fare,
currency, lead_window_days, scrape_timestamp
```

### `cleaned_flights`
Same as `raw_flights` + cleaning metadata:
```
quality_score, is_outlier, dedup_hash, extraction_batch_id
```

### `daily_index` / `weekly_index` / `monthly_index`
```
id, index_date, route, weight, route_price, route_index,
aggregate_index, base_period
```

---

## 10. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Scraping | Python 3.11+, Playwright | JS rendering, robust vs Selenium |
| Data | Pandas, NumPy | Industry-standard cleaning |
| Storage | SQLite | Zero-config, portable |
| Dashboard | Streamlit | Python-native, fast to build |
| Scheduler | APScheduler | In-process daily jobs |
| (Future API) | FastAPI + Pydantic | Async, auto-docs |

---

## 11. Milestones & Timeline

| Phase | Deliverable | Est. Duration |
|-------|-------------|---------------|
| P0 | Planning docs, scaffold, env setup | Day 1 |
| P1 | Playwright scraper MVP (Google Flights) | Days 2–4 |
| P2 | Cleaning pipeline + SQLite storage | Days 4–5 |
| P3 | Index builder | Day 6 |
| P4 | Streamlit dashboard | Days 7–8 |
| P5 | Scheduling + logging + error handling | Day 9 |
| P6 | Testing + back-test vs DGCA | Days 10–12 |

---

## 12. Acceptance Criteria

- [ ] Pipeline runs end-to-end: scrape → clean → index → dashboard.
- [ ] At least 40 scraped flights captured for a single run.
- [ ] Data cleaned of outliers and missing values programmatically.
- [ ] Daily APIx computed and stored in SQLite.
- [ ] Streamlit dashboard renders trends, heatmap, elasticity curve.
- [ ] ≥ 30 days back-test vs DGCA monthly data documented.
- [ ] Test suite with bundled fixtures (no live network in CI).
- [ ] README with setup + run instructions.

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Google Flights anti-bot / CAPTCHA | Rate limiting, human-like delays, retry with backoff, session management |
| Terms of service / ToS change | Ethical scraping policy, robots.txt check, keep volumes modest |
| Data inconsistency / missing values | Robust cleaning heuristics + fallback pricing |
| Google Flights structure change | Isolated scraper module, easy to swap to OTAs |
| OTA coupons pricing skew | Compare lowest OTA fare vs published; MVP uses Google aggregate |

---

## 14. Open Questions

1. Should the MVP include a weighted basket or simple average for APIx?
2. Is PowerBI/Tableau preferred over Streamlit by the stakeholder?
3. What is the acceptable max request rate to avoid ToS breach?
4. Do we need real-time "intra-day" scraping or is daily batch sufficient for Phase 1?

---

*End of PRD — next: Constraints file → HTML implementation plan ←*