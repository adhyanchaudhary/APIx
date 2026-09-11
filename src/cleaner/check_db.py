import sqlite3
import pandas as pd

db_path = "flights.db"
conn = sqlite3.connect(db_path)

print("--- 1. RECORD COUNT COMPARISON ---")
count_df = pd.read_sql_query("""
    SELECT 
        (SELECT COUNT(*) FROM raw_flights) AS raw_count,
        (SELECT COUNT(*) FROM cleaned_flights) AS cleaned_count,
        (SELECT COUNT(*) FROM raw_flights) - (SELECT COUNT(*) FROM cleaned_flights) AS removed_records
""", conn)
print(count_df.to_string(index=False))

print("\n--- 2. OUTLIER CHECK (cleaned_flights) ---")
outlier_df = pd.read_sql_query("""
    SELECT is_outlier, COUNT(*) as record_count 
    FROM cleaned_flights 
    GROUP BY is_outlier
""", conn)
print(outlier_df.to_string(index=False))

print("\n--- 3. NULL / MISSING VALUES AUDIT ---")
cleaned_data = pd.read_sql_query("SELECT * FROM cleaned_flights", conn)
null_counts = cleaned_data.isnull().sum().reset_index()
null_counts.columns = ['column_name', 'null_count']
print(null_counts.to_string(index=False))

print("\n--- 4. FARE SUMMARY COMPARISON ---")
price_summary = pd.read_sql_query("""
    SELECT 'raw' AS table_name, AVG(total_fare) AS avg_fare, MIN(total_fare) AS min_fare, MAX(total_fare) AS max_fare FROM raw_flights
    UNION ALL
    SELECT 'cleaned' AS table_name, AVG(total_fare) AS avg_fare, MIN(total_fare) AS min_fare, MAX(total_fare) AS max_fare FROM cleaned_flights
""", conn)
print(price_summary.to_string(index=False))

conn.close()