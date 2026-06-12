import type { ProductCard } from "@/lib/types";

// Build one SSE wire frame: `event: <name>\n data: <json>\n\n`.
export function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

// A ReadableStream that emits `wire` in small byte chunks, so the parser's
// cross-chunk frame buffering is exercised (frames split mid-boundary).
export function sseStream(wire: string, chunkSize = 13): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(wire);
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) {
        controller.enqueue(bytes.slice(i, i + chunkSize));
      }
      controller.close();
    },
  });
}

export const sampleProduct: ProductCard = {
  kind: "product",
  ps_number: "PS11752778",
  name: "Door Shelf Bin",
  price_usd: 36.08,
  in_stock: true,
  image_url: null,
  url: "https://www.partselect.com/PS11752778-Door-Shelf-Bin.htm",
  install_difficulty: "Really Easy",
  rating_avg: 4.8,
  review_count: 120,
};
