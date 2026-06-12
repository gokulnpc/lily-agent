import { describe, expect, it } from "vitest";
import { parseSse } from "@/lib/sse";
import type { MessageEvent, SseEvent } from "@/lib/types";
import { frame, sampleProduct, sseStream } from "./helpers";

async function collect(wire: string): Promise<SseEvent[]> {
  const out: SseEvent[] = [];
  for await (const ev of parseSse(sseStream(wire))) out.push(ev);
  return out;
}

describe("parseSse", () => {
  it("parses status, message, and done frames in order across chunk boundaries", async () => {
    const wire =
      frame("status", { node: "router", label: "Routing…" }) +
      frame("message", {
        text: "Here you go.",
        primary_intent: "product",
        blocked: false,
        invalid_identifiers: [],
        citations: ["https://www.partselect.com/x.htm"],
        structured: [sampleProduct],
        quick_replies: ["Compare parts"],
        current_model: "global.anthropic.claude-sonnet-4-6",
        trace: [],
      }) +
      frame("done", { session_id: "s1", trace_id: "trace-abc" });

    const events = await collect(wire);
    expect(events.map((e) => e.type)).toEqual(["status", "message", "done"]);

    const msg = events[1] as MessageEvent;
    expect(msg.text).toBe("Here you go.");
    expect(msg.structured[0]).toMatchObject({ kind: "product", ps_number: "PS11752778" });
    expect(msg.citations).toHaveLength(1);
  });

  it("folds the event name into `type`", async () => {
    const events = await collect(frame("error", { message: "boom" }));
    expect(events).toEqual([{ type: "error", message: "boom" }]);
  });

  it("ignores comment and blank lines and skips malformed JSON", async () => {
    const wire = `: keep-alive\n\n` + `event: bad\ndata: {not json}\n\n`;
    expect(await collect(wire)).toEqual([]);
  });

  it("flushes a trailing frame with no terminating blank line", async () => {
    const events = await collect(`event: done\ndata: {"session_id":"s","trace_id":"t"}`);
    expect(events).toEqual([{ type: "done", session_id: "s", trace_id: "t" }]);
  });
});
