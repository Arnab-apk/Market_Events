import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

// Walks the seven-step presentation story (docs/PRESENTATION_PLAN.md) against the
// running dev stack (`npm run dev` from the project root) using the offline replay demo.
// Also asserts the guided tour (React Bits Stepper), term tooltips and the low-sample warning.
// Screenshots land in web/tests/screenshots/<viewport>-<theme>/.

const VIEWPORTS = [
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
] as const;
const THEMES = ["light", "dark"] as const;
const SHOTS = path.join(__dirname, "screenshots");
const IGNORED_CONSOLE = [/Download the React DevTools/i, /\[HMR\]/, /\[Fast Refresh\]/];
const STORY = "/?view=events&workspace=demo&universe=demo&article=syn-002&cutoff=2026-01-12T12%3A00%3A00Z";

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

/** Hover a term and check its tooltip, then check the same tooltip on keyboard focus. */
async function expectTooltip(page: Page, term: string, text: RegExp) {
  const trigger = page.locator("button.term", { hasText: term }).first();
  await trigger.scrollIntoViewIfNeeded();
  await trigger.hover();
  const id = await trigger.getAttribute("aria-describedby");
  const tip = page.locator(`[id="${id}"]`);
  await expect(tip).toBeVisible();
  await expect(tip).toHaveText(text);
  await page.mouse.move(1, 1);
  await expect(tip).toBeHidden();
  await trigger.focus();
  await expect(tip).toBeVisible();
  await trigger.blur();
}

