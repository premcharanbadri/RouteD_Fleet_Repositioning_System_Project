"""Tests for the city graph and shortest-path algorithms."""

from __future__ import annotations

import math

import pytest

from app.domain.graph import CityGraph


def test_grid_dimensions() -> None:
    g = CityGraph(5, 4, seed=1)
    assert len(g.nodes) == 20
    # A w x h grid has w*(h-1) + h*(w-1) undirected edges.
    assert len(g.edges()) == 5 * 3 + 4 * 4


def test_astar_matches_dijkstra() -> None:
    g = CityGraph(8, 8, seed=3)
    dist, _ = g.dijkstra(0)
    for target in (7, 35, 63, 56):
        path, cost = g.shortest_path(0, target)
        assert path[0] == 0 and path[-1] == target
        assert cost == pytest.approx(dist[target])


def test_heuristic_is_admissible() -> None:
    """Straight-line distance must never exceed true travel cost."""
    g = CityGraph(7, 7, seed=5)
    dist, _ = g.dijkstra(0)
    src = g.node(0)
    for nid, true_cost in dist.items():
        n = g.node(nid)
        straight = math.hypot(n.x - src.x, n.y - src.y)
        assert straight <= true_cost + 1e-9


def test_cost_matrix_symmetric() -> None:
    g = CityGraph(6, 6, seed=2)
    terminals = [0, 5, 14, 35]
    matrix, geometry = g.cost_matrix(terminals)
    n = len(terminals)
    for i in range(n):
        assert matrix[i][i] == 0.0
        for j in range(n):
            assert matrix[i][j] == pytest.approx(matrix[j][i])
    assert geometry[(0, 35)][0] == 0 and geometry[(0, 35)][-1] == 35


def test_rejects_degenerate_grid() -> None:
    with pytest.raises(ValueError):
        CityGraph(1, 5)
