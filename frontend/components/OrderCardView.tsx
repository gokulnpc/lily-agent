import type { OrderCard } from "@/lib/types";

function money(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function date(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

// FR-21 — order status card: header, items, and an event timeline.
export function OrderCardView({ card }: { card: OrderCard }) {
  return (
    <div className="card order-card" data-testid="order-card">
      <div className="order-head">
        <span className="order-number">Order {card.order_number ?? "—"}</span>
        {card.order_status && (
          <span className="order-status">{card.order_status}</span>
        )}
      </div>
      <dl className="order-facts">
        <div>
          <dt>Placed</dt>
          <dd>{date(card.placed_at)}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{money(card.total_usd)}</dd>
        </div>
        {card.carrier && (
          <div>
            <dt>Carrier</dt>
            <dd>{card.carrier}</dd>
          </div>
        )}
        {card.tracking_number && (
          <div>
            <dt>Tracking</dt>
            <dd>{card.tracking_number}</dd>
          </div>
        )}
      </dl>

      {card.items.length > 0 && (
        <ul className="order-items">
          {card.items.map((it) => (
            <li key={it.ps_number}>
              <span className="order-item-name">
                {it.quantity}× {it.name}
              </span>
              <span className="order-item-ps">{it.ps_number}</span>
              <span className="order-item-price">{money(it.unit_price_usd)}</span>
            </li>
          ))}
        </ul>
      )}

      {card.timeline.length > 0 && (
        <ol className="order-timeline">
          {card.timeline.map((ev, i) => (
            <li key={`${ev.event_type}-${i}`}>
              <span className="timeline-dot" aria-hidden="true" />
              <span className="timeline-type">{ev.event_type}</span>
              {ev.description && (
                <span className="timeline-desc">{ev.description}</span>
              )}
              <span className="timeline-date">{date(ev.occurred_at)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
