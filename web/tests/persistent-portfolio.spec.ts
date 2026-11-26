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

test("live paper quotes update valuation, pause, and embed the selected intraday chart", async ({ page }) => {
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
  await page.route("https://s3.tradingview.com/**", route => route.fulfill({ contentType: "application/javascript", body: "/* deterministic widget load test */" }));
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
  await demo.getByText("TradingView chart (optional, external service)", { exact: true }).click();
  await demo.getByLabel("Load the TradingView widget").check();
  const frame = demo.locator('iframe[title="Independent TradingView hosted chart"]');
  await expect(frame).toHaveAttribute("srcdoc", /"symbol":"NSE:ASIANPAINT"/);
  await expect(frame).toHaveAttribute("srcdoc", /"interval":"1"/);
});
