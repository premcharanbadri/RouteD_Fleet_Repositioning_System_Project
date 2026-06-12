# Analytics endpoints backed by the Snowflake warehouse. These hard-depend on
# Snowflake (no offline fallback) and return 503 when it isn't configured.

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_network, require_warehouse
from app.database import get_db
from app.models import Network
from app.schemas import DemandSummaryRow, RunMetricRow, SyncResponse
from app.warehouse import analytics, etl

router = APIRouter(prefix="/api/analytics", dependencies=[Depends(require_warehouse)])


@router.post("/sync", response_model=SyncResponse)
def sync_warehouse(db: Session = Depends(get_db)) -> SyncResponse:
    return SyncResponse(rows=etl.sync(db))


@router.get("/demand-summary", response_model=list[DemandSummaryRow])
def demand_summary(network: Network = Depends(current_network)) -> list[DemandSummaryRow]:
    rows = analytics.demand_summary(network.id)
    return [DemandSummaryRow(**row) for row in rows]


@router.get("/run-metrics", response_model=list[RunMetricRow])
def run_metrics(network: Network = Depends(current_network)) -> list[RunMetricRow]:
    rows = analytics.run_metrics(network.id)
    return [RunMetricRow(**row) for row in rows]
