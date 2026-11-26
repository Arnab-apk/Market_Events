import { createCipheriv, createDecipheriv, hkdfSync, randomBytes, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { fetchUpstoxHoldings, UpstoxError } from "../../../_lib/upstox-holdings";

export const runtime = "nodejs";
const PATH = "/api/portfolio/upstox";
const COOKIE = "market_events_upstox_flow";
const FLOW_SECONDS = 600;
const HEADERS = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };
const STATE = /^[a-f0-9]{64}$/;
const CODE = /^[!-~]{1,1024}$/;

type Flow = { expiresAt: number; state: string; code?: string; extension?: boolean };

function config(request: NextRequest) {
  const clientId = process.env.UPSTOX_CLIENT_ID;
  const clientSecret = process.env.UPSTOX_CLIENT_SECRET;
  const redirectUri = process.env.UPSTOX_REDIRECT_URI;
  if (!clientId || !clientSecret || !redirectUri) return null;
  try {
    const url = new URL(redirectUri);
    const secure = url.protocol === "https:";
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    const allowedHost = process.env.VERCEL === "1" ? secure && !loopback : loopback;
    if (!allowedHost || url.host !== request.headers.get("host")
      || url.protocol !== request.nextUrl.protocol || !["http:", "https:"].includes(url.protocol)
      || url.pathname !== PATH || url.username || url.password || url.search || url.hash) return null;
    const cookieKey = Buffer.from(hkdfSync("sha256", clientSecret, url.href, "market-events:upstox-flow:v1", 32));
    return { clientId, clientSecret, redirectUri: url.href, origin: url.origin, secure, cookieKey };
  } catch {
    return null;
  }
}

// The redirect, callback, and preview may run in different Vercel instances.
// Keep only a short-lived encrypted state/code in the browser. Upstox consumes
// the authorization code atomically when the preview exchanges it.
function seal(key: Buffer, flow: Flow) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(flow), "utf8"), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString("base64url");
}

function readFlow(request: NextRequest, key: Buffer): Flow | null {
  const value = request.cookies.get(COOKIE)?.value;
  if (!value || !/^[A-Za-z0-9_-]{39,4096}$/.test(value)) return null;
  try {
    const data = Buffer.from(value, "base64url");
    const decipher = createDecipheriv("aes-256-gcm", key, data.subarray(0, 12));
    decipher.setAuthTag(data.subarray(12, 28));
    const json = Buffer.concat([decipher.update(data.subarray(28)), decipher.final()]).toString("utf8");
    const flow: Flow = JSON.parse(json);
    return flow.expiresAt > Date.now() && STATE.test(flow.state) ? flow : null;
  } catch {
    return null;
  }
}

function failure(detail: string, status: number) {
  return NextResponse.json({ detail }, { status, headers: HEADERS });
}

function cookie(response: NextResponse, value: string, secure: boolean, expiresAt = 0) {
  response.cookies.set(COOKIE, value, {
    path: PATH, httpOnly: true, sameSite: "lax", secure,
    maxAge: Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)),
  });
}

export async function POST(request: NextRequest) {
  const settings = config(request);
  if (!settings) return failure("Configure Upstox OAuth and open the app at its registered callback origin.", 503);
  if (request.headers.get("origin") !== settings.origin) return failure("Open the Portfolio page to connect Upstox.", 403);
  const action = request.nextUrl.searchParams.get("action");
  if (action === "preview") {
    const flow = readFlow(request, settings.cookieKey);
    if (!flow?.code) return failure("The Upstox connection expired. Connect again to retrieve holdings.", 410);
    let response: NextResponse;
    try {
      const csv = await fetchUpstoxHoldings(settings, flow.code);
      response = NextResponse.json({ csv }, { headers: HEADERS });
    } catch (error) {
      const status = error instanceof UpstoxError ? error.status : "unavailable";
      const messages = {
        denied: ["Upstox did not authorize the connection. Connect again.", 403],
        "rate-limited": ["Upstox is limiting requests. Wait a moment, then connect again.", 429],
        empty: ["Upstox returned no holdings.", 422],
        invalid: ["Upstox returned holdings that could not be imported.", 422],
        unavailable: ["Upstox could not be reached. Connect again or use a holdings CSV.", 502],
      } as const;
      const [detail, httpStatus] = messages[status];
      response = failure(detail, httpStatus);
    }
    cookie(response, "", settings.secure);
    return response;
  }
  if (action !== "start") return failure("Unknown portfolio action.", 400);
  const flow = {
    state: randomBytes(32).toString("hex"), expiresAt: Date.now() + FLOW_SECONDS * 1000,
    extension: request.nextUrl.searchParams.get("source") === "extension",
  };
  const authorization = new URL("https://api.upstox.com/v2/login/authorization/dialog");
  authorization.search = new URLSearchParams({
    response_type: "code", client_id: settings.clientId, redirect_uri: settings.redirectUri, state: flow.state,
  }).toString();
  const response = NextResponse.json({ url: authorization.href }, { headers: HEADERS });
  cookie(response, seal(settings.cookieKey, flow), settings.secure, flow.expiresAt);
  return response;
}

export async function GET(request: NextRequest) {
  const settings = config(request);
  if (!settings) return failure("This address is not configured as an Upstox callback.", 503);
  const flow = readFlow(request, settings.cookieKey);
  const state = request.nextUrl.searchParams.get("state") ?? "";
  const code = request.nextUrl.searchParams.get("code") ?? "";
  const target = new URL("/?view=portfolio&workspace=local&universe=live", settings.origin);
  if (flow?.extension) target.searchParams.set("source", "extension");
  const back = (status: string) => {
    target.searchParams.set("upstox", status);
    return NextResponse.redirect(target, { status: 303, headers: HEADERS });
  };
  if (!flow || flow.code || !STATE.test(state)
    || !timingSafeEqual(Buffer.from(state), Buffer.from(flow.state))) return back("expired");
  if (request.nextUrl.searchParams.has("error") || !CODE.test(code)) {
    const response = back("denied");
    cookie(response, "", settings.secure);
    return response;
  }
  const response = back("ready");
  cookie(response, seal(settings.cookieKey, { ...flow, code }), settings.secure, flow.expiresAt);
  return response;
}
