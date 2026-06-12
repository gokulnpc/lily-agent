import type { ComparisonCard } from "@/lib/types";

function price(p: number | null): string {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function stock(inStock: boolean | null): string {
  if (inStock === true) return "In stock";
  if (inStock === false) return "Out of stock";
  return "Check page";
}

// FR-11 — side-by-side comparison of 2–3 candidate parts.
export function ComparisonCardView({ card }: { card: ComparisonCard }) {
  return (
    <div className="card comparison-card" data-testid="comparison-card">
      <table className="comparison-table">
        <thead>
          <tr>
            <th scope="col">Part</th>
            <th scope="col">Price</th>
            <th scope="col">Stock</th>
            <th scope="col">Rating</th>
            <th scope="col">Difficulty</th>
          </tr>
        </thead>
        <tbody>
          {card.parts.map((p) => (
            <tr key={p.ps_number}>
              <th scope="row">
                <span className="comparison-name">{p.name}</span>
                <span className="comparison-ps">{p.ps_number}</span>
              </th>
              <td>{price(p.price_usd)}</td>
              <td>{stock(p.in_stock)}</td>
              <td>{p.rating_avg != null ? `★ ${p.rating_avg.toFixed(1)}` : "—"}</td>
              <td>{p.install_difficulty ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
