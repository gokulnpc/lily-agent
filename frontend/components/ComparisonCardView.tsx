import type { CSSProperties } from "react";
import type { ComparisonCard, ProductCard } from "@/lib/types";
import { StarIcon } from "@/components/icons";

function price(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function stock(inStock: boolean | null): string {
  if (inStock === true) return "In stock";
  if (inStock === false) return "Out of stock";
  return "Check page";
}

function bestFitPs(parts: ProductCard[]): string | null {
  const ranked = [...parts].sort(
    (a, b) =>
      Number(b.in_stock === true) - Number(a.in_stock === true) ||
      (b.rating_avg ?? 0) - (a.rating_avg ?? 0),
  );
  return ranked[0]?.ps_number ?? null;
}

function PartThumbnail() {
  return (
    <div className="comparison-part-img" aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--ps-border-strong)" strokeWidth="1.5">
        <rect x="3" y="6" width="18" height="12" rx="1.5" />
        <path d="M3 13h18" strokeLinecap="round" />
      </svg>
    </div>
  );
}

// FR-11: side-by-side comparison of 2-3 candidate parts; best fit column in gold.
export function ComparisonCardView({ card }: { card: ComparisonCard }) {
  const best = bestFitPs(card.parts);
  const cols = card.parts.length;

  return (
    <div
      className="card comparison-card"
      data-testid="comparison-card"
      style={{ "--cmp-cols": cols } as CSSProperties}
    >
      <div className="comparison-grid">
        {/* Header row */}
        <div className="comparison-grid-cell is-header" />
        {card.parts.map((p) => (
          <div
            key={p.ps_number}
            className={`comparison-grid-cell is-header${p.ps_number === best ? " is-best" : ""}`}
          >
            {p.ps_number === best && (
              <div className="comparison-best-banner">
                <StarIcon size={10} /> Best fit
              </div>
            )}
            <PartThumbnail />
            <div className="comparison-part-name">{p.name}</div>
            <div className="comparison-part-ps">{p.ps_number}</div>
          </div>
        ))}

        {/* Price row */}
        <div className="comparison-grid-cell is-label">Price</div>
        {card.parts.map((p) => (
          <div
            key={`price-${p.ps_number}`}
            className={`comparison-grid-cell is-value${p.ps_number === best ? " is-best" : ""}`}
          >
            {price(p.price_usd)}
          </div>
        ))}

        {/* Stock row */}
        <div className="comparison-grid-cell is-label">Stock</div>
        {card.parts.map((p) => (
          <div
            key={`stock-${p.ps_number}`}
            className={`comparison-grid-cell is-value-secondary${p.ps_number === best ? " is-best" : ""}`}
          >
            {stock(p.in_stock)}
          </div>
        ))}

        {/* Rating row */}
        <div className="comparison-grid-cell is-label">Rating</div>
        {card.parts.map((p) => (
          <div
            key={`rating-${p.ps_number}`}
            className={`comparison-grid-cell is-value-secondary${p.ps_number === best ? " is-best" : ""}`}
          >
            {p.rating_avg != null ? (
              <span className="comparison-rating">
                <StarIcon size={12} />
                {p.rating_avg.toFixed(1)}
              </span>
            ) : (
              "—"
            )}
          </div>
        ))}

        {/* Difficulty row */}
        <div className="comparison-grid-cell is-label">Difficulty</div>
        {card.parts.map((p) => (
          <div
            key={`diff-${p.ps_number}`}
            className={`comparison-grid-cell is-value-secondary${p.ps_number === best ? " is-best" : ""}`}
          >
            {p.install_difficulty ?? "—"}
          </div>
        ))}

        {/* CTA row */}
        <div className="comparison-grid-cell comparison-cta-cell" />
        {card.parts.map((p) => (
          <div
            key={`cta-${p.ps_number}`}
            className={`comparison-grid-cell comparison-cta-cell${p.ps_number === best ? " is-best" : ""}`}
          >
            {p.url ? (
              <a
                className={p.ps_number === best ? "btn btn-primary" : "btn btn-secondary"}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {p.ps_number === best ? "View part" : "View"}
              </a>
            ) : (
              "—"
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
