import { NextRequest } from "next/server";

// Same-origin SSE proxy. The browser POSTs here; we forward to the in-cluster
// gateway and pipe its SSE stream straight back, so the chat stream never leaves
// the origin and no public CORS is needed (Phase 3 locked decision).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const GATEWAY_URL =
  process.env.LILY_GATEWAY_URL ?? "http://gateway.agent.svc.cluster.local:80";

export async function POST(req: NextRequest) {
  const body = await req.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${GATEWAY_URL}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body,
      // Node fetch needs duplex for a streaming response body.
      // @ts-expect-error - duplex is valid at runtime but missing from the lib types.
      duplex: "half",
    });
  } catch {
    return sseError("The assistant is unreachable right now. Please try again.");
  }

  if (!upstream.ok || !upstream.body) {
    return sseError("The assistant returned an error. Please try again.");
  }

  const headers = new Headers({
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive",
  });
  const traceId = upstream.headers.get("x-trace-id");
  if (traceId) headers.set("x-trace-id", traceId);

  return new Response(upstream.body, { status: 200, headers });
}

// Surface transport failures as a well-formed `error` SSE frame so the client's
// single stream-parsing path handles them like any other event.
function sseError(message: string): Response {
  const frame = `event: error\ndata: ${JSON.stringify({ message })}\n\n`;
  return new Response(frame, {
    status: 200,
    headers: { "content-type": "text/event-stream; charset=utf-8" },
  });
}
