import type {
  Network,
  NetworkSummary,
  NlOrderResult,
  OptimizeResult,
  Order,
  PlanResult,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

function withNetwork(path: string, networkId?: number): string {
  return networkId ? `${path}?network_id=${networkId}` : path;
}

export const api = {
  getNetworks: () => request<NetworkSummary[]>("/api/networks"),
  getNetwork: (networkId?: number) =>
    request<Network>(withNetwork("/api/network", networkId)),
  getOrders: (networkId?: number) =>
    request<Order[]>(withNetwork("/api/orders", networkId)),
  getPlan: (networkId?: number) =>
    request<PlanResult>(withNetwork("/api/plan", networkId)),
  createNlOrder: (text: string, networkId?: number) =>
    request<NlOrderResult>(withNetwork("/api/orders/nl", networkId), {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  deleteOrder: (id: number, networkId?: number) =>
    request<void>(withNetwork(`/api/orders/${id}`, networkId), { method: "DELETE" }),
  optimize: (networkId?: number) =>
    request<OptimizeResult>(withNetwork("/api/optimize", networkId), { method: "POST" }),
};
