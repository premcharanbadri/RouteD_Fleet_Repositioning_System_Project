# OLAP queries over the star schema. These are the kind of aggregations the
# operational row store is the wrong tool for: per-zone demand profiles and
# cost/utilisation trends across many optimisation runs.

from __future__ import annotations

from app.warehouse.client import connect

# day_index % 7: 0=Mon .. 6=Sun, matching the seeded weekday shape (weekend-heavy).
_WEEKEND = "MOD(day_index, 7) IN (5, 6)"

_DEMAND_SUMMARY = f"""
    SELECT z.name AS zone_name,
           COUNT(*) AS days,
           AVG(f.demand) AS avg_demand,
           MIN(f.demand) AS min_demand,
           MAX(f.demand) AS max_demand,
           SUM(f.demand) AS total_demand,
           AVG(CASE WHEN {_WEEKEND} THEN f.demand END) AS weekend_avg,
           AVG(CASE WHEN NOT ({_WEEKEND}) THEN f.demand END) AS weekday_avg
    FROM fact_demand f
    JOIN dim_zone z ON z.zone_id = f.zone_id
    WHERE f.network_id = %(network_id)s
    GROUP BY z.name
    ORDER BY total_demand DESC
"""

_RUN_METRICS = """
    SELECT run_id, created_at, total_cost, served_count, unassigned_count
    FROM fact_optimization_run
    WHERE network_id = %(network_id)s
    ORDER BY created_at
"""


def demand_summary(network_id: int) -> list[dict]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(_DEMAND_SUMMARY, {"network_id": network_id})
        cols = [c[0].lower() for c in cur.description]
        return [_round(dict(zip(cols, row))) for row in cur.fetchall()]


def run_metrics(network_id: int) -> list[dict]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(_RUN_METRICS, {"network_id": network_id})
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _round(row: dict) -> dict:
    for key in ("avg_demand", "weekend_avg", "weekday_avg"):
        if row.get(key) is not None:
            row[key] = round(float(row[key]), 2)
    return row
