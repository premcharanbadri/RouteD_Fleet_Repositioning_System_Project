"""
dashboard.py — RouteD CitiBike Operations Dashboard
Run with: streamlit run dashboard.py
Requires: warehouse.parquet (run etl.py first)
Optimizer runs live per selected date — no separate optimizer step needed.
"""

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import plotly.express as px
import networkx as nx
from pathlib import Path
from io import StringIO

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RouteD — CitiBike Operations",
    page_icon="🚲",
    layout="wide"
)

COST_PER_KM = 2.0

# ── Haversine ─────────────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi    = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# ── Min-Cost Flow (runs live per date) ───────────────────────────────────────
@st.cache_data
def run_optimizer(snapshot_json: str) -> pd.DataFrame:
    from io import StringIO
    snapshot = pd.read_json(StringIO(snapshot_json))
    
    # Ensure kiosk_id is string after JSON round-trip
    snapshot["kiosk_id"] = snapshot["kiosk_id"].astype(str)
    
    surplus = snapshot[snapshot["status"] == "Surplus"].copy()
    deficit = snapshot[snapshot["status"] == "Deficit"].copy()

    if surplus.empty or deficit.empty:
        return pd.DataFrame()

    total_supply = int(surplus["net_flow"].sum())
    total_demand = int(abs(deficit["net_flow"].sum()))
    effective    = min(total_supply, total_demand)

    G = nx.DiGraph()
    G.add_node("source", demand=-effective)
    G.add_node("sink",   demand= effective)

    for _, row in surplus.iterrows():
        nid = f"S_{row['kiosk_id']}"
        G.add_node(nid, demand=0)
        G.add_edge("source", nid, capacity=min(int(row["net_flow"]), effective), weight=0)

    for _, row in deficit.iterrows():
        nid = f"D_{row['kiosk_id']}"
        G.add_node(nid, demand=0)
        G.add_edge(nid, "sink", capacity=int(abs(row["net_flow"])), weight=0)

    for _, s in surplus.iterrows():
        for _, d in deficit.iterrows():
            dist = haversine_km(s["lat"], s["lon"], d["lat"], d["lon"])
            cost = max(1, int(dist * COST_PER_KM * 10))
            cap  = min(int(s["net_flow"]), int(abs(d["net_flow"])))
            G.add_edge(f"S_{s['kiosk_id']}", f"D_{d['kiosk_id']}",
                       capacity=cap, weight=cost)

    try:
        flow_dict = nx.min_cost_flow(G)
    except Exception:
        return pd.DataFrame()

    # Use list-based lookup instead of set_index to avoid string/int mismatch
    s_lu = surplus.set_index("kiosk_id").astype({"lat": float, "lon": float})
    d_lu = deficit.set_index("kiosk_id").astype({"lat": float, "lon": float})
    moves = []

    for u, targets in flow_dict.items():
        if not u.startswith("S_"):
            continue
        s_id = u[2:]
        for v, flow in targets.items():
            if not v.startswith("D_") or flow <= 0:
                continue
            d_id = v[2:]
            try:
                dist = haversine_km(
                    float(s_lu.at[s_id, "lat"]), float(s_lu.at[s_id, "lon"]),
                    float(d_lu.at[d_id, "lat"]), float(d_lu.at[d_id, "lon"])
                )
                moves.append({
                    "from_kiosk_name": s_lu.at[s_id, "kiosk_name"],
                    "from_lat": float(s_lu.at[s_id, "lat"]),
                    "from_lon": float(s_lu.at[s_id, "lon"]),
                    "to_kiosk_name": d_lu.at[d_id, "kiosk_name"],
                    "to_lat": float(d_lu.at[d_id, "lat"]),
                    "to_lon": float(d_lu.at[d_id, "lon"]),
                    "bikes_to_move": flow,
                    "distance_km": round(dist, 2),
                    "estimated_cost": round(dist * COST_PER_KM * flow, 2)
                })
            except KeyError:
                continue

    return pd.DataFrame(moves)

