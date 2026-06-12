# The road network is generated deterministically from (width, height, seed),
# so the Network row stores those parameters rather than every node/edge.

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Network(Base):
    __tablename__ = "networks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default="metro")  # metro | cities
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    depots: Mapped[list[Depot]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )
    zones: Mapped[list[Zone]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )


class Depot(Base):
    __tablename__ = "depots"

    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))
    name: Mapped[str] = mapped_column(String(80))
    node_id: Mapped[int] = mapped_column(Integer)

    network: Mapped[Network] = relationship(back_populates="depots")
    vehicles: Mapped[list[Vehicle]] = relationship(
        back_populates="depot", cascade="all, delete-orphan"
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"))
    name: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer)

    depot: Mapped[Depot] = relationship(back_populates="vehicles")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))
    label: Mapped[str] = mapped_column(String(120))
    node_id: Mapped[int] = mapped_column(Integer)
    demand: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1=low, 2=normal, 3=high
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|assigned|delivered
    raw_text: Mapped[str | None] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    network: Mapped[Network] = relationship(back_populates="orders")


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    served_count: Mapped[int] = mapped_column(Integer, default=0)
    unassigned_count: Mapped[int] = mapped_column(Integer, default=0)
    briefing: Mapped[str | None] = mapped_column(String, nullable=True)

    routes: Mapped[list[Route]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("optimization_runs.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    demand: Mapped[int] = mapped_column(Integer, default=0)
    # Full node-id polyline through the road network, for map rendering.
    geometry: Mapped[list[int]] = mapped_column(JSON, default=list)

    run: Mapped[OptimizationRun] = relationship(back_populates="routes")
    vehicle: Mapped[Vehicle] = relationship()
    stops: Mapped[list[RouteStop]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.position"
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    position: Mapped[int] = mapped_column(Integer)
    arrival_cost: Mapped[float] = mapped_column(Float, default=0.0)

    route: Mapped[Route] = relationship(back_populates="stops")
    order: Mapped[Order] = relationship()


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))
    name: Mapped[str] = mapped_column(String(80))
    node_id: Mapped[int] = mapped_column(Integer)
    truck_count: Mapped[int] = mapped_column(Integer, default=0)

    network: Mapped[Network] = relationship(back_populates="zones")
    demand_history: Mapped[list[DemandHistory]] = relationship(
        back_populates="zone", cascade="all, delete-orphan", order_by="DemandHistory.day_index"
    )


class DemandHistory(Base):
    __tablename__ = "demand_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    day_index: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)

    zone: Mapped[Zone] = relationship(back_populates="demand_history")
