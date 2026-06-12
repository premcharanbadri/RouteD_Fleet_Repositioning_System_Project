# Star schema for the analytics warehouse: two dimensions and two fact tables.
# Snowflake accepts PRIMARY KEY syntax but doesn't enforce it; we keep it for
# documentation and downstream BI tools.

from __future__ import annotations

DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS dim_network (
        network_id INTEGER PRIMARY KEY,
        name       STRING,
        kind       STRING,
        width      INTEGER,
        height     INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_zone (
        zone_id    INTEGER PRIMARY KEY,
        network_id INTEGER,
        name       STRING,
        node_id    INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_demand (
        zone_id    INTEGER,
        network_id INTEGER,
        day_index  INTEGER,
        demand     INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_optimization_run (
        run_id           INTEGER PRIMARY KEY,
        network_id       INTEGER,
        created_at       TIMESTAMP_NTZ,
        total_cost       FLOAT,
        served_count     INTEGER,
        unassigned_count INTEGER
    )
    """,
)
