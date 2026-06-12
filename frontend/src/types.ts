export interface NodeT {
  id: number;
  x: number;
  y: number;
}

export interface EdgeT {
  source: number;
  target: number;
  time: number;
}

export interface Depot {
  id: number;
  name: string;
  node_id: number;
}

export interface NetworkSummary {
  id: number;
  name: string;
  kind: string;
}

export interface Network {
  id: number;
  name: string;
  kind: string;
  width: number;
  height: number;
  nodes: NodeT[];
  edges: EdgeT[];
  depots: Depot[];
}

export interface Order {
  id: number;
  label: string;
  node_id: number;
  demand: number;
  priority: number;
  status: string;
  raw_text: string | null;
  created_at: string;
}

export interface RouteStop {
  position: number;
  order_id: number;
  label: string;
  node_id: number;
  demand: number;
  priority: number;
  arrival_cost: number;
}

export interface Route {
  id: number;
  vehicle_id: number;
  vehicle_name: string;
  total_cost: number;
  demand: number;
  capacity: number;
  geometry: number[];
  stops: RouteStop[];
}

export interface OptimizeResult {
  run_id: number;
  total_cost: number;
  served_count: number;
  unassigned_count: number;
  unassigned_order_ids: number[];
  briefing: string;
  used_ai: boolean;
  routes: Route[];
}

export interface NlOrderResult {
  order: Order;
  interpreted: {
    label: string;
    demand: number;
    priority: number;
    zone: string;
    node_id: number;
  };
  used_ai: boolean;
}

export interface VehiclePosition {
  route_id: number;
  vehicle: string;
  x: number;
  y: number;
  progress: number;
}

export interface ZonePlan {
  zone_id: number;
  name: string;
  node_id: number;
  trucks: number;
  forecast: number;
  final_trucks: number;
  idle: number;
  unmet: number;
}

export interface Move {
  from_zone: number;
  to_zone: number;
  from_name: string;
  to_name: string;
  trucks: number;
  cost: number;
}

export interface PlanResult {
  zones: ZonePlan[];
  moves: Move[];
  move_cost: number;
  idle_before: number;
  idle_after: number;
  unmet_before: number;
  unmet_after: number;
  briefing: string;
  used_ai: boolean;
}
