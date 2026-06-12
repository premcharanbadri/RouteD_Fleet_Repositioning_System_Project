"""Network service: builds and caches the in-memory CityGraph for a Network row
and serialises it for the frontend."""

from __future__ import annotations

import hashlib
import threading

from app.domain.graph import CityGraph
from app.models import Network
from app.schemas import DepotOut, EdgeOut, NetworkOut, NodeOut

_cache: dict[tuple[int, int, int], CityGraph] = {}
_cache_lock = threading.Lock()


def get_graph(network: Network) -> CityGraph:
    key = (network.width, network.height, network.seed)
    graph = _cache.get(key)
    if graph is None:
        # Build under a lock so concurrent requests don't each rebuild the graph.
        with _cache_lock:
            graph = _cache.get(key)
            if graph is None:
                graph = CityGraph(network.width, network.height, network.seed)
                _cache[key] = graph
    return graph


def serialize_network(network: Network) -> NetworkOut:
    graph = get_graph(network)
    return NetworkOut(
        id=network.id,
        name=network.name,
        kind=network.kind,
        width=network.width,
        height=network.height,
        nodes=[NodeOut(id=n.id, x=n.x, y=n.y) for n in graph.nodes],
        edges=[EdgeOut(source=u, target=v, time=round(w, 3)) for u, v, w in graph.edges()],
        depots=[DepotOut.model_validate(d) for d in network.depots],
    )


def pick_node(graph: CityGraph, zone: str | None, seed_text: str) -> int:
    """Deterministically pick a grid node for a delivery, optionally biased to a
    named zone (north/south/east/west/center). Used to ground a free-text order
    onto an actual location on the map without external geocoding."""
    w, h = graph.width, graph.height
    x_lo, x_hi, y_lo, y_hi = 0, w - 1, 0, h - 1
    z = (zone or "").lower()
    if "north" in z:
        y_hi = max(0, h // 3)
    elif "south" in z:
        y_lo = min(h - 1, 2 * h // 3)
    if "west" in z:
        x_hi = max(0, w // 3)
    elif "east" in z:
        x_lo = min(w - 1, 2 * w // 3)
    if "center" in z or "central" in z or "downtown" in z:
        x_lo, x_hi = w // 3, 2 * w // 3
        y_lo, y_hi = h // 3, 2 * h // 3

    digest = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16)
    x = x_lo + (digest % (x_hi - x_lo + 1))
    y = y_lo + ((digest // 97) % (y_hi - y_lo + 1))
    return graph.node_id(x, y)
