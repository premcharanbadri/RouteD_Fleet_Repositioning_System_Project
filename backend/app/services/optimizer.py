# Turns the current orders into a dispatch plan: wires the road graph (shortest
# paths) and the CVRP solver together, then persists the result.

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import generate_briefing
from app.domain.vrp import clarke_wright
from app.models import (
    Network,
    OptimizationRun,
    Order,
    Route,
    RouteStop,
    Vehicle,
)
from app.schemas import OptimizeResponse, RouteOut, RouteStopOut
from app.services.network import get_graph


def optimize(db: Session, network: Network) -> OptimizeResponse:
    graph = get_graph(network)
    depot = network.depots[0]
    vehicles = sorted(
        db.scalars(select(Vehicle).where(Vehicle.depot_id == depot.id)).all(),
        key=lambda v: v.capacity,
        reverse=True,
    )
    orders = db.scalars(
        select(Order).where(Order.network_id == network.id, Order.status != "delivered")
    ).all()

    if not orders or not vehicles:
        return _empty_response(db, network, len(orders))

    # Cost matrix over the depot plus every order location.
    order_nodes = [o.node_id for o in orders]
    unique_nodes = list(dict.fromkeys([depot.node_id, *order_nodes]))
    unique_matrix, geometry = graph.cost_matrix(unique_nodes)
    pos = {node: i for i, node in enumerate(unique_nodes)}

    # Index 0 = depot, indices 1..N = orders (in `orders` order).
    terminals = [depot.node_id, *order_nodes]
    n = len(terminals)
    cost = [
        [unique_matrix[pos[terminals[a]]][pos[terminals[b]]] for b in range(n)] for a in range(n)
    ]
    demands = [0, *[o.demand for o in orders]]

    capacity = max(v.capacity for v in vehicles)
    solution = clarke_wright(cost, demands, capacity=capacity, num_vehicles=len(vehicles))

    # Persist the run.
    run = OptimizationRun(network_id=network.id)
    db.add(run)
    db.flush()

    unassigned_order_ids = [orders[i - 1].id for i in solution.unassigned]
    route_outs: list[RouteOut] = []

    for route, vehicle in zip(solution.routes, vehicles):
        if route.demand > vehicle.capacity:
            unassigned_order_ids.extend(orders[i - 1].id for i in route.stops)
            continue

        ordered_orders = [orders[i - 1] for i in route.stops]
        polyline = _build_polyline(depot.node_id, [o.node_id for o in ordered_orders], geometry)
        db_route = Route(
            run_id=run.id,
            vehicle_id=vehicle.id,
            total_cost=round(route.cost, 3),
            demand=route.demand,
            geometry=polyline,
        )
        db.add(db_route)
        db.flush()

        stop_outs: list[RouteStopOut] = []
        cumulative = 0.0
        prev_idx = 0  # depot index in `terminals`
        for position, (order, stop_idx) in enumerate(zip(ordered_orders, route.stops)):
            cumulative += cost[prev_idx][stop_idx]
            prev_idx = stop_idx
            db.add(
                RouteStop(
                    route_id=db_route.id,
                    order_id=order.id,
                    position=position,
                    arrival_cost=round(cumulative, 3),
                )
            )
            order.status = "assigned"
            stop_outs.append(
                RouteStopOut(
                    position=position,
                    order_id=order.id,
                    label=order.label,
                    node_id=order.node_id,
                    demand=order.demand,
                    priority=order.priority,
                    arrival_cost=round(cumulative, 3),
                )
            )

        route_outs.append(
            RouteOut(
                id=db_route.id,
                vehicle_id=vehicle.id,
                vehicle_name=vehicle.name,
                total_cost=round(route.cost, 3),
                demand=route.demand,
                capacity=vehicle.capacity,
                geometry=polyline,
                stops=stop_outs,
            )
        )

    for oid in unassigned_order_ids:
        pending_order = db.get(Order, oid)
        if pending_order is not None:
            pending_order.status = "pending"

    served = sum(len(r.stops) for r in route_outs)
    run.total_cost = round(sum(r.total_cost for r in route_outs), 3)
    run.served_count = served
    run.unassigned_count = len(unassigned_order_ids)

    briefing, used_ai = generate_briefing(route_outs, unassigned_order_ids, run.total_cost)
    run.briefing = briefing
    db.commit()

    return OptimizeResponse(
        run_id=run.id,
        total_cost=run.total_cost,
        served_count=served,
        unassigned_count=len(unassigned_order_ids),
        unassigned_order_ids=sorted(set(unassigned_order_ids)),
        briefing=briefing,
        used_ai=used_ai,
        routes=route_outs,
    )


def _build_polyline(
    depot_node: int, stop_nodes: list[int], geometry: dict[tuple[int, int], list[int]]
) -> list[int]:
    # Stitch per-leg shortest paths into one polyline: depot -> stops... -> depot.
    sequence = [depot_node, *stop_nodes, depot_node]
    polyline: list[int] = [depot_node]
    for a, b in zip(sequence, sequence[1:]):
        if a == b:
            continue
        leg = geometry[(a, b)]
        polyline.extend(leg[1:])  # skip the duplicated leg-start node
    return polyline


def _empty_response(db: Session, network: Network, order_count: int) -> OptimizeResponse:
    run = OptimizationRun(
        network_id=network.id,
        served_count=0,
        unassigned_count=order_count,
        briefing="No orders or no vehicles available to dispatch.",
    )
    db.add(run)
    db.commit()
    return OptimizeResponse(
        run_id=run.id,
        total_cost=0.0,
        served_count=0,
        unassigned_count=order_count,
        unassigned_order_ids=[],
        briefing=run.briefing or "",
        used_ai=False,
        routes=[],
    )
