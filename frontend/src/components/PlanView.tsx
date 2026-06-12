import { useMemo } from "react";
import type { Network, PlanResult } from "../types";
import { Briefing } from "./Briefing";

interface Props {
  network: Network;
  plan: PlanResult;
}

function zoneColor(idle: number, unmet: number): string {
  if (unmet > 0) return "#ef4444"; // still short on trucks
  if (idle > 0) return "#f59e0b"; // trucks sitting idle
  return "#16a34a"; // balanced
}

export function PlanView({ network, plan }: Props) {
  const coord = useMemo(() => {
    const m = new Map<number, { x: number; y: number }>();
    network.nodes.forEach((n) => m.set(n.id, { x: n.x, y: n.y }));
    return m;
  }, [network]);

  const zoneCoord = useMemo(() => {
    const m = new Map<number, { x: number; y: number }>();
    plan.zones.forEach((z) => {
      const p = coord.get(z.node_id);
      if (p) m.set(z.zone_id, p);
    });
    return m;
  }, [plan, coord]);

  const pad = 0.7;
  const viewBox = `${-pad} ${-pad} ${network.width - 1 + 2 * pad} ${network.height - 1 + 2 * pad}`;
  const maxTrucks = Math.max(1, ...plan.zones.map((z) => z.final_trucks));

  return (
    <main className="layout">
      <aside className="left">
        <section className="panel">
          <h2>Forecast & Fleet</h2>
          <p className="hint">
            Next-day demand is forecast per zone from its history, then trucks are repositioned
            by min-cost flow to cover it.
          </p>
          <table className="zone-table">
            <thead>
              <tr>
                <th>Zone</th>
                <th>Trucks</th>
                <th>Forecast</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              {plan.zones.map((z) => (
                <tr key={z.zone_id}>
                  <td>
                    <span className="swatch" style={{ background: zoneColor(z.idle, z.unmet) }} />
                    {z.name}
                  </td>
                  <td>{z.trucks}</td>
                  <td>{z.forecast}</td>
                  <td>
                    {z.final_trucks}
                    {z.unmet > 0 && <span className="warn-inline"> −{z.unmet}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </aside>

      <div className="center">
        <svg className="map" viewBox={viewBox} preserveAspectRatio="xMidYMid meet">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#0f172a" />
            </marker>
          </defs>

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

          {plan.moves.map((m, i) => {
            const a = zoneCoord.get(m.from_zone);
            const b = zoneCoord.get(m.to_zone);
            if (!a || !b) return null;
            const mx = (a.x + b.x) / 2;
            const my = (a.y + b.y) / 2;
            return (
              <g key={`m${i}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="#0f172a"
                  strokeWidth={0.05}
                  markerEnd="url(#arrow)"
                  opacity={0.7}
                />
                <text x={mx} y={my - 0.15} className="move-label">
                  {m.trucks}
                </text>
              </g>
            );
          })}

          {plan.zones.map((z) => {
            const p = zoneCoord.get(z.zone_id);
            if (!p) return null;
            const r = 0.22 + 0.28 * (z.final_trucks / maxTrucks);
            return (
              <g key={`z${z.zone_id}`}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={zoneColor(z.idle, z.unmet)}
                  stroke="#0f172a"
                  strokeWidth={0.03}
                  opacity={0.85}
                />
                <text x={p.x} y={p.y + 0.06} className="zone-count">
                  {z.final_trucks}
                </text>
                <text x={p.x} y={p.y - r - 0.12} className="zone-name">
                  {z.name}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="legend">
          <span><i className="ok-dot" /> Balanced</span>
          <span><i className="idle-dot" /> Idle trucks</span>
          <span><i className="short-dot" /> Unmet demand</span>
          <span className="sim-status">circle size = trucks after repositioning</span>
        </div>
      </div>

      <aside className="right">
        <Briefing text={plan.briefing} usedAi={plan.used_ai} title="Planning Briefing" />
        <section className="panel">
          <h2>
            Repositioning Moves <span className="count">{plan.moves.length}</span>
          </h2>
          {plan.moves.length === 0 ? (
            <p className="hint">Fleet already matches forecast demand — no moves needed.</p>
          ) : (
            <ul className="move-list">
              {plan.moves.map((m, i) => (
                <li key={i}>
                  <span>
                    {m.from_name} → {m.to_name}
                  </span>
                  <span className="move-trucks">
                    {m.trucks} truck(s) · cost {m.cost.toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {plan.unmet_after > 0 && (
            <p className="warn">
              {plan.unmet_after} unit(s) of demand still uncovered — fleet is capacity-limited.
            </p>
          )}
        </section>
      </aside>
    </main>
  );
}