for (const viewport of VIEWPORTS) for (const theme of THEMES) {
  test(`demo story · ${viewport.name} · ${theme}`, async ({ browser }) => {
    test.setTimeout(240_000);
    const folder = path.join(SHOTS, `${viewport.name}-${theme}`);
    mkdirSync(folder, { recursive: true });
    const context = await browser.newContext({ viewport, colorScheme: theme, reducedMotion: "reduce" });
    await context.addInitScript(value => { try { localStorage.setItem("market-events-theme", value); if (!sessionStorage.getItem("tour-reset")) { localStorage.removeItem("market-events-tour"); sessionStorage.setItem("tour-reset", "1"); } } catch { /* storage blocked */ } }, theme);
    const page = await context.newPage();
    const problems = watchConsole(page);
    let index = 0;
    const shot = async (name: string, fullPage = true) => {
      await page.waitForTimeout(250);
      await page.screenshot({ path: path.join(folder, `${String(++index).padStart(2, "0")}-${name}.png`), fullPage });
    };

    // 1 · Overview → load the synthetic replay demo; the replay status stays visible everywhere.
    await page.goto("/?view=overview");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(page.getByRole("button", { name: "Load synthetic demo (replay)" })).toBeVisible();
    await shot("overview-start", false);
    await page.getByRole("button", { name: "Load synthetic demo (replay)" }).click();
    await page.waitForURL(/workspace=demo/);
    await expect(page.getByRole("status").filter({ hasText: /synthetic replay demo loaded/i })).toBeVisible();
    await expect(page.locator(".demo-ribbon")).toContainText("Synthetic demo · recorded replay");

    // Guided tour: React Bits Stepper with 7 steps, current step announced, Next moves it.
    const tour = page.locator(".tour-card");
    await expect(tour.getByRole("heading", { name: /demo tour/i })).toBeVisible();
    await expect(tour.locator(".tour-badge")).toHaveCount(7);
    // Progress reads left to right: done badges always form an unbroken run from step 1.
    const doneFlags = await tour.locator(".tour-badge").evaluateAll(badges => badges.map(badge => badge.hasAttribute("data-done")));
    expect(doneFlags.slice(doneFlags.indexOf(false) < 0 ? doneFlags.length : doneFlags.indexOf(false)).every(flag => !flag)).toBe(true);
    const current = tour.locator('.tour-badge[aria-current="step"]');
    await expect(current).toHaveCount(1);
    const before = await current.getAttribute("aria-label");
    await shot("overview-demo-loaded", false);
    await tour.getByRole("button", { name: "Next step" }).click();
    await expect(tour.locator('.tour-badge[aria-current="step"]')).not.toHaveAttribute("aria-label", before ?? "");
    await expect(page.locator(".premium-price-visual")).toBeVisible({ timeout: 30_000 });
    await shot("overview-demo-full");

    // 2 · Evidence: import page, then the deep-linked demo story in the source inbox.
    await page.goto("/?view=imports&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { level: 1, name: "Import evidence" })).toBeVisible();
    await expect(page.locator(".demo-ribbon")).toBeVisible();
    await shot("imports", false);
    await page.goto(STORY);
    await expect(page.getByRole("heading", { name: "Source inbox" })).toBeVisible();
    await expect(page.locator(".selection-item.active")).toContainText("syn-002");
    await expect(page.getByText("Synthetic article · no web page")).toBeVisible();
    await expect(page.locator(".tour-bar")).toBeVisible();
    await shot("events-inbox", false);

    // 3 · Analyse the commodity-shock article under all three methods.
    await page.getByRole("button", { name: "Analyse under all three methods" }).click();
    await expect(page.locator(".trio-card")).toHaveCount(3, { timeout: 60_000 });
    await expect(page.locator(".run-summary .verdict")).toContainText(/Berger Paints/);
    await expect(page.locator(".score-formula")).toContainText("0.6 ×");
    await expectTooltip(page, "Signed evidence score", /not a probability/);
    await expectTooltip(page, "Evidence coverage", /available at the cutoff/);
    await shot("events-analysed");

    // 4 · The saved result opens by itself, with its audit trail.
    await page.goto("/?view=saved&workspace=demo&universe=demo&article=syn-002");
    await expect(page.getByRole("heading", { name: "Model call audit" })).toBeVisible({ timeout: 30_000 });
    await shot("saved-case");

    // 5 + 6 · Comparisons load by themselves; later outcomes stay separate from the decision.
    await page.goto("/?view=comparisons&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { name: "Method usage" })).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Evaluate later outcomes" }).click();
    await expect(page.getByRole("columnheader", { name: "Evidence label" })).toBeVisible({ timeout: 60_000 });
    await shot("comparisons");
    await page.goto("/?view=saved&workspace=demo&universe=demo&article=syn-002");
    await expect(page.locator(".outcome-card")).toBeVisible({ timeout: 30_000 });
    await page.locator(".outcome-card").scrollIntoViewIfNeeded();
    await shot("saved-outcome", false);

    // 7 · Strategy lab: indicators, a backtest with costs (low-sample warning), a Monte Carlo bootstrap.
    await page.goto("/?view=lab&workspace=demo&universe=demo");
    await expect(page.getByRole("heading", { level: 1, name: "Strategy lab" })).toBeVisible();
    await page.getByRole("button", { name: /load local history/i }).click();
    await expect(page.locator(".indicator-select").first()).toBeVisible({ timeout: 60_000 });
    await shot("lab-history", false);
    await page.getByRole("button", { name: /run backtest/i }).click();
    await expect(page.getByRole("heading", { name: /equity & execution report/i })).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".low-sample")).toContainText("Low sample size — fewer than 30 closed trades");
    await expect(page.locator(".metric").filter({ hasText: "Sharpe ratio" }).locator(".low-sample-flag")).toBeVisible();
    await expectTooltip(page, "Probabilistic Sharpe (PSR)", /does not account for trying many settings/);
    await shot("lab-backtest");
    await page.getByRole("button", { name: /simulate return paths/i }).click();
    await expect(page.locator(".simulation-svg")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".chart-legend")).toContainText("Starting capital");
    await page.locator(".simulation-svg").scrollIntoViewIfNeeded();
    await shot("lab-monte-carlo", false);

    // Restart tour: clears saved progress and sends the tour back to the first unfinished step.
    await page.goto("/?view=overview&workspace=demo&universe=demo");
    await page.locator(".tour-card").getByRole("button", { name: "Restart tour" }).first().click();
    await expect(page.locator(".tour-progress")).toHaveText("1 of 7 done");
    await expect(page.locator('.tour-badge[aria-current="step"]')).toHaveAttribute("aria-label", "Step 2: Pick a news story");
    await expect(page.locator(".skip-link")).toHaveCSS("width", "1px");

    await context.close();
    expect(problems, problems.join("\n")).toEqual([]);
  });
}
