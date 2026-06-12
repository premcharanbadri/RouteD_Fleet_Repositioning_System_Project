# [Click Here : RouteIQ - AI-Assisted Fleet Planning & Repositioning](https://youtu.be/ChAfpR3zz_c)



### Business Value: Turning Idle Assets into Operational Capital
In modern logistics, **idle assets are pure cost.** A truck sitting in the wrong neighborhood, or a delivery fleet struggling with inefficient stop-packing, burns fuel, labor, and capital—all while customers face unmet demand. 

RouteIQ is a full-stack, production-grade logistics platform engineered to solve this spatial-temporal imbalance. Whether it is a metro bike-share, a rental fleet, or an on-demand delivery network, the challenge is universal: **demand is uneven in space and time.** RouteIQ bridges this gap by forecasting demand, repositioning assets to optimize inventory, and orchestrating last-mile delivery routes—surfacing capacity pressure before it becomes a missed SLA.

---

## 🎥 Project Demo


https://github.com/user-attachments/assets/27858262-2075-470d-a2be-7beadf24367c


---

## 🛠 Engineering & Data Implementation

RouteIQ mirrors enterprise-level software standards, emphasizing the separation of concerns between algorithmic logic, transactional persistence, and analytical warehousing.

### 1. Data Science & Optimization Engines
* **Demand Forecasting:** Utilizes exponential smoothing and weekly seasonal indices to predict zonal demand, establishing the foundation for all subsequent planning.
* **Fleet Repositioning (Min-Cost Flow):** Models the city as a transportation network, solving a **Min-Cost Max-Flow** problem to redistribute trucks to deficit zones at minimal operational cost.
* **Dispatch Optimization (CVRP):** Implements a two-stage solver for the Capacitated Vehicle Routing Problem:
    * **Construction:** Clarke-Wright Savings heuristic.
    * **Refinement:** 2-opt local search for path optimization.
* **Pathfinding:** Implements A* for point-to-point transit and Dijkstra for complex cost-matrix computations.

### 2. Data Engineering & Architecture
* **Transactional (OLTP):** Relational data (orders, fleet state, topology) is managed via **SQLAlchemy 2.0 ORM** with SQLite/Postgres.
* **Analytical (OLAP):** Demonstrates enterprise scalability by decoupling heavy analytical workloads. Data is synced into a **Snowflake star-schema** (fact/dim tables), optimized for trend analysis like cost-per-run and unmet demand profiling.
* **Resilient AI/LLM Layer:** Integrates Anthropic’s Claude for natural language intake. To prevent system failure, we implemented a **Deterministic Fallback pattern**: the system transparently swaps to a rule-based parser if the LLM API is unavailable, ensuring 100% operational uptime.

### 3. Architecture Overview


---

## Tech Stack
* **Backend:** Python 3.12, FastAPI, Pydantic v2, WebSockets (for live simulation).
* **Frontend:** React 18, TypeScript (Strict), Vite, SVG-based rendering.
* **Tooling:** Docker, GitHub Actions (CI), `pytest` (rigorous algorithmic validation), `mypy`/`ruff`.

---

## Why this project fits your career goals
* **For Data/BA Roles:** Showcases expertise in star-schema design, ETL processes, and time-series forecasting.
* **For AI/ML Engineering Roles:** Highlights the ability to wrap GenAI in production-safe, deterministic fallbacks and implement core optimization algorithms from scratch.
* **For Software Engineering Roles:** Demonstrates modular architecture, WebSocket state management, and API hardening (rate-limiting, strict schema validation).

---

## Quick Start

### Local Development
```bash
# Backend (API & Algorithms)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
