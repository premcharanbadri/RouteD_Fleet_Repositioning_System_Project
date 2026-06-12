# Full reload of the operational data into the Snowflake star schema. The volume
# here is tiny (a demo network), so TRUNCATE + INSERT is simpler and clearly
# correct; a production pipeline would switch to incremental MERGE on the keys.

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DemandHistory, Network, OptimizationRun, Zone
from app.warehouse.client import connect
from app.warehouse.schema import DDL


def sync(db: Session) -> dict[str, int]:
    networks = list(db.scalars(select(Network)).all())
    zones = list(db.scalars(select(Zone)).all())
    history = list(db.scalars(select(DemandHistory)).all())
    runs = list(db.scalars(select(OptimizationRun)).all())

    zone_network = {z.id: z.network_id for z in zones}

    network_rows = [(n.id, n.name, n.kind, n.width, n.height) for n in networks]
    zone_rows = [(z.id, z.network_id, z.name, z.node_id) for z in zones]
    demand_rows = [
        (h.zone_id, zone_network.get(h.zone_id), h.day_index, h.count) for h in history
    ]
    run_rows = [
        (r.id, r.network_id, r.created_at, r.total_cost, r.served_count, r.unassigned_count)
        for r in runs
    ]

    with connect() as conn:
        cur = conn.cursor()
        for ddl in DDL:
            cur.execute(ddl)

        _reload(cur, "dim_network", "(network_id, name, kind, width, height)", network_rows)
        _reload(cur, "dim_zone", "(zone_id, network_id, name, node_id)", zone_rows)
        _reload(cur, "fact_demand", "(zone_id, network_id, day_index, demand)", demand_rows)
        _reload(
            cur,
            "fact_optimization_run",
            "(run_id, network_id, created_at, total_cost, served_count, unassigned_count)",
            run_rows,
        )
        conn.commit()

    return {
        "dim_network": len(network_rows),
        "dim_zone": len(zone_rows),
        "fact_demand": len(demand_rows),
        "fact_optimization_run": len(run_rows),
    }


def _reload(cur: Any, table: str, columns: str, rows: list[tuple]) -> None:
    cur.execute(f"TRUNCATE TABLE {table}")
    if not rows:
        return
    placeholders = ", ".join(["%s"] * len(rows[0]))
    cur.executemany(f"INSERT INTO {table} {columns} VALUES ({placeholders})", rows)
