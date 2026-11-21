"use client";

// Overview section: hero actions, research guide, workspace counts, saved price chart (POST /api/technicals),
// evidence-coverage ring, company table and recent sources. Uses Workspace data from GET /api/workspace.
import Link from "next/link";
import ResearchGuide from "./research-guide";
import { useId, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, ChartNoAxesCombined, Check, ChevronDown, CircleHelp, Database, FileText, Fingerprint, Layers3, LoaderCircle, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Api, Bar, Workspace, format, human, sourceTitle } from "./types";

type TechnicalData = { bars: Bar[]; snapshot: { history_bars: number } };
const dateLabel = (value: string) => {
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: dateOnly ? "UTC" : "Asia/Kolkata" })
    .format(new Date(dateOnly ? `${value}T00:00:00Z` : value));
};

export default function PremiumOverview({ api, data, href, onDemo, busy, effectsPaused }: {
  api: Api; data: Workspace; href: (view: string) => string; onDemo: () => void; busy: boolean; effectsPaused: boolean;
}) {
  const [companyId, setCompanyId] = useState(data.companies[0]?.instrument_id || "");
  const [series, setSeries] = useState<{ companyId: string; result: TechnicalData } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [range, setRange] = useState(0);
  const [query, setQuery] = useState("");
  const requestRef = useRef(0);
  const company = data.companies.find(row => row.instrument_id === companyId);
  const bars = series?.companyId === companyId ? series.result.bars : [];
  const shown = range ? bars.slice(-range) : bars;
  const latest = bars.at(-1)?.close ?? company?.latest_close;
  const previous = bars.at(-2)?.close;
  const change = latest != null && previous != null ? (latest / previous - 1) * 100 : null;
  const assessments = data.runs.filter(run => run.assessment);
  const coverage = assessments.length ? assessments.reduce((sum, run) => sum + run.assessment!.coverage, 0) / assessments.length : null;
  const completed = data.runs.filter(run => run.status === "completed").length;
  const needsReview = data.runs.filter(run => run.status !== "completed").length;
  const pre2021 = data.companies.reduce((sum, row) => sum + row.research_bars, 0);
  const maxBars = Math.max(1, ...data.companies.map(row => row.bars));
  const emptyLocal = data.workspace !== "demo" && !data.articles.length && !data.observations_count;
  const filtered = data.companies.filter(row => `${row.name} ${row.trading_symbol || ""}`.toLowerCase().includes(query.toLowerCase()));

  async function loadChart(target = companyId) {
    const request = ++requestRef.current;
    setCompanyId(target); setLoading(true); setError(""); setSeries(null);
    try {
      const result = await api<TechnicalData>("technicals", { company_id: target, decision_time: new Date().toISOString() });
      if (request === requestRef.current) setSeries({ companyId: target, result });
    } catch (reason) {
      if (request === requestRef.current) setError(reason instanceof Error ? reason.message : "Local history could not be opened.");
    } finally { if (request === requestRef.current) setLoading(false); }
  }

  return <div className="premium-overview">
    <div className="premium-heading"><div><div className="premium-overline"><span />YOUR RESEARCH, CONNECTED</div><h1>Research with evidence.<span> Understand what moves markets.</span></h1><p>Investigate dated financial news, examine the market context, and keep every source behind your conclusion.</p></div><div className="premium-heading-actions"><button className={`button ${emptyLocal ? "primary" : "secondary"}`} onClick={onDemo} disabled={busy} title="Loads bundled synthetic articles and prices with recorded model outputs. Offline: no keys or network calls.">{busy ? <LoaderCircle className="spin" size={14} /> : <BookOpen size={14} />}{busy ? "Loading synthetic demo…" : "Load synthetic demo (replay)"}</button><Link className={`button ${emptyLocal ? "secondary" : "primary"}`} href={href("imports")}><ArrowDownToLine size={14} />Import evidence</Link></div></div>

    <ResearchGuide data={data} href={href} paused={effectsPaused} />
    <div className="premium-summary-grid">
      <section className="premium-summary-panel" aria-label="Workspace summary">
        <div className="premium-primary-stat"><div className="premium-stat-label"><Database size={14} />Research workspace<span>{data.workspace === "demo" ? "Synthetic replay" : "Local evidence"}</span></div><div className="premium-stat-bottom"><div><span className="premium-stat-caption">Original source articles</span><strong>{format(data.articles.length, 0)}<small>articles</small></strong></div><span className="premium-soft-chip"><ShieldCheck size={12} />Source retained</span></div></div>
        <div className="premium-small-stat"><div className="premium-stat-label"><i className="premium-marker lime" />Saved research<ArrowUpRight size={13} /></div><strong>{format(data.runs.length, 0)}<small>runs</small></strong><span><Check size={11} />{completed} completed decisions</span></div>
        <div className="premium-small-stat"><div className="premium-stat-label"><i className="premium-marker gold" />Market evidence<ArrowUpRight size={13} /></div><strong>{format(data.observations_count, 0)}<small>records</small></strong><span>{pre2021} equity bars before 2021</span></div>
      </section>
      <section className="premium-companion"><div className="premium-companion-top"><span className="premium-sparkle"><Sparkles size={17} /></span><span>Built for a better question.</span><span className="premium-mini-label">RESEARCH LAB</span></div><p>Turn a market hypothesis into an experiment you can inspect.</p><Link href={href("lab")}>Open strategy lab<ArrowUpRight size={14} /></Link><div className="premium-companion-orb" aria-hidden="true" /></section>
    </div>

    <div className="premium-ticker" aria-label="Saved company snapshots">{data.companies.map((row, index) => <button key={row.instrument_id} disabled={loading} onClick={() => void loadChart(row.instrument_id)} title={`Open saved price history for ${row.name}`}><span className={`premium-token token-${index % 5}`}>{(row.trading_symbol || row.name).slice(0, 1)}</span><strong>{row.trading_symbol || row.name}</strong><span>{row.latest_close == null ? "No prices" : `₹${format(row.latest_close)}`}</span><small>{row.bars} sessions</small></button>)}<span className="premium-ticker-note">SAVED DATA / NOT LIVE</span></div>

    <div className="premium-analysis-grid">
      <section className="premium-chart-panel">
        <div className="premium-panel-header"><div><ChartNoAxesCombined size={15} /><h2>Saved price history</h2><span className="premium-mini-label">LOCAL PRICES</span></div><Link href={href("technicals")} aria-label="Open price indicators"><ArrowUpRight size={16} /></Link></div>
        <div className="premium-chart-toolbar"><label className="premium-instrument-select"><span className="sr-only">Chart company</span><span className="premium-token">{(company?.trading_symbol || company?.name || "M").slice(0, 1)}</span><select value={companyId} disabled={loading} onChange={event => { ++requestRef.current; setCompanyId(event.target.value); setSeries(null); setError(""); }}>{data.companies.map(row => <option key={row.instrument_id} value={row.instrument_id}>{row.name}</option>)}</select><ChevronDown size={12} /></label><div className="premium-range-controls" role="group" aria-label="Visible saved sessions">{[[0, "All"], [10, "10 sessions"], [30, "30 sessions"]].map(([value, label]) => <button key={value} aria-pressed={range === value} onClick={() => setRange(Number(value))}>{label}</button>)}</div></div>
        <div className="premium-price-line"><strong>{latest == null ? "—" : `₹${format(latest)}`}</strong>{change !== null && <span className={change >= 0 ? "premium-positive" : "premium-negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%<small>last observed session</small></span>}<button className="premium-chart-load" disabled={loading || !companyId} onClick={() => void loadChart()}>{loading ? <LoaderCircle size={12} className="spin" /> : <Activity size={12} />}{loading ? "Opening…" : bars.length ? "Refresh local chart" : "Load local chart"}</button></div>
        {error && <div className="premium-inline-error" role="alert">{error}</div>}
        {shown.length >= 2 ? <CloseArea bars={shown} name={company?.name || "Selected company"} /> : <div className="premium-chart-empty"><div className="premium-empty-grid" aria-hidden="true" /><div className="premium-empty-content"><span><ChartNoAxesCombined size={25} /></span><h3>{loading ? "Opening your saved observations" : series ? "More history is needed" : "A clearer view starts with your data"}</h3><p>{series ? "At least two eligible saved sessions are needed for a price series." : "Open your saved daily prices to explore the market, one observed session at a time."}</p><button disabled={loading || !companyId} onClick={() => void loadChart()}>{loading ? "Loading local history…" : "Open local history"}<ArrowRight size={13} /></button></div></div>}
        <div className="premium-chart-footer"><span><i />Saved close price</span><span>Observed sessions only. No provider or model calls.</span></div>
        {shown.length > 0 && <details className="premium-price-data"><summary>Inspect {shown.length} original price observations</summary><div className="table-scroll"><table><thead><tr><th>Session</th><th>Open</th><th>High</th><th>Low</th><th>Close</th></tr></thead><tbody>{shown.map(row => <tr key={row.time}><th scope="row">{row.time}</th>{[row.open,row.high,row.low,row.close].map((value,index) => <td key={index}>{format(value)}</td>)}</tr>)}</tbody></table></div></details>}
      </section>

      <aside className="premium-insight-panel" aria-label="Saved research overview"><div className="premium-panel-header"><div><Layers3 size={15} /><h2>Evidence coverage</h2></div><span title="Mean coverage of saved assessed cases; not predictive confidence"><CircleHelp size={14} /></span></div><CoverageRing value={coverage} /><div className="premium-coverage-caption">{coverage === null ? "Save an assessed case to build your overview." : "Mean coverage across your assessed cases."}<span>Evidence completeness, not predictive confidence.</span></div><div className="premium-coverage-legend"><div><span><i className="premium-marker lime" />Assessed cases</span><strong>{assessments.length.toString().padStart(2,"0")}</strong></div><div><span><i className="premium-marker muted" />Needs review</span><strong>{needsReview.toString().padStart(2,"0")}</strong></div></div><Link className="premium-view-evidence" href={href("saved")}>Explore saved evidence<ArrowUpRight size={14} /></Link></aside>
    </div>

    <section className="premium-watchlist"><div className="premium-watchlist-header"><div><h2>Companies in your workspace<span>{data.companies.length}</span></h2><p>A closer look at the companies in your workspace.</p></div><label className="premium-search"><Search size={14} /><span className="sr-only">Search watchlist</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a company…" /></label><Link href={href("technicals")}>All indicators<ArrowUpRight size={14} /></Link></div><div className="table-scroll"><table><thead><tr><th>Company / asset</th><th>Latest saved close</th><th>Stored sessions</th><th>History availability</th><th>Last observation</th><th>Research</th></tr></thead><tbody>{filtered.map((row,index) => <tr key={row.instrument_id}><td><button className="premium-company-button" disabled={loading} onClick={() => void loadChart(row.instrument_id)}><span className={`premium-token token-${index % 5}`}>{(row.trading_symbol || row.name).slice(0,1)}</span><span><strong>{row.name}</strong><small>{row.trading_symbol || row.instrument_id}</small></span></button></td><td className="premium-table-number">{row.latest_close == null ? "—" : `₹${format(row.latest_close)}`}</td><td className="premium-table-number">{format(row.bars,0)}</td><td><div className="premium-history-bar"><span style={{width:`${row.bars / maxBars * 100}%`}} /></div><small className="premium-history-label">{row.bars ? `${row.research_bars} pre-2021 bars` : "Awaiting imported history"}</small></td><td className="premium-table-date">{row.end ? dateLabel(row.end) : "Not available"}</td><td><Link className="premium-row-action" href={href("events")}>Explore<ArrowUpRight size={12} /></Link></td></tr>)}</tbody></table>{!filtered.length && <p className="premium-no-results">No companies match “{query}”.</p>}</div></section>

    <div className="premium-bottom-grid"><section className="premium-activity"><div className="premium-panel-header"><div><FileText size={15} /><h2>From your research desk</h2></div><Link href={href("events")}>All sources<ArrowUpRight size={13} /></Link></div>{data.articles.length ? data.articles.slice(-2).reverse().map(row => <Link className="premium-source" href={href("events")} key={row.article_id}><span><FileText size={16} /></span><div><strong>{sourceTitle(row.text).title}</strong><small>{sourceTitle(row.text).synthetic && <>Synthetic fixture<i /></>}{dateLabel(row.published_at)}<i />{row.article_id}</small></div><ArrowUpRight size={14} /></Link>) : <div className="premium-source-empty"><p>Your next insight starts with an original source.</p><Link href={href("imports")}>Bring your first article<ArrowRight size={13} /></Link></div>}</section><section className="premium-provenance"><Fingerprint size={25} /><div><h3>Good research leaves a trail.</h3><p>{data.workspace === "demo" ? "You’re viewing synthetic fixtures and recorded replay. Explore the workflow; real-market validation is separate." : "Sources, timestamps, evidence and every saved decision stay together in your local workspace."}</p><span><ShieldCheck size={11} />{human(data.workspace === "demo" ? "synthetic_replay" : "local_research")}</span></div></section></div>
  </div>;
}

function CoverageRing({ value }: { value: number | null }) {
  const id = useId();
  const bounded = Math.max(0,Math.min(1,value ?? 0));
  return <div className="premium-ring" role="img" aria-label={value === null ? "No assessed cases available" : `${Math.round(bounded*100)} percent mean evidence coverage`}><svg viewBox="0 0 220 220" aria-hidden="true"><defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="var(--chart-up)" /><stop offset="45%" stopColor="var(--chart-up)" /><stop offset="100%" stopColor="var(--chart-gold)" /></linearGradient></defs><circle cx="110" cy="110" r="82" fill="none" stroke="var(--mode-border)" strokeWidth="25" /><circle cx="110" cy="110" r="82" fill="none" stroke={`url(#${id})`} strokeWidth="25" strokeDasharray={`${bounded*515.22} 515.22`} transform="rotate(-90 110 110)" /><circle cx="110" cy="110" r="82" fill="none" stroke="var(--mode-panel)" strokeWidth="27" strokeDasharray="1 5" transform="rotate(-90 110 110)" /></svg><div><strong>{value === null ? "—" : Math.round(bounded*100)}{value !== null && <small>%</small>}</strong><span>Evidence coverage</span></div><span className="premium-ring-tag"><span />SAVED CASES</span></div>;
}

function CloseArea({ bars, name }: { bars: Bar[]; name: string }) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const width=760, height=235, top=15, bottom=218;
  const closes=bars.map(row=>row.close), low=Math.min(...closes), high=Math.max(...closes);
  const spread=high-low || Math.max(high*.02,1), min=low-spread*.12, max=high+spread*.12;
  const x=(index:number)=>index/(bars.length-1)*width;
  const y=(value:number)=>bottom-(value-min)/(max-min)*(bottom-top);
  const points=bars.map((row,index)=>`${x(index)},${y(row.close)}`).join(" ");
  const selected=Math.max(0,Math.min(bars.length-1,active ?? bars.length-1));
  return <div className="premium-price-visual"><div className="premium-chart-readout"><span>{dateLabel(bars[selected].time)}</span><strong>₹{format(bars[selected].close)}</strong><small>Close</small></div><div className="premium-plot"><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" tabIndex={0} aria-label={`${name} saved close-price chart, ${bars.length} sessions. ${bars[selected].time}: ${bars[selected].close}. Use left and right arrow keys to inspect.`} onKeyDown={event=>{if(event.key==="ArrowLeft"||event.key==="ArrowRight"){event.preventDefault();setActive(Math.max(0,Math.min(bars.length-1,selected+(event.key==="ArrowLeft"?-1:1))));}}} onPointerMove={event=>{const rect=event.currentTarget.getBoundingClientRect();setActive(Math.round((event.clientX-rect.left)/rect.width*(bars.length-1)));}} onPointerLeave={()=>setActive(null)}><defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-gold)" stopOpacity="0.25" /><stop offset="100%" stopColor="var(--chart-gold)" stopOpacity="0" /></linearGradient></defs>{[0,.25,.5,.75,1].map(value=><line key={value} x1="0" x2={width} y1={top+value*(bottom-top)} y2={top+value*(bottom-top)} stroke="var(--chart-grid)" strokeOpacity=".35" strokeDasharray="2 5" />)}{[0,.2,.4,.6,.8,1].map(value=><line key={value} x1={value*width} x2={value*width} y1={top} y2={bottom} stroke="var(--chart-grid)" strokeOpacity=".2" strokeDasharray="2 5" />)}<polygon points={`0,${bottom} ${points} ${width},${bottom}`} fill={`url(#${id})`} /><polyline points={points} fill="none" stroke="var(--chart-gold)" strokeWidth="1.7" vectorEffect="non-scaling-stroke" strokeLinejoin="round" /><line x1={x(selected)} x2={x(selected)} y1={top} y2={bottom} stroke="var(--chart-text)" strokeOpacity=".55" strokeDasharray="3 5" /><circle cx={x(selected)} cy={y(bars[selected].close)} r="3.2" fill="var(--chart-up)" stroke="var(--chart-bg)" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg><div className="premium-price-axis" aria-hidden="true">{[max,max-(max-min)*.25,(max+min)/2,min+(max-min)*.25,min].map((value,index)=><span style={{top:`${(top+index/4*(bottom-top))/height*100}%`}} key={index}>{format(value,1)}</span>)}</div></div><div className="premium-date-axis"><span>{dateLabel(bars[0].time)}</span><span>{dateLabel(bars[Math.floor(bars.length/2)].time)}</span><span>{dateLabel(bars.at(-1)!.time)}</span></div></div>;
}
