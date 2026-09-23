# APIx Index Methodology — Design Intent & Known Issues

Status: **as-is documentation** (design intent is authoritative). The fix
plan in §4 has been **implemented** (all three steps, 74 tests pass).

---

## 1. Design intent: a volatility-based live index

The live index exists to keep the **daily** APIx accurate when fares move
rapidly within a day, so the index is a defensible input to an inflation
figure. It is **not** a rate-limit workaround.

The intended flow:

1. **Prime** — the index is first computed over the **full basket**
   (all 12 routes x all 3 booking windows: t+1, t+7, t+30), establishing a
   complete baseline.
2. **Monitor** — a loop runs continuously over a rotating **subset of
   routes/windows**, re-scraping and refreshing those cell prices, often and
   repeatedly.
3. **Recompute** — after each subset refresh, the **full-basket index is
   recomputed** from the updated prices.
4. **Payoff** — rapid same-day fare changes are caught by the frequent subset
   passes, so the day's index (open frozen, close advancing) stays accurate
   under fast-moving fares.

The Google Flights rate cap (<= 60 req/h) is **only an operational constraint**
on how large/frequent the subset loop can be — it is not the reason the loop
exists.

Note on the current implementation: `live_engine` (src/live/run_live.py)
already recomputes the full basket each cycle via `run_index()`. A **prime
pass** now scrapes the full route pool once at startup (skipped via
`--no-prime`, or automatically when today's basket is already complete) so
the index never starts from a half-empty basket, and only then does the
rotating subset loop begin. The subset rotation remains a fixed time-slice
(rotate=N routes every `interval` s), not adaptive to volatility.

---

## 2. How the whole pipeline works

1. **Scrape** — Playwright/Chromium hits Google Flights for the route/window
   cells, landing raw fares in `raw_flights`. Each live cycle scrapes a
   rotating subset (see Section 1).
2. **Clean** — `clean_raw_data()` excludes outlier fares (is_outlier) and
   appends new raw rows to `cleaned_flights`.
3. **Collapse** — `route_price_per_day()` reduces each (route, window, date)
   cell to a single **median fare** (robust center; `min` available), carrying
   fares forward across gaps between observations.
4. **Route index** — each cell is priced against its own base: the fare on the
   shared base date (data start) when the cell existed then;
   `route_index = price / base * 100`.
5. **Composite** — `compute_daily_index()` blends every cell index into one
   daily headline APIx using **route weight x window weight**, via a robust
   estimator (weighted trimmed-mean default), and stamps it on every row of
   the date as open = close = aggregate.
6. **Freeze/open** — `write_index()` freezes the day's **open once** at the
   first observed composite (per DATE, not per route) and lets the **close**
   advance each cycle.
7. **Rolling** — `compute_rolling_index()` builds weekly (7-day) and monthly
   (30-day) series as rolling means of the daily closes (min_periods=1).
8. **Ticks** — the live engine diffs each cycle's headline against the
   previous, emits one `IndexUpdate` (biggest-mover cell as context) through a
   pub/sub hub; DB-writer and CLI subscribers persist it to `live_index` and
   print a stock-tape line.
9. **Dashboard** — a Streamlit app reads SQLite directly: cleaned views,
   composite trend, daily/weekly/monthly charts, and a live-tape fragment that
   refreshes every 10 s (engine state, tick count, session open/close, latest
   headline, day movement).

Every index run is a **full rebuild** from `cleaned_flights`, so index tables
are idempotent and self-healing (only `open_index` preserves prior state).

---

## 3. Known methodology defects (filed, NOT yet fixed)

### 3a. Why a cell can be empty despite forward-fill

`_carry_forward_missing_dates` (src/indexer/api_index.py) fills only the
calendar span `[first_obs, last_obs]` of each cell:

```python
calendar = pd.date_range(start=g.index.min(), end=g.index.max(), freq="D")
g = g.reindex(calendar).ffill()
```

A cell is **empty on date D** in three cases:

1. **D before the cell's first observation** — deliberately no phantom dates.
2. **The cell was never observed at all** — no span exists.
3. **D after the cell's last observation** — the fill stops at `max()`; it
   does NOT extend to today. **This is the live killer.**

Proof (e2e data): `BOM-MAA` t+1 and t+30 last observed 2026-09-16 →
absent from the index on 09-17/18/19, while `BOM-MAA` t+7 (observed daily)
stays present. A route that misses a scrape day silently drops its cells from
the composite and its weights redistribute.

### 3b. Late cells join at 100 (mixed bases)

A cell absent on the shared base date uses its **own first fare** as its base
(compute_daily_index fallback). Its first `route_index` is therefore exactly
**100.0 regardless of the cell's true relative price** (a genuinely ~130-price
premium debuts at 100; a ~70-discount cell also debuts at 100).

