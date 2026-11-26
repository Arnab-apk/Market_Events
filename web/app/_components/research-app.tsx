"use client";

// App shell: top bar (logo, main tabs, workspace switcher, ⚙ Settings), the demo banner, the API-down
// notice, a toast for action notices, the footer and the view router (routes.ts → panels). Loads
// GET /api/workspace, owns the `api` helper every panel uses, and runs POST /api/demo for "Load synthetic
// demo". Also exports shared pieces (PageHeading, Metric, Empty, JsonView, Status) used by the panels.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Layers3, LoaderCircle, RefreshCw, Settings } from "lucide-react";
import { Api, Scope, Workspace, human } from "./types";
import { ConnectionsPanel, EventsPanel, ImportsPanel, SavedPanel, ComparisonsPanel, TechnicalsPanel } from "./workspace-panels";
import StrategyLab from "./strategy-lab";
import Home from "./premium-overview";
import AppearancePicker from "./theme-toggle";
import { GlossaryList, Term, friendlyError } from "./ui";
import { SubTabs, Toast } from "./simple-ui";
import { normalizeView, type View } from "./routes";
import { resetTour } from "./demo-tour";
import { WorkspaceIntroduction } from "./workspace-introduction";
import packageInfo from "../../package.json";

const PortfolioPanel = dynamic(() => import("./portfolio-panel"));

const TABS: { id: View; label: string; extra?: Record<string, string> }[] = [
  { id: "home", label: "Home" },
  { id: "portfolio", label: "Portfolio" },
  { id: "analyse", label: "Analyse" },
  { id: "results", label: "Results" },
  { id: "lab", label: "Lab", extra: { tab: "indicators" } },
];
// One switcher, three plainly named options.
const WORKSPACES = [
  { value: "demo:demo", label: "Demo data (offline)" },
  { value: "local:live", label: "My data – real companies" },
  { value: "local:demo", label: "My data – demo companies" },
];
const SUBTABS = {
  results: [["saved", "Saved runs"], ["compare", "Compare methods"]],
  lab: [["indicators", "Indicators"], ["backtest", "Backtest"], ["montecarlo", "Monte Carlo"]],
  settings: [["import", "Import data"], ["connections", "Connections"], ["glossary", "Glossary"], ["appearance", "Appearance"], ["about", "About"]],
} as const;

export default function ResearchApp() {
  const parameters = useSearchParams();
  // Held above the keyed shell so a notice survives switching into the demo workspace.
  const [notice, setNotice] = useState("");
  const scope: Scope = {
    workspace: parameters.get("workspace") === "demo" ? "demo" : "local",
    universe: parameters.get("workspace") === "demo" || parameters.get("universe") === "demo" ? "demo" : "live",
  };
  const route = normalizeView(parameters.get("view"), parameters.get("tab"));
  return <WorkspaceShell key={`${scope.workspace}:${scope.universe}`} scope={scope} view={route.view} tab={route.tab} term={parameters.get("term") || ""} notice={notice} setNotice={setNotice} />;
}

export type Href = (view: string, extra?: Record<string, string>) => string;
export type PanelProps = { api: Api; data: Workspace; refresh: () => Promise<void>; href: Href; tab?: string };

