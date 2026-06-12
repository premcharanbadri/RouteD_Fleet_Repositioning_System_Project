"""Shared API dependencies."""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Network


def current_network(
    network_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> Network:
    if network_id is not None:
        network = db.get(Network, network_id)
        if network is None:
            raise HTTPException(status_code=404, detail="Network not found")
        return network
    network = db.scalar(select(Network).order_by(Network.id))
    if network is None:
        raise HTTPException(status_code=404, detail="No network configured")
    return network


def require_warehouse() -> None:
    # Guard the analytics tier; it has no offline fallback by design.
    if not get_settings().snowflake_enabled:
        raise HTTPException(
            status_code=503,
            detail="Analytics warehouse not configured (set SNOWFLAKE_* env vars)",
        )


_hits: dict[str, deque[float]] = {}
_hits_lock = threading.Lock()


def rate_limit_nl(request: Request) -> None:
    # Fixed 60s window per client IP, guarding the paid AI order endpoint.
    limit = get_settings().nl_rate_per_minute
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _hits_lock:
        window = _hits.setdefault(client, deque())
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests, slow down")
        window.append(now)
