# A seeded grid road network. Each road's travel time is its length times a
# congestion factor (>= 1.0), so the fastest path isn't the straight-line one.

from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: int
    x: float
    y: float


class CityGraph:
    # Node ids are row-major: id = y * width + x. Travel time is symmetric,
    # which the Clarke-Wright savings solver relies on.

    def __init__(self, width: int, height: int, seed: int = 7) -> None:
        if width < 2 or height < 2:
            raise ValueError("Grid must be at least 2x2")
        self.width = width
        self.height = height
        self.seed = seed
        self._nodes: dict[int, Node] = {}
        self._adj: dict[int, list[tuple[int, float]]] = {}
        self._build()

    def _build(self) -> None:
        rng = random.Random(self.seed)
        for y in range(self.height):
            for x in range(self.width):
                nid = self.node_id(x, y)
                self._nodes[nid] = Node(nid, float(x), float(y))
                self._adj[nid] = []

        # Connect each node to its right and bottom neighbour (undirected).
        for y in range(self.height):
            for x in range(self.width):
                u = self.node_id(x, y)
                if x + 1 < self.width:
                    self._link(u, self.node_id(x + 1, y), rng)
                if y + 1 < self.height:
                    self._link(u, self.node_id(x, y + 1), rng)

    def _link(self, u: int, v: int, rng: random.Random) -> None:
        congestion = 1.0 + rng.random() * 2.0  # in [1.0, 3.0)
        length = self._distance(u, v)
        time = length * congestion
        self._adj[u].append((v, time))
        self._adj[v].append((u, time))

    def node_id(self, x: int, y: int) -> int:
        return y * self.width + x

    @property
    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def node(self, nid: int) -> Node:
        return self._nodes[nid]

    def neighbors(self, nid: int) -> list[tuple[int, float]]:
        return self._adj[nid]

    def edges(self) -> list[tuple[int, int, float]]:
        """Each undirected edge once, as (u, v, travel_time)."""
        seen: set[tuple[int, int]] = set()
        out: list[tuple[int, int, float]] = []
        for u, nbrs in self._adj.items():
            for v, w in nbrs:
                key = (u, v) if u < v else (v, u)
                if key not in seen:
                    seen.add(key)
                    out.append((key[0], key[1], w))
        return out

    def _distance(self, u: int, v: int) -> float:
        a, b = self._nodes[u], self._nodes[v]
        return math.hypot(a.x - b.x, a.y - b.y)

    def dijkstra(self, source: int) -> tuple[dict[int, float], dict[int, int]]:
        """Single-source shortest travel times. Returns (dist, prev)."""
        dist: dict[int, float] = {source: 0.0}
        prev: dict[int, int] = {}
        pq: list[tuple[float, int]] = [(0.0, source)]
        visited: set[int] = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            for v, w in self._adj[u]:
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    def shortest_path(self, source: int, target: int) -> tuple[list[int], float]:
        # A*; straight-line distance is admissible since every edge's time >= its length.
        if source == target:
            return [source], 0.0

        def h(n: int) -> float:
            return self._distance(n, target)

        g: dict[int, float] = {source: 0.0}
        prev: dict[int, int] = {}
        pq: list[tuple[float, int]] = [(h(source), source)]
        visited: set[int] = set()

        while pq:
            _, u = heapq.heappop(pq)
            if u == target:
                return self._reconstruct(prev, target), g[target]
            if u in visited:
                continue
            visited.add(u)
            for v, w in self._adj[u]:
                ng = g[u] + w
                if ng < g.get(v, math.inf):
                    g[v] = ng
                    prev[v] = u
                    heapq.heappush(pq, (ng + h(v), v))
        raise ValueError(f"No path from {source} to {target}")

    @staticmethod
    def _reconstruct(prev: dict[int, int], target: int) -> list[int]:
        path = [target]
        while target in prev:
            target = prev[target]
            path.append(target)
        path.reverse()
        return path

    def cost_matrix(
        self, terminals: list[int]
    ) -> tuple[list[list[float]], dict[tuple[int, int], list[int]]]:
        # Travel-time matrix between terminals plus each path's node geometry,
        # via one Dijkstra per terminal.
        index = {nid: i for i, nid in enumerate(terminals)}
        n = len(terminals)
        matrix = [[0.0] * n for _ in range(n)]
        geometry: dict[tuple[int, int], list[int]] = {}

        for src in terminals:
            dist, prev = self.dijkstra(src)
            for dst in terminals:
                if src == dst:
                    continue
                if dst not in dist:
                    raise ValueError(f"Node {dst} unreachable from {src}")
                matrix[index[src]][index[dst]] = dist[dst]
                geometry[(src, dst)] = self._reconstruct(prev, dst)
        return matrix, geometry
