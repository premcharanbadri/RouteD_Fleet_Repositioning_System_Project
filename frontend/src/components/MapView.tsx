import { useMemo } from "react";
import type { Network, Order, Route, VehiclePosition } from "../types";

export const VEHICLE_COLORS = ["#2563eb", "#16a34a", "#db2777", "#d97706", "#7c3aed", "#0891b2"];

const PRIORITY_FILL: Record<number, string> = { 1: "#94a3b8", 2: "#f59e0b", 3: "#ef4444" };

interface Props {
  network: Network;
  orders: Order[];
  routes: Route[];
  positions: VehiclePosition[];
}

export function MapView({ network, orders, routes, positions }: Props) {
  const coord = useMemo(() => {
    const m = new Map<number, { x: number; y: number }>();
    network.nodes.forEach((n) => m.set(n.id, { x: n.x, y: n.y }));
    return m;
  }, [network]);

  // Stable colour + order→route assignment lookups.
  const routeColor = useMemo(() => {
    const m = new Map<number, string>();
    routes.forEach((r, i) => m.set(r.id, VEHICLE_COLORS[i % VEHICLE_COLORS.length]));
    return m;
  }, [routes]);

  const orderRoute = useMemo(() => {
    const m = new Map<number, number>();
    routes.forEach((r) => r.stops.forEach((s) => m.set(s.order_id, r.id)));
    return m;
  }, [routes]);

  const depotNode = network.depots[0]?.node_id;
  const pad = 0.7;
  const viewBox = `${-pad} ${-pad} ${network.width - 1 + 2 * pad} ${network.height - 1 + 2 * pad}`;

  return (
    <svg className="map" viewBox={viewBox} preserveAspectRatio="xMidYMid meet">
      {/* Roads */}
      {network.edges.map((e, i) => {
        const a = coord.get(e.source)!;
        const b = coord.get(e.target)!;
        return (
          <line
            key={`e${i}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#e2e8f0"
            strokeWidth={0.04}
          />
        );
      })}

      {/* Optimised route polylines */}
      {routes.map((r) => {
        const pts = r.geometry
          .map((nid) => coord.get(nid))
          .filter(Boolean)
          .map((p) => `${p!.x},${p!.y}`)
          .join(" ");
        return (
          <polyline
            key={`r${r.id}`}
            points={pts}
            fill="none"
            stroke={routeColor.get(r.id)}
            strokeWidth={0.09}
            strokeLinejoin="round"
            strokeLinecap="round"
            opacity={0.85}
          />
        );
      })}

      {/* Order drop-offs */}
      {orders.map((o) => {
        const p = coord.get(o.node_id);
        if (!p) return null;
        const assignedRoute = orderRoute.get(o.id);
        const fill = assignedRoute ? routeColor.get(assignedRoute)! : PRIORITY_FILL[o.priority];
        return (
          <g key={`o${o.id}`}>
            <circle cx={p.x} cy={p.y} r={0.16} fill={fill} stroke="#0f172a" strokeWidth={0.025} />
            {o.priority === 3 && (
              <circle cx={p.x} cy={p.y} r={0.26} fill="none" stroke="#ef4444" strokeWidth={0.03} />
            )}
          </g>
        );
      })}

      {/* Depot */}
      {depotNode !== undefined && coord.get(depotNode) && (
        <rect
          x={coord.get(depotNode)!.x - 0.18}
          y={coord.get(depotNode)!.y - 0.18}
          width={0.36}
          height={0.36}
          fill="#0f172a"
          rx={0.05}
        />
      )}

      {/* Live vehicles */}
      {positions.map((v) => (
        <circle
          key={`v${v.route_id}`}
          cx={v.x}
          cy={v.y}
          r={0.2}
          fill={routeColor.get(v.route_id) ?? "#0f172a"}
          stroke="#ffffff"
          strokeWidth={0.05}
        />
      ))}
    </svg>
  );
}
