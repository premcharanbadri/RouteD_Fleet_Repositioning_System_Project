# WebSocket that animates vehicles along their optimised routes. On connect we
# load the latest run, turn each route polyline into (x, y) waypoints, and stream
# position frames at a fixed tick until every vehicle is back at the depot.

from __future__ import annotations

import asyncio
import math

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Network, OptimizationRun, Route
from app.services.network import get_graph

router = APIRouter()

TICK_SECONDS = 0.1
SPEED = 0.25  # grid units advanced per tick


class _Vehicle:
    """Tracks one vehicle's progress along a polyline of (x, y) points."""

    def __init__(self, route_id: int, name: str, points: list[tuple[float, float]]) -> None:
        self.route_id = route_id
        self.name = name
        self.points = points
        self.seg_lengths = [
            math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])
        ]
        self.total = sum(self.seg_lengths) or 1.0
        self.travelled = 0.0

    @property
    def arrived(self) -> bool:
        return self.travelled >= self.total

    def advance(self, step: float) -> tuple[float, float]:
        self.travelled = min(self.total, self.travelled + step)
        remaining = self.travelled
        for i, length in enumerate(self.seg_lengths):
            if remaining <= length or length == 0:
                ax, ay = self.points[i]
                bx, by = self.points[i + 1]
                t = remaining / length if length else 0.0
                return ax + (bx - ax) * t, ay + (by - ay) * t
            remaining -= length
        return self.points[-1]


def _load_vehicles() -> list[_Vehicle]:
    with SessionLocal() as db:
        network = db.scalar(select(Network))
        if network is None:
            return []
        run = db.scalar(
            select(OptimizationRun)
            .where(OptimizationRun.network_id == network.id)
            .order_by(OptimizationRun.created_at.desc())
        )
        if run is None:
            return []
        graph = get_graph(network)
        routes = db.scalars(select(Route).where(Route.run_id == run.id)).all()
        vehicles: list[_Vehicle] = []
        for route in routes:
            pts = [(graph.node(nid).x, graph.node(nid).y) for nid in route.geometry]
            if len(pts) >= 2:
                vehicles.append(_Vehicle(route.id, route.vehicle.name, pts))
        return vehicles


@router.websocket("/ws/simulation")
async def simulate(ws: WebSocket) -> None:
    await ws.accept()
    vehicles = _load_vehicles()
    if not vehicles:
        await ws.send_json({"type": "empty"})
        await ws.close()
        return

    try:
        while True:  # replay loop
            for v in vehicles:
                v.travelled = 0.0
            while not all(v.arrived for v in vehicles):
                frame = [
                    {
                        "route_id": v.route_id,
                        "vehicle": v.name,
                        "x": round((p := v.advance(SPEED))[0], 3),
                        "y": round(p[1], 3),
                        "progress": round(v.travelled / v.total, 3),
                    }
                    for v in vehicles
                ]
                await ws.send_json({"type": "frame", "vehicles": frame})
                await asyncio.sleep(TICK_SECONDS)
            await ws.send_json({"type": "complete"})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