# ── Load warehouse ────────────────────────────────────────────────────────────
@st.cache_data
def load_warehouse():
    if not Path("warehouse.parquet").exists():
        return None
    df = pd.read_parquet("warehouse.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df

wh = load_warehouse()

st.title("🚲 RouteD — CitiBike Demand & Fleet Optimization")
st.caption("Austin, TX · Supply-demand analysis and repositioning intelligence")

if wh is None:
    st.error("warehouse.parquet not found. Run `python etl.py` first.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Controls")
dates    = sorted(wh["date"].dt.date.unique(), reverse=True)
sel_date = st.sidebar.selectbox("📅 Select Date", dates)
snapshot = wh[wh["date"] == pd.Timestamp(sel_date)].copy()

surplus_ct  = (snapshot["status"] == "Surplus").sum()
deficit_ct  = (snapshot["status"] == "Deficit").sum()
balanced_ct = (snapshot["status"] == "Balanced").sum()

if deficit_ct == 0:
    st.sidebar.info("No deficit stations on this date — try an earlier date to see repositioning arcs.")

# ── Run optimizer live for selected date ──────────────────────────────────────
plan = run_optimizer(snapshot.to_json(date_format="iso"))

# ── KPI Row ───────────────────────────────────────────────────────────────────
unmet = snapshot[snapshot["status"] == "Deficit"]["net_flow"].abs().sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🏙️ Active Stations", len(snapshot))
c2.metric("🟢 Surplus",         surplus_ct)
c3.metric("🔴 Deficit",         deficit_ct)
c4.metric("⚪ Balanced",        balanced_ct)
c5.metric("📉 Unmet Demand",    int(unmet))

st.divider()

# ── Map + Plan ────────────────────────────────────────────────────────────────
left, right = st.columns([3, 2])

with left:
    st.subheader("🗺️ Station Health Map")

    color_map = {
        "Surplus":  [0,   200, 100, 200],
        "Deficit":  [220,  50,  50, 200],
        "Balanced": [160, 160, 160, 160],
    }
    snapshot["color"]  = snapshot["status"].map(color_map)
    snapshot["radius"] = (snapshot["net_flow"].abs().clip(1, 40) * 10 + 80).astype(int)

    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=snapshot,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
        radius_min_pixels=5,
        radius_max_pixels=30,
    )

    layers = [scatter]

    if plan is not None and not plan.empty:
        arc = pdk.Layer(
            "ArcLayer",
            data=plan,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon",   "to_lat"],
            get_source_color=[0, 180, 255, 220],
            get_target_color=[255, 140,   0, 220],
            get_width=3,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(arc)

    view = pdk.ViewState(
        latitude=snapshot["lat"].mean(),
        longitude=snapshot["lon"].mean(),
        zoom=12,
        pitch=35,
    )

    tooltip = {
        "html": "<b>{kiosk_name}</b><br/>Status: <b>{status}</b><br/>Net Flow: {net_flow}<br/>Departures: {departures} | Arrivals: {arrivals}",
        "style": {"background": "rgba(0,0,0,0.8)", "color": "white", "fontSize": "12px", "padding": "8px"}
    }

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=view,
        tooltip=tooltip,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    ))
    st.caption("🟢 Surplus  🔴 Deficit  ⚪ Balanced  │  Arcs show recommended repositioning moves")

with right:
    st.subheader("📋 Repositioning Plan")

    if plan is None or plan.empty:
        st.info("No repositioning needed on this date — all stations are balanced or surplus only.")
    else:
        disp = plan[[
            "from_kiosk_name", "to_kiosk_name",
            "bikes_to_move", "distance_km", "estimated_cost"
        ]].rename(columns={
            "from_kiosk_name": "From",
            "to_kiosk_name":   "To",
            "bikes_to_move":   "Bikes",
            "distance_km":     "Dist (km)",
            "estimated_cost":  "Cost ($)"
        })
        st.dataframe(
            disp.sort_values("Bikes", ascending=False),
            width="stretch",
            height=300
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Bikes Moved",    int(plan["bikes_to_move"].sum()))
        m2.metric("Total Distance", f"{plan['distance_km'].sum():.1f} km")
        m3.metric("Est. Cost",      f"${plan['estimated_cost'].sum():.2f}")

st.divider()

# ── Trend charts ──────────────────────────────────────────────────────────────
st.subheader("📈 Network Trends")
tab1, tab2, tab3 = st.tabs(["Daily Demand", "Station Status Over Time", "Top Imbalanced Stations"])

with tab1:
    daily = (
        wh.groupby("date")
        .agg(total_departures=("departures","sum"),
             total_arrivals=("arrivals","sum"))
        .reset_index()
    )
    fig = px.line(
        daily, x="date", y=["total_departures","total_arrivals"],
        color_discrete_map={"total_departures":"#EF553B","total_arrivals":"#00CC96"},
        title="Daily Departures vs Arrivals Across Network",
        labels={"value":"Trips","date":"Date","variable":""}
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

with tab2:
    status_trend = (
        wh.groupby(["date","status"])
        .size().reset_index(name="count")
    )
    fig2 = px.area(
        status_trend, x="date", y="count", color="status",
        color_discrete_map={"Surplus":"#00CC96","Deficit":"#EF553B","Balanced":"#B0B0B0"},
        title="Station Health Distribution Over Time"
    )
    fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, width="stretch")

with tab3:
    top = (
        snapshot.assign(abs_flow=snapshot["net_flow"].abs())
        .nlargest(15, "abs_flow")
        [["kiosk_name","net_flow","status","departures","arrivals"]]
    )
    fig3 = px.bar(
        top, x="net_flow", y="kiosk_name", color="status", orientation="h",
        color_discrete_map={"Surplus":"#00CC96","Deficit":"#EF553B","Balanced":"#B0B0B0"},
        title=f"Top 15 Imbalanced Stations — {sel_date}",
        labels={"net_flow":"Net Flow (Arrivals − Departures)","kiosk_name":""}
    )
    fig3.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis={"categoryorder":"total ascending"}
    )
    st.plotly_chart(fig3, width="stretch")

st.divider()

# ── Raw data explorer ─────────────────────────────────────────────────────────
with st.expander("🔍 Raw Station Data Explorer"):
    status_filter = st.multiselect(
        "Filter by status",
        ["Surplus","Deficit","Balanced"],
        default=["Surplus","Deficit","Balanced"]
    )
    filtered = snapshot[snapshot["status"].isin(status_filter)]
    st.dataframe(
        filtered[["kiosk_name","status","net_flow","departures","arrivals","lat","lon"]]
        .sort_values("net_flow"),
        width="stretch"
    )
    st.caption(f"Showing {len(filtered)} stations")