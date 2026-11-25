import { expect, test, type Browser, type Page } from "@playwright/test";
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";

// Walks the presentation story (docs/presentation/DEMO_SCRIPT.md) against the running dev stack
// (`npm run dev` from the project root) using the offline replay demo, on the simple UI:
// 4 tabs (Home · Analyse · Results · Lab) + ⚙ Settings. Also checks that every pre-redesign
// ?view= URL lands on the right new tab, that tab and sub-tab clicks keep the back button working,
// that light is the default theme, and that a 390 px phone has no horizontal page scroll.
// Screenshots land in web/tests/screenshots/<viewport>-<theme>/ (gitignored).

const VIEWPORTS = [
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
] as const;
const PHONE = { name: "390x844", width: 390, height: 844 } as const;
const THEMES = ["light", "dark"] as const;
const SHOTS = path.join(__dirname, "screenshots");
const IGNORED_CONSOLE = [/Download the React DevTools/i, /\[HMR\]/, /\[Fast Refresh\]/];
const DEMO = "workspace=demo&universe=demo";
const STORY = `/?view=events&${DEMO}&article=syn-002&cutoff=2026-01-12T12%3A00%3A00Z`;
const STORY_TITLE = "Crude-oil supply disruption for a paint maker";
const SETTINGS = "Settings: import data, connections, glossary";

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

/** A fresh context with a saved theme (or none) and the tour progress cleared once. */
async function open(browser: Browser, viewport: { width: number; height: number }, theme: "light" | "dark" | null, colorScheme: "light" | "dark" = theme ?? "light") {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, colorScheme, reducedMotion: "reduce" });
  await context.addInitScript(value => {
    try {
      if (value) localStorage.setItem("market-events-theme", value);
      if (!sessionStorage.getItem("tour-reset")) { localStorage.removeItem("market-events-tour"); sessionStorage.setItem("tour-reset", "1"); }
    } catch { /* storage blocked */ }
  }, theme);
  const page = await context.newPage();
  return { context, page, problems: watchConsole(page) };
}

/** Keep the existing PNGs during preliminary QA. */
function shooter(page: Page, folderName: string) {
  const capture = process.env.PLAYWRIGHT_SKIP_SCREENSHOTS !== "1";
  const folder = path.join(SHOTS, folderName);
  if (capture) {
    mkdirSync(folder, { recursive: true });
    for (const file of readdirSync(folder)) if (file.endsWith(".png")) rmSync(path.join(folder, file));
  }
  let index = 0;
  return async (name: string, fullPage = true) => {
    if (!capture) return;
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(folder, `${String(++index).padStart(2, "0")}-${name}.png`), fullPage });
  };
}

/** The active main tab (or ⚙ Settings) and, when given, the active sub-tab. */
async function expectTab(page: Page, tab: "Home" | "Analyse" | "Results" | "Lab" | "Settings", sub?: string) {
  if (tab === "Settings") {
    await expect(page.getByRole("link", { name: SETTINGS })).toHaveAttribute("aria-current", "page");
    await expect(page.locator('nav[aria-label="Main"] a[aria-current="page"]')).toHaveCount(0);
  } else {
    await expect(page.locator('nav[aria-label="Main"] a[aria-current="page"]')).toHaveText(tab);
  }
  if (sub) await expect(page.locator('nav.subtabs a[aria-current="page"]')).toHaveText(sub);
  else await expect(page.locator("nav.subtabs")).toHaveCount(0);
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

async function expectNoSideScroll(page: Page, where: string) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `horizontal page scroll on ${where}`).toBeLessThanOrEqual(0);
}

async function expectDownload(page: Page, name: string, filename: string | RegExp) {
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name, exact: true }).click();
  const download = await downloadPromise;
  if (typeof filename === "string") expect(download.suggestedFilename()).toBe(filename);
  else expect(download.suggestedFilename()).toMatch(filename);
  expect(await download.failure()).toBeNull();
}

