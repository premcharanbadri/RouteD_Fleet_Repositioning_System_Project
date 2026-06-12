import { useEffect, useState } from "react";
import type { VehiclePosition } from "../types";

type SimStatus = "idle" | "running" | "complete" | "empty";

/**
 * Subscribes to the backend WebSocket and exposes the latest vehicle positions.
 * Opening/closing the socket is driven entirely by the `enabled` flag.
 */
export function useSimulation(enabled: boolean) {
  const [positions, setPositions] = useState<VehiclePosition[]>([]);
  const [status, setStatus] = useState<SimStatus>("idle");

  useEffect(() => {
    if (!enabled) {
      setPositions([]);
      setStatus("idle");
      return;
    }

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/simulation`);
    setStatus("running");

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "frame") {
        setPositions(msg.vehicles as VehiclePosition[]);
      } else if (msg.type === "complete") {
        setStatus("complete");
      } else if (msg.type === "empty") {
        setStatus("empty");
      }
    };
    ws.onclose = () => setStatus((s) => (s === "running" ? "idle" : s));

    return () => ws.close();
  }, [enabled]);

  return { positions, status };
}
