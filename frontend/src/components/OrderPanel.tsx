import { useState } from "react";
import type { Order } from "../types";

const PRIORITY_LABEL: Record<number, string> = { 1: "low", 2: "normal", 3: "high" };

interface Props {
  orders: Order[];
  onAddNl: (text: string) => Promise<void>;
  onDelete: (id: number) => void;
  busy: boolean;
  lastInterpretedAi: boolean | null;
}

export function OrderPanel({ orders, onAddNl, onDelete, busy, lastInterpretedAi }: Props) {
  const [text, setText] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    await onAddNl(text.trim());
    setText("");
  };

  return (
    <section className="panel">
      <h2>Orders <span className="count">{orders.length}</span></h2>

      <form onSubmit={submit} className="nl-form">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='e.g. "Rush 3 boxes to East Austin, urgent"'
          aria-label="Natural language order"
        />
        <button type="submit" disabled={busy}>Add</button>
      </form>
      {lastInterpretedAi !== null && (
        <p className="hint">
          Parsed by {lastInterpretedAi ? "AI (Claude)" : "rule-based fallback"}.
        </p>
      )}

      <ul className="order-list">
        {orders.map((o) => (
          <li key={o.id} className={`order priority-${o.priority}`}>
            <div className="order-main">
              <span className="order-label">{o.label}</span>
              <span className={`badge ${o.status}`}>{o.status}</span>
            </div>
            <div className="order-meta">
              <span>{o.demand} units</span>
              <span>· {PRIORITY_LABEL[o.priority]} priority</span>
              <button className="link-danger" onClick={() => onDelete(o.id)} aria-label="Delete order">
                remove
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
