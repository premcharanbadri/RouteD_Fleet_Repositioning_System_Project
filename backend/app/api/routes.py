"""REST endpoints for networks, orders and optimisation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import parse_order
from app.api.deps import current_network, rate_limit_nl
from app.database import get_db
from app.models import Network, Order, Vehicle
from app.schemas import (
    NetworkOut,
    NetworkSummary,
    NlOrderRequest,
    NlOrderResponse,
    OptimizeResponse,
    OrderCreate,
    OrderOut,
    PlanResponse,
    VehicleOut,
)
from app.services.network import get_graph, serialize_network
from app.services.optimizer import optimize
from app.services.planning import build_plan

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/networks", response_model=list[NetworkSummary])
def list_networks(db: Session = Depends(get_db)) -> list[Network]:
    return list(db.scalars(select(Network).order_by(Network.id)).all())


@router.get("/network", response_model=NetworkOut)
def get_network(network: Network = Depends(current_network)) -> NetworkOut:
    return serialize_network(network)


@router.get("/plan", response_model=PlanResponse)
def get_plan(network: Network = Depends(current_network)) -> PlanResponse:
    return build_plan(network)


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(
    network: Network = Depends(current_network), db: Session = Depends(get_db)
) -> list[Vehicle]:
    depot_ids = [d.id for d in network.depots]
    return list(db.scalars(select(Vehicle).where(Vehicle.depot_id.in_(depot_ids))).all())


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    network: Network = Depends(current_network), db: Session = Depends(get_db)
) -> list[Order]:
    return list(
        db.scalars(
            select(Order).where(Order.network_id == network.id).order_by(Order.created_at)
        ).all()
    )


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    network: Network = Depends(current_network),
    db: Session = Depends(get_db),
) -> Order:
    graph = get_graph(network)
    if payload.node_id not in range(network.width * network.height):
        raise HTTPException(status_code=422, detail="node_id out of range")
    _ = graph  # validation only
    order = Order(
        network_id=network.id,
        label=payload.label,
        node_id=payload.node_id,
        demand=payload.demand,
        priority=payload.priority,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.post(
    "/orders/nl",
    response_model=NlOrderResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_nl)],
)
def create_order_nl(
    payload: NlOrderRequest,
    network: Network = Depends(current_network),
    db: Session = Depends(get_db),
) -> NlOrderResponse:
    graph = get_graph(network)
    interpreted, used_ai = parse_order(payload.text, graph)
    order = Order(
        network_id=network.id,
        label=interpreted["label"],
        node_id=interpreted["node_id"],
        demand=interpreted["demand"],
        priority=interpreted["priority"],
        raw_text=payload.text,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return NlOrderResponse(
        order=OrderOut.model_validate(order), interpreted=interpreted, used_ai=used_ai
    )


@router.delete("/orders/{order_id}", status_code=204)
def delete_order(
    order_id: int,
    network: Network = Depends(current_network),
    db: Session = Depends(get_db),
) -> None:
    order = db.get(Order, order_id)
    if order is None or order.network_id != network.id:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()


@router.post("/optimize", response_model=OptimizeResponse)
def run_optimization(
    network: Network = Depends(current_network), db: Session = Depends(get_db)
) -> OptimizeResponse:
    return optimize(db, network)
