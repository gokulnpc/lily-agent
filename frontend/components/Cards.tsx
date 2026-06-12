import type { Card } from "@/lib/types";
import { ComparisonCardView } from "@/components/ComparisonCardView";
import { OrderCardView } from "@/components/OrderCardView";
import { ProductCardView } from "@/components/ProductCardView";

// Render the `structured[]` union, dispatching on the `kind` discriminant.
export function Cards({ cards }: { cards: Card[] }) {
  if (cards.length === 0) return null;
  return (
    <div className="cards" data-testid="cards">
      {cards.map((card, i) => {
        switch (card.kind) {
          case "product":
            return <ProductCardView key={`${card.ps_number}-${i}`} card={card} />;
          case "comparison":
            return <ComparisonCardView key={`cmp-${i}`} card={card} />;
          case "order":
            return <OrderCardView key={`ord-${card.order_number}-${i}`} card={card} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