for (const viewport of VIEWPORTS) for (const theme of THEMES) {
  test(`demo story · ${viewport.name} · ${theme}`, async ({ browser }) => {
    test.setTimeout(240_000);
    const { context, page, problems } = await open(browser, viewport, theme);
    const shot = shooter(page, `${viewport.name}-${theme}`);
    const tour = page.locator('section[aria-label="Get started"]');

    // 1 · Home (old ?view=overview URL) → load the synthetic replay demo; the demo banner shows everywhere.
    await page.goto("/?view=overview");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
    await expectTab(page, "Home");
    await expect(page.getByRole("button", { name: "Explore demo" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Connect real data" })).toHaveAttribute("href", /workspace=local&universe=live&tab=connections/);
    await shot("home-start", false);
    await page.getByRole("button", { name: "Explore demo" }).click();
    await page.waitForURL(/workspace=demo/);
    await expect(page.getByRole("status").filter({ hasText: /synthetic replay demo loaded/i })).toBeVisible();
    await expect(page.locator(".demo-ribbon")).toContainText("Demo mode");
    await expect(page.locator(".demo-ribbon")).toContainText("invented test data");
    await expect(page.locator(".demo-ribbon")).toContainText("nothing here places orders");
    await expect(page.locator(".site-footer")).toHaveText("Research tool, not advice · Strategy history ends 31 Dec 2020 · No order execution");

    // "New here?" strip: 3 steps, done ones form an unbroken run from step 1, and the demo step is done.
    await expect(tour).toBeVisible();
    await expect(tour.locator(".tour-steps li")).toHaveCount(3);
    await expect(tour.locator(".tour-steps li").first()).toHaveAttribute("data-done", "");
    const doneFlags = await tour.locator(".tour-steps li").evaluateAll(steps => steps.map(step => step.hasAttribute("data-done")));
    const firstOpen = doneFlags.indexOf(false);
    expect(doneFlags.slice(firstOpen < 0 ? doneFlags.length : firstOpen).every(flag => !flag)).toBe(true);
    await expect(page.getByRole("region", { name: "Summary" }).locator(".stat-tile")).not.toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Latest stories" })).toBeVisible();
    await shot("home-demo-loaded", false);
    await shot("home-demo-full");

    // 2 · Analyse (old ?view=events URL, deep-linked story kept): the story card with its source facts.
    await page.goto(STORY);
    await expectTab(page, "Analyse");
    await expect(page.getByRole("heading", { name: /^Stories/ })).toBeVisible();
    await expect(page.locator(".story-row.selected")).toContainText(STORY_TITLE);
    await expect(page.getByRole("heading", { level: 1, name: "Berger Paints" })).toBeVisible();
    await expect(page.getByText("Synthetic article · no web page")).toBeVisible();
    await expect(page.getByText("Only news and prices available before the decision time are used.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Run recorded replay" })).toBeVisible();
    await shot("analyse-story", false);

    // 3 · Analyse the commodity-shock article under all three methods (More options).
    await page.locator("details.more-options > summary").click();
    await page.getByRole("button", { name: "Run all three methods and compare" }).click();
    await expect(page.locator(".trio-card")).toHaveCount(3, { timeout: 60_000 });
    await expect(page.locator(".verdict-card .verdict")).toContainText(/Berger Paints/);
    await expect(page.locator(".verdict-card").getByRole("heading", { name: "What pushed the score" })).toBeVisible();
    await expect(page.locator(".score-formula")).toContainText("0.6 ×");
    await expect(page.getByText("The score measures evidence strength. It is not a probability or a forecast.")).toBeVisible();
    await expectTooltip(page, "Signed evidence score", /not a probability/);
    await expectTooltip(page, "Data coverage", /available at the cutoff/);
    await shot("analyse-verdict");

    // 4 · Results › Saved runs (old ?view=saved URL): the saved run opens by itself, with its audit trail.
    await page.goto(`/?view=saved&${DEMO}&article=syn-002`);
    await expectTab(page, "Results", "Saved runs");
    await expect(page.getByRole("heading", { level: 1, name: "Results" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Model call audit" })).toBeVisible({ timeout: 30_000 });
    await shot("results-saved");

    // 5 + 6 · Results › Compare methods (old ?view=comparisons URL); later outcomes stay separate from the decision.
    await page.goto(`/?view=comparisons&${DEMO}`);
    await expectTab(page, "Results", "Compare methods");
    await expect(page.getByRole("heading", { name: "Method usage" })).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Evaluate later outcomes" }).click();
    await expect(page.getByRole("columnheader", { name: "Evidence label" })).toBeVisible({ timeout: 60_000 });
    await shot("results-compare");
    await page.goto(`/?view=saved&${DEMO}&article=syn-002`);
    await expect(page.locator(".outcome-card")).toBeVisible({ timeout: 30_000 });
    await page.locator(".outcome-card").scrollIntoViewIfNeeded();
    await shot("results-outcome", false);

    // 7a · Lab › Indicators (old ?view=technicals URL): indicator readings and the price chart.
    await page.goto(`/?view=technicals&${DEMO}`);
    await expectTab(page, "Lab", "Indicators");
    await expect(page.getByRole("heading", { level: 1, name: "Lab" })).toBeVisible();
    await expect(page.locator(".lab-banner")).toContainText("data ends 31 Dec 2020");
    await page.getByRole("button", { name: "Compute price indicators" }).click();
    await expect(page.getByRole("heading", { name: "What the indicators say" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("group", { name: "Indicators to show" }).locator(".chip")).not.toHaveCount(0);
    await shot("lab-indicators");

    // 7b · Lab › Backtest (old ?view=lab URL): history, a backtest with costs (low-sample warning).
    await page.goto(`/?view=lab&${DEMO}`);
    await expectTab(page, "Lab", "Backtest");
    await page.getByRole("button", { name: /load local history/i }).click();
    await expect(page.getByRole("group", { name: "Chart indicators" }).locator(".chip").first()).toBeVisible({ timeout: 60_000 });
    await shot("lab-history", false);
    await page.getByRole("button", { name: /^run backtest$/i }).click();
    await expect(page.getByRole("heading", { name: /equity & execution report/i })).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".low-sample")).toContainText("Low sample size — fewer than 30 closed trades");
    await expect(page.locator(".stat-tile").filter({ hasText: "Sharpe ratio" }).locator(".low-sample-flag")).toBeVisible();
    await expectTooltip(page, "Probabilistic Sharpe (PSR)", /does not account for trying many settings/);
    await shot("lab-backtest");

    // 7c · Lab › Monte Carlo (sub-tab click keeps the backtest): a bootstrap of the backtest's own returns.
    await page.locator('nav.subtabs').getByRole("link", { name: "Monte Carlo" }).click();
    await expectTab(page, "Lab", "Monte Carlo");
    await page.getByRole("button", { name: /simulate return paths/i }).click();
    await expect(page.locator(".simulation-svg")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".chart-legend")).toContainText("Starting capital");
    await page.locator(".simulation-svg").scrollIntoViewIfNeeded();
    await shot("lab-monte-carlo", false);
    await page.goBack();
    await expectTab(page, "Lab", "Backtest");
    await expect(page.getByRole("heading", { name: /equity & execution report/i })).toBeVisible();

    // 8 · Settings (old ?view=imports and ?view=connections URLs) and its other sub-tabs.
    await page.goto(`/?view=imports&${DEMO}`);
    await expectTab(page, "Settings", "Import data");
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Import evidence" })).toBeVisible();
    await shot("settings-import", false);
    await page.goto(`/?view=connections&${DEMO}`);
    await expectTab(page, "Settings", "Connections");
    await expect(page.locator(".api-status")).toContainText("API connected");
    await shot("settings-connections", false);
    await page.locator(".demo-ribbon").getByRole("link", { name: "What does this mean?" }).click();
    await expectTab(page, "Settings", "Glossary");
    await expect(page.getByRole("searchbox", { name: "Search the glossary" })).toHaveValue("Synthetic demo");
    await expect(page.locator(".glossary dt", { hasText: "Synthetic demo" })).toBeVisible();
    await shot("settings-glossary", false);
    await page.locator("nav.subtabs").getByRole("link", { name: "Appearance" }).click();
    await expectTab(page, "Settings", "Appearance");
    await expect(page.getByRole("radio", { name: new RegExp(`^${theme}`, "i") })).toBeChecked();
    await shot("settings-appearance", false);

    // Tour: later steps are ticked; Restart clears the click-only ones; Skip hides the strip; About brings it back.
    await page.goto(`/?view=home&${DEMO}`);
    const later = (name: string) => tour.locator(".tour-later > span", { hasText: name }).locator(".tour-tick");
    await expect(later("compare methods")).toHaveCount(1);
    await expect(later("test a price rule")).toHaveCount(1);
    await tour.getByRole("button", { name: "Restart tour" }).click();
    await expect(later("compare methods")).toHaveCount(0);
    await expect(later("test a price rule")).toHaveCount(0);
    await tour.getByRole("button", { name: "Skip tour" }).click();
    await expect(tour).toHaveCount(0);
    await page.goto(`/?view=settings&tab=about&${DEMO}`);
    await page.getByRole("button", { name: "Restart the tour" }).click();
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Home" }).click();
    await expect(tour).toBeVisible();
    await expect(page.locator(".skip-link")).toHaveCSS("width", "1px");

    await context.close();
    expect(problems, problems.join("\n")).toEqual([]);
  });
}

test("old ?view= URLs land on the right new tab and keep the other parameters", async ({ browser }) => {
  test.setTimeout(120_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  const cases = [
    ["overview", "Home", undefined],
    ["events", "Analyse", undefined],
    ["saved", "Results", "Saved runs"],
    ["comparisons", "Results", "Compare methods"],
    ["technicals", "Lab", "Indicators"],
    ["lab", "Lab", "Backtest"],
    ["imports", "Settings", "Import data"],
    ["connections", "Settings", "Connections"],
  ] as const;
  for (const [view, tab, sub] of cases) {
    await page.goto(`/?view=${view}&${DEMO}`);
    await expectTab(page, tab, sub);
    await expect(page.locator(".demo-ribbon"), `?view=${view} kept workspace=demo`).toBeVisible();
  }
  // The new names, and an unknown view falling back to Home.
  await page.goto(`/?view=results&tab=compare&${DEMO}`);
  await expectTab(page, "Results", "Compare methods");
  await page.goto(`/?view=lab&tab=montecarlo&${DEMO}`);
  await expectTab(page, "Lab", "Monte Carlo");
  await page.goto(`/?view=settings&${DEMO}`);
  await expectTab(page, "Settings", "Import data");
  await page.goto(`/?view=nope&${DEMO}`);
  await expectTab(page, "Home");
  // article= survives the old URL: the story is selected in Analyse.
  await page.goto(`/?view=events&${DEMO}&article=syn-001`);
  await expect(page.locator(".story-row.selected")).toContainText("Earnings growth");
  await context.close();
  expect(problems, problems.join("\n")).toEqual([]);
});

test("the 4 tabs, Settings and sub-tabs are clickable and the back button works", async ({ browser }) => {
  test.setTimeout(120_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  const main = page.getByRole("navigation", { name: "Main" });
  await page.goto(`/?view=home&${DEMO}`);
  await expectTab(page, "Home");
  await main.getByRole("link", { name: "Analyse" }).click();
  await expectTab(page, "Analyse");
  await expect(page).toHaveURL(/view=analyse/);
  await main.getByRole("link", { name: "Results" }).click();
  await expectTab(page, "Results", "Saved runs");
  await page.locator("nav.subtabs").getByRole("link", { name: "Compare methods" }).click();
  await expectTab(page, "Results", "Compare methods");
  await expect(page).toHaveURL(/tab=compare/);
  await main.getByRole("link", { name: "Lab" }).click();
  await expectTab(page, "Lab", "Indicators");
  for (const sub of ["Backtest", "Monte Carlo", "Indicators"]) {
    await page.locator("nav.subtabs").getByRole("link", { name: sub }).click();
    await expectTab(page, "Lab", sub);
  }
  await page.getByRole("link", { name: SETTINGS }).click();
  await expectTab(page, "Settings", "Import data");
  for (const sub of ["Connections", "Glossary", "Appearance", "About", "Import data"]) {
    await page.locator("nav.subtabs").getByRole("link", { name: sub }).click();
    await expectTab(page, "Settings", sub);
  }
  // Back walks the same path in reverse.
  await page.goBack();
  await expectTab(page, "Settings", "About");
  await page.goBack(); await page.goBack(); await page.goBack(); await page.goBack();
  await expectTab(page, "Settings", "Import data");
  await page.goBack();
  await expectTab(page, "Lab", "Indicators");
  // Workspace switcher: three plainly named options; switching keeps the current view.
  const workspace = page.locator(".workspace-select select");
  await expect(workspace.locator("option")).toHaveText(["Demo data (offline)", "My data – real companies", "My data – demo companies"]);
  await workspace.selectOption({ label: "My data – demo companies" });
  await expect(page).toHaveURL(url => url.searchParams.get("workspace") === "local" && url.searchParams.get("universe") === "demo");
  await expectTab(page, "Lab", "Indicators");
  await expect(workspace).toHaveValue("local:demo");
  await workspace.selectOption({ label: "My data – real companies" });
  await expect(page).toHaveURL(url => url.searchParams.get("workspace") === "local" && url.searchParams.get("universe") === "live");
  await expectTab(page, "Lab", "Indicators");
  await expect(page.locator(".demo-ribbon")).toHaveCount(0);
  await page.getByRole("link", { name: "marketevents home" }).click();
  await expectTab(page, "Home");
  await context.close();
  expect(problems, problems.join("\n")).toEqual([]);
});

test("an explicit replay repeat links back to the original and an early cutoff abstains", async ({ browser }) => {
  test.setTimeout(90_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  async function analyse() {
    const responsePromise = page.waitForResponse(response =>
      new URL(response.url()).pathname === "/api/research/analyse" && response.request().method() === "POST");
    await page.getByRole("button", { name: "Run recorded replay" }).click();
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    await expect(page.getByRole("status").filter({ hasText: /Analysis saved/ })).toBeAttached();
    return response.json();
  }
  try {
    await page.goto(STORY);
    const original = await analyse();
    const verdict = page.getByRole("region", { name: "Verdict" });
    await expect(verdict.locator(".breakdown-notes")).toContainText(/conflict/i);
    await page.getByText("More options", { exact: true }).click();
    const repeat = page.getByRole("checkbox", { name: /Repeat experiment/ });
    await repeat.check();
    const repeated = await analyse();
    expect(repeated.run_id).not.toBe(original.run_id);
    expect(repeated.parent_run_id).toBe(original.run_id);

    await repeat.uncheck();
    await page.getByLabel("Time", { exact: true }).fill("16:00");
    const early = await analyse();
    expect(early.assessment.direction).toBe("abstain");
    await expect(verdict.getByText("No verdict: evidence incomplete.")).toBeVisible();
    await expect(verdict.locator(".breakdown-notes")).toContainText(/commodity/i);
  } finally {
    await context.close();
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

test("synthetic articles and prices import through Settings and appear in the workspace", async ({ browser }) => {
  test.setTimeout(90_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  const scope = "workspace=local&universe=demo";
  const article = {
    article_id: "ui-qa-synthetic-import",
    source_url: "https://fixtures.invalid/ui-qa-synthetic-import",
    text: "Synthetic UI QA import article about Berger Paints earnings.",
    published_at: "2020-12-30T10:00:00Z",
    first_seen_at: "2020-12-30T10:05:00Z",
  };
  const prices = [
    "instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit",
    "SYNTHETIC:UI_QA,equity,2020-12-30T10:00:00Z,2020-12-30T10:05:00Z,100,102,99,101,123,INR,share",
  ].join("\n");
  async function importRecords(kind: "articles" | "prices", content: string) {
    await page.getByLabel("Records").fill(content);
    const responsePromise = page.waitForResponse(response =>
      new URL(response.url()).pathname === "/api/research/import" && response.request().method() === "POST");
    await page.getByRole("button", { name: "Validate and import" }).click();
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    expect(response.request().postDataJSON()).toMatchObject({ kind, content });
    const result = await response.json();
    expect(result.errors).toEqual([]);
    expect([0, 1]).toContain(result.added); // Re-running the spec imports the same immutable fixture.
    await expect(page.getByRole("heading", { name: "Import report" })).toBeVisible();
    await expect(page.getByText(/No rows were rejected/)).toBeVisible();
    return result.added;
  }
  try {
    const endpoint = `/api/research/workspace?${scope}`;
    const before = await (await context.request.get(endpoint)).json();
    await page.goto(`/?view=settings&tab=import&${scope}`);
    await importRecords("articles", JSON.stringify(article));
    await page.getByRole("button", { name: "Market prices (CSV)" }).click();
    const added = await importRecords("prices", prices);
    const after = await (await context.request.get(endpoint)).json();
    expect(after.observations_count).toBe(before.observations_count + added);
    expect(after.observations_count).toBeGreaterThan(0);
    expect(after.articles).toEqual(expect.arrayContaining([expect.objectContaining(article)]));

    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Analyse" }).click();
    await expect(page.getByRole("button", { name: /Synthetic UI QA import article/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Analyse with configured models" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Run recorded replay" })).toHaveCount(0);

    await page.getByRole("link", { name: SETTINGS }).click();
    await page.locator("nav.subtabs").getByRole("link", { name: "Connections" }).click();
    await expect(page.getByRole("button", { name: "Download history ending 2020" })).toBeDisabled();
    await expect(page.getByRole("heading", { name: "Refresh recent prices and news" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh selected recent evidence" })).toBeDisabled();
  } finally {
    await context.close();
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

test("light is the default theme, even when the system is dark; dark works from Settings › Appearance", async ({ browser }) => {
  const { context, page, problems } = await open(browser, VIEWPORTS[0], null, "dark");
  await page.goto(`/?view=settings&tab=appearance&${DEMO}`);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-theme-preference", "default");
  await page.getByRole("radio", { name: /^Dark/ }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("radio", { name: /^System/ }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("radio", { name: /^Light/ }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await context.close();
  expect(problems, problems.join("\n")).toEqual([]);
});

test("a replay run exposes its inputs, audit and downloadable snapshot", async ({ browser }) => {
  test.setTimeout(90_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  try {
    await page.goto(STORY);
    const inbox = page.getByRole("searchbox", { name: "Search" });
    await inbox.fill("story-does-not-exist");
    await expect(page.getByText("No stories match this search.")).toBeVisible();
    await inbox.fill("paint maker");
    await expect(page.locator(".story-rows").getByRole("button", { name: new RegExp(STORY_TITLE, "i") })).toBeVisible();
    await expect(page.getByText("first seen", { exact: false }).first()).toBeVisible();
    await page.getByRole("button", { name: /^Use demo cutoff/ }).click();
    await expect(page.getByLabel("Date", { exact: true })).toHaveValue("2026-01-12");
    await expect(page.getByLabel("Method").locator("option")).toHaveCount(3);
    await page.getByText("More options", { exact: true }).click();
    await expect(page.getByText("Recorded replay uses saved model responses.")).toBeVisible();
    const repeat = page.getByRole("checkbox", { name: /Repeat experiment/ });
    await repeat.check();
    await expect(page.getByRole("button", { name: "Run all three methods and compare" })).toBeDisabled();
    await repeat.uncheck();

    const runPromise = page.waitForResponse(response =>
      response.url().includes("/api/research/analyse?") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Run recorded replay" }).click();
    const response = await runPromise;
    expect(response.ok()).toBe(true);
    const run = await response.json();
    expect(run).toMatchObject({ article_id: "syn-002", mode: "replay" });
    await expect(page.getByRole("status").filter({ hasText: /Analysis saved/ })).toBeAttached();

    const verdict = page.locator(".verdict-card");
    await verdict.getByText("Numbers at the decision time", { exact: true }).click();
    await expect(verdict.getByRole("columnheader", { name: "Input" })).toBeVisible();
    await verdict.getByText("Full audit trail (sources, model calls, rules)", { exact: true }).click();
    await expect(verdict.getByRole("heading", { name: "Model call audit" })).toBeVisible();
    await expect(verdict.getByRole("heading", { name: "Supporting source passages" })).toBeVisible();
    await verdict.getByText("Inspect saved extraction, numbers and call trace (JSON)", { exact: true }).click();
    await expect(verdict.locator(".json-view pre")).toContainText(run.run_id);
    await expectDownload(page, "Download snapshot", `run-${run.run_id}.json`);

    await verdict.getByRole("link", { name: "Open in Results" }).click();
    await expectTab(page, "Results", "Saved runs");
    await expect(page).toHaveURL(new RegExp(`run=${run.run_id}`));
    await expect(page.getByRole("heading", { name: "Model call audit" })).toBeVisible();
    await expectDownload(page, "Download snapshot", `case-${run.run_id}.json`);
    const savedSearch = page.getByRole("searchbox", { name: "Search" });
    await savedSearch.fill("story-does-not-exist");
    await expect(page.getByText("No saved runs match this search.")).toBeVisible();
    await savedSearch.fill("paint maker");
    await expect(page.locator(".runs-table tbody tr").first()).toContainText(STORY_TITLE);

    await page.locator("nav.subtabs").getByRole("link", { name: "Compare methods" }).click();
    await page.getByText(/^Same article, different methods/).click();
    await expect(page.getByRole("columnheader", { name: "Article · cutoff" })).toBeVisible();
    await page.getByText(/Agreement with hand labels/).click();
    await expect(page.getByRole("columnheader", { name: "Filter recall" })).toBeVisible();
    await page.getByText("Matched cohorts, run manifest and ablations (JSON)", { exact: true }).click();
    await expect(page.locator("details").filter({ hasText: "Matched cohorts, run manifest and ablations (JSON)" }).locator("pre")).toBeVisible();
    await expectDownload(page, "Download comparisons", "research-comparisons.json");
  } finally {
    await context.close();
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

test("offline lab reports, opt-in and animation controls are reachable", async ({ browser }) => {
  test.setTimeout(120_000);
  const { context, page, problems } = await open(browser, VIEWPORTS[0], "light");
  try {
    await page.goto(`/?view=lab&tab=indicators&${DEMO}`);
    await page.getByRole("button", { name: "Compute price indicators" }).click();
    await expect(page.getByRole("heading", { name: "What the indicators say" })).toBeVisible({ timeout: 60_000 });
    const chips = page.getByRole("group", { name: "Indicators to show" });
    const indicator = chips.getByRole("button").first();
    await expect(indicator).toHaveAttribute("aria-pressed", "true");
    await indicator.click();
    await expect(indicator).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator("canvas").first()).toBeVisible();
    await expectDownload(page, "Download snapshot", "technical-snapshot.json");

    await page.route("https://s3.tradingview.com/**", route => route.fulfill({ contentType: "application/javascript", body: "" }));
    const widget = page.locator('iframe[title="Independent TradingView hosted chart"]');
    await page.getByText("TradingView chart (optional, external service)", { exact: true }).click();
    const optIn = page.getByRole("checkbox", { name: "Load the TradingView widget" });
    await expect(optIn).not.toBeChecked();
    await expect(widget).toHaveCount(0);
    await optIn.check();
    await expect(widget).toBeVisible();
    await optIn.uncheck();
    await expect(widget).toHaveCount(0);

    await page.locator("nav.subtabs").getByRole("link", { name: "Backtest" }).click();
    await page.getByText("Download daily prices from Upstox (explicit action)", { exact: true }).click();
    await expect(page.getByRole("button", { name: "Download historical candles" })).toBeDisabled();
    await page.getByRole("button", { name: "Load local history" }).click();
    await expect(page.getByRole("group", { name: "Chart indicators" })).toBeVisible();
    await expectDownload(page, "History JSON", "study-history.json");
    await page.getByText("Advanced parameters", { exact: true }).click();
    await page.getByRole("checkbox", { name: "Also test a walk-forward split" }).check();
    await expect(page.getByRole("checkbox", { name: "Also test a walk-forward split" })).toBeChecked();
    await page.getByRole("button", { name: "Run backtest", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Equity & execution report" })).toBeVisible({ timeout: 60_000 });
    await page.getByText(/^Trades \(\d+\)$/).click();
    await expect(page.locator("details").filter({ has: page.getByText(/^Trades \(\d+\)$/) })).toHaveAttribute("open", "");
    await expect(page.getByText("Walk-forward check", { exact: true })).toBeVisible();
    await expectDownload(page, "Download backtest JSON", "backtest.json");

    await page.locator("nav.subtabs").getByRole("link", { name: "Monte Carlo" }).click();
    await page.getByRole("button", { name: "Simulate return paths" }).click();
    await expect(page.getByText("System reduced-motion preference is active. Complete static paths are displayed.")).toBeVisible();
    const replay = page.getByRole("button", { name: "Replay", exact: true });
    await expect(replay).toBeDisabled();
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const reduce = page.getByRole("checkbox", { name: "Reduced motion" });
    if (await reduce.isChecked()) await reduce.uncheck();
    await replay.click();
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(page.getByRole("button", { name: "Play", exact: true })).toBeEnabled();
    await reduce.check();
    await expect(replay).toBeDisabled();
    await expectDownload(page, "Download Monte Carlo JSON", "monte-carlo.json");
  } finally {
    await context.close();
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

test(`phone · ${PHONE.name} · light: every screen fits without horizontal page scroll`, async ({ browser }) => {
  test.setTimeout(180_000);
  const { context, page, problems } = await open(browser, PHONE, "light");
  const shot = shooter(page, `${PHONE.name}-light`);
  const screens = [
    ["home", `/?view=home&${DEMO}`, "Home", undefined],
    ["analyse", STORY, "Analyse", undefined],
    ["results-saved", `/?view=results&tab=saved&${DEMO}&article=syn-002`, "Results", "Saved runs"],
    ["results-compare", `/?view=results&tab=compare&${DEMO}`, "Results", "Compare methods"],
    ["lab-indicators", `/?view=lab&tab=indicators&${DEMO}`, "Lab", "Indicators"],
    ["lab-backtest", `/?view=lab&tab=backtest&${DEMO}`, "Lab", "Backtest"],
    ["lab-monte-carlo", undefined, "Lab", "Monte Carlo"],
    ["settings-import", `/?view=settings&tab=import&${DEMO}`, "Settings", "Import data"],
    ["settings-glossary", undefined, "Settings", "Glossary"],
    ["settings-connections", undefined, "Settings", "Connections"],
    ["settings-appearance", undefined, "Settings", "Appearance"],
    ["settings-about", undefined, "Settings", "About"],
  ] as const;
  const main = page.getByRole("navigation", { name: "Main" });
  for (const [name, url, tab, sub] of screens) {
    if (url) await page.goto(url);
    else await page.locator("nav.subtabs").getByRole("link", { name: sub, exact: true }).click();
    await expectTab(page, tab, sub);
    await expect(page.locator(".demo-ribbon")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });
    if (name === "results-saved") await expect(page.getByRole("heading", { name: "Model call audit" })).toBeVisible({ timeout: 30_000 });
    if (name === "results-compare") await expect(page.getByRole("heading", { name: "Method usage" })).toBeVisible({ timeout: 60_000 });
    if (name === "lab-backtest") {
      await page.getByRole("button", { name: /^run backtest$/i }).click();
      await expect(page.getByRole("heading", { name: /equity & execution report/i })).toBeVisible({ timeout: 60_000 });
    }
    if (name === "lab-indicators") {
      await page.getByRole("button", { name: "Compute price indicators" }).click();
      await expect(page.getByRole("heading", { name: "What the indicators say" })).toBeVisible({ timeout: 60_000 });
    }
    if (name === "lab-monte-carlo") {
      await page.getByRole("button", { name: "Simulate return paths" }).click();
      await expect(page.locator(".simulation-svg")).toBeVisible();
    }
    await expect(main).toBeVisible();
    await expectNoSideScroll(page, name);
    await shot(name);
    await page.setViewportSize({ width: 360, height: PHONE.height });
    await expectNoSideScroll(page, `${name} at 360 px`);
    await page.setViewportSize({ width: PHONE.width, height: PHONE.height });
  }
  // All four tabs and ⚙ stay reachable (44 px targets) on the phone.
  for (const link of await main.getByRole("link").all()) {
    const box = await link.boundingBox();
    expect(box && box.height >= 44, `${await link.textContent()} tab is at least 44 px tall`).toBe(true);
  }
  const gear = await page.getByRole("link", { name: SETTINGS }).boundingBox();
  expect(gear && gear.width >= 44 && gear.height >= 44).toBe(true);
  for (const [tab, sub] of [["Home", undefined], ["Analyse", undefined], ["Results", "Saved runs"], ["Lab", "Indicators"]] as const) {
    await main.getByRole("link", { name: tab, exact: true }).click();
    await expectTab(page, tab, sub);
  }
  await page.getByRole("link", { name: SETTINGS }).click();
  await expectTab(page, "Settings", "Import data");
  await context.close();
  expect(problems, problems.join("\n")).toEqual([]);
});
