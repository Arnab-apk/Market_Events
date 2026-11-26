import { expect, test } from "@playwright/test";

const portfolio = "/?view=portfolio&workspace=local&universe=live&source=extension";
const csv = "symbol,exchange,quantity,average_cost\nASIANPAINT,NSE,10,100";

test.beforeEach(async ({ page }) => {
  let saved: { revision: number; snapshot: unknown } = { revision: 0, snapshot: null };
  await page.route("**/api/research/portfolio?*", route => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      saved = { revision: saved.revision + 1, snapshot: body.snapshot };
    }
    return route.fulfill({ json: saved });
  });
  await page.route("**/api/research/workspace?*", route => route.fulfill({ json: {
    workspace: "local", universe: "live", mode: "live", provenance: "imported evidence",
    exists: false, companies: [], articles: [], runs: [], outcomes: [], readiness: [], observations_count: 0,
  } }));
});

test("the extension entry opens Upstox sign-in once", async ({ page }) => {
  let starts = 0;
  await page.route("**/api/portfolio/upstox?action=start&source=extension", route => {
    starts++;
    return route.fulfill({ json: { url: "https://api.upstox.com/test-sign-in" } });
  });
  await page.route("https://api.upstox.com/test-sign-in", route => route.fulfill({
    contentType: "text/html", body: "<h1>Upstox sign-in test</h1>",
  }));
  await page.goto(portfolio + "&connect=upstox");
  await expect(page.getByRole("heading", { name: "Upstox sign-in test" })).toBeVisible();
  expect(starts).toBe(1);
});

test("returning from the extension previews once and confirms holdings on the website", async ({ page }) => {
  let previews = 0;
  await page.route("**/api/portfolio/upstox?action=preview&source=extension", route => {
    previews++;
    return route.fulfill({ json: { csv } });
  });
  await page.goto(portfolio + "&upstox=ready");
  await expect(page.getByRole("region", { name: "CSV preview rows" })).toContainText("ASIANPAINT");
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
  expect(previews).toBe(1);
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("ASIANPAINT");
  await page.reload();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("ASIANPAINT");
  expect(previews).toBe(1);
});

test("paper portfolio uses refreshed Indian prices and keeps broker sign-in optional", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const symbols = ["ASIANPAINT", "BERGEPAINT", "PIDILITIND", "INDIGO", "RELIANCE"];
  const companies = symbols.map((symbol, index) => ({
    instrument_id: `LIVE:NSE:${symbol}`, name: symbol, bars: 9, research_bars: 0,
    latest_close: 1000 + index * 137, start: new Date().toISOString(), end: new Date().toISOString(),
  }));
  await page.route("**/api/research/workspace?*", route => route.fulfill({ json: {
    workspace: "local", universe: "live", mode: "live", provenance: "imported evidence",
    exists: true, companies, articles: [], runs: [], outcomes: [], readiness: [], observations_count: 45,
  } }));
  await page.route("**/api/research/sync/live?*", route => {
    expect(route.request().postDataJSON()).toMatchObject({ include_news: false, include_commodities: false });
    return route.fulfill({ json: { errors: [] } });
  });
  await page.goto("/?view=portfolio&workspace=local&universe=live");
  await page.getByRole("button", { name: "Create ₹1,00,000 paper portfolio" }).click();
  await expect(page.getByRole("region", { name: "CSV preview rows" }).getByRole("row")).toHaveCount(6);
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByText("Virtual starting balance", { exact: true })).toBeVisible();
  await expect(page.getByText("Unspent cash", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("RELIANCE");
  await expect(page.getByRole("button", { name: "Connect Upstox (optional)" })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Virtual starting balance", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({ path: testInfo.outputPath("paper-portfolio.png"), fullPage: true });
});
