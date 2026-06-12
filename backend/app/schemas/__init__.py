"""Pydantic request/response schemas (the API contract)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NodeOut(BaseModel):
    id: int
    x: float
    y: float


class EdgeOut(BaseModel):
    source: int
    target: int
    time: float


class DepotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    node_id: int


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    capacity: int
    depot_id: int


class NetworkSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: str


class NetworkOut(BaseModel):
    id: int
    name: str
    kind: str
    width: int
    height: int
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    depots: list[DepotOut]


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    node_id: int
    demand: int
    priority: int
    status: str
    raw_text: str | None = None
    created_at: datetime


class OrderCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    node_id: int
    demand: int = Field(default=1, ge=1, le=20)
    priority: int = Field(default=2, ge=1, le=3)


class NlOrderRequest(BaseModel):
    text: str = Field(min_length=1, max_length=280)


class NlOrderResponse(BaseModel):
    order: OrderOut
    interpreted: dict
    used_ai: bool


class RouteStopOut(BaseModel):
    position: int
    order_id: int
    label: str
    node_id: int
    demand: int
    priority: int
    arrival_cost: float


class RouteOut(BaseModel):
    id: int
    vehicle_id: int
    vehicle_name: str
    total_cost: float
    demand: int
    capacity: int
    geometry: list[int]
    stops: list[RouteStopOut]


class OptimizeResponse(BaseModel):
    run_id: int
    total_cost: float
    served_count: int
    unassigned_count: int
    unassigned_order_ids: list[int]
    briefing: str
    used_ai: bool
    routes: list[RouteOut]


class ZonePlan(BaseModel):
    zone_id: int
    name: str
    node_id: int
    trucks: int
    forecast: int
    final_trucks: int
    idle: int
    unmet: int


class MoveOut(BaseModel):
    from_zone: int
    to_zone: int
    from_name: str
    to_name: str
    trucks: int
    cost: float


class PlanResponse(BaseModel):
    zones: list[ZonePlan]
    moves: list[MoveOut]
    move_cost: float
    idle_before: int
    idle_after: int
    unmet_before: int
    unmet_after: int
    briefing: str
    used_ai: bool


class SyncResponse(BaseModel):
    rows: dict[str, int]


class DemandSummaryRow(BaseModel):
    zone_name: str
    days: int
    avg_demand: float
    min_demand: int
    max_demand: int
    total_demand: int
    weekend_avg: float | None = None
    weekday_avg: float | None = None


class RunMetricRow(BaseModel):
    run_id: int
    created_at: datetime
    total_cost: float
    served_count: int
    unassigned_count: int
