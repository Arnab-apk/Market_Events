import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

// Walks the seven-step presentation story (docs/PRESENTATION_PLAN.md) against the
// running dev stack (`npm run dev` from the project root) using the offline replay demo.
// Screenshots land in web/tests/screenshots/<viewport>-<theme>/.

const VIEWPORTS = [
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
] as const;
const THEMES = ["light", "dark"] as const;
const SHOTS = path.join(__dirname, "screenshots");
const IGNORED_CONSOLE = [/Download the React DevTools/i, /\[HMR\]/, /\[Fast Refresh\]/];

function watchConsole(page: Page) {
  const problems: string[] = [];
  page.on("console", message => {
    if (!["error", "warning"].includes(message.type())) return;
    const text = message.text();
    if (!IGNORED_CONSOLE.some(pattern => pattern.test(text))) problems.push(`${message.type()}: ${text}`);
  });
  page.on("pageerror", error => problems.push(`pageerror: ${error.message}`));
  return problems;
}

for (const viewport of VIEWPORTS) for (const theme of THEMES) {
  test(`demo story · ${viewport.name} · ${theme}`, async ({ browser }) => {
    test.setTimeout(240_000);
    const folder = path.join(SHOTS, `${viewport.name}-${theme}`);
    mkdirSync(folder, { recursive: true });
    const context = await browser.newContext({ viewport, colorScheme: theme, reducedMotion: "reduce" });
    await context.addInitScript(value => { try { localStorage.setItem("market-events-theme", value); } catch { /* storage blocked */ } }, theme);
    const page = await context.newPage();
    const problems = watchConsole(page);
    let index = 0;
    const shot = async (name: string, fullPage = true) => {
      await page.waitForTimeout(250);
      await page.screenshot({ path: path.join(folder, `${String(++index).padStart(2, "0")}-${name}.png`), fullPage });
    };

    // 1 · Overview → load the synthetic replay demo.
    await page.goto("/?view=overview");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await shot("overview-start", false);
    await page.getByRole("button", { name: /load synthetic demo/i }).click();
    await page.waitForURL(/workspace=demo/);
    await expect(page.getByRole("status").filter({ hasText: /synthetic replay demo loaded/i })).toBeVisible();
    await expect(page.locator(".premium-ticker button").first()).toBeVisible();
    await shot("overview-demo-loaded", false);
    await page.locator(".premium-ticker button").first().click();
    await expect(page.locator(".premium-price-visual")).toBeVisible();
    await shot("overview-demo-full");

    // 2 · Evidence: source inbox + import page.
    await page.goto("/?view=imports&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { level: 1, name: "Import evidence" })).toBeVisible();
    await shot("imports", false);
    await page.goto("/?view=events&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { name: "Source inbox" })).toBeVisible();
    await shot("events-inbox", false);

    // 3 · Analyse the commodity-shock article (crude oil → paint maker) under a policy.
    await page.getByLabel("Search sources").fill("crude");
    await page.locator(".selection-item").first().click();
    await page.getByLabel("Research method").selectOption("slm_filter");
    await page.getByRole("button", { name: /analyse and save run/i }).click();
    await expect(page.locator(".run-summary")).toBeVisible({ timeout: 60_000 });
    await shot("events-analysed");

    // 4 · Open the saved result with its audit trail.
    await page.goto("/?view=saved&workspace=demo&universe=demo");
    await page.getByRole("button", { name: /open saved evidence/i }).click();
    await expect(page.getByRole("heading", { name: "Model call audit" })).toBeVisible();
    await shot("saved-case");

    // 5 + 6 · Later outcomes, then the policy comparison.
    await page.goto("/?view=comparisons&workspace=demo&universe=demo");
    await page.getByRole("button", { name: /evaluate later outcomes/i }).click();
    await expect(page.getByRole("heading", { name: "Policy usage" })).toBeVisible({ timeout: 60_000 });
    await shot("comparisons");
    await page.goto("/?view=saved&workspace=demo&universe=demo");
    await page.getByRole("button", { name: /open saved evidence/i }).click();
    await expect(page.getByRole("heading", { name: /later outcome/i })).toBeVisible();
    await page.getByRole("heading", { name: /later outcome/i }).scrollIntoViewIfNeeded();
    await shot("saved-outcome", false);

    // 7 · Strategy lab: indicators, a backtest with costs, a Monte Carlo bootstrap.
    await page.goto("/?view=lab&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { level: 1, name: "Strategy lab" })).toBeVisible();
    const instrument = page.getByLabel("Instrument");
    const eligible = await instrument.locator("option").evaluateAll(options =>
      options.some(option => /· [1-9]\d* pre-2021 bars/.test(option.textContent || "")));
    if (!eligible) {
      // The replay demo only ships 2026 bars; the lab is capped at 2020 (cross-agent request filed).
      await shot("lab-no-eligible-history");
      test.info().annotations.push({ type: "blocked", description: "Strategy lab: no pre-2021 bars in the demo workspace" });
      await context.close();
      expect(problems, problems.join("\n")).toEqual([]);
      return;
    }
    await page.getByRole("button", { name: /load local history/i }).click();
    await expect(page.locator(".chart-frame, .price-chart").first()).toBeVisible({ timeout: 60_000 });
    await shot("lab-history", false);
    await page.getByRole("button", { name: /run backtest/i }).click();
    await expect(page.getByRole("heading", { name: /equity & execution report/i })).toBeVisible({ timeout: 60_000 });
    await shot("lab-backtest");
    await page.getByRole("button", { name: /simulate return paths/i }).click();
    await expect(page.locator(".simulation-svg")).toBeVisible({ timeout: 60_000 });
    await page.locator(".simulation-svg").scrollIntoViewIfNeeded();
    await shot("lab-monte-carlo", false);

    await context.close();
    expect(problems, problems.join("\n")).toEqual([]);
  });
}
