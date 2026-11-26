import { expect, test } from "@playwright/test";

const DEMO_PORTFOLIO = "/?view=portfolio&workspace=demo&universe=demo";

test("sample CSV previews, confirms, prices and opens company research", async ({ page }) => {
  await page.goto("/?view=home");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Portfolio" }).click();
  await page.getByRole("link", { name: "Try sample in demo" }).click();
  await expect(page.getByRole("heading", { name: "Portfolio", exact: true })).toBeVisible();
  const download = await page.request.get("/sample-portfolio.csv");
  expect(download.ok()).toBeTruthy();
  expect(await download.text()).toContain("symbol,exchange,quantity,average_cost");

  await page.getByRole("button", { name: "Load sample CSV" }).click();
  await expect(page.getByRole("region", { name: "CSV preview rows" }).getByRole("row")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByText("₹4,150.00", { exact: true })).toBeVisible();
  await expect(page.getByText("₹4,469.73", { exact: true })).toBeVisible();
  await expect(page.getByText("+₹319.73", { exact: true })).toBeVisible();
  await expect(page.getByText("3 of 3 holdings priced")).toBeVisible();
  await expect(page.getByText("Synthetic demo closes")).toBeVisible();
  const assistant = page.getByRole("region", { name: "Portfolio research assistant" });
  await expect(assistant.getByText(/holdings with saved assessments/)).toBeVisible();
  await expect(assistant.getByRole("link").first()).toHaveAttribute("href", /view=results.*run=/);
  await assistant.getByLabel("Research question").selectOption("conflicts");
  await expect(assistant.getByRole("status")).toContainText("assessment per holding");
  await expect(assistant.getByRole("button", { name: "Ask AI to suggest cases" })).toHaveCount(0);

  await page.getByRole("link", { name: "View research for ASIANPAINT on NSE" }).click();
  await expect(page).toHaveURL(/view=analyse.*company=NSE%3AASIANPAINT/);
  await expect(page.getByRole("heading", { name: "Asian Paints", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^Earnings growth Asian Paints/ }).click();
  await expect(page.getByRole("heading", { name: "Earnings growth", exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Portfolio" }).click();
  const holdings = page.getByRole("region", { name: "Portfolio holdings table" });
  await expect(holdings).toBeVisible();
  await page.reload();
  await expect(holdings.getByRole("row")).toHaveCount(4);
  await page.getByRole("combobox", { name: "Data" }).selectOption("local:demo");
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
});

test("invalid rows block confirmation and a valid import shows partial coverage", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(DEMO_PORTFOLIO);
  const chooser = page.getByLabel("Holdings CSV");
  const upload = (body: string) => chooser.setInputFiles({ name: "holdings.csv", mimeType: "text/csv", buffer: Buffer.from(body) });
  const header = "symbol,exchange,quantity,average_cost\n";
  await upload(`${header}ASIANPAINT,NSE,10,100\nASIANPAINT,NSE,5,200`);
  await expect(page.getByText("Fix 1 row in the CSV and choose the file again.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Import holdings", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Cancel preview" }).click();
  await expect(page.getByRole("heading", { name: "Import preview" })).toHaveCount(0);

  await upload(`${header}ASIANPAINT,NSE,10,100\nASIANPAINT,BSE,5,200`);
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByText("1 of 2 holdings priced")).toBeVisible();
  await expect(page.getByText("+₹160.97", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("+16.10% on ₹1,000.00 invested")).toBeVisible();
  await expect(page.getByText("100.00%", { exact: true })).toBeVisible();
  const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(pageWidth).toBe(390);
  await page.getByRole("link", { name: "View research for ASIANPAINT on BSE" }).click();
  await expect(page.getByRole("heading", { name: "No stories for BSE:ASIANPAINT" })).toBeVisible();
  await page.getByRole("link", { name: "Show all stories" }).click();
  await expect(page.getByRole("button", { name: "Change story" })).toBeVisible();
});

test("an Upstox callback previews holdings and preserves a confirmed import until replaced", async ({ page }) => {
  const endpoint = "/api/research/portfolio?workspace=local&universe=live";
  const initial = await (await page.request.get(endpoint)).json();
  await page.request.post(endpoint, { data: { revision: initial.revision, snapshot: null } });
  await page.route("**/api/portfolio/upstox?action=preview", route => route.fulfill({
    json: { csv: "symbol,exchange,quantity,average_cost\nASIANPAINT,NSE,10,100" },
  }));
  await page.goto("/?view=portfolio&workspace=local&universe=live&upstox=ready");
  await page.getByRole("button", { name: "Preview Upstox holdings" }).click();
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
  await expect(page.getByRole("region", { name: "CSV preview rows" })).toContainText("ASIANPAINT");
  await page.getByRole("button", { name: "Import holdings", exact: true }).click();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("ASIANPAINT");
  await page.reload();
  await expect(page.getByRole("region", { name: "Portfolio holdings table" })).toContainText("ASIANPAINT");
  await page.getByRole("button", { name: "Clear saved holdings" }).click();
  await page.reload();
  await expect(page.getByRole("heading", { name: "No holdings imported" })).toBeVisible();
});
