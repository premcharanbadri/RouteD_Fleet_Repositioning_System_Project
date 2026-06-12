"""Tests for the CVRP solver."""

from __future__ import annotations

from app.domain.graph import CityGraph
from app.domain.vrp import (
    clarke_wright,
    nearest_neighbor,
    route_cost,
    two_opt,
)


def _matrix() -> list[list[float]]:
    g = CityGraph(8, 8, seed=11)
    terminals = [g.node_id(4, 4), 0, 7, 56, 63, 27, 36, 9]
    matrix, _ = g.cost_matrix(terminals)
    return matrix


def test_nearest_neighbor_visits_all() -> None:
    cost = _matrix()
    order = nearest_neighbor([1, 2, 3, 4, 5, 6, 7], cost)
    assert sorted(order) == [1, 2, 3, 4, 5, 6, 7]


def test_two_opt_never_worsens() -> None:
    cost = _matrix()
    nn = nearest_neighbor([1, 2, 3, 4, 5, 6, 7], cost)
    improved = two_opt(nn, cost)
    assert route_cost(improved, cost) <= route_cost(nn, cost) + 1e-9


def test_clarke_wright_respects_capacity() -> None:
    cost = _matrix()
    demands = [0, 3, 4, 5, 2, 6, 1, 4]
    sol = clarke_wright(cost, demands, capacity=10, num_vehicles=3)
    assert len(sol.routes) <= 3
    for route in sol.routes:
        assert route.demand <= 10
        assert route.demand == sum(demands[s] for s in route.stops)


def test_every_stop_assigned_or_listed_once() -> None:
    cost = _matrix()
    demands = [0, 3, 4, 5, 2, 6, 1, 4]
    sol = clarke_wright(cost, demands, capacity=10, num_vehicles=3)
    served = [s for r in sol.routes for s in r.stops]
    assert sorted(served + sol.unassigned) == [1, 2, 3, 4, 5, 6, 7]


def test_oversized_order_is_unassigned() -> None:
    cost = _matrix()
    demands = [0, 99, 2, 3, 1, 2, 1, 1]  # stop 1 cannot fit any vehicle
    sol = clarke_wright(cost, demands, capacity=10, num_vehicles=3)
    assert 1 in sol.unassigned


def test_fleet_size_capped() -> None:
    cost = _matrix()
    demands = [0, 9, 9, 9, 9, 9, 9, 9]  # forces many separate routes
    sol = clarke_wright(cost, demands, capacity=10, num_vehicles=2)
    assert len(sol.routes) <= 2
