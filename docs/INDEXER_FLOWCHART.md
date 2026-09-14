# APIx Indexer — Computation Flowchart

```mermaid
flowchart TD
    A["cleaned_flights<br/>(one row per flight)"] --> B["route_price_per_day"]

    B --> B1["drop NA fares<br/>exclude is_outlier = 1"]
    B1 --> B2["groupby route x window x scrape_date<br/>take MEDIAN fare -> cell route_price"]
    B2 --> B3["forward-fill coverage gaps<br/>(carry last known fare per route x window)"]
    B3 --> C["prices: one route_price per cell"]

    W1["route weights (traffic share, sum = 1)"] --> CW["cell_weight = route_weight x window_weight"]
    W2["window weights<br/>T+1 0.2 / T+7 0.3 / T+30 0.5"] --> CW

    C --> D["base_date = first date with any data"]
    CW --> E["for each (route x window) cell present on a date"]

    D --> Q{"cell had a price<br/>on the base date?"}
    Q -- yes --> BASE["base = cell price on shared base_date"]
    Q -- no --> BASE2["base = cell's own first fare<br/>(joins basket at 100 later)"]

    BASE --> RI["route_index = route_price / base x 100<br/>(base = 100)"]
    BASE2 --> RI
    RI --> AGG["aggregate = weighted_trimmed_mean<br/>of day's route_index x cell_weight,<br/>re-normalised over present cells"]

    AGG --> DAILY["daily_index table<br/>columns: date, window, route, weight,<br/>route_price, route_index, aggregate_index"]

    DAILY --> ROLL("rolling average: mean, min_periods = 1")
    ROLL --> RR1["per route x window:<br/>7-day rolling of route_price + route_index"]
    ROLL --> RA1["per window x date (deduped):<br/>7-day rolling of aggregate_index"]
    RR1 --> WK["weekly_index table (7-day)"]
    RA1 --> WK

    ROLL --> RR2["per route x window:<br/>30-day rolling of route_price + route_index"]
    ROLL --> RA2["per window x date (deduped):<br/>30-day rolling of aggregate_index"]
    RR2 --> MO["monthly_index table (30-day)"]
    RA2 --> MO
```

## Same thing in text form

```
cleaned_flights
   │  drop NA fares / outliers
   ▼
median fare per (route × window × day)   ──►   one "cell price"
   │  forward-fill gaps
   ▼
cell price
   │
   ├── base date = first date with data
   ├── cell weight = route weight × window weight   (traffic × booking share)
   │
   ▼
route_index = cell_price / base_price × 100         (each cell starts at 100)
   │
   ▼
daily aggregate_index = weighted trimmed mean        (re-normalised per day)
       of { route_index × cell_weight }
   │
   ▼
daily_index  ──►  7-day rolling means  ──►  weekly_index
   └──────────►  30-day rolling means  ──►  monthly_index
```

## Key formulas

```
route_index(t, r, w) = median_fare(t, r, w) / base_fare(r, w) × 100

cell_weight(r, w)   = route_weight(r) × window_weight(w)

aggregate APIx(t)   = weighted_trimmed_mean(
                          route_index(t, r, w),
                          weights = cell_weight(r, w)
                      )   over cells present on date t

weekly / monthly     = rolling_mean of the above over the last 7 / 30 days
                       (per route for price & index, and on the deduped
                       aggregate headline)
```