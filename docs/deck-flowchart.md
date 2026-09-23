# APIx — Data Pipeline (Mermaid Flowchart)

```mermaid
flowchart TD
    subgraph COLLECT["Phase 1 — Collection"]
        B[Google Flights] --> C[Playwright Scraper]
        D[APScheduler<br/>daily cron] --> C
        C -->|60 req/h · retries · jitter| E[(raw_flights)]
    end

    subgraph CLEAN["Phase 2 — Cleaning"]
        E --> F[Type Cast]
        G[Dedup on dedup_hash] --> H[Null Fare Drop]
        F --> H
        H --> I[IQR Outlier Flag<br/>1.5x fence]
        I --> J[Quality Score]
        J --> K[(cleaned_flights)]
    end

    subgraph INDEX["Phase 3 — Index Engine"]
        K --> L[Collapse to Cells<br/>median fare · route x window x day]
        L --> M[Cell Weights<br/>route_wt x window_sh]
        M --> N[Route Index<br/>P(t) / P(0) x 100]
        N --> O[Daily Composite<br/>weighted trimmed mean]
        O --> P[7-day rolling] --> Q[(weekly_index)]
        O --> R[30-day rolling] --> S[(monthly_index)]
        O --> T[(daily_index)]
    end

    subgraph OUTPUT["Phase 4 — Output"]
        Q --> U[Streamlit Dashboard]
        S --> U
        T --> U
        T --> V[FastAPI · Future]
        T --> W[NN Fare Classifier]
    end
```

Same flow as `docs/deck-slides.html` slide 1 — scrape → clean → index → output.