// Unit tests for app/_components/routes.ts: the one place that maps ?view=&tab= (new and old URLs)
// onto the main tabs and Settings. Run with: node --test web/tests/routes.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_TAB, TABS, VIEWS, normalizeQuery, normalizeView } from "../app/_components/routes.ts";

test("the six views and their sub-tabs", () => {
  assert.deepEqual([...VIEWS], ["home", "portfolio", "analyse", "results", "lab", "settings"]);
  assert.deepEqual([...TABS.results], ["saved", "compare"]);
  assert.deepEqual([...TABS.lab], ["indicators", "backtest", "montecarlo"]);
  assert.deepEqual([...TABS.settings], ["import", "connections", "glossary", "appearance", "about"]);
  assert.deepEqual({ ...DEFAULT_TAB }, { results: "saved", lab: "indicators", settings: "import" });
});

for (const [view, tab, expected] of [
  ["home", null, { view: "home", tab: "" }],
  ["portfolio", null, { view: "portfolio", tab: "" }],
  ["analyse", null, { view: "analyse", tab: "" }],
  ["results", "compare", { view: "results", tab: "compare" }],
  ["results", "saved", { view: "results", tab: "saved" }],
  ["lab", "montecarlo", { view: "lab", tab: "montecarlo" }],
  ["lab", "indicators", { view: "lab", tab: "indicators" }],
  ["settings", "glossary", { view: "settings", tab: "glossary" }],
  ["settings", "about", { view: "settings", tab: "about" }],
]) test(`new view ${view}${tab ? `&tab=${tab}` : ""}`, () => {
  assert.deepEqual(normalizeView(view, tab), expected);
});

for (const [view, expected] of [
  ["results", "saved"],
  ["settings", "import"],
]) test(`${view} without a tab opens its default tab`, () => {
  assert.deepEqual(normalizeView(view, null), { view, tab: expected });
  assert.deepEqual(normalizeView(view, ""), { view, tab: expected });
});

test("an unknown sub-tab falls back to the view's default tab", () => {
  assert.deepEqual(normalizeView("results", "nope"), { view: "results", tab: "saved" });
  assert.deepEqual(normalizeView("lab", "nope"), { view: "lab", tab: "indicators" });
  assert.deepEqual(normalizeView("settings", "compare"), { view: "settings", tab: "import" });
});

test("views without sub-tabs ignore a tab", () => {
  assert.deepEqual(normalizeView("home", "compare"), { view: "home", tab: "" });
  assert.deepEqual(normalizeView("analyse", "saved"), { view: "analyse", tab: "" });
});

// Old URLs (before the redesign) must keep landing on the same content.
for (const [old, expected] of [
  ["overview", { view: "home", tab: "" }],
  ["events", { view: "analyse", tab: "" }],
  ["technicals", { view: "lab", tab: "indicators" }],
  ["lab", { view: "lab", tab: "backtest" }],
  ["saved", { view: "results", tab: "saved" }],
  ["comparisons", { view: "results", tab: "compare" }],
  ["imports", { view: "settings", tab: "import" }],
  ["connections", { view: "settings", tab: "connections" }],
]) test(`old ?view=${old} maps to ${expected.view}${expected.tab ? `/${expected.tab}` : ""}`, () => {
  assert.deepEqual(normalizeView(old, null), expected);
});

test("old views ignore any tab they are given", () => {
  assert.deepEqual(normalizeView("comparisons", "saved"), { view: "results", tab: "compare" });
  assert.deepEqual(normalizeView("imports", "glossary"), { view: "settings", tab: "import" });
});

test("missing or unknown views open Home", () => {
  assert.deepEqual(normalizeView(null, null), { view: "home", tab: "" });
  assert.deepEqual(normalizeView(undefined, undefined), { view: "home", tab: "" });
  assert.deepEqual(normalizeView("", "compare"), { view: "home", tab: "" });
  assert.deepEqual(normalizeView("admin", null), { view: "home", tab: "" });
  assert.deepEqual(normalizeView("toString", null), { view: "home", tab: "" });
  assert.deepEqual(normalizeView("results", "toString"), { view: "results", tab: "saved" });
});

test("normalizeQuery rewrites view and tab and keeps every other parameter", () => {
  const next = normalizeQuery(new URLSearchParams("view=saved&workspace=demo&universe=demo&article=syn-002&cutoff=2026-01-12T12%3A00%3A00Z"));
  assert.equal(next.get("view"), "results");
  assert.equal(next.get("tab"), "saved");
  assert.equal(next.get("workspace"), "demo");
  assert.equal(next.get("universe"), "demo");
  assert.equal(next.get("article"), "syn-002");
  assert.equal(next.get("cutoff"), "2026-01-12T12:00:00Z");
});

test("normalizeQuery drops the tab for views without sub-tabs", () => {
  const next = normalizeQuery(new URLSearchParams("view=events&tab=compare&company=X"));
  assert.equal(next.get("view"), "analyse");
  assert.equal(next.has("tab"), false);
  assert.equal(next.get("company"), "X");
});

test("normalizeQuery does not change its input", () => {
  const input = new URLSearchParams("view=technicals");
  normalizeQuery(input);
  assert.equal(input.toString(), "view=technicals");
});
