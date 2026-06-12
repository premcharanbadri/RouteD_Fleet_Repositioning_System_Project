# Forecast next-day demand per zone, then reposition the fleet to match it.

from __future__ import annotations

from app.ai.client import generate_plan_briefing
from app.domain.forecasting import forecast
from app.domain.repositioning import plan_repositioning
from app.models import Network
from app.schemas import MoveOut, PlanResponse, ZonePlan
from app.services.network import get_graph


def build_plan(network: Network) -> PlanResponse:
    zones = sorted(network.zones, key=lambda z: z.id)
    if not zones:
        return PlanResponse(
            zones=[], moves=[], move_cost=0.0,
            idle_before=0, idle_after=0, unmet_before=0, unmet_after=0,
            briefing="No zones configured for this network.", used_ai=False,
        )

    graph = get_graph(network)
    cost_matrix, _ = graph.cost_matrix([z.node_id for z in zones])

    supply = [z.truck_count for z in zones]
    demand = []
    for z in zones:
        history = [d.count for d in z.demand_history]
        demand.append(round(forecast(history, horizon_phase=len(history) % 7)))

    plan = plan_repositioning([z.id for z in zones], supply, demand, cost_matrix)
    name_of = {z.id: z.name for z in zones}

    zone_plans = [
        ZonePlan(
            zone_id=z.zone_id,
            name=name_of[z.zone_id],
            node_id=next(zn.node_id for zn in zones if zn.id == z.zone_id),
            trucks=z.supply,
            forecast=z.forecast,
            final_trucks=z.final_supply,
            idle=z.idle,
            unmet=z.unmet,
        )
        for z in plan.zones
    ]
    moves = [
        MoveOut(
            from_zone=m.from_zone,
            to_zone=m.to_zone,
            from_name=name_of[m.from_zone],
            to_name=name_of[m.to_zone],
            trucks=m.trucks,
            cost=m.cost,
        )
        for m in plan.moves
    ]

    briefing, used_ai = generate_plan_briefing(zone_plans, plan.idle_before, plan.idle_after,
                                               plan.unmet_before, plan.unmet_after, plan.move_cost)
    return PlanResponse(
        zones=zone_plans,
        moves=moves,
        move_cost=plan.move_cost,
        idle_before=plan.idle_before,
        idle_after=plan.idle_after,
        unmet_before=plan.unmet_before,
        unmet_after=plan.unmet_after,
        briefing=briefing,
        used_ai=used_ai,
    )
