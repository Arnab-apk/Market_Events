import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parsePortfolioCsv, portfolioStorageKey, readPortfolioSnapshot, valuePortfolio } from "../app/_lib/portfolio.ts";

const sample = readFileSync(new URL("../public/sample-portfolio.csv", import.meta.url), "utf8");
const header = "symbol,exchange,quantity,average_cost";
const quotes = [
  { instrument_id: "NSE:ASIANPAINT", latest_close: 116.096896, end: "2026-01-23T10:00:00Z" },
  { instrument_id: "NSE:INDIGO", latest_close: 290.242239, end: "2026-01-23T10:00:00Z" },
  { instrument_id: "NSE:PIDILITIND", latest_close: 232.193791, end: "2026-01-23T10:00:00Z" },
];

test("the bundled portfolio yields reproducible totals and market-value weights", () => {
  const result = valuePortfolio(parsePortfolioCsv(sample).rows.map(row => row.holding), quotes, "demo");
  assert.equal(result.invested, 4150);
  assert.equal(result.pricedCount, 3);
  assert.equal(result.marketValue.toFixed(2), "4469.73");
  assert.equal(result.pnl.toFixed(2), "319.73");
  assert.equal((result.returnRatio * 100).toFixed(2), "7.70");
  assert.equal(result.rows.reduce((sum, row) => sum + row.weight, 0).toFixed(8), "1.00000000");
  assert.ok(result.rows[1].pnl < 0);
});

test("unpriced holdings stay in invested cost but stay out of P&L and allocation", () => {
  const holdings = parsePortfolioCsv(`${header}\nASIANPAINT,NSE,2,100\nASIANPAINT,BSE,10,200`).rows.map(row => row.holding);
  const result = valuePortfolio(holdings, [{ ...quotes[0], latest_close: 150 }], "demo");
  assert.equal(result.invested, 2200);
  assert.equal(result.pricedCost, 200);
  assert.equal(result.pricedCount, 1);
  assert.equal(result.marketValue, 300);
  assert.equal(result.pnl, 100);
  assert.equal(result.returnRatio, 0.5);
  assert.deepEqual(result.rows.map(row => row.weight), [1, null]);
  const wrongUniverse = valuePortfolio(holdings, quotes, "live");
  assert.equal(wrongUniverse.marketValue, null);
  assert.equal(wrongUniverse.pnl, null);
  assert.equal(wrongUniverse.returnRatio, null);
});

test("a priced zero-cost holding has P&L and no percentage return", () => {
  const holdings = parsePortfolioCsv(`${header}\nASIANPAINT,NSE,1,0`).rows.map(row => row.holding);
  const result = valuePortfolio(holdings, [{ ...quotes[0], latest_close: 150 }], "demo");
  assert.equal(result.pnl, 150);
  assert.equal(result.returnRatio, null);
});

test("the preview supports quoted reordered headers, BOM, CRLF, and exact error line numbers", () => {
  const result = parsePortfolioCsv('\uFEFF"Exchange",quantity,average_cost,symbol\r\n"nse",3,"20.5", indigo \r\n\r\nNSE,4,10,INDIGO\r\nBSE,-1,10,ABC\r\n,,,\r\n');
  assert.deepEqual(result.rows[0], { line: 2, holding: { symbol: "INDIGO", exchange: "NSE", quantity: 3, averageCost: 20.5 } });
  assert.match(result.rows[1].error, /Duplicate holding/);
  assert.equal(result.rows[1].line, 4);
  assert.match(result.rows[2].error, /Quantity must be/);
  assert.match(result.rows[3].error, /valid stock symbol/);
  assert.match(parsePortfolioCsv(`${header}\n"not closed`).fileError, /line 2/);
  assert.match(parsePortfolioCsv("symbol,exchange,exchange,average_cost").fileError, /CSV headers/);
});

test("the confirmed portfolio is scoped and corrupt stored snapshots are ignored", () => {
  const scope = { workspace: "demo", universe: "demo" };
  assert.notEqual(portfolioStorageKey(scope), portfolioStorageKey({ ...scope, workspace: "local" }));
  const holding = parsePortfolioCsv(sample).rows[0].holding;
  const snapshot = { source: "sample-portfolio.csv", importedAt: "2026-11-25T10:00:00Z", holdings: [holding] };
  assert.deepEqual(readPortfolioSnapshot(JSON.stringify(snapshot)), snapshot);
  assert.equal(readPortfolioSnapshot("not JSON"), null);
  assert.equal(readPortfolioSnapshot(JSON.stringify({ ...snapshot, holdings: [holding, holding] })), null);
});
