import { expect, test } from "@playwright/test";
import type { Run } from "../app/_components/types";

const symbols = ["ASIANPAINT", "BERGEPAINT", "PIDILITIND", "INDIGO", "RELIANCE"];
const names = ["Asian Paints", "Berger Paints", "Pidilite Industries", "InterGlobe Aviation", "Reliance Industries"];
const companies = symbols.map((symbol, index) => ({ instrument_id: `LIVE:NSE:${symbol}`,
  trading_symbol: symbol, name: names[index], bars: 60, research_bars: 0,
  latest_close: 1000, start: "2026-09-01T10:00:00Z", end: "2026-11-25T10:00:00Z" }));
const snapshot = { source: "Indian stocks · paper money", importedAt: "2026-11-26T04:00:00Z",
  holdings: symbols.map(symbol => ({ symbol, exchange: "NSE", quantity: 19, averageCost: 1000 })),
  paper: { startingCash: 100000, cash: 5000 } };
const article = { article_id: "LIVE:NEWS:fixture", text: "Public test headline", source_url: "https://fixtures.invalid/news",
  published_at: "2026-11-25T09:00:00Z", first_seen_at: "2026-11-26T04:00:00Z" };
const run = { run_id: "saved-reliance-case", article_id: article.article_id, created_at: "2026-11-26T04:01:00Z",
  decision_time: "2026-11-26T04:00:00Z", policy: "slm_delegate", mode: "live", status: "abstained",
  error: null, latency_ms: 1, features: null, calls: [],
  extraction: { company_id: "LIVE:NSE:RELIANCE", event_type: "other", direction: "neutral", source_spans: [], validation_status: "validated" },
  assessment: { direction: "abstain", evidence_score: -0.08, coverage: 1, explanation: "Unsupported event family",
    inputs: {}, conflicts: [], abstention_reasons: ["Unsupported event family"] } } satisfies Run;

for (const width of [1366, 320]) {
  test(`Home shows all five tracked companies and the saved paper account at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/research/workspace?*", route => route.fulfill({ json: {
      workspace: "local", universe: "live", mode: "live", exists: true, provenance: "imported evidence",
      companies, articles: [article], runs: [run], outcomes: [], readiness: [], observations_count: 300,
    } }));
    await page.route("**/api/research/portfolio?*", route => route.fulfill({ json: { revision: 1, snapshot } }));
    await page.goto("/?view=home&workspace=local&universe=live");
    const tracked = page.getByRole("region", { name: "Companies", exact: true });
    await expect(tracked.locator("a.company-card")).toHaveCount(5);
    await expect(tracked.getByText("Not analysed yet", { exact: true })).toHaveCount(4);
    for (const name of names) await expect(tracked.getByRole("link", { name: new RegExp(name) })).toBeVisible();
    await expect(page.getByRole("region", { name: "Summary" }).locator(".stat-tile").filter({ hasText: /^Analysed/ }).locator(".stat-value")).toHaveText("1");
    const account = page.getByRole("region", { name: "Your paper portfolio", exact: true });
    await expect(account).toContainText("₹1,00,000.00");
    await expect(account).toContainText("₹5,000.00");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await account.getByRole("link", { name: "Open paper portfolio", exact: true }).click();
    await expect(page).toHaveURL(/view=portfolio.*workspace=local.*universe=live/);
    await expect(page.getByRole("region", { name: "Portfolio holdings table" }).getByRole("row")).toHaveCount(6);
  });
}

test("tracked companies remain visible before any news or analysis is imported", async ({ page }) => {
  await page.route("**/api/research/workspace?*", route => route.fulfill({ json: {
    workspace: "local", universe: "live", mode: "live", exists: true, provenance: "imported evidence",
    companies, articles: [], runs: [], outcomes: [], readiness: [], observations_count: 300,
  } }));
  await page.route("**/api/research/portfolio?*", route => route.fulfill({ json: { revision: 1, snapshot } }));
  await page.goto("/?view=home&workspace=local&universe=live");
  const tracked = page.getByRole("region", { name: "Companies", exact: true });
  await expect(tracked.locator("a.company-card")).toHaveCount(5);
  await expect(tracked.getByText("Not analysed yet", { exact: true })).toHaveCount(5);
  await expect(page.getByRole("heading", { name: "No stories yet", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your paper portfolio", exact: true })).toBeVisible();
});
