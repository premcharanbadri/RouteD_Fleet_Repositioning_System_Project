# RouteIQ — AI-Assisted Fleet Planning & Dispatch

RouteIQ is a full-stack logistics platform that covers the whole operational
pipeline: **forecast** next-day demand per zone, **reposition** the fleet to
match it, then **route** the day's deliveries. It visualizes each stage on a map
and explains the plan in plain English. It is built end-to-end — relational
database → REST/WebSocket API → React UI — around a core of classic graph,
flow, and time-series algorithms, with an LLM layer for natural-language order
intake and operational briefings.

> **Business value:** idle assets are pure cost. A truck sitting in the wrong
> city, or a delivery fleet that can't pack stops efficiently, burns fuel,
> labor, and capital while customers wait. The same problem shows up at a U-Haul
> depot, an Uber surge zone, and a Zomato kitchen cluster: *demand is uneven in
> space and time, and the fleet has to move to meet it.* RouteIQ forecasts that
> demand, repositions trucks to cut idle inventory and unmet demand, and then
> optimizes the last-mile routes — surfacing capacity pressure before it becomes
> a missed SLA.

Two coordinated problems, two views in the app:

- **Planning** *(forecast + reposition)* — predict each zone's demand from its
  history and solve a min-cost flow that moves trucks from surplus zones to
  deficit zones. Presets for an on-demand metro fleet and a U-Haul-style
  rental fleet, both grounded in real Austin, TX neighborhoods.
- **Dispatch** *(routing)* — given the orders on hand, compute fastest paths and
  pack stops into capacity-respecting vehicle routes, then animate them live.

---

## What it does

1. **Forecast demand** — for each zone, blend a moving average, exponential
   smoothing, and weekly seasonal indices over its demand history to predict
   next-day volume.
2. **Reposition the fleet** — model surplus/deficit zones as a transportation
   problem and solve it with **min-cost max-flow**, producing the cheapest set of
   truck moves that minimizes idle trucks and unmet demand.
