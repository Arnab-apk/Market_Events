import { expect, test } from "@playwright/test";

const url = "/?view=portfolio&workspace=local&universe=live";
const endpoint = "/api/research/portfolio?workspace=local&universe=live";

test("confirmed holdings persist in a new browser context and concurrent edits are refused", async ({ page, browser }) => {
  const initial = await (await page.request.get(endpoint)).json();
  await page.request.post(endpoint, { data: { revision: initial.revision, snapshot: null } });
  await page.goto(url);
  await page.getByLabel("Holdings CSV").setInputFiles({ name: "practice.csv", mimeType: "text/csv",
    buffer: Buffer.from("symbol,exchange,quantity,average_cost\nASIANPAINT,NSE,7,2621.20") });
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByText("1 holdings imported and saved to your private workspace.", { exact: true })).toBeVisible();
  const context = await browser.newContext();
  const other = await context.newPage();
  await other.goto(new URL(url, page.url()).toString());
  await expect(other.getByRole("region", { name: "Portfolio holdings table" })).toContainText("ASIANPAINT");
  // The first tab clears at the current revision; the second still holds the previous revision.
  await page.getByRole("button", { name: "Clear saved holdings" }).click();
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
  await other.getByRole("button", { name: "Clear saved holdings" }).click();
  await expect(other.getByRole("alert").filter({ hasText: "changed in another tab" })).toBeVisible();
  await other.getByRole("button", { name: "Reload saved portfolio" }).click();
  await expect(other.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
  await context.close();
});

test("live paper quotes update valuation and render the intraday chart without the embed", async ({ page }) => {
  const snapshot = { source: "Paper test", importedAt: new Date().toISOString(),
    holdings: [{ symbol: "ASIANPAINT", exchange: "NSE", quantity: 2, averageCost: 100 }],
    paper: { startingCash: 1000, cash: 800 } };
  await page.route("**/api/research/portfolio?*", route => route.fulfill({ json: { revision: 1, snapshot } }));
  let calls = 0;
  await page.route("**/api/research/paper-quotes?*", route => {
    calls++;
    return route.fulfill({ json: { source: "Upstox", fetched_at: new Date().toISOString(), missing: [],
      quotes: [{ instrument_id: "LIVE:NSE:ASIANPAINT", price: calls === 1 ? 110 : 115,
        last_trade_at: new Date().toISOString() }] } });
  });
  await page.route("**/api/research/portfolio-chart?*", route => {
    expect(route.request().postDataJSON()).toEqual({ exchange: "NSE", symbol: "ASIANPAINT" });
    return route.fulfill({ json: { source: "Upstox", session: "current session", fetched_at: new Date().toISOString(),
      bars: [{ time: 1795664700, open: 103, high: 111, low: 101, close: 110, volume: 500 }] } });
  });
  await page.clock.install();
  await page.goto(url);
  const demo = page.getByRole("region", { name: "Live paper demo" });
  await demo.getByLabel("Refresh paper prices every 15 seconds").check();
  await expect(demo.getByRole("region", { name: "Latest paper prices" })).toContainText("₹110.00");
  await expect(demo).toContainText("₹1,020.00");
  await page.clock.fastForward(15_000);
  await expect(demo.getByRole("region", { name: "Latest paper prices" })).toContainText("₹115.00");
  await expect(demo).toContainText("₹1,030.00");
  await demo.getByLabel("Refresh paper prices every 15 seconds").uncheck();
  await page.clock.fastForward(30_000);
  expect(calls).toBe(2);
  const chart = demo.getByRole("img", { name: "NSE:ASIANPAINT Upstox intraday candlestick chart" });
  await expect(chart.locator("canvas").first()).toBeVisible();
  await expect(demo.getByRole("link", { name: "Open this chart on TradingView" })).toHaveAttribute("href", /symbol=NSE%3AASIANPAINT/);
});

test("a stock outside the preset can be selected, previewed and saved", async ({ page }) => {
  const snapshot = { source: "Custom Indian stocks · paper money", importedAt: new Date().toISOString(),
    holdings: [{ symbol: "INFY", exchange: "NSE", quantity: 50, averageCost: 1800 }],
    paper: { startingCash: 100000, cash: 10000 } };
  let saved: unknown = null;
  await page.route("**/api/research/portfolio?*", route => {
    if (route.request().method() === "POST") saved = route.request().postDataJSON().snapshot;
    return route.fulfill({ json: { revision: saved ? 1 : 0, snapshot: saved } });
  });
  await page.route("**/api/research/stock-search?*", route => {
    expect(route.request().postDataJSON()).toEqual({ exchange: "NSE", query: "Infosys" });
    return route.fulfill({ json: { matches: [{ name: "Infosys Limited", exchange: "NSE", trading_symbol: "INFY", instrument_id: "LIVE:NSE:INFY" }] } });
  });
  await page.route("**/api/research/paper-preview?*", route => {
    expect(route.request().postDataJSON()).toEqual({ stocks: [{ symbol: "INFY", exchange: "NSE" }] });
    return route.fulfill({ json: { snapshot } });
  });
  await page.route("**/api/research/portfolio-chart?*", route => route.fulfill({ json: { source: "Upstox", session: "current session", bars: [] } }));
  await page.goto(url);
  await page.getByText("Choose your own paper stocks", { exact: true }).click();
  await page.getByLabel("Stock name or ticker").fill("Infosys");
  await page.getByRole("button", { name: "Search stocks", exact: true }).click();
  await page.getByRole("button", { name: "Add INFY · Infosys Limited", exact: true }).click();
  await page.getByRole("button", { name: "Preview selected paper stocks", exact: true }).click();
  await expect(page.getByRole("region", { name: "CSV preview rows" })).toContainText("INFY");
  expect(saved).toBeNull();
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("INFY");
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).not.toContainText("ASIANPAINT");
});
