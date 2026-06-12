"""Integration tests for the REST API (happy paths + key edge cases)."""

from __future__ import annotations


def test_network_seeded(client) -> None:
    resp = client.get("/api/network")
    assert resp.status_code == 200
    body = resp.json()
    assert body["width"] * body["height"] == len(body["nodes"])
    assert len(body["depots"]) == 1


def test_orders_seeded(client) -> None:
    assert len(client.get("/api/orders").json()) >= 10
    assert len(client.get("/api/vehicles").json()) == 3


def test_create_and_delete_order(client) -> None:
    created = client.post(
        "/api/orders", json={"label": "Test Stop", "node_id": 12, "demand": 2, "priority": 3}
    )
    assert created.status_code == 201
    oid = created.json()["id"]

    assert client.delete(f"/api/orders/{oid}").status_code == 204
    assert client.delete(f"/api/orders/{oid}").status_code == 404


def test_create_order_rejects_bad_node(client) -> None:
    resp = client.post(
        "/api/orders", json={"label": "Bad", "node_id": 999999, "demand": 1, "priority": 2}
    )
    assert resp.status_code == 422


def test_nl_order_fallback_parses_quantity_and_priority(client) -> None:
    resp = client.post(
        "/api/orders/nl", json={"text": "Deliver 5 boxes to the east side, urgent"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["used_ai"] is False  # no API key in tests
    assert body["interpreted"]["demand"] == 5
    assert body["interpreted"]["priority"] == 3


def test_networks_listed(client) -> None:
    nets = client.get("/api/networks").json()
    kinds = {n["kind"] for n in nets}
    assert {"metro", "cities"} <= kinds


def test_plan_reduces_idle_and_unmet(client) -> None:
    cities = next(n for n in client.get("/api/networks").json() if n["kind"] == "cities")
    resp = client.get("/api/plan", params={"network_id": cities["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["zones"]) == 5
    assert body["idle_after"] <= body["idle_before"]
    assert body["unmet_after"] <= body["unmet_before"]
    assert body["briefing"]


def test_oversized_body_rejected(client) -> None:
    resp = client.post("/api/orders/nl", json={"text": "x" * 100_000})
    assert resp.status_code == 413


def test_nl_endpoint_rate_limited(client) -> None:
    from app.api import deps
    from app.config import get_settings

    deps._hits.clear()  # isolate from other tests that hit this endpoint
    limit = get_settings().nl_rate_per_minute
    codes = [
        client.post("/api/orders/nl", json={"text": "Deliver 1 box"}).status_code
        for _ in range(limit + 1)
    ]
    assert codes[-1] == 429
    assert codes.count(201) == limit


def test_analytics_requires_warehouse(client) -> None:
    # No Snowflake configured in tests, so the whole analytics tier should 503.
    assert client.post("/api/analytics/sync").status_code == 503
    assert client.get("/api/analytics/demand-summary").status_code == 503
    assert client.get("/api/analytics/run-metrics").status_code == 503


def test_optimize_assigns_within_capacity(client) -> None:
    resp = client.post("/api/optimize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["served_count"] >= 1
    assert body["briefing"]
    for route in body["routes"]:
        assert route["demand"] <= route["capacity"]
        assert route["geometry"][0] == route["geometry"][-1]  # returns to depot
