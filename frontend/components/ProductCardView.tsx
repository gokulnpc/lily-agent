import type { ProductCard } from "@/lib/types";
import { ArrowRightIcon, CartIcon, StarIcon } from "@/components/icons";

function price(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function stockLabel(inStock: boolean | null): { text: string; cls: string } {
  if (inStock === true) return { text: "In stock", cls: "stock-in" };
  if (inStock === false) return { text: "Out of stock", cls: "stock-out" };
  return { text: "Stock unknown", cls: "stock-unknown" };
}

function difficultyBars(difficulty: string | null): number {
  if (!difficulty) return 0;
  const d = difficulty.toLowerCase();
  if (d.includes("really easy") || d.includes("very easy")) return 1;
  if (d.includes("easy")) return 2;
  if (d.includes("moderate") || d.includes("medium")) return 3;
  return 2;
}

export function ProductCardView({ card }: { card: ProductCard }) {
  const stock = stockLabel(card.in_stock);
  const filledBars = difficultyBars(card.install_difficulty);

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
          <span className={`product-stock ${stock.cls}`}>
            <span className="stock-dot" aria-hidden="true" />
            {stock.text}
          </span>
        </div>
        <div className="product-sub">
          {card.rating_avg != null && (
            <span className="product-rating">
              <StarIcon size={15} />
              {card.rating_avg.toFixed(1)}
              {card.review_count != null && (
                <span className="product-rating-count"> ({card.review_count})</span>
              )}
            </span>
          )}
          {card.rating_avg != null && card.install_difficulty && (
            <span className="product-sub-divider" aria-hidden="true" />
          )}
          {card.install_difficulty && (
            <span className="product-difficulty">
              <span className="difficulty-bars" aria-hidden="true">
                {[1, 2, 3].map((n) => (
                  <span
                    key={n}
                    className={`difficulty-bar${n <= filledBars ? " is-filled" : ""}`}
                  />
                ))}
              </span>
              {card.install_difficulty}
            </span>
          )}
        </div>
        {card.url && (
          <div className="product-cta">
            <a
              className="btn btn-primary"
              href={card.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View part
              <ArrowRightIcon size={15} />
            </a>
            <a
              className="btn btn-secondary"
              href={card.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <CartIcon size={15} />
              Add to cart
            </a>
          </div>
        )}
      </div>
    </article>
  );
}
