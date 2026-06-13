import type { OrderCard, OrderEvent } from "@/lib/types";
import { CheckIcon } from "@/components/icons";

function money(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatMeta(card: OrderCard): string {
  const parts: string[] = [];
  if (card.placed_at) parts.push(`Placed ${shortDate(card.placed_at)}`);
  if (card.carrier) parts.push(card.carrier);
  if (card.tracking_number) parts.push(card.tracking_number);
  return parts.join(" · ") || "—";
}

function stepLabel(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function ItemThumbnail({ name }: { name: string }) {
  const isFilter = name.toLowerCase().includes("filter");
  return (
    <div className="order-item-img" aria-hidden="true">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--ps-border-strong)" strokeWidth="1.5">
        {isFilter ? (
          <circle cx="12" cy="12" r="8" />
        ) : (
          <>
            <rect x="3" y="6" width="18" height="12" rx="1.5" />
            <path d="M3 13h18" strokeLinecap="round" />
          </>
        )}
      </svg>
    </div>
  );
}

function Stepper({ timeline }: { timeline: OrderEvent[] }) {
  const steps = timeline.slice(0, 5);
  if (steps.length === 0) return null;

  const lastIndex = steps.length - 1;

  return (
    <div className="order-stepper" data-testid="order-stepper">
      {steps.map((ev, i) => {
        const isLast = i === lastIndex;
        const isDone = i < lastIndex;
        const dotClass = isLast ? "is-current" : isDone ? "is-done" : "is-pending";
        const lineClass = isDone ? "is-done" : isLast ? "is-current" : "is-pending";

        return (
          <span key={`${ev.event_type}-${i}`} style={{ display: "contents" }}>
            <div className="order-step">
              <span className={`order-step-dot ${dotClass}`} style={isDone ? { color: "#fff" } : undefined}>
                {isDone && <CheckIcon size={9} />}
              </span>
              <span className={`order-step-label${!isDone && !isLast ? " is-pending" : ""}`}>
                {stepLabel(ev.event_type)}
              </span>
              <span className="order-step-date">{shortDate(ev.occurred_at)}</span>
            </div>
            {i < steps.length - 1 && (
              <div className="order-step-connector">
                <span className={`order-step-line ${lineClass}`} />
              </div>
            )}
          </span>
        );
      })}
    </div>
  );
}

// FR-21 — order status card: header, items, and a horizontal event stepper.
export function OrderCardView({ card }: { card: OrderCard }) {
  const orderLabel = card.order_number ? `Order #${card.order_number}` : "Order —";

  return (
    <div className="card order-card" data-testid="order-card">
      <div className="order-head">
        <div className="order-head-left">
          <div className="order-number-row">
            <span className="order-number">{orderLabel}</span>
            {card.order_status && (
              <span className="order-status">{card.order_status}</span>
            )}
          </div>
          <div className="order-meta">{formatMeta(card)}</div>
        </div>
        <div className="order-total-block">
          <div className="order-total-label">Total</div>
          <div className="order-total-value">{money(card.total_usd)}</div>
        </div>
      </div>

      {card.items.length > 0 && (
        <ul className="order-items">
          {card.items.map((it) => (
            <li key={it.ps_number}>
              <ItemThumbnail name={it.name} />
              <div className="order-item-body">
                <div className="order-item-name">{it.name}</div>
                <div className="order-item-ps">
                  {it.ps_number} · Qty {it.quantity}
                </div>
              </div>
              <span className="order-item-price">{money(it.unit_price_usd)}</span>
            </li>
          ))}
        </ul>
      )}

      <Stepper timeline={card.timeline} />
    </div>
  );
}
