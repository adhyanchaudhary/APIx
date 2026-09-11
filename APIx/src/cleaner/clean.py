import hashlib
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "indexer.yaml"


def _load_cleaning_config(cfg_path: Path | None = None) -> dict:
    path = cfg_path or CONFIG_PATH
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("cleaning", {})


def _compute_hash(row: pd.Series) -> str:
    key = f"{row['route']}|{row['carrier']}|{row['depart_time']}|{row['total_fare']}|{row['lead_window_days']}"
    return hashlib.md5(key.encode()).hexdigest()


def _flag_outliers_iqr(group: pd.Series, multiplier: float = 1.5) -> pd.Series:
    q1 = group.quantile(0.25)
    q3 = group.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return group.apply(lambda x: 1 if x < lower or x > upper else 0)


def _compute_quality_score(df: pd.DataFrame) -> pd.Series:
    score = pd.Series(1.0, index=df.index)
    for col in ["carrier", "depart_time", "arrive_time", "duration_mins", "total_fare"]:
        score = score.where(df[col].notna(), score - 0.2)
    score = score.where(df["stops"].isin([0, 1, 2]), score - 0.1)
    return score.clip(lower=0, upper=1)


def clean_raw_data(
    db_path: str | Path | None = None,
    cfg_path: Path | None = None,
) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.storage.database import DB_PATH, get_connection

    path = Path(db_path) if db_path else DB_PATH
    cfg = _load_cleaning_config(cfg_path)

    multiplier = cfg.get("iqr_multiplier", 1.5)
    null_action = cfg.get("null_fare_action", "drop")

    log.info("Reading raw_flights from %s", path)
    conn = get_connection(path)
    df = pd.read_sql("SELECT * FROM raw_flights", conn)
    conn.close()

    if df.empty:
        log.warning("raw_flights is empty — nothing to clean")
        return {"raw": 0, "cleaned": 0, "duplicates": 0, "outliers": 0, "nulls": 0}

    raw_count = len(df)
    log.info("Loaded %d raw rows", raw_count)

    df["dedup_hash"] = df.apply(_compute_hash, axis=1)
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["dedup_hash"], keep="first")
    duplicates = before_dedup - len(df)
    log.info("Removed %d duplicates", duplicates)

    if null_action == "drop":
        before_null = len(df)
        df = df.dropna(subset=["total_fare"])
        nulls = before_null - len(df)
        log.info("Dropped %d rows with null fare", nulls)
    else:
        df = df.sort_values(["route", "lead_window_days", "scrape_timestamp"])
        df["total_fare"] = df.groupby(["route", "lead_window_days"])["total_fare"].transform(
            lambda x: x.ffill()
        )
        nulls = int(df["total_fare"].isna().sum())
        df = df.dropna(subset=["total_fare"])
        log.info("Forward-filled null fares, dropped %d remaining", nulls)

    df["is_outlier"] = (
        df.groupby(["route", "lead_window_days"])["total_fare"]
        .transform(lambda x: _flag_outliers_iqr(x, multiplier))
    )
    outlier_count = int(df["is_outlier"].sum())
    log.info("Flagged %d outliers via IQR (×%.1f)", outlier_count, multiplier)

    df["quality_score"] = _compute_quality_score(df)
    df["scrape_date"] = pd.to_datetime(df["scrape_timestamp"]).dt.date.astype(str)
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df["depart_time"] = pd.to_datetime(df["depart_time"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    df["arrive_time"] = pd.to_datetime(df["arrive_time"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

    keep_cols = [
        "scrape_date", "route", "origin", "dest", "carrier", "flight_no",
        "depart_time", "arrive_time", "duration_mins", "stops",
        "base_fare", "taxes", "total_fare", "currency", "lead_window_days",
        "scrape_timestamp", "quality_score", "is_outlier", "dedup_hash",
    ]
    df = df[keep_cols]

    log.info("Writing %d cleaned rows to cleaned_flights", len(df))
    conn = get_connection(path)
    df.to_sql("cleaned_flights", conn, if_exists="append", index=False)
    conn.close()

    stats = {
        "raw": raw_count,
        "cleaned": len(df),
        "duplicates": duplicates,
        "outliers": outlier_count,
        "nulls": nulls,
    }
    log.info("Cleaning complete: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    result = clean_raw_data()
    print(f"\nResults: {result}")
