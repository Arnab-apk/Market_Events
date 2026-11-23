"use client";

// App shell: sidebar, top bar, the single workspace switcher, the always-visible synthetic/replay ribbon
// and the section router. Loads GET /api/workspace, owns the `api` helper every panel uses, and runs
// POST /api/demo for "Load synthetic demo". Also exports shared UI pieces (PageHeading, Metric, Empty, JsonView, Status).
import { useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Activity, ArrowDownToLine, BarChart3, Database, FlaskConical, FolderOpen, Layers3,
  LayoutDashboard, LoaderCircle, Menu, Newspaper, Pause, Play, PlugZap, RefreshCw, ShieldCheck, X,
} from "lucide-react";
import { Api, Scope, Workspace, human } from "./types";
import { ConnectionsPanel, EventsPanel, ImportsPanel, SavedPanel, ComparisonsPanel, TechnicalsPanel } from "./workspace-panels";
import StrategyLab from "./strategy-lab";
import { useReducedMotion } from "./use-reduced-motion";
import PremiumOverview from "./premium-overview";
import SpotlightCard from "./react-bits/SpotlightCard";
import AnimatedContent from "./react-bits/AnimatedContent";
import ThemeToggle, { useTheme } from "./theme-toggle";
import { EffectsPaused, GlossaryButton, Term, friendlyError } from "./ui";
import { TourBar } from "./demo-tour";

