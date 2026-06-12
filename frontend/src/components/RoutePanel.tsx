import type { Route } from "../types";
import { VEHICLE_COLORS } from "./MapView";

interface Props {
  routes: Route[];
  unassignedCount: number;
}

export function RoutePanel({ routes, unassignedCount }: Props) {
  if (routes.length === 0) {
    return (
      <section className="panel">
        <h2>Routes</h2>
        <p className="hint">Click “Optimize Dispatch” to plan routes.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Routes <span className="count">{routes.length}</span></h2>
      {routes.map((r, i) => {
        const color = VEHICLE_COLORS[i % VEHICLE_COLORS.length];
        const fill = Math.min(100, Math.round((r.demand / r.capacity) * 100));
        return (
          <div key={r.id} className="route-card">
            <div className="route-head">
              <span className="swatch" style={{ background: color }} />
              <strong>{r.vehicle_name}</strong>
              <span className="route-cost">cost {r.total_cost.toFixed(1)}</span>
            </div>
            <div className="load-bar" title={`${r.demand} / ${r.capacity} capacity`}>
              <div className="load-fill" style={{ width: `${fill}%`, background: color }} />
              <span className="load-text">{r.demand}/{r.capacity}</span>
            </div>
            <ol className="stop-list">
              {r.stops.map((s) => (
                <li key={s.order_id}>
                  <span>{s.label}</span>
                  <span className="stop-eta">{s.arrival_cost.toFixed(1)}</span>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
      {unassignedCount > 0 && (
        <p className="warn">{unassignedCount} order(s) unassigned — fleet capacity exceeded.</p>
      )}
    </section>
  );
}
