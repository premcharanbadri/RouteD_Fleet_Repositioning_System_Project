"""
optimizer.py — RouteD Min-Cost Flow Repositioning Engine
Reads warehouse.parquet, finds best date with both surplus AND deficit,
runs Min-Cost Flow, writes reposition_plan.csv
"""

import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path

WAREHOUSE   = "warehouse.parquet"
OUTPUT      = "reposition_plan.csv"
COST_PER_KM = 2.0
TARGET_DATE = "2018-06-15"  # None = auto-find best date with both surplus + deficit

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi    = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def find_best_date(wh: pd.DataFrame) -> pd.Timestamp:
    """Find most recent date that has both surplus and deficit stations."""
    summary = (
        wh.groupby("date")["status"]
        .apply(lambda x: set(x))
        .reset_index()
    )
    summary["has_both"] = summary["status"].apply(
        lambda s: "Surplus" in s and "Deficit" in s
    )
    valid = summary[summary["has_both"]].sort_values("date", ascending=False)
    if valid.empty:
        raise ValueError("No date found with both surplus and deficit stations.")
    best = valid.iloc[0]["date"]
    print(f"[OPT] Auto-selected date with surplus+deficit: {pd.Timestamp(best).date()}")
    return pd.Timestamp(best)

def run_min_cost_flow(snapshot: pd.DataFrame) -> pd.DataFrame:
    surplus = snapshot[snapshot["status"] == "Surplus"].copy()
    deficit = snapshot[snapshot["status"] == "Deficit"].copy()

    if surplus.empty or deficit.empty:
        print("[OPT] No surplus/deficit pair found.")
        return pd.DataFrame()

    print(f"[OPT] Surplus stations: {len(surplus)}  |  Deficit stations: {len(deficit)}")

    total_supply = int(surplus["net_flow"].sum())
    total_demand = int(abs(deficit["net_flow"].sum()))
    print(f"[OPT] Total supply: {total_supply}  |  Total demand: {total_demand}")

    # Balance supply and demand for MCF
    effective_supply = min(total_supply, total_demand)

    G = nx.DiGraph()
    G.add_node("source", demand=-effective_supply)
    G.add_node("sink",   demand= effective_supply)

    # Source → surplus nodes
    for _, row in surplus.iterrows():
        nid = f"S_{row['kiosk_id']}"
        supply = min(int(row["net_flow"]), effective_supply)
        G.add_node(nid, demand=0)
        G.add_edge("source", nid, capacity=supply, weight=0)

    # Deficit nodes → sink
    for _, row in deficit.iterrows():
        nid = f"D_{row['kiosk_id']}"
        G.add_node(nid, demand=0)
        G.add_edge(nid, "sink", capacity=int(abs(row["net_flow"])), weight=0)

    # Surplus → deficit edges weighted by distance
    for _, s in surplus.iterrows():
        for _, d in deficit.iterrows():
            dist = haversine_km(s["lat"], s["lon"], d["lat"], d["lon"])
            cost = max(1, int(dist * COST_PER_KM * 10))
            cap  = min(int(s["net_flow"]), int(abs(d["net_flow"])))
            G.add_edge(
                f"S_{s['kiosk_id']}",
                f"D_{d['kiosk_id']}",
                capacity=cap,
                weight=cost
            )

    try:
        flow_dict = nx.min_cost_flow(G)
    except Exception as e:
        print(f"[OPT] MCF error: {e}")
        return pd.DataFrame()

    s_lookup = surplus.set_index("kiosk_id")
    d_lookup = deficit.set_index("kiosk_id")
    moves = []

    for u, targets in flow_dict.items():
        if not u.startswith("S_"):
            continue
        s_id = u[2:]
        for v, flow in targets.items():
            if not v.startswith("D_") or flow <= 0:
                continue
            d_id = v[2:]
            dist = haversine_km(
                s_lookup.loc[s_id, "lat"], s_lookup.loc[s_id, "lon"],
                d_lookup.loc[d_id, "lat"], d_lookup.loc[d_id, "lon"]
            )
            moves.append({
                "from_kiosk_id":   s_id,
                "from_kiosk_name": s_lookup.loc[s_id, "kiosk_name"],
                "from_lat":        s_lookup.loc[s_id, "lat"],
                "from_lon":        s_lookup.loc[s_id, "lon"],
                "to_kiosk_id":     d_id,
                "to_kiosk_name":   d_lookup.loc[d_id, "kiosk_name"],
                "to_lat":          d_lookup.loc[d_id, "lat"],
                "to_lon":          d_lookup.loc[d_id, "lon"],
                "bikes_to_move":   flow,
                "distance_km":     round(dist, 2),
                "estimated_cost":  round(dist * COST_PER_KM * flow, 2)
            })

    return pd.DataFrame(moves)

def main():
    print(f"[OPT] Loading warehouse ...")
    wh = pd.read_parquet(WAREHOUSE)

    target = pd.Timestamp(TARGET_DATE) if TARGET_DATE else find_best_date(wh)
    snapshot = wh[wh["date"] == target].copy()
    print(f"[OPT] Snapshot size: {len(snapshot)} stations")

    moves = run_min_cost_flow(snapshot)

    if moves.empty:
        print("[OPT] No moves generated.")
        return

    moves.to_csv(OUTPUT, index=False)
    print(f"\n[OPT] ✓ Plan written → {OUTPUT}")
    print(f"[OPT] Moves:         {len(moves)}")
    print(f"[OPT] Bikes moved:   {moves['bikes_to_move'].sum()}")
    print(f"[OPT] Distance:      {moves['distance_km'].sum():.1f} km")
    print(f"[OPT] Est. cost:    ${moves['estimated_cost'].sum():.2f}")
    print("\nTop 5 moves:")
    print(moves.nlargest(5, "bikes_to_move")[
        ["from_kiosk_name","to_kiosk_name","bikes_to_move","distance_km"]
    ].to_string(index=False))

if __name__ == "__main__":
    main()