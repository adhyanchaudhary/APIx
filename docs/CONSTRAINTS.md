# Project Constraints

## Technical Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| TC1 | Python ≥ 3.10 | Playwright async + typed features; installed Python 3.13.7 |
| TC2 | Headless Chromium only | No GUI browser dependency; CI-friendly |
| TC3 | SQLite as sole DB | Zero infra, single-file DB, no server |
| TC4 | Streamlit for UI | MVP speed; Python-native |
| TC5 | Max concurrent scrapers: 1 | Avoid anti-bot triggers |
| TC6 | Max requests per hour: 60 | 1 per minute, per route × window |
| TC7 | No secrets in code | Use .env + python-dotenv |
| TC8 | Windows compatible | Development environment is Windows |
| TC9 | No GPU required | All computation CPU-bound, NumPy sufficient |
| TC10 | Single-user MVP | No auth, no multi-tenancy |

---

## Data Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| DC1 | Google Flights only | MVP data source, single target |
| DC2 | Max 4 cities: DEL, BOM, BLR, MAA | Phased rollout |
| DC3 | Max 12 routes (6 pairs × 2 directions) | Manageable basket size |
| DC4 | Advance-purchase: T+1, T+7, T+30 only | MVP windows; T+15, T+45 in Phase 2 |
| DC5 | Fares in INR only | Indian domestic routes |
| DC6 | Minimum 30 data points before APIx | Statistical validity threshold |
| DC7 | Scraping frequency: once daily | Batch mode, not real-time |
| DC8 | Historical data: max 90 days | Storage + compute reasonableness |

---

## Legal / Ethical Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| LC1 | Honor robots.txt | Legal compliance |
| LC2 | No scraping login-gated content | Ethical boundary |
| LC3 | Respect ToS of Google Flights | Avoid account bans |
| LC4 | Min volume, max value | Fewest queries needed for statistically valid index |
| LC5 | Cache aggressively | Reduce repeat requests to same endpoint |
| LC6 | No personal data collected | No PII, no tracking, no cookies |
| LC7 | Source attribution in docs | Credit DGCA, Google Flights |

---

## Performance Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| PC1 | Full scrape cycle ≤ 60 min | 12 routes × 3 windows × 3600s/h ÷ 3600s/h = 12min budget |
| PC2 | Dashboard load ≤ 5s cold, ≤ 1s cached | Good UX for demo |
| PC3 | DB size ≤ 500 MB at 90 days | SQLite pragmatic limit |
| PC4 | Peak RAM ≤ 2 GB | Laptop-friendly |
| PC5 | Disk I/O minimal during scrape | SQLite WAL mode for writes |

---

## Testing Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| TC-T1 | Tests runnable offline | No live scraping in CI |
| TC-T2 | Unit tests for: cleaner, indexer, models | Core logic verified |
| TC-T3 | Playwright tests use recorded fixtures | Deterministic |
| TC-T4 | Coverage ≥ 80% on src/core modules | Quality gate |
| TC-T5 | pytest as test framework | Python standard |

---

## Deployment Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| DP1 | Local first | No cloud deployment for MVP |
| DP2 | Docker optional | Nice-to-have, not mandatory |
| DP3 | Requirements.txt pinned | Reproducible installs |
| DP4 | Windows + macOS primary | Developer machines |
| DP5 | No long-running daemon in MVP | Scheduled task / cron sufficient |

---

## APIx Formula Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| AX1 | Base period = first available date | Index = 100 on day 1 |
| AX2 | Weight = proportional to DGCA traffic data | Representative basket |
| AX3 | Index rounded to 2 decimal places | Convention |
| AX4 | Missing route → skip, don't impute | Transparency |
| AX5 | Index normalised: basket = 100 on base day | Standard index convention |

---

*Update these constraints as design evolves. All MVP constraints are tentative.*