# Frontend

This folder contains the React/Vite-based UI for the RouteIQ application. It provides network selection, order management, dispatch optimization, route visualization, live vehicle simulation, and planning/fleet repositioning views.

## Directory structure

- `Dockerfile` - Container configuration for building the frontend image.
- `index.html` - HTML entry point used by Vite.
- `nginx.conf` - Nginx configuration used for serving the built frontend.
- `package.json` - Project dependencies and npm scripts.
- `tsconfig.json` - TypeScript compiler configuration.
- `vite.config.ts` - Vite configuration for development and build.
- `src/` - Application source code.
  - `App.tsx` - Main application shell and view/router between dispatch and planning.
  - `main.tsx` - React entry point that mounts the app.
  - `styles.css` - Shared UI styles for layout, panels, map, and tables.
  - `types.ts` - TypeScript type definitions for network, orders, routes, plans, and simulation messages.
  - `api/`
    - `client.ts` - Fetch wrapper and backend API methods for networks, orders, plans, natural-language order creation, deletion, and optimization.
  - `components/`
    - `Briefing.tsx` - Panel showing the generated briefing text and whether AI was used.
    - `MapView.tsx` - SVG map that renders the network, roads, routes, order locations, depot, and live vehicle positions.
    - `OrderPanel.tsx` - Sidebar panel for listing orders, deleting orders, and adding new orders using natural language.
    - `PlanView.tsx` - Planning view that displays zone forecasts, repositioning moves, and an SVG repositioning map.
    - `RoutePanel.tsx` - Route list panel showing optimized vehicle routes, load usage, and unassigned orders.
  - `hooks/`
    - `useSimulation.ts` - WebSocket hook for subscribing to live vehicle positions and simulation status.

## UI functionality

### Main features
- Select a network dataset using the top navigation dropdown.
- Toggle between `Dispatch` and `Planning` modes using top tabs.
- Display top-level metrics for the selected mode:
  - Dispatch: total travel cost, served count, unassigned count.
  - Planning: idle trucks, unmet demand, move cost.

### Dispatch view
- Displays a sidebar list of current orders with priority, demand, and status.
- Supports adding a new order through a natural language input field.
- Shows whether the last order was parsed by AI or fallback rule logic.
- Allows deletion of individual orders.
- Optimizes dispatch routes by calling the backend and then renders:
  - Route cards with vehicle names, cost, capacity usage, and stop list.
  - Map visualization of routes, order locations, and depot.
- Plays/stops live simulation by opening a WebSocket to receive vehicle positions.

### Planning view
- Loads the next-day planning result lazily only when the planning tab is selected.
- Displays a forecast & fleet summary table by zone.
- Shows a repositioning map with zone status and move arrows.
- Lists truck repositioning moves including source, destination, truck count, and cost.
- Displays a briefing describing the repositioning outcome and whether AI was used.

### Networking and API integration
- The frontend fetches backend data from endpoints under `/api/`.
- It uses the `useSimulation` hook to connect to `/ws/simulation` and render live vehicle positions.
- The UI manages backend errors, loading states, and plan/result invalidation when network or orders change.

## Notes
- The frontend is written in TypeScript and rendered with Vite.
- The app is named `RouteIQ` in the UI header.
- `dispatch` mode requires a network with a depot; otherwise, the dispatch tab is disabled.
- The planning UI is designed for fleet repositioning and demand forecasting visualization.
