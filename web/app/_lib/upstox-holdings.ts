import { parsePortfolioCsv } from "./portfolio";

const API = "https://api.upstox.com/v2";

export class UpstoxError extends Error {
  constructor(readonly status: "denied" | "rate-limited" | "empty" | "invalid" | "unavailable") {
    super(status);
  }
}

async function readResponse(response: Response) {
  if (response.status === 401 || response.status === 403) throw new UpstoxError("denied");
  if (response.status === 429) throw new UpstoxError("rate-limited");
  if (!response.ok) throw new UpstoxError("unavailable");
  return response.json();
}

export function normalizeUpstoxHoldings(payload: unknown): string {
  if (!payload || typeof payload !== "object" || !("status" in payload) || payload.status !== "success"
    || !("data" in payload) || !Array.isArray(payload.data) || payload.data.length > 250) {
    throw new UpstoxError("invalid");
  }
  if (!payload.data.length) throw new UpstoxError("empty");
  const rows = payload.data.map(row => {
    if (!row || typeof row !== "object") throw new UpstoxError("invalid");
    const symbol = row.trading_symbol ?? row.tradingsymbol;
    const { exchange, quantity, average_price: cost } = row;
    if (typeof symbol !== "string" || !/^[A-Z0-9][A-Z0-9&._-]{0,31}$/i.test(symbol)
      || (exchange !== "NSE" && exchange !== "BSE") || !Number.isSafeInteger(quantity)
      || typeof cost !== "number" || !Number.isFinite(cost)) throw new UpstoxError("invalid");
    return [symbol, exchange, quantity, cost].join(",");
  });
  const csv = ["symbol,exchange,quantity,average_cost", ...rows].join("\n");
  const preview = parsePortfolioCsv(csv);
  if (preview.fileError || preview.rows.some(row => "error" in row)) throw new UpstoxError("invalid");
  return csv;
}

export async function fetchUpstoxHoldings(
  config: { clientId: string; clientSecret: string; redirectUri: string },
  code: string,
  transport: typeof fetch = fetch,
) {
  const token = await readResponse(await transport(`${API}/login/authorization/token`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code, client_id: config.clientId, client_secret: config.clientSecret,
      redirect_uri: config.redirectUri, grant_type: "authorization_code",
    }),
    cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15_000),
  }));
  if (typeof token?.access_token !== "string" || !token.access_token) throw new UpstoxError("denied");
  const payload = await readResponse(await transport(`${API}/portfolio/long-term-holdings`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token.access_token}` },
    cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15_000),
  }));
  return normalizeUpstoxHoldings(payload);
}