Effect: the composite's level becomes a blend of cells measured against
different reference points — a mixed-base index where basket growth
contaminates the level over time.

### 3c. Implicit reweighting of missing cells (mixed composition)

Missing cells are skipped in `compute_daily_index` and the aggregate
renormalizes over the survivors (`weighted_mean = sum(v*w)/sum(w)`, so the
denominator is the weight of *present* cells only). A missing cell's weight is
silently redistributed onto the others. When missing-ness is driven by the
rotating scrape schedule (systematic, not random), day-to-day coverage changes
move the headline even when prices are flat.

---

## 4. Fix plan — IMPLEMENTED (all three steps; 74 tests pass)

### Step 1 — Carry prices to the present (fixes empty cells) ✓
- `_carry_forward_missing_dates` in `src/indexer/api_index.py` reindexes each
  cell to the **global** calendar `[global_min, global_max]` instead of
  `[min, max]`, then `ffill()`; leading (pre-first-obs) NaNs are dropped so
  "no phantom dates" stays true.
- A `price_obs_date` column rides alongside the fare (the last date each value
  was REALLY observed), making imputed rows identifiable.
- Result: cells keep their last fare through today; the composite stops
  jumping for coverage reasons.
- Tests: `test_cell_carries_forward_to_global_max_not_cell_max`,
  `test_price_obs_date_stamped_on_real_observations`.

### Step 2 — Make coverage/staleness visible (fixes *silent* reweighting) ✓
- `INDEX_COLUMNS` extended with `price_obs_date`; migration in
  `_ensure_index_columns` in `src/storage/database.py` adds
  `price_obs_date TEXT` (legacy rows back-filled NULL). Weekly/monthly carry
  the column but leave it NULL (rolling rows don't hold a real obs date).
- Dashboard live tape (`src/dashboard/app.py`) gains **Basket Coverage %**
  (present cells / `TOTAL_BASKET_CELLS` = 36) and **Max staleness**
  (days since `price_obs_date`); a `st.warning` flags when staleness exceeds
  the cap.
- Config `stale_cap_days` — **decision: policy (b), keep but flag** (the
  staleness metric turns orange; no deterministic drop).
- Tests: `test_stale_cap_loads_from_config`,
  `test_daily_rows_carry_price_obs_date_rolling_rows_null`,
  `test_cell_staleness_days_measures_carry_forward`,
  `test_init_db_migrates_legacy_index_tables_adds_price_obs_date`.

### Step 3 — Chain-link late cells (fixes join-at-100) ✓
- `_resolve_late_cell_bases` replaces "own first fare as base" with a splice on
  debut day D against a bridge anchor that already has a base on the shared
  date:
  - `anchor_index(D) = anchor_price(D) / anchor_base * 100`
  - late cell debuts at `anchor_index(D)` (NOT 100)
  - `virtual_base(cell) = first_fare(cell) * 100 / anchor_index(D)`
- Anchor selection order (**decision: default decided**): (1) same route, the
  closest *other* active window present on the shared base; (2) same window,
  nearest *route* by |price on debut day − debut fare|; (3) fallback to
  join-at-100 if no anchor exists.
- Result: every cell expressed on the shared base-date basis; `base_period`
  stays the global base. Since runs are full rebuilds, historical dates are
  retroactively corrected on the next `run_index()`.
- Tests: `test_cells_without_a_shared_base_join_at_bridge_level` (flipped
  semantics — expects bridge level, not 100), `test_late_cell_bridge_prefers_
  closest_same_route_window`, `test_late_cell_bridge_falls_back_to_same_window_
  nearest_route`, `test_late_cell_without_any_anchor_still_joins_at_100`.

### Side effects common to all steps
- Next `run_index()` rewrites all historical daily/weekly/monthly rows
  (absolute levels shift — expected, not a bug).
- Open/close freeze logic is untouched by Steps 1-3.

---

## 5. Ops — running and stopping the live machinery

Start the live loop (targets the real scraped DB by convention):

```powershell
python -m src.live.run_live --db data/e2e_real.db --interval 180 --rotate 1
```

Start the dashboard:

```powershell
python -m streamlit run src/dashboard/app.py --server.port 8504 --server.headless true --browser.gatherUsageStats false
```

Stop everything:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine
Stop-Process -Id <pid> -Force
```

Watch: a zombie `python -m streamlit run app.py` (wrong entrypoint) can
respawn after restart; kill it too. Verify the loop is stopped by polling
`live_index` count (should stop increasing).