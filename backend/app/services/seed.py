"""Idempotent demo-data seeding so the app is useful the moment it boots.

Seeds two preset networks over real Austin, TX areas:
  * "Austin Metro" — an on-demand delivery grid with a depot, vans and live
    orders for the routing view, plus zones/demand history for planning.
  * "U-Haul Austin" — a rental fleet spread across Austin neighborhoods, used
    only for the forecast + repositioning view (no per-order routing).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.graph import CityGraph
from app.models import DemandHistory, Depot, Network, Order, Vehicle, Zone
from app.services.network import get_graph, pick_node

# Real Austin spots, placed by their rough direction from downtown.
_DEMO_ORDERS = [
    ("Whole Foods Market — The Domain", "north", 4, 3),
    ("Texas State Capitol", "center", 2, 2),
    ("Franklin Barbecue", "east", 6, 3),
    ("Mozart's Coffee Roasters", "west", 3, 1),
    ("Home Slice Pizza — South Congress", "south", 2, 2),
    ("Q2 Stadium", "north", 5, 2),
    ("Veracruz All Natural", "east", 1, 1),
    ("Moody Center", "center", 3, 3),
    ("Saint Elmo Brewing", "south", 4, 2),
    ("Tarrytown Pharmacy", "west", 2, 1),
]

# Austin neighborhoods. (name, direction from downtown, parked trucks, weekly demand baseline)
_METRO_ZONES = [
    ("The Domain", "north", 6, 4),
    ("Downtown", "center", 2, 9),
    ("East Austin", "east", 5, 5),
    ("Zilker", "west", 4, 3),
    ("South Congress", "south", 1, 7),
]

_CITY_ZONES = [
    ("Downtown", "center", 12, 8),
    ("The Domain", "north", 4, 11),
    ("East Austin", "east", 9, 7),
    ("South Austin", "south", 3, 9),
    ("Westlake", "west", 7, 4),
]


def _weekly_demand(base: int, zone_index: int, days: int = 21) -> list[int]:
    """Three weeks of synthetic daily demand with a weekend bump, deterministic
    per zone so forecasts are stable across restarts."""
    weekday_shape = [-1, -1, 0, 0, 1, 3, 2]  # Mon..Sun, weekend-heavy
    counts = []
    for day in range(days):
        shape = weekday_shape[day % 7]
        wobble = ((day * 7 + zone_index * 13) % 5) - 2  # small repeatable noise
        counts.append(max(0, base + shape + wobble))
    return counts


def _add_zones(
    db: Session,
    network: Network,
    graph: CityGraph,
    specs: Sequence[tuple[str, str, int, int]],
) -> None:
    for index, (name, hint, trucks, base) in enumerate(specs):
        zone = Zone(
            network_id=network.id,
            name=name,
            node_id=pick_node(graph, hint, name),
            truck_count=trucks,
        )
        db.add(zone)
        db.flush()
        for day, count in enumerate(_weekly_demand(base, index)):
            db.add(DemandHistory(zone_id=zone.id, day_index=day, count=count))


def _seed_metro(db: Session) -> Network:
    network = Network(name="Austin Metro", kind="metro", width=10, height=8, seed=7)
    db.add(network)
    db.flush()

    graph = get_graph(network)
    center = graph.node_id(network.width // 2, network.height // 2)
    depot = Depot(network_id=network.id, name="Downtown Depot", node_id=center)
    db.add(depot)
    db.flush()

    for i in range(3):
        db.add(Vehicle(depot_id=depot.id, name=f"Van {i + 1}", capacity=10))

    for label, hint, demand, priority in _DEMO_ORDERS:
        db.add(
            Order(
                network_id=network.id,
                label=label,
                node_id=pick_node(graph, hint, label),
                demand=demand,
                priority=priority,
            )
        )

    _add_zones(db, network, graph, _METRO_ZONES)
    return network


def _seed_cities(db: Session) -> None:
    network = Network(name="U-Haul Austin", kind="cities", width=14, height=10, seed=23)
    db.add(network)
    db.flush()
    graph = get_graph(network)
    _add_zones(db, network, graph, _CITY_ZONES)


def seed_if_empty(db: Session) -> Network:
    existing = db.scalar(select(Network))
    if existing is not None:
        return existing

    metro = _seed_metro(db)
    _seed_cities(db)
    db.commit()
    return metro
