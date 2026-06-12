import { NextResponse } from "next/server";

// Liveness/readiness + ALB target-group health check. Cheap and dependency-free
// (the frontend's only upstream is the gateway, reached per-request).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET() {
  return NextResponse.json({ status: "ok" });
}
