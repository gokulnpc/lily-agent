// The chat SSE contract (mirrors services/gateway/src/gateway/chat.py). The wire
// carries `event: <name>` + `data: <json>`; the parser folds the name into `type`.

export interface ProductCard {
  kind: "product";
  ps_number: string;
  name: string;
  price_usd: number | null;
  in_stock: boolean | null;
  image_url: string | null;
  url: string | null;
  install_difficulty: string | null;
  rating_avg: number | null;
  review_count: number | null;
}

export interface ComparisonCard {
  kind: "comparison";
  parts: ProductCard[];
}

export interface OrderItem {
  ps_number: string;
  name: string;
  unit_price_usd: number;
  quantity: number;
}

export interface OrderEvent {
  event_type: string;
  occurred_at: string;
  description?: string | null;
}

export interface OrderCard {
  kind: "order";
  order_number: string | null;
  order_status: string | null;
  placed_at: string | null;
  carrier: string | null;
  tracking_number: string | null;
  total_usd: number | null;
  items: OrderItem[];
  timeline: OrderEvent[];
}

export type Card = ProductCard | ComparisonCard | OrderCard;

export interface StatusEvent {
  type: "status";
  node: string;
  label: string;
}

export interface MessageEvent {
  type: "message";
  text: string;
  primary_intent: string | null;
  blocked: boolean;
  invalid_identifiers: string[];
  citations: string[];
  structured: Card[];
  quick_replies: string[];
  current_model: string | null;
  trace: string[];
}

export interface DoneEvent {
  type: "done";
  session_id: string;
  trace_id: string;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  trace_id?: string;
}

export type SseEvent = StatusEvent | MessageEvent | DoneEvent | ErrorEvent;