function WorkspaceShell({ scope, view, tab, term, notice, setNotice }: { scope: Scope; view: View; tab: string; term: string; notice: string; setNotice: (value: string) => void }) {
  const { workspace, universe } = scope;
  const router = useRouter();
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const api: Api = useCallback(async <T,>(endpoint: string, body?: unknown): Promise<T> => {
    const query = new URLSearchParams({ workspace, universe });
    let response: Response;
    try {
      response = await fetch(`/api/research/${endpoint}?${query}`, {
        method: body === undefined ? "GET" : "POST",
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
      });
    } catch { throw new Error(friendlyError("Failed to fetch")); }
    const result = await response.json().catch(() => ({ detail: "The research API returned an unreadable response. Check the server log and retry." }));
    if (!response.ok) {
      const detail = result.detail;
      const raw = Array.isArray(detail) ? detail.map((e: { msg: string; loc?: string[] }) => `${e.loc?.slice(1).join(".") || "Request"}: ${e.msg}`).join("; ") : detail || "The request failed";
      throw new Error(friendlyError(raw));
    }
    return result as T;
  }, [workspace, universe]);
  const refresh = useCallback(async () => {
    const next = await api<Workspace>("workspace");
    setData(next);
    setError("");
  }, [api]);
  useEffect(() => {
    let active = true;
    api<Workspace>("workspace").then(next => { if (active) setData(next); })
      .catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [api]);
  const dismiss = useCallback(() => setNotice(""), [setNotice]);
  const link = (target: string, to: Scope, extra?: Record<string, string>) => `/?${new URLSearchParams({ view: target, workspace: to.workspace, universe: to.universe, ...extra })}`;
  const href: Href = (target, extra) => link(target, scope, extra);
  const demoHref: Href = (target, extra) => link(target, { workspace: "demo", universe: "demo" }, extra);
  async function loadDemo() {
    setBusy(true); setError("");
    try {
      await api("demo", {});
      if (scope.workspace === "demo") await refresh();
      router.push(demoHref("home"));
      setNotice("Synthetic replay demo loaded. Everything in it is invented test data.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Demo could not be loaded"); }
    finally { setBusy(false); }
  }
  const reload = () => { setBusy(true); refresh().catch(reason => setError(reason.message)).finally(() => setBusy(false)); };
  const props: PanelProps | null = data ? { api, data, refresh, href, tab } : null;
  const demo = scope.workspace === "demo";
  const unreachable = /Can't reach the research engine/.test(error);
  const apiState = data ? "API connected" : error ? "API unreachable" : "Connecting…";
  const subTabs = (id: keyof typeof SUBTABS, label: string, vertical = false) => <SubTabs label={label} current={tab} vertical={vertical}
    tabs={SUBTABS[id].map(([value, text]) => ({ id: value, label: text, href: href(id, { tab: value }) }))} />;

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="topbar"><div className="topbar-inner">
      <Link className="brand" href={href("home")}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 17l5-6 4 4 8-10" /></svg><span>marketevents</span><span className="sr-only"> home</span></Link>
      <nav className="main-tabs" aria-label="Main">{TABS.map(item => <Link key={item.id} href={href(item.id, item.extra)} aria-current={view === item.id ? "page" : undefined}>{item.label}</Link>)}</nav>
      <div className="topbar-tools">
        <label className="workspace-select"><span className="sr-only">Data</span><select disabled={busy} value={`${workspace}:${universe}`} onChange={event => {
          const [next, nextUniverse] = event.target.value.split(":") as [Scope["workspace"], Scope["universe"]];
          router.push(link(view, { workspace: next, universe: nextUniverse }, tab ? { tab } : undefined));
        }}>{WORKSPACES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <Link className="icon-button settings-button" href={href("settings")} aria-label="Settings: import data, connections, glossary" title={apiState} aria-current={view === "settings" ? "page" : undefined}><Settings size={20} aria-hidden="true" /><i className={`api-dot ${data ? "up" : error ? "down" : ""}`} aria-hidden="true" /></Link>
      </div>
    </div></header>
    {universe === "demo" && <div className="demo-ribbon" role="note"><p><span className="demo-badge">{demo ? "Demo mode" : "Demo companies"}</span><span>{demo ? "All articles, prices and model answers are invented test data. Not advice; nothing here places orders." : "Using local data for the demo company universe."}</span><Link href={href("settings", { tab: "glossary", term: "Synthetic demo" })}>What does this mean?</Link></p></div>}
    {error && <div className="api-alert" role="alert"><p><strong>{unreachable ? "Can't reach the research engine." : "Could not complete the request."}</strong> {unreachable ? "The local Python service on port 8000 isn't responding. Start the dev stack with npm.cmd run dev, then retry." : error}</p><button type="button" className="button secondary" onClick={reload} disabled={busy}>Retry</button></div>}
    <main id="main-content" className="content" tabIndex={-1}>
      {!data && !error && <div className="loading-state"><LoaderCircle className="spin" size={24} aria-hidden="true" /><p>Opening your research workspace…</p></div>}
      {data && props && <>
        {view === "home" && <>
          <WorkspaceIntroduction aboutHref={href("settings", { tab: "about" })} />
          <Home api={api} data={data} href={href} demoHref={demoHref} realDataHref={link("settings", { workspace: "local", universe: "live" }, { tab: "connections" })} onDemo={loadDemo} busy={busy} />
        </>}
        {view === "portfolio" && <PortfolioPanel api={api} data={data} refresh={refresh} scope={scope} href={href} demoHref={demoHref} />}
        {view === "analyse" && <EventsPanel {...props} />}
        {view === "results" && <div className="view-stack">
          <PageTitle title="Results" description="Every saved analysis, and how the three methods compare." />
          {subTabs("results", "Results sections")}
          {tab === "compare" ? <ComparisonsPanel {...props} /> : <SavedPanel {...props} />}
        </div>}
        {view === "lab" && <div className="view-stack">
          <PageTitle title="Lab" description="Price indicators, backtests and Monte Carlo on saved daily prices." />
          <p className="lab-banner" role="note"><strong>Historical study</strong> · data ends 31 Dec 2020 · not a forecast</p>
          {subTabs("lab", "Lab sections")}
          {tab === "indicators" ? <TechnicalsPanel {...props} /> : <StrategyLab {...props} tab={tab === "montecarlo" ? "montecarlo" : "backtest"} />}
        </div>}
        {view === "settings" && <div className="view-stack">
          <PageTitle title="Settings" description="Import data, connections, glossary and appearance." />
          <div className="settings-layout">
            <aside className="settings-nav">{subTabs("settings", "Settings sections", true)}</aside>
            <div className="settings-body">
              {tab === "import" && <ImportsPanel {...props} />}
              {tab === "connections" && <>
                <div className="api-status card"><span><i className={`api-dot ${data ? "up" : error ? "down" : ""}`} aria-hidden="true" />{apiState}</span><span className="muted">Workspace: {human(data.provenance || data.workspace)}</span><button type="button" className="button secondary" onClick={reload} disabled={busy}><RefreshCw size={15} aria-hidden="true" />Refresh workspace</button></div>
                <ConnectionsPanel {...props} />
              </>}
              {tab === "glossary" && <section className="card" aria-labelledby="glossary-title"><h2 id="glossary-title">Glossary</h2><p className="muted section-note">Every number and label in plain English. Underlined terms on other pages show the same text on hover or focus.</p><GlossaryList key={term} initial={term} /></section>}
              {tab === "appearance" && <section className="card" aria-labelledby="appearance-title"><h2 id="appearance-title">Appearance</h2><p className="muted section-note">Light is the default. Your choice is saved in this browser.</p><AppearancePicker /></section>}
              {tab === "about" && <About />}
            </div>
          </div>
        </div>}
      </>}
    </main>
    <footer className="site-footer"><p>Research tool, not advice · Strategy history ends 31 Dec 2020 · No order execution</p></footer>
    <Toast message={notice} onDismiss={dismiss} />
  </div>;
}

function PageTitle({ title, description }: { title: string; description: ReactNode }) {
  return <div className="page-title"><h1>{title}</h1><p>{description}</p></div>;
}

function About() {
  return <section className="card about" aria-labelledby="about-title">
    <h2 id="about-title">About marketevents</h2>
    <p>A research tool that turns a dated news story into evidence you can check: which company, what event, what the prices did up to the decision time, and why it got its verdict. It is <strong>not advice</strong> and it <strong>never places orders</strong>.</p>
    <ul>
      <li>The <Term name="Signed evidence score">evidence score</Term> measures evidence strength. It is not a probability or a forecast.</li>
      <li>Historical strategy studies stop at 31 Dec 2020 by design.</li>
      <li>Demo data is invented: articles, prices and model answers are synthetic test fixtures.</li>
    </ul>
    <h3>Guided tour</h3>
    <p><button type="button" className="button secondary" onClick={resetTour}>Restart the tour</button> <span className="muted">Shows the “New here?” steps on Home again.</span></p>
    <h3>Licences</h3>
    <p>Charts: TradingView Lightweight Charts (Apache 2.0). Icons: Lucide (ISC). The optional hosted chart in Lab › Indicators is loaded from TradingView only when you turn it on. Earlier versions used decorative React Bits effects (MIT + Commons Clause); the simple UI removed them.</p>
    <p className="muted">Version {packageInfo.version}</p>
  </section>;
}

/** @deprecated The shell renders the page h1; kept for panels that still use it. Renders an h2 block. */
export function PageHeading({ title, description, children }: { eyebrow?: string; title: string; description: ReactNode; children?: ReactNode }) {
  return <div className="page-heading"><div><h2>{title}</h2><p>{description}</p></div>{children && <div className="heading-actions">{children}</div>}</div>;
}
/** A labelled number tile (kept for the strategy lab). */
export function Metric({ label, value, detail, icon, term, tone }: { label: string; value: ReactNode; detail?: ReactNode; icon?: ReactNode; term?: string; tone?: "positive" | "negative" }) {
  return <div className="metric"><div className="stat-label">{term ? <Term name={term}>{label}</Term> : label}{icon}</div><strong className={`stat-value${tone ? ` tone-${tone}` : ""}`}>{value}</strong>{detail && <span className="stat-detail">{detail}</span>}</div>;
}
export function Empty({ title, description, action }: { title: string; description: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><Layers3 size={24} aria-hidden="true" /><h3>{title}</h3><p>{description}</p>{action}</div>;
}
export function JsonView({ value, title = "Inspect retained data" }: { value: unknown; title?: string }) {
  return <details className="json-view"><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function Status({ value }: { value: string }) {
  return <span className={`pill ${["completed", "positive", "explanation_completed", "validated"].includes(value) ? "green" : ["failed", "negative", "invalid", "explanation_failed"].includes(value) ? "red" : "neutral"}`}>{human(value)}</span>;
}
