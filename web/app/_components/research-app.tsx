"use client";

// App shell: sidebar, top bar, workspace switcher and the section router. Loads GET /api/workspace,
// owns the `api` helper every panel uses, and runs POST /api/demo for "Load synthetic demo".
// Also exports shared UI pieces (PageHeading, Metric, Empty, JsonView, Status).
import { createContext, useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Activity, ArrowDownToLine, BarChart3,
  CircleHelp, Database, FlaskConical, FolderOpen, Layers3,
  LayoutDashboard, LoaderCircle, Menu, Newspaper, Pause, Play, PlugZap, RefreshCw, ShieldCheck, X,
} from "lucide-react";
import { Api, Scope, Workspace, human } from "./types";
import { ConnectionsPanel, EventsPanel, ImportsPanel, SavedPanel, ComparisonsPanel, TechnicalsPanel } from "./workspace-panels";
import StrategyLab from "./strategy-lab";
import { useReducedMotion } from "./use-reduced-motion";
import PremiumOverview from "./premium-overview";
import SpotlightCard from "./react-bits/SpotlightCard";
import ThemeToggle, { useTheme } from "./theme-toggle";

const EffectsPaused = createContext(false);
const subscribeMobile = (notify: () => void) => {
  const media = window.matchMedia("(max-width: 1100px)");
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const readMobile = () => window.matchMedia("(max-width: 1100px)").matches;
const serverMobile = () => false;

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "events", label: "Event research", icon: Newspaper },
  { id: "technicals", label: "Price indicators", icon: Activity },
  { id: "lab", label: "Strategy lab", icon: FlaskConical },
  { id: "saved", label: "Saved results", icon: FolderOpen },
  { id: "comparisons", label: "Comparisons", icon: BarChart3 },
  { id: "imports", label: "Import evidence", icon: ArrowDownToLine },
  { id: "connections", label: "Connections", icon: PlugZap },
];

export default function ResearchApp() {
  const parameters = useSearchParams();
  const [effectsPaused, setEffectsPaused] = useState(false);
  // Held above the keyed shell so a notice survives switching into the demo workspace.
  const [notice, setNotice] = useState("");
  const scope: Scope = {
    workspace: parameters.get("workspace") === "demo" ? "demo" : "local",
    universe: parameters.get("workspace") === "demo" || parameters.get("universe") === "demo" ? "demo" : "live",
  };
  const section = navigation.find(item => item.id === parameters.get("view"))?.id || "overview";
  return <WorkspaceShell key={`${scope.workspace}:${scope.universe}`} scope={scope} section={section} effectsPaused={effectsPaused} onEffectsPause={() => setEffectsPaused(value => !value)} notice={notice} setNotice={setNotice} />;
}

export type PanelProps = { api: Api; data: Workspace; refresh: () => Promise<void>; href: (view: string) => string };

