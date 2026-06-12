import { NextRequest, NextResponse } from "next/server";

// Same-origin proxy for 👍/👎 (FR-25). Forwards to the gateway's /feedback,
// which records a structured log line + Prometheus counter against the trace_id.
export const runtime = "nodejs";

const GATEWAY_URL =
  process.env.LILY_GATEWAY_URL ?? "http://gateway.agent.svc.cluster.local:80";

export async function POST(req: NextRequest) {
  const body = await req.text();
  try {
    const upstream = await fetch(`${GATEWAY_URL}/feedback`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    });
    return new NextResponse(null, { status: upstream.ok ? 204 : 502 });
  } catch {
    return new NextResponse(null, { status: 502 });
  }
}
