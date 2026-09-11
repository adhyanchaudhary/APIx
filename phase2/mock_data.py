import os
import random

import pandas as pd
from sqlalchemy import create_engine

ROUTES = [
    "DEL-BOM", "DEL-BLR", "DEL-MAA", "DEL-HYD",
    "DEL-CCU", "DEL-PNQ", "DEL-JAI", "DEL-GOA",
    "DEL-AMD", "DEL-KOJ", "DEL-GAU", "DEL-SXR",
]

CARRIER_CODES = ["6E", "AI", "UK", "SG", "QP"]

BASE_DATE = pd.Timestamp("2026-09-10")

EXTREME_FARES = [820, 940, 26500, 31000, 780, 880, 29000, 33500]


def build_mock_df(seed=42):
    random.seed(seed)
    rows = []
    for route in ROUTES:
        base = random.randint(3200, 5200)
        for day in range(1, 31):
            fare = base + random.randint(0, 900)
            if day <= 3:
                fare *= random.uniform(2.0, 4.0)
            elif day <= 10:
                fare *= random.uniform(1.3, 1.8)
            code = random.choice(CARRIER_CODES)
            rows.append({
                "route": route,
                "carrier": code,
                "flight_no": f"{code}{random.randint(100, 999)}",
                "date": (BASE_DATE + pd.Timedelta(days=day)).strftime("%Y-%m-%d"),
                "total_fare": round(fare, 2),
                "stops": random.choice([0, 0, 1, 2]),
                "duration_mins": random.randint(95, 240),
                "status": "available",
                "is_cancellation": False,
            })
    df = pd.DataFrame(rows)

    df = pd.concat([df, df.sample(15, random_state=seed).copy()], ignore_index=True)

    sold_out = df.sample(10, random_state=seed + 1).copy()
    sold_out["status"] = "sold_out"
    df = pd.concat([df, sold_out], ignore_index=True)

    cancelled = df.sample(6, random_state=seed + 2).copy()
    cancelled["is_cancellation"] = True
    df = pd.concat([df, cancelled], ignore_index=True)

    null_fare = df.sample(8, random_state=seed + 3).copy()
    null_fare["total_fare"] = float("nan")
    df = pd.concat([df, null_fare], ignore_index=True)

    null_carrier = df.sample(6, random_state=seed + 4).copy()
    null_carrier["carrier"] = None
    df = pd.concat([df, null_carrier], ignore_index=True)

    outliers = pd.DataFrame([
        {
            "route": random.choice(ROUTES),
            "carrier": random.choice(CARRIER_CODES),
            "flight_no": "XX900",
            "date": (BASE_DATE + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
            "total_fare": fare,
            "stops": random.choice([0, 1]),
            "duration_mins": random.randint(100, 220),
            "status": "available",
            "is_cancellation": False,
        }
        for fare in EXTREME_FARES
    ])
    df = pd.concat([df, outliers], ignore_index=True)

    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def build_mock_db(db_path, seed=42):
    if os.path.exists(db_path):
        os.remove(db_path)
    df = build_mock_df(seed=seed)
    engine = create_engine(f"sqlite:///{db_path}")
    df.to_sql("raw_flights", engine, if_exists="replace", index=False)
    engine.dispose()
    return df