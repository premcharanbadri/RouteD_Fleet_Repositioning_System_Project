# Capacitated vehicle routing: Clarke-Wright savings to build routes, then 2-opt
# to polish each one. Works on cost-matrix indices (0 = depot, 1..N = stops) so
# it stays decoupled from the graph, database and API.

from __future__ import annotations

from dataclasses import dataclass, field

Matrix = list[list[float]]


@dataclass
class VehicleRoute:
    stops: list[int]  # ordered stop indices (excludes the depot)
    demand: int
    cost: float


@dataclass
class VrpSolution:
    routes: list[VehicleRoute]
    unassigned: list[int] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.routes)


def route_cost(stops: list[int], cost: Matrix, depot: int = 0) -> float:
    """Closed-tour cost: depot -> stops... -> depot."""
    if not stops:
        return 0.0
    total = cost[depot][stops[0]]
    for a, b in zip(stops, stops[1:]):
        total += cost[a][b]
    total += cost[stops[-1]][depot]
    return total


def nearest_neighbor(stops: list[int], cost: Matrix, depot: int = 0) -> list[int]:
    """Greedy construction: always hop to the closest unvisited stop."""
    remaining = set(stops)
    order: list[int] = []
    current = depot
    while remaining:
        nxt = min(remaining, key=lambda s: cost[current][s])
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return order


def two_opt(stops: list[int], cost: Matrix, depot: int = 0) -> list[int]:
    # Reverse any segment whose reversal shortens the tour, until none does.
    if len(stops) < 3:
        return stops[:]
    best = stops[:]
    best_cost = route_cost(best, cost, depot)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                cand_cost = route_cost(candidate, cost, depot)
                if cand_cost + 1e-9 < best_cost:
                    best, best_cost = candidate, cand_cost
                    improved = True
    return best


def clarke_wright(
    cost: Matrix,
    demands: list[int],
    capacity: int,
    num_vehicles: int,
    depot: int = 0,
) -> VrpSolution:
    # Capped at num_vehicles routes. Stops that don't fit the fleet/capacity
    # limits come back in `unassigned` instead of being dropped silently.
    stops = [i for i in range(len(demands)) if i != depot]

    # Start with one route per stop that fits a vehicle.
    routes: list[list[int]] = []
    unassigned: list[int] = []
    for s in stops:
        if demands[s] > capacity:
            unassigned.append(s)
        else:
            routes.append([s])

    route_of = {s: idx for idx, r in enumerate(routes) for s in r}
    route_demand = {idx: demands[r[0]] for idx, r in enumerate(routes)}

    # Phase 1: compute savings and merge.
    savings: list[tuple[float, int, int]] = []
    for a_idx in range(len(stops)):
        for b_idx in range(a_idx + 1, len(stops)):
            i, j = stops[a_idx], stops[b_idx]
            saving = cost[depot][i] + cost[depot][j] - cost[i][j]
            savings.append((saving, i, j))
    savings.sort(reverse=True)

    for saving, i, j in savings:
        if saving <= 0:
            break
        ri, rj = route_of.get(i), route_of.get(j)
        if ri is None or rj is None or ri == rj:
            continue
        route_i, route_j = routes[ri], routes[rj]
        # i and j must each sit at an end of their route to merge cleanly.
        if not _is_endpoint(route_i, i) or not _is_endpoint(route_j, j):
            continue
        if route_demand[ri] + route_demand[rj] > capacity:
            continue

        merged = _merge(route_i, i, route_j, j)
        routes[ri] = merged
        route_demand[ri] = route_demand[ri] + route_demand[rj]
        for node in route_j:
            route_of[node] = ri
        routes[rj] = []
        route_demand[rj] = 0

    active = [r for r in routes if r]

    # Phase 2: 2-opt polish each route.
    active = [two_opt(r, cost, depot) for r in active]

    # Phase 3: respect fleet size — keep the heaviest routes, drop the rest.
    active.sort(key=lambda r: sum(demands[s] for s in r), reverse=True)
    kept, overflow = active[:num_vehicles], active[num_vehicles:]
    for r in overflow:
        unassigned.extend(r)

    solution_routes = [
        VehicleRoute(stops=r, demand=sum(demands[s] for s in r), cost=route_cost(r, cost, depot))
        for r in kept
    ]
    return VrpSolution(routes=solution_routes, unassigned=sorted(unassigned))


def _is_endpoint(route: list[int], node: int) -> bool:
    return route[0] == node or route[-1] == node


def _merge(route_i: list[int], i: int, route_j: list[int], j: int) -> list[int]:
    """Join two routes so that ``i`` and ``j`` become adjacent."""
    left = route_i if route_i[-1] == i else route_i[::-1]
    right = route_j if route_j[0] == j else route_j[::-1]
    return left + right