const subscribeMobile = (notify: () => void) => {
  const media = window.matchMedia("(max-width: 1100px)");
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const readMobile = () => window.matchMedia("(max-width: 1100px)").matches;
const serverMobile = () => false;

const navigation = [
  { id: "overview", label: "Overview", short: "Overview", icon: LayoutDashboard },
  { id: "events", label: "Event research", short: "Research", icon: Newspaper },
  { id: "technicals", label: "Price indicators", short: "Indicators", icon: Activity },
  { id: "lab", label: "Strategy lab", short: "Strategy lab", icon: FlaskConical },
  { id: "saved", label: "Saved results", short: "Results", icon: FolderOpen },
  { id: "comparisons", label: "Comparisons", short: "Compare", icon: BarChart3 },
  { id: "imports", label: "Import evidence", short: "Import", icon: ArrowDownToLine },
  { id: "connections", label: "Connections", short: "Connections", icon: PlugZap },
];
// One switcher, three plainly named options (UX_AUDIT §3.5).
const WORKSPACES = [
  { value: "demo:demo", label: "Synthetic demo (offline)" },
  { value: "local:live", label: "My data – real companies" },
  { value: "local:demo", label: "My data – demo companies" },
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

export type Href = (view: string, extra?: Record<string, string>) => string;
export type PanelProps = { api: Api; data: Workspace; refresh: () => Promise<void>; href: Href };

function WorkspaceShell({ scope, section, effectsPaused, onEffectsPause, notice, setNotice }: { scope: Scope; section: string; effectsPaused: boolean; onEffectsPause: () => void; notice: string; setNotice: (value: string) => void }) {
  const { workspace, universe } = scope;
  const router = useRouter();
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const reducedMotion = useReducedMotion();
  const motionOff = effectsPaused || reducedMotion;
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
  const link = (view: string, target: Scope, extra?: Record<string, string>) => `/?${new URLSearchParams({ view, workspace: target.workspace, universe: target.universe, ...extra })}`;
  const href = (view: string, extra?: Record<string, string>) => link(view, scope, extra);
  const demoHref = (view: string, extra?: Record<string, string>) => link(view, { workspace: "demo", universe: "demo" }, extra);
  async function loadDemo() {
    setBusy(true); setError("");
    try {
      await api("demo", {});
      if (scope.workspace === "demo") await refresh();
      router.push(demoHref("overview"));
      setNotice("Synthetic replay demo loaded. These fixtures do not validate real-market performance.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Demo could not be loaded"); }
    finally { setBusy(false); }
  }
  const props = data ? { api, data, refresh, href } : null;
  const demo = scope.workspace === "demo";
  const unreachable = /Can't reach the research engine/.test(error);
  return <EffectsPaused value={motionOff}><div className="app-shell" data-motion={motionOff ? "paused" : "playing"}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    {menu && <button className="nav-scrim" onClick={() => setMenu(false)} aria-label="Close navigation" />}
    <aside ref={sidebarRef} id="workspace-navigation" inert={isMobile && !menu} className={`sidebar ${menu ? "is-open" : ""}`}>
      <Link className="brand" href={href("overview")}><span className="brand-mark"><Activity size={23} aria-hidden="true" /></span><span>market<span className="brand-light">events</span><span className="sr-only"> home</span><small aria-hidden="true">RESEARCH WORKSPACE</small></span></Link>
      <nav aria-label="Main navigation">{navigation.map((item, index) => <div key={item.id}>{index === 6 && <div className="sidebar-label data-label">DATA & SETUP</div>}<Link href={href(item.id)} className={`nav-item ${section === item.id ? "active" : ""}`} aria-current={section === item.id ? "page" : undefined} onClick={() => setMenu(false)}><item.icon size={18} aria-hidden="true" /><span>{item.label}</span>{item.id === "saved" && Boolean(data?.runs.length) && <span className="nav-count">{data?.runs.length}</span>}{item.id === "lab" && <span className="nav-tag">2020</span>}</Link></div>)}</nav>
      <div className="sidebar-bottom"><div className="research-note"><ShieldCheck size={18} aria-hidden="true" /><div><strong>Evidence comes first</strong><p>Every decision keeps its sources, timing and audit trail.</p></div></div><div className="sidebar-footer"><GlossaryButton className="button secondary glossary-sidebar" label="Glossary of terms" /></div></div>
    </aside>
    <div className="main-wrap"><header className="topbar">
      <Link className="desktop-brand" href={href("overview")}><span className="brand-mark"><Activity size={18} aria-hidden="true" /></span><span>market<span className="brand-light">events</span><span className="sr-only"> home</span></span></Link>
      <div className="breadcrumb"><button ref={menuButtonRef} className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={menu} aria-controls="workspace-navigation" onClick={() => setMenu(true)}><Menu size={20} /></button><strong>{navigation.find(item => item.id === section)?.label}</strong></div>
      <nav className="desktop-nav" aria-label="Workspace sections">{navigation.map(item => <Link key={item.id} title={item.label} href={href(item.id)} aria-current={section === item.id ? "page" : undefined}>{item.short}</Link>)}</nav>
      <div className="topbar-right"><ThemeToggle />{!reducedMotion && <button className="motion-toggle" aria-pressed={effectsPaused} title="Pause or resume the animated background and number count-ups" onClick={onEffectsPause}>{effectsPaused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}<span>{effectsPaused ? "Effects paused" : "Effects on"}</span></button>}
        <GlossaryButton className="icon-button glossary-top" label="Glossary" />
        <label className="header-workspace"><Database size={12} aria-hidden="true" /><span className="sr-only">Workspace</span><select disabled={busy} value={`${scope.workspace}:${scope.universe}`} onChange={event => { const [next, nextUniverse] = event.target.value.split(":") as [Scope["workspace"], Scope["universe"]]; router.push(link(section, { workspace: next, universe: nextUniverse })); }}>{WORKSPACES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <span className="connection-state" role="status"><i className={data ? "connected" : error ? "down" : ""} aria-hidden="true" /><span>{data ? "API connected" : error ? "API unreachable" : "Connecting…"}</span></span>
      </div></header>
      {demo && <div className="demo-ribbon" role="note"><ShieldCheck size={13} aria-hidden="true" /><strong>Synthetic demo · recorded replay</strong><span>Invented articles and prices with pre-recorded model answers. Offline; nothing here is real-market evidence.</span><Term name="Synthetic demo">What does this mean?</Term></div>}
      <main id="main-content" className="main-content">
        {error && <div className="alert error" role="alert"><strong>{unreachable ? "Can't reach the research engine." : "Could not complete the request"}</strong><p>{unreachable ? "The local Python service on port 8000 isn't responding. Start the dev stack with npm.cmd run dev, then retry." : error}</p><button className="text-button" onClick={() => refresh().catch(reason => setError(reason.message))}>Retry</button></div>}
        {notice && <div className="alert" role="status">{notice}<button className="icon-button" aria-label="Dismiss notice" onClick={() => setNotice("")}><X size={16} /></button></div>}
        {!data && !error && <div className="loading-state"><LoaderCircle className="spin" size={25} /><p>Opening your research workspace…</p></div>}
        {data && props && section !== "overview" && <TourBar data={data} links={{ href, demoHref }} onDemo={loadDemo} busy={busy} />}
        {data && props && <AnimatedContent key={section} trigger="mount" distance={10} duration={0.28} ease="power2.out" initialOpacity={0}>
          {section === "overview" && <PremiumOverview api={api} data={data} href={href} demoHref={demoHref} onDemo={loadDemo} busy={busy} />}
          {section === "events" && <EventsPanel {...props} />}
          {section === "saved" && <SavedPanel {...props} />}
          {section === "imports" && <ImportsPanel {...props} />}
          {section === "connections" && <ConnectionsPanel {...props} />}
          {section === "comparisons" && <ComparisonsPanel {...props} />}
          {section === "technicals" && <TechnicalsPanel {...props} />}
          {section === "lab" && <StrategyLab {...props} />}
        </AnimatedContent>}
        <footer className="main-footer"><span><ShieldCheck size={13} aria-hidden="true" /> Research, with a record.</span><span>Historical strategy window ends 31 Dec 2020 · No order execution</span><button className="text-button" onClick={() => { setBusy(true); refresh().catch(reason => setError(reason.message)).finally(() => setBusy(false)); }} disabled={busy}><RefreshCw size={13} aria-hidden="true" />Refresh workspace</button></footer>
      </main>
    </div>
  </div></EffectsPaused>;
}

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: ReactNode; children?: ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{children && <div className="heading-actions">{children}</div>}</div>;
}
export function Metric({ label, value, detail, icon, term, tone }: { label: string; value: ReactNode; detail?: ReactNode; icon?: ReactNode; term?: string; tone?: "positive" | "negative" }) {
  const paused = useContext(EffectsPaused);
  const theme = useTheme();
  return <SpotlightCard className="metric" theme={theme} paused={paused} spotlightColor="#b9ff66" intensity={0.12} borderGlow={0.7} spotlightSize={280} proximity={40} flare={false}><div className="metric-label">{term ? <Term name={term}>{label}</Term> : label}{icon}</div><strong className={tone ? `tone-${tone}` : undefined}>{value}</strong>{detail && <span>{detail}</span>}</SpotlightCard>;
}
export function Empty({ title, description, action }: { title: string; description: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Layers3 size={25} aria-hidden="true" /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
export function JsonView({ value, title = "Inspect retained data" }: { value: unknown; title?: string }) {
  return <details className="json-view"><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function Status({ value }: { value: string }) {
  return <span className={`pill ${["completed", "positive", "explanation_completed", "validated"].includes(value) ? "green" : ["failed", "negative", "invalid", "explanation_failed"].includes(value) ? "red" : "neutral"}`}>{human(value)}</span>;
}
