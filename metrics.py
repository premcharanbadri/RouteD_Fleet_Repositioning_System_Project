"""
metrics.py — RouteD Business Impact Quantification
Calculates all recruiter/client-facing metrics from warehouse.parquet
"""

import pandas as pd
import numpy as np

COST_PER_KM       = 2.0      # $ per km fleet travel
REVENUE_PER_TRIP  = 3.50     # $ avg CitiBike trip revenue (industry benchmark)
REBALANCE_COST_HR = 25.0     # $ per hour for a rebalancing crew member (Austin labor)
MINS_PER_MOVE     = 15       # avg minutes to physically move one bike
UNMET_TRIP_LOSS   = 3.50     # $ lost revenue per unmet demand unit (missed trip)

wh = pd.read_parquet("warehouse.parquet")
wh["date"] = pd.to_datetime(wh["date"])

print("=" * 65)
print("RouteD — BUSINESS IMPACT METRICS")
print("=" * 65)

# ── 1. Network Scale ──────────────────────────────────────────────
print("\n── 1. NETWORK SCALE ─────────────────────────────────────────")
total_records  = len(wh)
unique_stations = wh["kiosk_id"].nunique()
date_range     = (wh["date"].max() - wh["date"].min()).days / 365
total_days     = wh["date"].nunique()
total_trips    = wh["departures"].sum()

print(f"Total station-day records:     {total_records:,}")
print(f"Unique stations monitored:     {unique_stations}")
print(f"Date range:                    {wh['date'].min().date()} → {wh['date'].max().date()} ({date_range:.1f} years)")
print(f"Total operational days:        {total_days:,}")
print(f"Total trips in dataset:        {total_trips:,.0f}")

# ── 2. Supply-Demand Imbalance ────────────────────────────────────
print("\n── 2. SUPPLY-DEMAND IMBALANCE ───────────────────────────────")
deficit_days = wh[wh["status"] == "Deficit"]
surplus_days = wh[wh["status"] == "Surplus"]

daily_unmet = (
    deficit_days.groupby("date")["net_flow"]
    .apply(lambda x: abs(x).sum())
    .reset_index(name="unmet")
)
daily_idle = (
    surplus_days.groupby("date")["net_flow"]
    .agg("sum")
    .reset_index(name="idle")
)

days_with_deficit = len(daily_unmet)
avg_daily_unmet   = daily_unmet["unmet"].mean()
max_daily_unmet   = daily_unmet["unmet"].max()
total_unmet       = daily_unmet["unmet"].sum()

avg_daily_idle    = daily_idle["idle"].mean() if not daily_idle.empty else 0
max_daily_idle    = daily_idle["idle"].max()  if not daily_idle.empty else 0
total_idle        = daily_idle["idle"].sum()  if not daily_idle.empty else 0

print(f"Days with deficit stations:    {days_with_deficit:,} of {total_days:,} ({100*days_with_deficit/total_days:.1f}%)")
print(f"Avg daily unmet demand:        {avg_daily_unmet:.1f} bikes/day")
print(f"Max single-day unmet demand:   {max_daily_unmet:.0f} bikes")
print(f"Total unmet demand (all time): {total_unmet:,.0f} bikes")
print(f"Avg daily idle inventory:      {avg_daily_idle:.1f} bikes/day")
print(f"Max single-day idle inventory: {max_daily_idle:.0f} bikes")
print(f"Total idle inventory (all-time): {total_idle:,.0f} bikes")

# ── 3. Revenue Impact ─────────────────────────────────────────────
print("\n── 3. REVENUE IMPACT ────────────────────────────────────────")
total_revenue_at_risk = total_unmet * UNMET_TRIP_LOSS
annual_revenue_at_risk = (total_unmet / date_range) * UNMET_TRIP_LOSS
daily_revenue_at_risk  = avg_daily_unmet * UNMET_TRIP_LOSS

print(f"Revenue per trip (benchmark):  ${REVENUE_PER_TRIP:.2f}")
print(f"Daily revenue at risk:         ${daily_revenue_at_risk:.2f}")
print(f"Annual revenue at risk:        ${annual_revenue_at_risk:,.0f}")
print(f"Total revenue at risk (all):   ${total_revenue_at_risk:,.0f}")

