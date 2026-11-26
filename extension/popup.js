let origin = "https://final-yr-proj.vercel.app";
const real = { workspace: "local", universe: "live" };
const demo = { workspace: "demo", universe: "demo" };
const verdicts = new Map([
  ["positive_evidence", "Positive evidence"],
  ["negative_evidence", "Negative evidence"],
  ["mixed_evidence", "Mixed evidence"],
  ["insufficient_evidence", "Insufficient evidence"],
]);
const byId = id => document.getElementById(id);
const cutoffFormat = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata",
});
let requestNumber = 0;

function siteUrl(scope, view, params = {}) {
  const url = new URL("/", origin);
  url.search = new URLSearchParams({ view, ...scope, ...params });
  return url.href;
}

async function latest(scope) {
  const url = new URL("/api/research/workspace", origin);
  url.search = new URLSearchParams(scope);
  const response = await fetch(url, {
    credentials: "include",
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(2500),
  });
  if (!response.ok) throw new Error("Workspace unavailable");
  const { runs, articles } = await response.json();
  const run = runs
    .filter(item => item.assessment && item.run_id && !item.status?.startsWith("explanation_")
      && !item.config_snapshot?.explanation_parent_run_id && Number.isFinite(Date.parse(item.created_at)))
    .reduce((best, item) => !best || Date.parse(item.created_at) > Date.parse(best.created_at) ? item : best, null);
  if (!run) return null;
  return { run, article: articles.find(item => item.article_id === run.article_id) };
}

async function showPreview(scope, fallbackToDemo = false) {
  const request = ++requestNumber;
  const status = byId("status");
  const details = byId("details");
  byId("real").setAttribute("aria-pressed", String(scope === real));
  byId("demo").setAttribute("aria-pressed", String(scope === demo));
  byId("preview").hidden = true;
  status.hidden = false;
  status.textContent = "Loading the latest saved analysis…";
  details.href = siteUrl(scope, "results", { tab: "saved" });
  details.textContent = "Open saved analyses";
  document.querySelector(".portfolio").href = siteUrl(scope, "portfolio");
  try {
    const preview = await latest(scope);
    if (request !== requestNumber) return;
    if (!preview && fallbackToDemo) {
      await showPreview(demo);
      return;
    }
    if (!preview) {
      status.textContent = scope === demo
        ? "No demo analysis saved. Open the demo workspace to analyse a sample story."
        : "No real analysis saved. Connect a data source or import evidence to get started.";
      details.href = scope === demo
        ? siteUrl(demo, "home")
        : siteUrl(real, "settings", { tab: "connections" });
      details.textContent = scope === demo ? "Open demo workspace" : "Set up real data";
      return;
    }
    const { run, article } = preview;
    const { evidence_label: label, evidence_score: score, coverage } = run.assessment;
    const title = article?.story_title?.trim() || article?.text?.trim();
    const hasScore = Number.isFinite(score) && Math.abs(score) <= 1;
    byId("source").textContent = scope === demo
      ? "Synthetic demo · saved analysis"
      : run.mode === "replay" ? "Real workspace · recorded replay" : "Real workspace · saved analysis";
    byId("story").textContent = title ? title.slice(0, 85) + (title.length > 85 ? "…" : "") : "Latest saved assessment";
    const cutoff = Date.parse(run.decision_time);
    byId("cutoff").textContent = Number.isFinite(cutoff) ? `Decision cutoff ${cutoffFormat.format(cutoff)} IST` : "";
    byId("verdict").textContent = verdicts.get(label) ?? "Evidence assessment";
    byId("score").textContent = hasScore ? `${score > 0 ? "+" : ""}${score.toFixed(2)}` : "No score";
    byId("coverage").textContent = Number.isFinite(coverage) ? `${Math.round(coverage * 100)}%` : "Unavailable";
    byId("scale").hidden = !hasScore;
    byId("scale-labels").hidden = !hasScore;
    if (hasScore) byId("marker").style.left = `${(score + 1) * 50}%`;
    details.href = siteUrl(scope, "results", { tab: "saved", run: run.run_id });
    details.textContent = "Open for analysis";
    byId("preview").hidden = false;
    status.hidden = true;
  } catch {
    if (request !== requestNumber) return;
    status.textContent = origin.startsWith("https:")
      ? "Open the website and sign into Vercel to view saved analysis."
      : "The local app is unavailable. Start Market Events and reopen this popup.";
    details.href = siteUrl(scope, "home");
    details.textContent = "Open Market Events";
  }
}

byId("real").addEventListener("click", () => void showPreview(real));
byId("demo").addEventListener("click", () => void showPreview(demo));
byId("website").addEventListener("change", event => {
  origin = event.target.value;
  void showPreview(real);
});
byId("connect").addEventListener("click", async () => {
  byId("connect").disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({ action: "connect-upstox", origin });
    if (!result?.ok) throw new Error("Could not open the Upstox sign-in window. Try again.");
    window.close();
  } catch (error) {
    byId("status").hidden = false;
    byId("status").textContent = error.message;
    byId("connect").disabled = false;
  }
});
void showPreview(real, true);
