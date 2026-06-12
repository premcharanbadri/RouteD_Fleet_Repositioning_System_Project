# Snowflake connection for the analytics tier. The connector is imported lazily
# (it's an optional dependency) so the app boots without it installed.

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import get_settings


@contextmanager
def connect() -> Iterator[Any]:
    import snowflake.connector

    s = get_settings()
    conn = snowflake.connector.connect(
        account=s.snowflake_account,
        user=s.snowflake_user,
        password=s.snowflake_password,
        warehouse=s.snowflake_warehouse,
        database=s.snowflake_database,
        schema=s.snowflake_schema,
        role=s.snowflake_role or None,
    )
    try:
        yield conn
    finally:
        conn.close()
