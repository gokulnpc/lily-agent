"use client";

import { useState } from "react";
import { ThumbsDownIcon, ThumbsUpIcon } from "@/components/icons";

// FR-25: per-message thumbs feedback keyed to the turn's trace_id. POSTs to the
// same-origin /api/feedback proxy (to the gateway /feedback). Fire-and-forget;
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
      <span className="feedback-label">Was this helpful?</span>
      <button
        type="button"
        className={`feedback-btn feedback-up ${picked === "up" ? "is-picked" : ""}`}
        aria-label="Helpful"
        aria-pressed={picked === "up"}
        disabled={picked !== null}
        onClick={() => send("up")}
      >
        <ThumbsUpIcon size={16} />
      </button>
      <button
        type="button"
        className={`feedback-btn feedback-down ${picked === "down" ? "is-picked" : ""}`}
        aria-label="Not helpful"
        aria-pressed={picked === "down"}
        disabled={picked !== null}
        onClick={() => send("down")}
      >
        <ThumbsDownIcon size={16} />
      </button>
    </div>
  );
}