3. **Ingest orders** — type a request in plain English ("*Rush 3 boxes to the
   north warehouse, urgent*"). An LLM extracts quantity, priority, and area and
   grounds it onto a map location. With no API key, a deterministic rule-based
   parser does the same job offline.
4. **Optimize dispatch** — compute the fastest paths between the depot and every
   stop, then partition stops into capacity-respecting vehicle routes and order
   each route to minimize travel time.
5. **Visualize & simulate** — render the road network, the plan, and the
   optimized routes, then watch the vehicles drive in real time over a WebSocket.
6. **Brief the operator** — generate a short summary of each plan (idle vs. unmet
   reduction, move cost, capacity pressure, unassigned orders).

---

## Architecture

A conventional **3-tier / layered architecture** with a clean separation between
pure algorithms, persistence, and transport:

```
┌─────────────────────────────────────────────────────────────┐
│  React + TypeScript SPA  (presentation)                      │
│  · SVG map  · order panel  · route panel  · live simulation  │
└───────────────▲───────────────────────────▲─────────────────┘
        REST (fetch)                  WebSocket (live positions)
┌───────────────┴───────────────────────────┴─────────────────┐
│  FastAPI  (application / transport)                          │
│   api/ ── routers, deps, websocket                           │
│   services/ ── orchestration (optimizer, planning, network)  │
│   ai/ ── LLM client + deterministic fallback                 │
│   domain/ ── PURE algorithms: graph, CVRP, forecast, flow    │
│   models/ + schemas/ ── ORM entities + API contracts         │
└───────────────────────────▲─────────────────────────────────┘
                     SQLAlchemy ORM
┌───────────────────────────┴─────────────────────────────────┐
│  Relational DB  ·  SQLite (dev)  /  PostgreSQL (prod)        │
└─────────────────────────────────────────────────────────────┘
```

The `domain/` layer has **no dependency on the web framework or the database**,
so the algorithms are unit-tested in isolation.

---

## Algorithms (the core)

| Problem | Technique | Where |
|---|---|---|
| Predict next-day demand per zone | **Moving average + exponential smoothing + weekly seasonal indices** | `domain/forecasting.py` |
| Reposition trucks (surplus → deficit) | **Min-cost max-flow** (successive shortest paths / SPFA) over a transportation network | `domain/repositioning.py` |
| Road network | Weighted undirected graph (grid of intersections, congestion-weighted travel times) | `domain/graph.py` |
| Fastest route between two points | **A\*** search with an admissible straight-line heuristic | `graph.shortest_path` |
| All-pairs depot/stop times + geometry | **Dijkstra** (min-heap) per terminal | `graph.cost_matrix` |
| Assign stops to vehicles under capacity | **Clarke-Wright savings** heuristic for CVRP | `domain/vrp.py` |
| Order stops within a route | **2-opt** local search | `vrp.two_opt` |
| Baseline construction | Greedy **nearest-neighbor** | `vrp.nearest_neighbor` |

The repositioning step is solved **exactly** — the transportation problem is a
min-cost flow, which is polynomial. Routing is **NP-hard** (it contains the TSP),
so RouteIQ uses the standard construct-then-improve heuristic pipeline that
delivers near-optimal routes in milliseconds — exactly the trade-offs taught in
an algorithms/AI course.

---

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (ORM), Pydantic v2, WebSockets
- **Frontend:** React 18 + TypeScript (strict), Vite, plain CSS, SVG rendering
- **Database:** SQLite (zero-config dev) / PostgreSQL (Docker/prod) for OLTP;
  optional **Snowflake** analytical warehouse (OLAP tier)
- **AI:** Anthropic Claude via tool-use (structured output), with an offline
  rule-based fallback so the app never hard-depends on the network
- **Tooling:** pytest, ruff, mypy, Docker / docker-compose, GitHub Actions CI

---

## Run it

### Option A — local (SQLite, zero config)

```bash
# Backend  → http://localhost:8000  (auto-creates + seeds the demo networks)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend → http://localhost:5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Use the **Planning** tab to forecast demand and
reposition the fleet, or the **Dispatch** tab and click **Optimize Dispatch** to
route the metro orders. Switch presets with the network selector.

### Option B — full stack in Docker (PostgreSQL)

```bash
# App → http://localhost:8080
docker compose up --build
```

### Enable AI (optional)

```bash
export ANTHROPIC_API_KEY=sk-...     # or set it in backend/.env
```

Without a key, natural-language parsing and briefings transparently fall back to
the deterministic implementation (the UI labels which path was used).

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/networks` | List available networks (metro / cities presets) |
| `GET` | `/api/network` | Road network (nodes, edges, depots) for rendering |
| `GET` | `/api/plan` | Forecast demand + repositioning plan + briefing |
| `GET` | `/api/orders` | List delivery orders |
| `POST` | `/api/orders` | Create an order (structured) |
| `POST` | `/api/orders/nl` | Create an order from natural language (rate-limited) |
| `DELETE` | `/api/orders/{id}` | Remove an order |
| `POST` | `/api/optimize` | Run the optimizer; returns routes + briefing |
| `POST` | `/api/analytics/sync` | ETL operational data into the Snowflake warehouse |
| `GET` | `/api/analytics/demand-summary` | Per-zone demand profile (OLAP, weekday vs. weekend) |
| `GET` | `/api/analytics/run-metrics` | Cost / served / unassigned trend across optimization runs |
| `WS` | `/ws/simulation` | Stream live vehicle positions along the latest plan |

All endpoints accept an optional `?network_id=` to target a specific network.
Interactive docs at `http://localhost:8000/docs`.

### Hardening

- CORS locked to the configured frontend origin
- Request-body size limit (`max_request_bytes`, default 64 KB) → `413`
- Per-client rate limit on the paid AI order endpoint (`nl_rate_per_minute`) → `429`
- Input bounds enforced by Pydantic (demand/priority ranges, text length, node range)
- `optimize` runs as a single transaction; the in-memory graph cache is built
  under a lock to keep concurrent requests race-free
- No secrets or PII in responses — the demo data is fully synthetic, so
  GDPR/PCI/SOC 2 data-handling controls are **N/A** by design

---

## Analytics warehouse (Snowflake) — optional OLAP tier

The operational database is **OLTP** — row-oriented, transactional, millisecond
reads on the hot path (orders, optimize, live simulation). Historical analysis is
a different workload, so it lives in a separate **OLAP** tier on Snowflake rather
than overloading the operational store. This is the textbook **OLTP → ETL → OLAP**
split, modeled as a small **star schema**:

```
dim_network ─┐                 ┌─ fact_demand            (zone × day grain)
dim_zone ────┴── shared keys ──┴─ fact_optimization_run  (one row per run)
```

- `POST /api/analytics/sync` runs the ETL (`app/warehouse/etl.py`): a full reload
  of zones, demand history and optimization runs into the star schema.
- `GET /api/analytics/demand-summary` — per-zone demand profile (avg/min/max,
  weekday vs. weekend) computed in Snowflake.
- `GET /api/analytics/run-metrics` — cost / served / unassigned trend across runs.

The tier is **config-gated**: set the `SNOWFLAKE_*` vars and install the extra
(`pip install -e ".[snowflake]"`) to enable it; otherwise the endpoints return
`503` and the rest of the app runs unchanged. Snowflake is **never** on the
operational path.

---

## Tests

```bash
cd backend && pytest        # algorithm + API tests
ruff check app tests        # lint
```

The suite verifies the parts that actually matter: A\* agrees with Dijkstra, the
heuristic is admissible, the cost matrix is symmetric, CVRP never violates
capacity, every stop is either routed or explicitly unassigned, 2-opt never
worsens a route, the forecast tracks level and seasonality, repositioning
conserves flow and never increases idle/unmet, and the API enforces its bounds,
body-size limit, and rate limit.

---

## Project structure

```
backend/
  app/
    domain/      graph, CVRP, forecasting, repositioning (pure Python, no I/O)
    models/      SQLAlchemy ORM entities
    schemas/     Pydantic request/response models
    services/    optimizer, planning, network, seed orchestration
    warehouse/   Snowflake OLAP tier: star-schema DDL, ETL, analytics queries
    ai/          LLM client + deterministic fallback
    api/         REST routers + WebSocket + deps (rate limit, network select)
    main.py      app factory (CORS, body-size limit)
  tests/         pytest (graph, vrp, forecasting, repositioning, api)
frontend/
  src/
    components/  MapView, OrderPanel, RoutePanel, Briefing, PlanView
    hooks/       useSimulation (WebSocket)
    api/         typed fetch client
docker-compose.yml · .github/workflows/ci.yml · Makefile
```
