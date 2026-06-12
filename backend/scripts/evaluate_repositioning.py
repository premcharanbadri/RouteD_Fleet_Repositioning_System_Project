import pandas as pd
import numpy as np
import math
from sqlalchemy import create_engine

# 1. Configuration
DATABASE_URL = "sqlite:///./metrobike_dev.db" 
TRIPS_CSV = "data/raw/trips.csv"

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in miles."""
    R = 3959.0 # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def evaluate_repositioning(engine):
    print("Loading valid zones and coordinates from the database...")
    zones_df = pd.read_sql("SELECT zone_id, latitude, longitude FROM dim_zone", engine)
    
    # ADD THESE TWO LINES: Force the strings into decimals
    zones_df['latitude'] = zones_df['latitude'].astype(float)
    zones_df['longitude'] = zones_df['longitude'].astype(float)
    
    # Create a dictionary for fast coordinate lookups: {zone_id: (lat, lon)}
    zone_coords = zones_df.set_index('zone_id')[['latitude', 'longitude']].apply(tuple, axis=1).to_dict()
    valid_zones = set(zones_df['zone_id'])

    print("Scanning 2.27M trips to find the highest-imbalance day...")
    df_trips = pd.read_csv(TRIPS_CSV, on_bad_lines='skip', low_memory=False)
    df_trips.columns = df_trips.columns.str.strip()
    
    trip_cols = ['Checkout Date', 'Checkout Kiosk ID', 'Return Kiosk ID']
    df_trips = df_trips[trip_cols]
    
    # Clean IDs
    df_trips['Checkout Kiosk ID'] = pd.to_numeric(df_trips['Checkout Kiosk ID'], errors='coerce')
    df_trips['Return Kiosk ID'] = pd.to_numeric(df_trips['Return Kiosk ID'], errors='coerce')
    df_trips = df_trips.dropna()
    
    # Filter to our valid zones
    df_trips = df_trips[df_trips['Checkout Kiosk ID'].isin(valid_zones) & df_trips['Return Kiosk ID'].isin(valid_zones)]
    
    # Find the peak day (the day with the most total movement)
    peak_date = df_trips['Checkout Date'].value_counts().idxmax()
    print(f"Targeting Peak Day: {peak_date}")
    
    # Isolate trips for the peak day
    peak_trips = df_trips[df_trips['Checkout Date'] == peak_date]
    
    print("Calculating baseline surplus (idle bikes) and deficit (unmet demand)...")
    # Outflow (Bikes leaving) vs Inflow (Bikes arriving)
    outflow = peak_trips.groupby('Checkout Kiosk ID').size()
    inflow = peak_trips.groupby('Return Kiosk ID').size()
    
    # Net Inventory = Arriving - Leaving. 
    # Positive = Bikes piling up (Surplus). Negative = Stations empty (Deficit).
    net_inventory = inflow.sub(outflow, fill_value=0)
    
    surplus_nodes = net_inventory[net_inventory > 0].to_dict()
    deficit_nodes = net_inventory[net_inventory < 0].abs().to_dict()
    
    baseline_idle = sum(surplus_nodes.values())
    baseline_unmet = sum(deficit_nodes.values())
    
    print("Simulating fleet repositioning (Greedy Min-Cost Flow approximation)...")
    # Calculate all possible moves and their distances
    possible_moves = []
    for s_id, s_vol in surplus_nodes.items():
        for d_id, d_vol in deficit_nodes.items():
            if s_id in zone_coords and d_id in zone_coords:
                dist = haversine(zone_coords[s_id][0], zone_coords[s_id][1], 
                                 zone_coords[d_id][0], zone_coords[d_id][1])
                possible_moves.append((dist, s_id, d_id))
    
    # Sort by shortest distance first to minimize cost
    possible_moves.sort(key=lambda x: x[0])
    
    total_bikes_moved = 0
    total_miles_driven = 0
    
    # Execute the moves
    for dist, s_id, d_id in possible_moves:
        if surplus_nodes[s_id] > 0 and deficit_nodes[d_id] > 0:
            # Move as many bikes as possible between this pair
            move_vol = min(surplus_nodes[s_id], deficit_nodes[d_id])
            
            surplus_nodes[s_id] -= move_vol
            deficit_nodes[d_id] -= move_vol
            
            total_bikes_moved += move_vol
            total_miles_driven += (move_vol * dist)
            
    # Calculate Optimized Metrics
    optimized_idle = sum(surplus_nodes.values())
    optimized_unmet = sum(deficit_nodes.values())
    
    unmet_reduction = ((baseline_unmet - optimized_unmet) / baseline_unmet) * 100
    idle_reduction = ((baseline_idle - optimized_idle) / baseline_idle) * 100

    print("\n" + "="*60)
    print("📈 ROUTEIQ BUSINESS VALUE EVALUATION")
    print("="*60)
    print(f"Operational Peak Day    : {peak_date}")
    print(f"Total Trips on Peak Day : {len(peak_trips):,}")
    print("-" * 60)
    print("BASELINE (DO NOTHING):")
    print(f"Idle Bikes (Surplus)    : {baseline_idle:,.0f} bikes trapped at full stations")
    print(f"Unmet Demand (Deficit)  : {baseline_unmet:,.0f} missing bikes at empty stations")
    print("-" * 60)
    print("OPTIMIZED (WITH REPOSITIONING):")
    print(f"Bikes Repositioned      : {total_bikes_moved:,.0f} bikes moved")
    print(f"Fleet Mileage Cost      : {total_miles_driven:,.1f} truck miles driven")
    print(f"Remaining Idle Bikes    : {optimized_idle:,.0f} bikes")
    print(f"Remaining Unmet Demand  : {optimized_unmet:,.0f} bikes")
    print("-" * 60)
    print("ROI DELTA:")
    print(f"⬇️ Idle Inventory Reduced by : {idle_reduction:.1f}%")
    print(f"⬇️ Unmet Demand Reduced by   : {unmet_reduction:.1f}%")
    print("="*60)

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    evaluate_repositioning(engine)