# If optimization resolves all unmet demand
total_revenue_recoverable  = total_revenue_at_risk
annual_revenue_recoverable = annual_revenue_at_risk
print(f"\nIf optimization deployed:")
print(f"  Annual recoverable revenue:  ${annual_revenue_recoverable:,.0f}")
print(f"  Total recoverable revenue:   ${total_revenue_recoverable:,.0f}")

# ── 4. Operational Cost Savings ───────────────────────────────────
print("\n── 4. OPERATIONAL COST SAVINGS ──────────────────────────────")
# Without optimization: random/manual rebalancing assumed 2x distance
# With optimization: MCF minimizes distance
assumed_manual_km_per_bike = 3.0   # industry assumption without routing
optimized_km_per_bike      = 9.6 / 21  # from our validated dashboard output

manual_daily_cost     = avg_daily_unmet * assumed_manual_km_per_bike * COST_PER_KM
optimized_daily_cost  = avg_daily_unmet * optimized_km_per_bike * COST_PER_KM
daily_cost_saving     = manual_daily_cost - optimized_daily_cost
annual_cost_saving    = daily_cost_saving * 365

print(f"Avg km/bike (manual routing):  {assumed_manual_km_per_bike:.2f} km")
print(f"Avg km/bike (MCF optimized):   {optimized_km_per_bike:.2f} km")
print(f"Daily cost without optimizer:  ${manual_daily_cost:.2f}")
print(f"Daily cost with optimizer:     ${optimized_daily_cost:.2f}")
print(f"Daily routing cost saving:     ${daily_cost_saving:.2f}")
print(f"Annual routing cost saving:    ${annual_cost_saving:,.0f}")

# ── 5. Labor / Time Savings ───────────────────────────────────────
print("\n── 5. LABOR & TIME SAVINGS ──────────────────────────────────")
hrs_per_day_manual    = (avg_daily_unmet * MINS_PER_MOVE) / 60
labor_cost_per_day    = hrs_per_day_manual * REBALANCE_COST_HR
annual_labor_cost     = labor_cost_per_day * 365

# Optimized routing reduces unnecessary moves by consolidating routes
# Conservative: 20% labor reduction from better routing
labor_saving_pct      = 0.20
annual_labor_saving   = annual_labor_cost * labor_saving_pct

print(f"Avg bikes to reposition/day:   {avg_daily_unmet:.1f}")
print(f"Time per bike move:            {MINS_PER_MOVE} min")
print(f"Daily rebalancing hours:       {hrs_per_day_manual:.1f} hrs")
print(f"Daily labor cost:              ${labor_cost_per_day:.2f}")
print(f"Annual labor cost:             ${annual_labor_cost:,.0f}")
print(f"Annual labor saving (20%):     ${annual_labor_saving:,.0f}")

# ── 6. KPI Summary ───────────────────────────────────────────────
print("\n── 6. KPI SUMMARY (RESUME-READY) ────────────────────────────")
total_annual_impact = annual_revenue_recoverable + annual_cost_saving + annual_labor_saving
print(f"Stations monitored:            {unique_stations}")
print(f"Trip records processed:        {total_trips:,.0f}")
print(f"Years of data:                 {date_range:.0f}")
print(f"Avg daily unmet demand:        {avg_daily_unmet:.0f} bikes/day")
print(f"Avg daily idle inventory:      {avg_daily_idle:.0f} bikes/day")
print(f"Daily revenue at risk:         ${daily_revenue_at_risk:.0f}")
print(f"Annual revenue recoverable:    ${annual_revenue_recoverable:,.0f}")
print(f"Annual routing cost saving:    ${annual_cost_saving:,.0f}")
print(f"Annual labor saving:           ${annual_labor_saving:,.0f}")
print(f"Total annual business impact:  ${total_annual_impact:,.0f}")
print(f"Pct days with imbalance:       {100*days_with_deficit/total_days:.0f}%")