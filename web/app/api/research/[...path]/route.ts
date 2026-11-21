import { NextRequest } from "next/server";
import { acceptsLocalOrigin } from "../../../_lib/request-origin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const reads = new Set(["health", "workspace", "comparisons"]);
const writes = new Set([
  "demo", "import", "analyse", "technicals", "history", "backtest", "monte-carlo",
  "outcomes", "analyse-news",
]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const [action, identifier] = path;
  const isRead = request.method === "GET";
  const allowed = path.length === 1
    ? (isRead ? reads : writes).has(action)
    : path.length === 2 && Boolean(identifier) && (
      (isRead && action === "case") ||
      (!isRead && action === "explain") ||
      (!isRead && action === "sync" && ["live", "historical"].includes(identifier))
    );
  if (!allowed) return Response.json({ detail: "Unknown research endpoint" }, { status: 404 });
  if (!isRead && !acceptsLocalOrigin(request.headers.get("origin"), request.headers.get("host"), request.nextUrl.protocol, request.nextUrl.port)) {
    return Response.json({ detail: "Cross-origin mutation refused" }, { status: 403 });
  }
  const target = new URL(`/api/${path.map(encodeURIComponent).join("/")}`,
    process.env.MARKET_EVENTS_API_URL || "http://127.0.0.1:8000");
  for (const key of ["workspace", "universe"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) target.searchParams.set(key, value);
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: isRead ? undefined : await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(180_000),
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "Python API is unavailable. Start both services with npm run dev from the project root." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
