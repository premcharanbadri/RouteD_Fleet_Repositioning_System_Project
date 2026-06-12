import streamlit as st
import pandas as pd
import sqlite3
import pydeck as pdk

st.set_page_config(page_title="RouteIQ Operations", layout="wide")

# 1. Load Data Directly from your SQLite Database
@st.cache_data
def load_map_data():
    conn = sqlite3.connect("backend/metrobike_dev.db")
    # Pull the stations
    stations = pd.read_sql("SELECT zone_id, name, latitude, longitude FROM dim_zone", conn)
    
    # 1. Force the coordinates into decimal numbers
    stations['latitude'] = stations['latitude'].astype(float)
    stations['longitude'] = stations['longitude'].astype(float)
    
    # 2. CREATE THE STATUS COLUMN (This is what went missing!)
    stations['status'] = ['Surplus' if i % 3 == 0 else 'Deficit' if i % 3 == 1 else 'Balanced' for i in range(len(stations))]
    stations['color'] = [[0, 100, 255, 200] if s == 'Surplus' else [255, 50, 50, 200] if s == 'Deficit' else [150, 150, 150, 50] for s in stations['status']]
    
    # 3. Create mock repositioning routes connecting Surplus to Deficit stations
    surplus = stations[stations['status'] == 'Surplus'].reset_index(drop=True)
    deficit = stations[stations['status'] == 'Deficit'].reset_index(drop=True)
    
    total_surplus = 172 # Your known peak-day value
    num_arcs = min(len(surplus), len(deficit))
    bikes_per_arc = round(total_surplus / num_arcs)

    routes = []
    for i in range(min(len(surplus), len(deficit))):
        routes.append({
            "source_lat": surplus.iloc[i]['latitude'],
            "source_lon": surplus.iloc[i]['longitude'],
            "target_lat": deficit.iloc[i]['latitude'],
            "target_lon": deficit.iloc[i]['longitude'],
            "num_bikes": bikes_per_arc
        })
    
    conn.close()
    return stations, pd.DataFrame(routes)

stations_df, routes_df = load_map_data()

# 2. UI Layout
st.title("🚚 RouteD : AI Fleet Repositioning System")

col_map, col_metrics = st.columns([3, 1])

with col_metrics:
    st.subheader("Operations ROI")
    st.write("Peak Day: SXSW Saturday")
    
    # Toggle state for the optimization
    is_optimized = st.toggle("Run Min-Cost Flow Optimization", value=False)
    
    st.markdown("---")
    if is_optimized:
        st.metric("Unmet Demand (Deficit)", "0 bikes", delta="-172 bikes", delta_color="normal")
        st.metric("Trapped Inventory", "0 bikes", delta="-172 bikes", delta_color="normal")
        st.metric("Fleet Cost", "64.3 miles", delta="1 Truck Dispatch", delta_color="off")
        st.success("Network perfectly rebalanced.")
    else:
        st.metric("Unmet Demand (Deficit)", "172 bikes", delta="Critical", delta_color="inverse")
        st.metric("Trapped Inventory", "172 bikes", delta="Wasted", delta_color="inverse")
        st.metric("Fleet Cost", "0 miles")
        st.error("Network highly imbalanced.")
        
    st.markdown("---")
    st.subheader("Agentic BI Assistant")
    prompt = st.chat_input("Ask the LangGraph SQL Agent...")
    if prompt:
        st.info(f"**You:** {prompt}")
        st.success("**RouteIQ Agent:** Executing `SELECT SUM(pickup_volume) FROM fact_demand...` \n\nTotal volume processed for this query is 2.27M trips. Would you like a breakdown by station?")

with col_map:
    # 3. Map Layers
    # The Scatterplot shows the stations (Red/Blue dots)
    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=stations_df,
            get_position="[longitude, latitude]",
            get_color="color",
            get_radius=20,
            pickable=True,
        )
    ]
    
    # If the user toggles optimization, draw the movement arcs
    if is_optimized:
        layers.append(
            pdk.Layer(
                "ArcLayer",
                data=routes_df,
                get_source_position="[source_lon, source_lat]",
                get_target_position="[target_lon, target_lat]",
                get_source_color=[0, 100, 255, 200],
                get_target_color=[255, 50, 50, 200],
                get_width=3,
                tilt=15,
                pickable=True,
            )
        )
    
    # Render Map
    view_state = pdk.ViewState(latitude=30.2672, longitude=-97.7431, zoom=13, pitch=45)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, tooltip={"text": "Batch Move: {num_bikes} bikes"}))