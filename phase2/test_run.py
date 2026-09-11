import pandas as pd
from sqlalchemy import create_engine

from mock_data import build_mock_db
from pipeline import clean_flights, write_cleaned

DB_PATH = "flights.db"

# 1. Initialize or reset mock database
build_mock_db(DB_PATH)

# 2. Extract raw data using a context manager to prevent connection leaks
engine = create_engine(f"sqlite:///{DB_PATH}")
with engine.connect() as conn:
    raw_df = pd.read_sql_table("raw_flights", conn)
engine.dispose()

# 3. Clean raw records via Phase 2 pipeline
raw_count = len(raw_df)
cleaned_df = clean_flights(raw_df)

# 4. Save cleaned output to SQLite database
write_cleaned(cleaned_df, DB_PATH)

# 5. Define deduplication keys (includes depart_time to handle flight_no = "N/A")
dedup_keys = ["route", "carrier", "flight_no", "date"]
if "depart_time" in cleaned_df.columns:
    dedup_keys.append("depart_time")

# 6. Audit & log execution summary
print("=== PIPELINE VALIDATION SUMMARY ===")
print(f"raw rows:                   {raw_count}")
print(f"cleaned rows:               {len(cleaned_df)}")
print(f"rows removed:               {raw_count - len(cleaned_df)}")
print(f"outliers flagged:           {int(cleaned_df['is_outlier'].sum())}")
print(f"remaining null fares:       {int(cleaned_df['total_fare'].isna().sum())}")
print(f"remaining duplicates:       {int(cleaned_df.duplicated(dedup_keys).sum())}")
print(f"remaining sold_out:         {int((cleaned_df['status'] == 'sold_out').sum())}")
print(f"remaining cancellations:    {int(cleaned_df['is_cancellation'].sum())}")
print(f"routes in cleaned data:     {cleaned_df['route'].nunique()}")
print(f"\ndtypes:\n{cleaned_df.dtypes}")