function WorkspaceShell({ scope, section, effectsPaused, onEffectsPause, notice, setNotice }: { scope: Scope; section: string; effectsPaused: boolean; onEffectsPause: () => void; notice: string; setNotice: (value: string) => void }) {
  const { workspace, universe } = scope;
  const router = useRouter();
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const reducedMotion = useReducedMotion();
  const isMobile = useSyncExternalStore(subscribeMobile, readMobile, serverMobile);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!isMobile || !menu) return;
    const sidebar = sidebarRef.current;
    const trigger = menuButtonRef.current;
    const focusable = () => Array.from(sidebar?.querySelectorAll<HTMLElement>('a[href],button:not(:disabled),select:not(:disabled)') || []);
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setMenu(false); }
      if (event.key === "Tab") {
        const elements = focusable();
        const first = elements[0], last = elements.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); trigger?.focus(); };
  }, [isMobile, menu]);
  const api: Api = useCallback(async <T,>(endpoint: string, body?: unknown): Promise<T> => {
    const query = new URLSearchParams({ workspace, universe });
    const response = await fetch(`/api/research/${endpoint}?${query}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
    });
    const result = await response.json().catch(() => ({ detail: "The research API returned an unreadable response. Check the server log and retry explicitly." }));
    if (!response.ok) {
      const detail = result.detail;
      throw new Error(Array.isArray(detail) ? detail.map((e: { msg: string; loc?: string[] }) => `${e.loc?.slice(1).join(".") || "Request"}: ${e.msg}`).join("; ") : detail || "The request failed");
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
  function href(view: string, workspace = scope.workspace, universe = scope.universe) {
    return `/?${new URLSearchParams({ view, workspace, universe })}`;
  }
  async function loadDemo() {
    setBusy(true); setError("");
    try {
      await api("demo", {});
      if (scope.workspace === "demo") await refresh();
      router.push(href("overview", "demo", "demo"));
      setNotice("Synthetic replay demo loaded. These fixtures do not validate real-market performance.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Demo could not be loaded"); }
    finally { setBusy(false); }
  }
  const props = data ? { api, data, refresh, href } : null;
  return <EffectsPaused value={effectsPaused || reducedMotion}><div className="app-shell" data-motion={effectsPaused || reducedMotion ? "paused" : "playing"}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    {menu && <button className="nav-scrim" onClick={() => setMenu(false)} aria-label="Close navigation" />}
    <aside ref={sidebarRef} id="workspace-navigation" inert={isMobile && !menu} className={`sidebar ${menu ? "is-open" : ""}`}>
      <Link className="brand" href={href("overview")} aria-label="Market Events home"><span className="brand-mark"><Activity size={23} /></span><span>market<span className="brand-light">events</span><small>RESEARCH WORKSPACE</small></span></Link>
      <div className="sidebar-label">WORKSPACE</div>
      <label className="workspace-selector"><Database size={16} /><span className="sr-only">Workspace</span><select value={scope.workspace} onChange={e => router.push(href(section, e.target.value as Scope["workspace"], e.target.value === "demo" ? "demo" : "live"))}><option value="local">Your workspace</option><option value="demo">Synthetic demo</option></select></label>
      {scope.workspace === "local" && <label className="universe-selector">Company universe<select aria-label="Company universe" value={scope.universe} onChange={e => router.push(href(section, "local", e.target.value as Scope["universe"]))}><option value="live">Provider companies</option><option value="demo">Demo / local companies</option></select></label>}
      <nav aria-label="Main navigation">{navigation.map((item, index) => <div key={item.id}>{index === 6 && <div className="sidebar-label data-label">DATA & SETUP</div>}<Link href={href(item.id)} className={`nav-item ${section === item.id ? "active" : ""}`} aria-current={section === item.id ? "page" : undefined} onClick={() => setMenu(false)}><item.icon size={18} /><span>{item.label}</span>{item.id === "saved" && Boolean(data?.runs.length) && <span className="nav-count">{data?.runs.length}</span>}{item.id === "lab" && <span className="nav-tag">2020</span>}</Link></div>)}</nav>
      <div className="sidebar-bottom"><div className="research-note"><ShieldCheck size={18} /><div><strong>Evidence comes first</strong><p>Every decision keeps its sources, timing and audit trail.</p></div></div><div className="sidebar-footer"><span className="avatar">AR</span><div><strong>Local researcher</strong><small>Private workspace</small></div><CircleHelp size={17} /></div></div>
    </aside>
    <div className="main-wrap"><header className="topbar">
      <Link className="desktop-brand" href={href("overview")} aria-label="Market Events home"><span className="brand-mark"><Activity size={18} aria-hidden="true" /></span><span>market<span className="brand-light">events</span></span></Link>
      <div className="breadcrumb"><button ref={menuButtonRef} className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={menu} aria-controls="workspace-navigation" onClick={() => setMenu(true)}><Menu size={20} /></button><strong>{navigation.find(item => item.id === section)?.label}</strong></div>
      <nav className="desktop-nav" aria-label="Workspace sections">{navigation.map(item => <Link key={item.id} aria-label={item.label} href={href(item.id)} aria-current={section === item.id ? "page" : undefined}>{({overview:"Overview",events:"Research",technicals:"Indicators",lab:"Strategies",saved:"Results",comparisons:"Compare",imports:"Import",connections:"Setup"} as Record<string,string>)[item.id]}</Link>)}</nav>
      <div className="topbar-right"><ThemeToggle /><button className="motion-toggle" aria-label={effectsPaused ? "Enable visual effects" : "Pause visual effects"} aria-pressed={effectsPaused || reducedMotion} disabled={reducedMotion} title={reducedMotion ? "Reduced motion follows your system preference" : "Toggle ambient visual effects"} onClick={onEffectsPause}>{effectsPaused || reducedMotion ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}<span>{effectsPaused || reducedMotion ? "Effects paused" : "Effects"}</span></button>
        <label className="header-workspace"><Database size={12} aria-hidden="true" /><span className="sr-only">Active workspace</span><select disabled={busy} value={`${scope.workspace}:${scope.universe}`} onChange={event => { const [workspace,universe] = event.target.value.split(":") as [Scope["workspace"], Scope["universe"]]; router.push(href(section,workspace,universe)); }}><option value="local:live">My workspace</option><option value="local:demo">Local / demo universe</option><option value="demo:demo">Synthetic demo</option></select></label>
        <span className="connection-state" title={data ? "Local research API connected" : "Connecting to local API"}><i className={data ? "connected" : ""} /><span className="sr-only">{data ? "Local API connected" : "Connecting to API"}</span></span><span className="header-monogram" aria-hidden="true">me</span>
      </div></header>
      <main id="main-content" className="main-content">
        {error && <div className="alert error" role="alert"><strong>Could not complete the request</strong><p>{error}</p><button className="text-button" onClick={() => refresh().catch(reason => setError(reason.message))}>Retry connection</button></div>}
        {notice && <div className="alert" role="status">{notice}<button className="icon-button" aria-label="Dismiss notice" onClick={() => setNotice("")}><X size={16} /></button></div>}
        {!data && !error && <div className="loading-state"><LoaderCircle className="spin" size={25} /><p>Opening your research workspace…</p></div>}
        {data && props && <div key={section} className="page-enter">
          {section === "overview" && <PremiumOverview api={api} data={data} href={href} onDemo={loadDemo} busy={busy} effectsPaused={effectsPaused || reducedMotion} />}
          {section === "events" && <EventsPanel {...props} />}
          {section === "saved" && <SavedPanel {...props} />}
          {section === "imports" && <ImportsPanel {...props} />}
          {section === "connections" && <ConnectionsPanel {...props} />}
          {section === "comparisons" && <ComparisonsPanel {...props} />}
          {section === "technicals" && <TechnicalsPanel {...props} />}
          {section === "lab" && <StrategyLab {...props} />}
        </div>}
        <footer className="main-footer"><span><ShieldCheck size={13} /> Research, with a record.</span><span>Historical strategy window ends 31 Dec 2020 · No order execution</span><button className="text-button" onClick={() => { setBusy(true); refresh().catch(reason => setError(reason.message)).finally(() => setBusy(false)); }} disabled={busy}><RefreshCw size={13} />Refresh workspace</button></footer>
      </main>
    </div>
  </div></EffectsPaused>;
}

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{children && <div className="heading-actions">{children}</div>}</div>;
}
export function Metric({ label, value, detail, icon }: { label: string; value: string; detail?: string; icon?: React.ReactNode }) {
  const paused = useContext(EffectsPaused);
  const theme = useTheme();
  return <SpotlightCard className="metric" theme={theme} paused={paused} spotlightColor="#b9ff66" intensity={0.12} borderGlow={0.7} spotlightSize={280} proximity={40} flare={false}><div className="metric-label">{label}{icon}</div><strong>{value}</strong>{detail && <span>{detail}</span>}</SpotlightCard>;
}
export function Empty({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Layers3 size={25} /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
export function JsonView({ value, title = "Inspect retained data" }: { value: unknown; title?: string }) {
  return <details className="json-view"><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function Status({ value }: { value: string }) {
  return <span className={`pill ${["completed", "positive", "explanation_completed", "validated"].includes(value) ? "green" : ["failed", "negative", "invalid", "explanation_failed"].includes(value) ? "red" : "neutral"}`}>{human(value)}</span>;
}
