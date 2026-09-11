import hashlib
import pandas as pd
from sqlalchemy import create_engine


def cast_types(df):
    df = df.copy()
    df["total_fare"] = df["total_fare"].astype(float)
    # Using errors="coerce" prevents full failure if an invalid date string pops up
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["stops"] = df["stops"].astype("Int64")
    df["duration_mins"] = df["duration_mins"].astype("Int64")
    df["is_cancellation"] = df["is_cancellation"].fillna(False).astype(bool)
    return df


def deduplicate(df):
    df = df.copy()
    
    # Check if depart_time exists in raw schema to distinguish flights when flight_no is "N/A"
    depart_str = df["depart_time"].fillna("").astype(str) if "depart_time" in df.columns else ""
    
    key = (
        df["route"].fillna("").astype(str)
        + "|"
        + df["carrier"].fillna("").astype(str)
        + "|"
        + df["flight_no"].fillna("").astype(str)
        + "|"
        + df["date"].fillna("").astype(str)
        + "|"
        + depart_str  # Safeguard for flight_no = "N/A"
    )
    df["dedup_hash"] = key.map(lambda s: hashlib.md5(s.encode("utf-8")).hexdigest())
    df = df.drop_duplicates(subset="dedup_hash", keep="first")
    return df.drop(columns=["dedup_hash"])


def filter_unavailable(df):
    df = df.copy()
    mask = (df["status"].fillna("available") != "sold_out") & (~df["is_cancellation"])
    return df[mask]


def handle_nulls(df):
    df = df.copy()
    df = df.dropna(subset=["total_fare"])
    df["carrier"] = df["carrier"].fillna("UNKNOWN")
    return df


def flag_outliers(df):
    df = df.copy()
    g = df.groupby("route")["total_fare"]
    q1 = g.transform(lambda x: x.quantile(0.25))
    q3 = g.transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    
    # Fill NaN outlier evaluations with False (handles low-count routes gracefully)
    outlier_mask = (df["total_fare"] < lower) | (df["total_fare"] > upper)
    df["is_outlier"] = outlier_mask.fillna(False)
    return df


def clean_flights(raw_df):
    df = cast_types(raw_df)
    df = deduplicate(df)
    df = filter_unavailable(df)
    df = handle_nulls(df)
    df = flag_outliers(df)
    return df


def write_cleaned(cleaned_df, db_path, if_exists="replace"):
    engine = create_engine(f"sqlite:///{db_path}")
    # Context manager ensures clean commit and auto-closes connection
    with engine.begin() as conn:
        cleaned_df.to_sql("cleaned_flights", conn, if_exists=if_exists, index=False)
    engine.dispose()