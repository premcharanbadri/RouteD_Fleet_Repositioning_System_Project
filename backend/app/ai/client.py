"""Anthropic-backed AI helpers with deterministic fallbacks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.services.network import pick_node

if TYPE_CHECKING:
    from app.domain.graph import CityGraph
    from app.schemas import RouteOut, ZonePlan

settings = get_settings()

_PRIORITY_WORDS = {
    3: ("urgent", "asap", "high", "rush", "immediately", "critical"),
    1: ("whenever", "low", "no rush", "flexible"),
}
_ZONE_WORDS = ("north", "south", "east", "west", "center", "central", "downtown")

_ORDER_TOOL = {
    "name": "record_order",
    "description": "Extract a structured delivery order from a dispatcher's free-text request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "description": "Short human label for the drop-off, e.g. 'Acme Corp, North St'.",
            },
            "demand": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "Number of parcels/units.",
            },
            "priority": {
                "type": "integer",
                "enum": [1, 2, 3],
                "description": "1=low, 2=normal, 3=high/urgent.",
            },
            "zone": {
                "type": "string",
                "description": "Optional area hint: north/south/east/west/center, else empty.",
            },
        },
        "required": ["label", "demand", "priority"],
    },
}


def _client() -> Any:
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# Natural-language order intake.
def parse_order(text: str, graph: CityGraph) -> tuple[dict, bool]:
    """Return (interpreted_order, used_ai). The interpreted order always contains
    label, node_id, demand and priority — ready to persist as an Order."""
    if settings.ai_enabled:
        try:
            fields = _parse_order_ai(text)
            return _ground(fields, text, graph), True
        except Exception:
            pass  # fall through to the rule-based parser
    return _ground(_parse_order_rules(text), text, graph), False


def _parse_order_ai(text: str) -> dict:
    resp = _client().messages.create(
        model=settings.routeiq_ai_model,
        max_tokens=400,
        tools=[_ORDER_TOOL],
        tool_choice={"type": "tool", "name": "record_order"},
        messages=[{"role": "user", "content": f"Dispatcher request: {text}"}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise ValueError("No tool_use block returned")


def _parse_order_rules(text: str) -> dict:
    lowered = text.lower()
    units = r"box|boxes|parcel|parcels|unit|units|package|packages|item|items"
    demand_match = re.search(rf"(\d+)\s*(?:{units})?", lowered)
    demand = max(1, min(20, int(demand_match.group(1)))) if demand_match else 1

    priority = 2
    for level, words in _PRIORITY_WORDS.items():
        if any(w in lowered for w in words):
            priority = level
            break

    zone = next((z for z in _ZONE_WORDS if z in lowered), "")
    label = text.strip()[:80]
    return {"label": label, "demand": demand, "priority": priority, "zone": zone}


def _ground(fields: dict, text: str, graph: CityGraph) -> dict:
    node_id = pick_node(graph, fields.get("zone"), text)
    return {
        "label": (fields.get("label") or text.strip())[:120],
        "demand": max(1, min(20, int(fields.get("demand", 1)))),
        "priority": int(fields.get("priority", 2)) if fields.get("priority") in (1, 2, 3) else 2,
        "zone": fields.get("zone", ""),
        "node_id": node_id,
    }


# Dispatch briefing.
def generate_briefing(
    routes: list[RouteOut], unassigned_ids: list[int], total_cost: float
) -> tuple[str, bool]:
    summary = _briefing_facts(routes, unassigned_ids, total_cost)
    if settings.ai_enabled and routes:
        try:
            return _briefing_ai(summary), True
        except Exception:
            pass
    return _briefing_rules(summary), False


def _briefing_facts(routes: list[RouteOut], unassigned_ids: list[int], total_cost: float) -> dict:
    return {
        "vehicles_used": len(routes),
        "total_cost": round(total_cost, 1),
        "stops": sum(len(r.stops) for r in routes),
        "unassigned": len(unassigned_ids),
        "routes": [
            {
                "vehicle": r.vehicle_name,
                "stops": len(r.stops),
                "load": r.demand,
                "capacity": r.capacity,
                "cost": round(r.total_cost, 1),
                "high_priority": sum(1 for s in r.stops if s.priority == 3),
            }
            for r in routes
        ],
    }


def _briefing_ai(summary: dict) -> str:
    resp = _client().messages.create(
        model=settings.routeiq_ai_model,
        max_tokens=400,
        system=(
            "You are a logistics dispatch assistant. Given a JSON optimisation summary, "
            "write a concise 2-4 sentence operational briefing for the dispatcher: how many "
            "vehicles are deployed, overall efficiency, any capacity pressure or unassigned "
            "orders to watch. Be specific and practical. No markdown headers."
        ),
        messages=[{"role": "user", "content": str(summary)}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def _briefing_rules(summary: dict) -> str:
    if not summary["routes"]:
        return "No routes were generated — add orders and vehicles, then re-optimise."
    parts = [
        f"Dispatching {summary['vehicles_used']} vehicle(s) across {summary['stops']} stop(s) "
        f"for a total travel cost of {summary['total_cost']}."
    ]
    tight = [r for r in summary["routes"] if r["load"] >= 0.9 * r["capacity"]]
    if tight:
        names = ", ".join(r["vehicle"] for r in tight)
        parts.append(f"Near-capacity: {names} — little room for last-minute add-ons.")
    high = sum(r["high_priority"] for r in summary["routes"])
    if high:
        parts.append(f"{high} high-priority order(s) are scheduled early on their routes.")
    if summary["unassigned"]:
        parts.append(
            f"{summary['unassigned']} order(s) could not be assigned within current fleet "
            "capacity — consider adding a vehicle."
        )
    return " ".join(parts)


def generate_plan_briefing(
    zones: list[ZonePlan],
    idle_before: int,
    idle_after: int,
    unmet_before: int,
    unmet_after: int,
    move_cost: float,
) -> tuple[str, bool]:
    summary = _plan_facts(zones, idle_before, idle_after, unmet_before, unmet_after, move_cost)
    if settings.ai_enabled and zones:
        try:
            return _plan_ai(summary), True
        except Exception:
            pass
    return _plan_rules(summary), False


def _plan_facts(
    zones: list[ZonePlan],
    idle_before: int,
    idle_after: int,
    unmet_before: int,
    unmet_after: int,
    move_cost: float,
) -> dict:
    return {
        "idle_before": idle_before,
        "idle_after": idle_after,
        "unmet_before": unmet_before,
        "unmet_after": unmet_after,
        "move_cost": round(move_cost, 1),
        "zones": [
            {
                "name": z.name,
                "trucks": z.trucks,
                "forecast": z.forecast,
                "final": z.final_trucks,
                "idle": z.idle,
                "unmet": z.unmet,
            }
            for z in zones
        ],
    }


def _plan_ai(summary: dict) -> str:
    resp = _client().messages.create(
        model=settings.routeiq_ai_model,
        max_tokens=400,
        system=(
            "You are a fleet planning assistant. Given a JSON summary of forecast demand and a "
            "truck repositioning plan, write a concise 2-4 sentence briefing for the operations "
            "manager: how repositioning cuts idle trucks and unmet demand, the move cost, and any "
            "zone still short on trucks. Be specific and practical. No markdown headers."
        ),
        messages=[{"role": "user", "content": str(summary)}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def _plan_rules(summary: dict) -> str:
    if not summary["zones"]:
        return "No zones configured — add zones with demand history to plan repositioning."
    parts = [
        f"Forecast demand across {len(summary['zones'])} zone(s). Repositioning trucks for a "
        f"move cost of {summary['move_cost']} cuts idle trucks from {summary['idle_before']} to "
        f"{summary['idle_after']} and unmet demand from {summary['unmet_before']} to "
        f"{summary['unmet_after']}."
    ]
    short = [z for z in summary["zones"] if z["unmet"] > 0]
    if short:
        names = ", ".join(f"{z['name']} (short {z['unmet']})" for z in short)
        parts.append(f"Still under-supplied after moves: {names} — fleet is capacity-limited.")
    else:
        parts.append("Every zone's forecast demand is covered after repositioning.")
    return " ".join(parts)
