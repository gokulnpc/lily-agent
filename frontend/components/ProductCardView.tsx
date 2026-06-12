import type { ProductCard } from "@/lib/types";

function price(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function stockLabel(inStock: boolean | null): { text: string; cls: string } {
  if (inStock === true) return { text: "In stock", cls: "stock-in" };
  if (inStock === false) return { text: "Out of stock", cls: "stock-out" };
  return { text: "Check product page", cls: "stock-unknown" };
}

export function ProductCardView({ card }: { card: ProductCard }) {
  const stock = stockLabel(card.in_stock);
  return (
    <article className="card product-card" data-testid="product-card">
      {card.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="product-img" src={card.image_url} alt={card.name} />
      ) : (
        <div className="product-img product-img--placeholder" aria-hidden="true" />
      )}
      <div className="product-body">
        <h3 className="product-name">{card.name}</h3>
        <p className="product-ps">{card.ps_number}</p>
        <div className="product-meta">
          <span className="product-price">{price(card.price_usd)}</span>
          <span className={`product-stock ${stock.cls}`}>{stock.text}</span>
        </div>
        <div className="product-sub">
          {card.rating_avg != null && (
            <span>
              ★ {card.rating_avg.toFixed(1)}
              {card.review_count != null && ` (${card.review_count})`}
            </span>
          )}
          {card.install_difficulty && <span>{card.install_difficulty}</span>}
        </div>
        {card.url && (
          <a
            className="product-link"
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View part →
          </a>
        )}
      </div>
    </article>
  );
}
