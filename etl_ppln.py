"""
etl.py — RouteD CitiBike ETL Pipeline
Loads kiosks.csv and trips.csv, cleans data, aggregates daily
demand per station, and writes warehouse.parquet for downstream use.
"""

import pandas as pd
import numpy as np
import re
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
KIOSKS_CSV = "kiosks.csv"
TRIPS_CSV  = "trips.csv"
OUTPUT     = "warehouse.parquet"

# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_location(loc_str):
    """Extract (lat, lon) from strings like '(30.2848, -97.72756)'."""
    if pd.isna(loc_str):
        return np.nan, np.nan
    nums = re.findall(r"[-\d.]+", str(loc_str))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return np.nan, np.nan


def load_kiosks(path: str) -> pd.DataFrame:
    print(f"[ETL] Loading kiosks from {path} ...")
    df = pd.read_csv(path, sep=",", low_memory=False)

    # Normalise column names
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[^\w]", "_", regex=True)
    )

    # Debug — print actual columns so we can verify
    print("[ETL] Kiosk columns found:", df.columns.tolist())

    # Find location column dynamically
    loc_col = [c for c in df.columns if "location" in c]
    if not loc_col:
        raise ValueError(f"No location column found. Columns are: {df.columns.tolist()}")
    
    df[["lat", "lon"]] = df[loc_col[0]].apply(
        lambda x: pd.Series(parse_location(x))
    )

    # Keep useful columns
    keep = ["kiosk_id", "kiosk_name", "kiosk_status",
            "number_of_docks", "lat", "lon", "council_district"]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()

    df = df.dropna(subset=["lat", "lon"])
    df["kiosk_id"] = df["kiosk_id"].astype(str)

    print(f"[ETL] Kiosks loaded: {len(df)} stations")
    return df

def clean_kiosk_id(series):
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.where(numeric.notna(), other=pd.NA).astype("Int64").astype(str).replace("<NA>", pd.NA)

def load_trips(path: str) -> pd.DataFrame:
    print(f"[ETL] Loading trips from {path} (this may take a moment) ...")
    df = pd.read_csv(
        path,
        sep=",",
        low_memory=False,
        usecols=lambda c: c.strip() in [
            "Trip ID", "Checkout Datetime", "Checkout Date",
            "Checkout Kiosk ID", "Checkout Kiosk",
            "Return Kiosk ID", "Return Kiosk",
            "Trip Duration Minutes", "Month", "Year", "Bike Type"
        ]
    )

    # Normalise column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Parse date
    df["checkout_date"] = pd.to_datetime(df["checkout_date"], errors="coerce")
    df = df.dropna(subset=["checkout_date"])

    # Cast IDs to string
    df["checkout_kiosk_id"] = clean_kiosk_id(df["checkout_kiosk_id"])
    df["return_kiosk_id"]   = clean_kiosk_id(df["return_kiosk_id"])
    df = df.dropna(subset=["checkout_kiosk_id", "return_kiosk_id"])     

    # Clean duration (may have commas in large numbers)
    if df["trip_duration_minutes"].dtype == object:
        df["trip_duration_minutes"] = (
            df["trip_duration_minutes"].astype(str)
            .str.replace(",", "").str.strip()
        )
    df["trip_duration_minutes"] = pd.to_numeric(
        df["trip_duration_minutes"], errors="coerce"
    )

    print(f"[ETL] Trips loaded: {len(df):,} records")
    return df


def build_warehouse(kiosks: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    print("[ETL] Aggregating daily demand ...")

    # Daily departures — group by checkout date and checkout station
    deps = (
        trips.groupby(["checkout_date", "checkout_kiosk_id"])
        .size()
        .reset_index(name="departures")
        .rename(columns={"checkout_date": "date", "checkout_kiosk_id": "kiosk_id"})
    )

    # Daily arrivals — group by checkout date (trip date) and RETURN station
    arrs = (
        trips.groupby(["checkout_date", "return_kiosk_id"])
        .size()
        .reset_index(name="arrivals")
        .rename(columns={"checkout_date": "date", "return_kiosk_id": "kiosk_id"})
    )

    # Merge on date + kiosk_id — both now use same column names
    daily = pd.merge(deps, arrs, on=["date", "kiosk_id"], how="outer")
    daily[["departures", "arrivals"]] = daily[["departures", "arrivals"]].fillna(0)
    daily["net_flow"] = daily["arrivals"] - daily["departures"]

    # Attach station metadata
    warehouse = pd.merge(daily, kiosks, on="kiosk_id", how="inner")

    # Meaningful thresholds — deficit is genuinely losing bikes
    warehouse["status"] = warehouse["net_flow"].apply(
        lambda x: "Surplus" if x > 3 else ("Deficit" if x < -3 else "Balanced")
    )

    print(f"[ETL] Warehouse built: {len(warehouse):,} station-day records")
    print(f"[ETL] Date range: {warehouse['date'].min()} → {warehouse['date'].max()}")
    print(f"[ETL] Unique stations: {warehouse['kiosk_id'].nunique()}")
    return warehouse


def main():
    kiosks   = load_kiosks(KIOSKS_CSV)
    trips    = load_trips(TRIPS_CSV)
    wh       = build_warehouse(kiosks, trips)

    # Write parquet
    table = pa.Table.from_pandas(wh)
    pq.write_table(table, OUTPUT)
    print(f"[ETL] ✓ Written → {OUTPUT}  ({Path(OUTPUT).stat().st_size / 1e6:.1f} MB)")

    # Quick summary
    latest = wh[wh["date"] == wh["date"].max()]
    print(f"\n[ETL] Latest day snapshot ({wh['date'].max().date()}):")
    print(latest["status"].value_counts().to_string())


if __name__ == "__main__":
    main()