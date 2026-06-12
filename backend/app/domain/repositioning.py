"""Decide how to move idle trucks from surplus zones to forecasted-demand zones.

This is the classic transportation problem: ship units from sources (zones with
more trucks than forecasted demand) to sinks (zones short of trucks) at minimum
total move cost. We solve it as a min-cost max-flow.
"""

from __future__ import annotations

from dataclasses import dataclass

INF = float("inf")


@dataclass
class Move:
    from_zone: int
    to_zone: int
    trucks: int
    cost: float


@dataclass
class ZoneOutlook:
    zone_id: int
    supply: int
    forecast: int
    final_supply: int
    idle: int
    unmet: int


@dataclass
class RepositioningPlan:
    moves: list[Move]
    zones: list[ZoneOutlook]
    move_cost: float
    idle_before: int
    idle_after: int
    unmet_before: int
    unmet_after: int


class _MinCostFlow:
    """Min-cost max-flow via successive shortest paths (SPFA / Bellman-Ford)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.graph: list[list[int]] = [[] for _ in range(n)]
        # Each edge: [to, capacity, cost, reverse_index]
        self.edges: list[list] = []

    def add_edge(self, u: int, v: int, capacity: int, cost: float) -> int:
        eid = len(self.edges)
        self.graph[u].append(eid)
        self.edges.append([v, capacity, cost, eid + 1])
        self.graph[v].append(eid + 1)
        self.edges.append([u, 0, -cost, eid])
        return eid

    def solve(self, source: int, sink: int) -> tuple[int, float]:
        total_flow = 0
        total_cost = 0.0
        while True:
            dist = [INF] * self.n
            in_queue = [False] * self.n
            prev_edge = [-1] * self.n
            dist[source] = 0.0
            queue = [source]
            while queue:
                u = queue.pop(0)
                in_queue[u] = False
                for eid in self.graph[u]:
                    v, cap, cost, _ = self.edges[eid]
                    if cap > 0 and dist[u] + cost < dist[v]:
                        dist[v] = dist[u] + cost
                        prev_edge[v] = eid
                        if not in_queue[v]:
                            in_queue[v] = True
                            queue.append(v)
            if dist[sink] == INF:
                break

            # Push the bottleneck along the cheapest path.
            push = INF
            v = sink
            while v != source:
                eid = prev_edge[v]
                push = min(push, self.edges[eid][1])
                v = self.edges[self.edges[eid][3]][0]
            v = sink
            while v != source:
                eid = prev_edge[v]
                self.edges[eid][1] -= push
                self.edges[self.edges[eid][3]][1] += push
                v = self.edges[self.edges[eid][3]][0]
            total_flow += int(push)
            total_cost += push * dist[sink]
        return total_flow, total_cost

    def flow_on(self, edge_id: int, original_capacity: int) -> int:
        return original_capacity - self.edges[edge_id][1]


def plan_repositioning(
    zone_ids: list[int],
    supply: list[int],
    forecast: list[int],
    cost_matrix: list[list[float]],
) -> RepositioningPlan:
    n = len(zone_ids)
    surplus = [max(0, supply[i] - forecast[i]) for i in range(n)]
    deficit = [max(0, forecast[i] - supply[i]) for i in range(n)]

    idle_before = sum(surplus)
    unmet_before = sum(deficit)

    source, sink = n, n + 1
    flow = _MinCostFlow(n + 2)
    move_edges: list[tuple[int, int, int]] = []  # (edge_id, from_index, to_index)

    for i in range(n):
        if surplus[i] > 0:
            flow.add_edge(source, i, surplus[i], 0.0)
        if deficit[i] > 0:
            flow.add_edge(i, sink, deficit[i], 0.0)

    for i in range(n):
        if surplus[i] == 0:
            continue
        for j in range(n):
            if i == j or deficit[j] == 0:
                continue
            eid = flow.add_edge(i, j, surplus[i], cost_matrix[i][j])
            move_edges.append((eid, i, j))

    _, move_cost = flow.solve(source, sink)

    moves: list[Move] = []
    inflow = [0] * n
    outflow = [0] * n
    for eid, i, j in move_edges:
        moved = flow.flow_on(eid, surplus[i])
        if moved > 0:
            moves.append(Move(zone_ids[i], zone_ids[j], moved, round(cost_matrix[i][j] * moved, 3)))
            outflow[i] += moved
            inflow[j] += moved

    zones: list[ZoneOutlook] = []
    idle_after = 0
    unmet_after = 0
    for i in range(n):
        final = supply[i] - outflow[i] + inflow[i]
        idle = max(0, final - forecast[i])
        unmet = max(0, forecast[i] - final)
        idle_after += idle
        unmet_after += unmet
        zones.append(
            ZoneOutlook(zone_ids[i], supply[i], forecast[i], final, idle, unmet)
        )

    return RepositioningPlan(
        moves=moves,
        zones=zones,
        move_cost=round(move_cost, 3),
        idle_before=idle_before,
        idle_after=idle_after,
        unmet_before=unmet_before,
        unmet_after=unmet_after,
    )
