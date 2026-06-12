import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { Briefing } from "./components/Briefing";
import { MapView } from "./components/MapView";
import { OrderPanel } from "./components/OrderPanel";
import { PlanView } from "./components/PlanView";
import { RoutePanel } from "./components/RoutePanel";
import { useSimulation } from "./hooks/useSimulation";
import type { Network, NetworkSummary, OptimizeResult, Order, PlanResult } from "./types";

type View = "dispatch" | "planning";

export default function App() {
  const [networks, setNetworks] = useState<NetworkSummary[]>([]);
  const [networkId, setNetworkId] = useState<number | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [view, setView] = useState<View>("dispatch");

  const [orders, setOrders] = useState<Order[]>([]);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);

  const [busy, setBusy] = useState(false);
  const [simOn, setSimOn] = useState(false);
  const [lastAi, setLastAi] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { positions, status: simStatus } = useSimulation(simOn);

  const hasDispatch = (network?.depots.length ?? 0) > 0;

  useEffect(() => {
    (async () => {
      try {
        const nets = await api.getNetworks();
        setNetworks(nets);
        setNetworkId(nets[0]?.id ?? null);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  // Reload everything when the selected network changes.
  useEffect(() => {
    if (networkId == null) return;
    setResult(null);
    setPlan(null);
    setSimOn(false);
    (async () => {
      try {
        const [net, ord] = await Promise.all([
          api.getNetwork(networkId),
          api.getOrders(networkId),
        ]);
        setNetwork(net);
        setOrders(ord);
        if (net.depots.length === 0) setView("planning");
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [networkId]);

  // Load the plan lazily the first time the planning view is shown.
  useEffect(() => {
    if (view !== "planning" || networkId == null || plan) return;
    (async () => {
      try {
        setBusy(true);
        setPlan(await api.getPlan(networkId));
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    })();
  }, [view, networkId, plan]);

  const refreshOrders = useCallback(async () => {
    if (networkId == null) return;
    setOrders(await api.getOrders(networkId));
  }, [networkId]);

  const invalidatePlan = () => {
    setResult(null);
    setSimOn(false);
  };

  const handleAddNl = async (text: string) => {
    if (networkId == null) return;
    setBusy(true);
    try {
      const res = await api.createNlOrder(text, networkId);
      setLastAi(res.used_ai);
      await refreshOrders();
      invalidatePlan();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (networkId == null) return;
    await api.deleteOrder(id, networkId);
    await refreshOrders();
    invalidatePlan();
  };

  const handleOptimize = async () => {
    if (networkId == null) return;
    setBusy(true);
    setSimOn(false);
    try {
      const res = await api.optimize(networkId);
      setResult(res);
      await refreshOrders();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (error) return <div className="fatal">Failed to reach backend: {error}</div>;
  if (!network) return <div className="loading">Loading network…</div>;

  const hasRoutes = (result?.routes.length ?? 0) > 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>RouteIQ</h1>
          <span>AI-assisted demand forecasting, fleet repositioning & dispatch</span>
        </div>

        <div className="nav">
          <select
            className="net-select"
            value={networkId ?? ""}
            onChange={(e) => setNetworkId(Number(e.target.value))}
          >
            {networks.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
              </option>
            ))}
          </select>
          <div className="tabs">
            <button
              className={view === "dispatch" ? "tab active" : "tab"}
              onClick={() => setView("dispatch")}
              disabled={!hasDispatch}
              title={hasDispatch ? "" : "This network has no depot/vehicles"}
            >
              Dispatch
            </button>
            <button
              className={view === "planning" ? "tab active" : "tab"}
              onClick={() => setView("planning")}
            >
              Planning
            </button>
          </div>
        </div>

        {view === "dispatch" ? (
          <>
            <div className="stats">
              <Stat label="Travel cost" value={result ? result.total_cost.toFixed(1) : "—"} />
              <Stat label="Served" value={result ? String(result.served_count) : "—"} />
              <Stat label="Unassigned" value={result ? String(result.unassigned_count) : "—"} />
            </div>
            <div className="actions">
              <button className="primary" onClick={handleOptimize} disabled={busy}>
                {busy ? "Optimizing…" : "Optimize Dispatch"}
              </button>
              <button className="secondary" onClick={() => setSimOn((s) => !s)} disabled={!hasRoutes}>
                {simOn ? "Stop" : "Play"} Simulation
              </button>
            </div>
          </>
        ) : (
          <div className="stats">
            <Stat label="Idle trucks" value={plan ? `${plan.idle_before}→${plan.idle_after}` : "—"} />
            <Stat label="Unmet demand" value={plan ? `${plan.unmet_before}→${plan.unmet_after}` : "—"} />
            <Stat label="Move cost" value={plan ? plan.move_cost.toFixed(1) : "—"} />
          </div>
        )}
      </header>

      {view === "dispatch" ? (
        <main className="layout">
          <aside className="left">
            <OrderPanel
              orders={orders}
              onAddNl={handleAddNl}
              onDelete={handleDelete}
              busy={busy}
              lastInterpretedAi={lastAi}
            />
          </aside>

          <div className="center">
            <MapView
              network={network}
              orders={orders}
              routes={result?.routes ?? []}
              positions={simOn ? positions : []}
            />
            <div className="legend">
              <span><i className="depot-dot" /> Depot</span>
              <span><i className="hi-dot" /> High priority</span>
              <span><i className="norm-dot" /> Normal</span>
              <span><i className="low-dot" /> Low</span>
              {simOn && <span className="sim-status">simulation: {simStatus}</span>}
            </div>
          </div>

          <aside className="right">
            {result && <Briefing text={result.briefing} usedAi={result.used_ai} />}
            <RoutePanel
              routes={result?.routes ?? []}
              unassignedCount={result?.unassigned_count ?? 0}
            />
          </aside>
        </main>
      ) : plan ? (
        <PlanView network={network} plan={plan} />
      ) : (
        <div className="loading">Building plan…</div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
