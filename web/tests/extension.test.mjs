import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

test("the extension opens broker sign-in and moves only its own callback to the main window", async () => {
  const listeners = {};
  const values = {};
  const actions = [];
  const chrome = {
    runtime: { id: "test-extension", onMessage: { addListener: fn => { listeners.message = fn; } } },
    windows: {
      getLastFocused: async () => ({ id: 3 }),
      create: async options => { actions.push(options); return { id: 8, tabs: [{ id: 12 }] }; },
      update: async (...args) => { actions.push(["window", ...args]); },
    },
    tabs: {
      get: async () => ({ id: 12, windowId: 8, url: actions[0].url }),
      move: async (...args) => { actions.push(["move", ...args]); },
      update: async (...args) => { actions.push(["tab", ...args]); },
      onUpdated: { addListener: fn => { listeners.updated = fn; } },
      onRemoved: { addListener: fn => { listeners.removed = fn; } },
    },
    storage: { session: {
      set: async data => Object.assign(values, data),
      get: async key => ({ [key]: values[key] }),
      remove: async key => { delete values[key]; },
    } },
  };
  const context = vm.createContext({ chrome, URL, URLSearchParams, Date });
  vm.runInContext(readFileSync(new URL("../../extension/background.js", import.meta.url), "utf8"), context);
  assert.equal(listeners.message({ action: "connect-upstox", origin: "https://evil.invalid" }, { id: "test-extension" }, () => {}), false);
  const response = await new Promise(resolve => {
    listeners.message({ action: "connect-upstox", origin: "https://final-yr-proj.vercel.app" }, { id: "test-extension" }, resolve);
  });
  assert.equal(response.ok, true);
  assert.equal(actions[0].type, "popup");
  assert.equal(new URL(actions[0].url).searchParams.get("connect"), "upstox");
  await vm.runInContext('finishSignIn(12, { url: "https://evil.invalid/?source=extension&upstox=ready" })', context);
  assert.equal(actions.filter(item => item[0] === "move").length, 0);
  await vm.runInContext('finishSignIn(12, { windowId: 8, url: "https://final-yr-proj.vercel.app/?view=portfolio&source=extension&upstox=ready" })', context);
  assert.equal(actions.filter(item => item[0] === "move").length, 1);
  assert.equal(actions.find(item => item[0] === "move")[2].windowId, 3);
  assert.equal(values["12"], undefined);
});
