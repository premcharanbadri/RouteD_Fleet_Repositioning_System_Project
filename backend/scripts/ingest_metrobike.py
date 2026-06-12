import pandas as pd
import os
from sqlalchemy import create_engine

# 1. Configuration
DATABASE_URL = "sqlite:///./metrobike_dev.db" 
TRIPS_CSV = "data/raw/trips.csv"
KIOSKS_CSV = "data/raw/kiosks.csv"

def ingest_kiosks(engine):
    print("Loading kiosks...")
    # Read only the exact columns we need using your provided headers
    kiosk_cols = ['Kiosk ID', 'Kiosk Name', 'Kiosk Status', 'Location', 'Number of Docks']
    df_kiosks = pd.read_csv(KIOSKS_CSV, usecols=kiosk_cols)
    
    # Filter for active kiosks (filling empty statuses to prevent errors)
    df_active = df_kiosks[df_kiosks['Kiosk Status'].fillna('').str.lower() == 'active'].copy()
    
    # Extract Lat/Lon from the 'Location' column (format: "(lat, lon)")
    df_active[['latitude', 'longitude']] = df_active['Location'].str.extract(r'\(([^,]+),\s*([^)]+)\)')
    
    # Rename to match your RouteIQ dim_zone schema
    zones_to_insert = df_active[['Kiosk ID', 'Kiosk Name', 'latitude', 'longitude', 'Number of Docks']].rename(columns={
        'Kiosk ID': 'zone_id',
        'Kiosk Name': 'name',
        'Number of Docks': 'capacity'
    })
    
    print(f"Inserting {len(zones_to_insert)} active zones...")
    zones_to_insert.to_sql('dim_zone', con=engine, if_exists='append', index=False)
    
    # Return the valid zone IDs to filter our trips
    return zones_to_insert['zone_id'].tolist()

def ingest_trips(engine, valid_zone_ids):
    print("Loading trips (skipping malformed rows, this may take a minute)...")
    
    # Remove usecols, add on_bad_lines='skip' to bypass unescaped commas, and low_memory=False
    df_trips = pd.read_csv(TRIPS_CSV, on_bad_lines='skip', low_memory=False)
    
    # Strip any hidden whitespace from the CSV headers
    df_trips.columns = df_trips.columns.str.strip()
    
    # Now that it's safely loaded, filter down to the columns we need
    trip_cols = ['Trip ID', 'Checkout Date', 'Checkout Kiosk ID', 'Return Kiosk ID']
    
    # Quick safety check to ensure the headers match
    missing = [c for c in trip_cols if c not in df_trips.columns]
    if missing:
        print(f"AVAILABLE COLUMNS: {df_trips.columns.tolist()}")
        raise KeyError(f"Missing columns: {missing}")
        
    df_trips = df_trips[trip_cols]
    
    print("Cleaning dates and filtering invalid kiosks...")
    # Clean up dates
    df_trips['Checkout Date'] = pd.to_datetime(df_trips['Checkout Date']).dt.date
    
    # Filter out trips that start or end at inactive/missing kiosks
    # We use pd.to_numeric to coerce any weird strings to NaN, then filter
    df_trips['Checkout Kiosk ID'] = pd.to_numeric(df_trips['Checkout Kiosk ID'], errors='coerce')
    df_trips['Return Kiosk ID'] = pd.to_numeric(df_trips['Return Kiosk ID'], errors='coerce')
    
    # Drop rows where the ID couldn't be parsed, then convert to match our valid_zones list
    df_trips = df_trips.dropna(subset=['Checkout Kiosk ID', 'Return Kiosk ID'])
    
    df_trips = df_trips[
        df_trips['Checkout Kiosk ID'].isin(valid_zone_ids) & 
        df_trips['Return Kiosk ID'].isin(valid_zone_ids)
    ]
    
    print("Aggregating daily demand...")
    # Group by Date and Checkout Kiosk to get DAILY DEMAND
    daily_demand = df_trips.groupby(['Checkout Date', 'Checkout Kiosk ID']).size().reset_index(name='trip_count')
    
    # Rename columns to match the fact_demand schema
    demand_to_insert = daily_demand.rename(columns={
        'Checkout Date': 'date',
        'Checkout Kiosk ID': 'zone_id',
        'trip_count': 'pickup_volume'
    })
    
    print(f"Inserting {len(demand_to_insert)} daily demand records...")
    demand_to_insert.to_sql('fact_demand', con=engine, if_exists='append', index=False)

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    
    valid_zones = ingest_kiosks(engine)
    ingest_trips(engine, valid_zones)
    
    print("Ingestion complete. RouteIQ is now fueled by real Austin data.")