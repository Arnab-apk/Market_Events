const origins = new Set(["https://final-yr-proj.vercel.app", "http://127.0.0.1:3000"]);
const FLOW_TTL = 10 * 60 * 1000;

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message?.action !== "connect-upstox"
    || !origins.has(message.origin)) return false;
  void openSignIn(message.origin).then(() => respond({ ok: true }))
    .catch(() => respond({ ok: false }));
  return true;
});

async function openSignIn(origin) {
  const mainWindow = await chrome.windows.getLastFocused({ windowTypes: ["normal"] });
  const url = new URL("/", origin);
  url.search = new URLSearchParams({
    view: "portfolio", workspace: "local", universe: "live", connect: "upstox", source: "extension",
  });
  const popup = await chrome.windows.create({
    url: url.href, type: "popup", width: 520, height: 760, focused: true,
  });
  const tab = popup.tabs?.[0];
  if (!tab?.id) throw new Error("Sign-in window has no tab");
  await chrome.storage.session.set({
    [String(tab.id)]: { mainWindowId: mainWindow.id, origin, expiresAt: Date.now() + FLOW_TTL },
  });
  // Recover a callback that arrived before the storage write completed.
  await finishSignIn(tab.id, await chrome.tabs.get(tab.id));
}

async function finishSignIn(tabId, tab) {
  const key = String(tabId);
  const flow = (await chrome.storage.session.get(key))[key];
  if (!flow) return;
  if (flow.expiresAt < Date.now()) {
    await chrome.storage.session.remove(key);
    return;
  }
  let url;
  try { url = new URL(tab.url); } catch { return; }
  if (url.origin !== flow.origin || url.pathname !== "/"
    || url.searchParams.get("source") !== "extension" || !url.searchParams.has("upstox")) return;
  await chrome.storage.session.remove(key);
  try {
    await chrome.tabs.move(tabId, { windowId: flow.mainWindowId, index: -1 });
    await chrome.tabs.update(tabId, { active: true });
    await chrome.windows.update(flow.mainWindowId, { focused: true });
  } catch {
    // If the original window was closed, keep the authenticated website visible.
    if (tab.windowId) await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
  }
}

chrome.tabs.onUpdated.addListener((tabId, change, tab) => {
  if (change.url) void finishSignIn(tabId, tab).catch(() => {});
});
chrome.tabs.onRemoved.addListener(tabId => {
  void chrome.storage.session.remove(String(tabId));
});
