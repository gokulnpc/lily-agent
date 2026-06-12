"use client";

import { useState } from "react";

// FR-25 — per-message 👍/👎 keyed to the turn's trace_id. POSTs to the
// same-origin /api/feedback proxy (→ gateway /feedback). Fire-and-forget;
// the UI just reflects the chosen rating.
export function Feedback({
  traceId,
  sessionId,
}: {
  traceId: string | null;
  sessionId: string;
}) {
  const [picked, setPicked] = useState<"up" | "down" | null>(null);
  if (!traceId) return null;

  async function send(rating: "up" | "down") {
    setPicked(rating);
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          trace_id: traceId,
          session_id: sessionId,
          rating,
        }),
      });
    } catch {
      // Non-blocking; feedback loss is acceptable.
    }
  }

  return (
    <div className="feedback" data-testid="feedback">
      <button
        type="button"
        className={`feedback-btn ${picked === "up" ? "is-picked" : ""}`}
        aria-label="Helpful"
        aria-pressed={picked === "up"}
        disabled={picked !== null}
        onClick={() => send("up")}
      >
        👍
      </button>
      <button
        type="button"
        className={`feedback-btn ${picked === "down" ? "is-picked" : ""}`}
        aria-label="Not helpful"
        aria-pressed={picked === "down"}
        disabled={picked !== null}
        onClick={() => send("down")}
      >
        👎
      </button>
    </div>
  );
}
