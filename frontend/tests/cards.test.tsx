import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Cards } from "@/components/Cards";
import type { ComparisonCard, OrderCard } from "@/lib/types";
import { sampleProduct } from "./helpers";

describe("Cards", () => {
  it("renders a product card with price, stock, and PS number", () => {
    render(<Cards cards={[sampleProduct]} />);
    expect(screen.getByTestId("product-card")).toBeInTheDocument();
    expect(screen.getByText("Door Shelf Bin")).toBeInTheDocument();
    expect(screen.getByText("PS11752778")).toBeInTheDocument();
    expect(screen.getByText("$36.08")).toBeInTheDocument();
    expect(screen.getByText("In stock")).toBeInTheDocument();
  });

  it("renders unknown stock as a 'check product page' hint", () => {
    render(<Cards cards={[{ ...sampleProduct, in_stock: null, price_usd: null }]} />);
    expect(screen.getByText("Check product page")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders a comparison card as a table of parts", () => {
    const card: ComparisonCard = {
      kind: "comparison",
      parts: [sampleProduct, { ...sampleProduct, ps_number: "PS999", name: "Alt Bin", price_usd: 41.5 }],
    };
    render(<Cards cards={[card]} />);
    expect(screen.getByTestId("comparison-card")).toBeInTheDocument();
    expect(screen.getByText("Alt Bin")).toBeInTheDocument();
    expect(screen.getByText("PS999")).toBeInTheDocument();
    expect(screen.getByText("$41.50")).toBeInTheDocument();
  });

  it("renders an order card with status, items, and timeline", () => {
    const card: OrderCard = {
      kind: "order",
      order_number: "LILY-1001",
      order_status: "shipped",
      placed_at: "2026-06-01T12:00:00Z",
      carrier: "UPS",
      tracking_number: "1Z999",
      total_usd: 72.16,
      items: [{ ps_number: "PS11752778", name: "Door Shelf Bin", unit_price_usd: 36.08, quantity: 2 }],
      timeline: [
        { event_type: "placed", occurred_at: "2026-06-01T12:00:00Z", description: "Order received" },
        { event_type: "shipped", occurred_at: "2026-06-02T09:00:00Z", description: null },
      ],
    };
    render(<Cards cards={[card]} />);
    expect(screen.getByTestId("order-card")).toBeInTheDocument();
    expect(screen.getByText("Order LILY-1001")).toBeInTheDocument();
    expect(screen.getByText("shipped", { selector: ".order-status" })).toBeInTheDocument();
    expect(screen.getByText("1Z999")).toBeInTheDocument();
    expect(screen.getByText("2× Door Shelf Bin")).toBeInTheDocument();
    expect(screen.getByText("placed", { selector: ".timeline-type" })).toBeInTheDocument();
    expect(screen.getByText("Order received")).toBeInTheDocument();
  });

  it("renders nothing for an empty card list", () => {
    const { container } = render(<Cards cards={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
