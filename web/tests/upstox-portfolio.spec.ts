import { expect, test } from "@playwright/test";
import { NextRequest } from "next/server";
import { GET, POST } from "../app/api/portfolio/upstox/route";

for (const [name, callback] of [
  ["loopback", "http://127.0.0.1:3000/api/portfolio/upstox"],
  ["Vercel", "https://final-yr-proj.vercel.app/api/portfolio/upstox"],
] as const) test(`Upstox state binds the ${name} browser and uses a single-use code`, async () => {
  const origin = new URL(callback).origin;
  const hosted = name === "Vercel";
  const keys = ["UPSTOX_CLIENT_ID", "UPSTOX_CLIENT_SECRET", "UPSTOX_REDIRECT_URI", "VERCEL"];
  const previous = keys.map(key => process.env[key]);
  process.env.UPSTOX_CLIENT_ID = "test-client";
  process.env.UPSTOX_CLIENT_SECRET = "test-secret";
  process.env.UPSTOX_REDIRECT_URI = callback;
  if (hosted) process.env.VERCEL = "1";
  else delete process.env.VERCEL;
  const originalFetch = globalThis.fetch;
  const requests: string[] = [];
  let codeConsumed = false;
  globalThis.fetch = async (target, options) => {
    const url = String(target);
    requests.push(url);
    if (url.endsWith("/login/authorization/token")) {
      expect(options?.body).toBeInstanceOf(URLSearchParams);
      expect(String(options?.body)).toContain("code=fixture-code");
      expect((options?.body as URLSearchParams).get("redirect_uri")).toBe(callback);
      if (codeConsumed) return Response.json({}, { status: 403 });
      codeConsumed = true;
      return Response.json({ access_token: "private-token" });
    }
    expect(url).toBe("https://api.upstox.com/v2/portfolio/long-term-holdings");
    expect(new Headers(options?.headers).get("authorization")).toBe("Bearer private-token");
    return Response.json({ status: "success", data: [
      { trading_symbol: "ASIANPAINT", exchange: "NSE", quantity: 10, average_price: 100, t1_quantity: 4, collateral_quantity: 3 },
    ] });
  };
  const request = (query: string, method: "GET" | "POST", cookie?: string, sender = origin) =>
    new NextRequest(`${callback}?${query}`, {
      method, headers: { host: new URL(callback).host, origin: sender, ...(cookie ? { cookie } : {}) },
    });
  try {
    expect((await POST(request("action=start", "POST", undefined, "https://other.invalid"))).status).toBe(403);
    const start = await POST(request("action=start", "POST"));
    expect(start.status).toBe(200);
    const setCookie = start.headers.get("set-cookie")!;
    expect(setCookie).toContain("HttpOnly");
    if (hosted) expect(setCookie).toContain("Secure");
    const cookie = setCookie.split(";")[0];
    const authorization = new URL((await start.json()).url);
    expect(authorization.origin).toBe("https://api.upstox.com");
    expect(authorization.searchParams.get("redirect_uri")).toBe(callback);
    const state = authorization.searchParams.get("state");
    const query = `state=${state}&code=fixture-code`;
    expect((await GET(request(query, "GET"))).headers.get("location")).toContain("upstox=expired");
    expect((await GET(request("state=wrong&code=fixture-code", "GET", cookie))).headers.get("location")).toContain("upstox=expired");
    const changedCookie = cookie.replace(/=(.)/, (_, c: string) => c === "a" ? "=b" : "=a");
    expect((await GET(request(query, "GET", changedCookie))).headers.get("location")).toContain("upstox=expired");
    expect(requests).toHaveLength(0);
    const result = await GET(request(query, "GET", cookie));
    expect(result.status).toBe(303);
    expect(result.headers.get("location")).toBe(`${origin}/?view=portfolio&workspace=local&universe=live&upstox=ready`);
    expect(requests).toHaveLength(0);
    expect((await POST(request("action=preview", "POST"))).status).toBe(410);
    expect((await POST(request("action=preview", "POST", cookie))).status).toBe(410);
    const readyCookie = result.headers.get("set-cookie")!.split(";")[0];
    expect(readyCookie).not.toContain("fixture-code");
    const preview = await POST(request("action=preview", "POST", readyCookie));
    expect(await preview.json()).toEqual({ csv: "symbol,exchange,quantity,average_cost\nASIANPAINT,NSE,10,100" });
    expect(preview.headers.get("set-cookie")).toContain("Max-Age=0");
    expect((await GET(request(query, "GET", readyCookie))).headers.get("location")).toContain("upstox=expired");
    expect(requests).toHaveLength(2);
    expect((await POST(request("action=preview", "POST", readyCookie))).status).toBe(403);
    expect(requests).toHaveLength(3);
    const wrongHost = new NextRequest("https://unregistered.vercel.app/api/portfolio/upstox?action=start", {
      method: "POST", headers: { host: "unregistered.vercel.app", origin: "https://unregistered.vercel.app" },
    });
    expect((await POST(wrongHost)).status).toBe(503);
  } finally {
    globalThis.fetch = originalFetch;
    keys.forEach((key, index) => {
      if (previous[index] === undefined) delete process.env[key];
      else process.env[key] = previous[index];
    });
  }
});
