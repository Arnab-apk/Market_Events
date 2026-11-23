"use client";

// Section panels: Event research (POST /api/analyse), Saved results (GET /api/case/<id>, POST /api/outcomes,
// /api/explain/<id>), Import evidence (POST /api/import), Price indicators (POST /api/technicals),
// Connections (POST /api/sync/<kind>, /api/analyse-news) and Comparisons (GET /api/comparisons).
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { WorkspaceSummary } from "./workspace-summary";
import {
  ArrowDownToLine, CheckCircle2, Database, FileJson, FlaskConical,
  LoaderCircle, Play, PlugZap, RefreshCw, ShieldCheck, Star,
} from "lucide-react";
import { Empty, JsonView, PageHeading, PanelProps, Status } from "./research-app";
import { PriceChart } from "./research-charts";
import { INTROS } from "./glossary";
import { Count, CutoffField, Term, Time, formatIst } from "./ui";
import { markTourStep } from "./demo-tour";
import { Article, Bar, Outcome, POLICY_ORDER, Run, Workspace, downloadJson, format, human, isSyntheticSource, policyLabel, signedPercent, signedScore, sourceTitle, wholePercent } from "./types";

const POLICIES = POLICY_ORDER;
const FEATURE_LABELS: Record<string, string> = {
  equity_return: "Equity return (reaction day)", benchmark_return: "Sector benchmark return", excess_return: "Equity excess return",
  relative_volume: "Relative volume (context only)", commodity_return: "Commodity return",
};
const tierOf = (model: string) => /slm|small/i.test(model) ? "small" : /llm|large/i.test(model) ? "large" : "other";
const companyName = (data: Workspace, id: string | null | undefined) => data.companies.find(row => row.instrument_id === id)?.name ?? id ?? "Unknown company";

function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function execute(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The request could not be completed"); }
    finally { setBusy(false); }
  }
  return { busy, error, execute };
}
function ErrorMessage({ message }: { message: string }) {
  return message ? <div className="alert error" role="alert">{message}</div> : null;
}
function Submit({ busy, children, disabled }: { busy: boolean; children: React.ReactNode; disabled?: boolean }) {
  return <button type="submit" className="button primary" disabled={busy || disabled}>{busy ? <LoaderCircle className="spin" size={16} /> : <Play size={15} />}{busy ? "Working…" : children}</button>;
}
/** Group exact-duplicate article texts so the inbox doesn't repeat the same headline. */
function groupArticles(articles: Article[]) {
  const groups = new Map<string, Article[]>();
  for (const row of articles) {
    const key = row.text.trim();
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return [...groups.values()];
}

// ============================== Event research ==============================
export function EventsPanel({ api, data, refresh, href }: PanelProps) {
  const parameters = useSearchParams();
  const story = useMemo(() => data.demo_story ?? [], [data.demo_story]);
  const featured = story.map(item => data.articles.find(row => row.article_id === item.article_id)).filter((row): row is Article => Boolean(row));
  const companyFilter = parameters.get("company");
  const filterName = companyFilter ? companyName(data, companyFilter) : null;
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [articleId, setArticleId] = useState(parameters.get("article") || featured[0]?.article_id || data.articles[0]?.article_id || "");
  const demoCutoff = story.find(item => item.article_id === articleId)?.suggested_decision_times?.[0] ?? story[0]?.suggested_decision_times?.[0] ?? "2026-01-12T12:00:00Z";
  const [cutoff, setCutoff] = useState(parameters.get("cutoff") || (data.workspace === "demo" ? demoCutoff : new Date().toISOString()));
  const [policy, setPolicy] = useState("slm_delegate");
  const [mode, setMode] = useState("replay");
  const [repeat, setRepeat] = useState(false);
  const [result, setResult] = useState<Run | null>(null);
  const [trio, setTrio] = useState<Run[]>([]);
  const action = useAction();
  const article = data.articles.find(row => row.article_id === articleId);
  const articleTitle = article ? sourceTitle(article.text) : null;
  const storyItem = story.find(item => item.article_id === articleId);
  useEffect(() => { if (story[0] && articleId === story[0].article_id) markTourStep("story"); }, [articleId, story]);
  function select(id: string) { setArticleId(id); setResult(null); setTrio([]); }
  function analyse(policies: readonly string[]) {
    if (!cutoff) return;
    setResult(null); setTrio([]);
    void action.execute(async () => {
      const runs: Run[] = [];
      for (const each of policies) runs.push(await api<Run>("analyse", { article_id: articleId, decision_time: cutoff, policy: each, mode, repeat_run: policies.length === 1 && repeat }));
      if (runs.length > 1) setTrio(runs);
      setResult(runs.find(run => run.policy === policy) || runs.at(-1) || null);
      await refresh();
    });
  }
  const matchesFilter = (row: Article) => {
    const text = `${row.text} ${row.article_id}`.toLowerCase();
    if (query && !text.includes(query.toLowerCase())) return false;
    if (filterName && !text.includes(filterName.toLowerCase().split(" ")[0])) return false;
    return true;
  };
  const featuredIds = new Set(featured.map(row => row.article_id));
  const groups = groupArticles(data.articles.filter(row => !featuredIds.has(row.article_id) && matchesFilter(row)));
  const pinned = featured.filter(matchesFilter);
  const item = (row: Article, extra?: React.ReactNode) => <button key={row.article_id} className={`selection-item ${row.article_id === articleId ? "active" : ""}`} disabled={action.busy} aria-pressed={row.article_id === articleId} onClick={() => select(row.article_id)}>
    <strong>{row.story_title ?? sourceTitle(row.text).title}</strong>
    {row.story_title && <span className="selection-text">{sourceTitle(row.text).title}</span>}
    <small>{sourceTitle(row.text).synthetic && <span className="synthetic-tag">Synthetic</span>}{formatIst(row.published_at)} · {row.article_id}{extra}</small>
  </button>;
  return <><PageHeading eyebrow="SOURCE → EVENT → EVIDENCE" title="Event research" description={INTROS.events} />
    <WorkspaceSummary items={[{ label: "Source inbox", value: data.articles.length, detail: "Original articles in this workspace" }, { label: "Saved research", value: data.runs.length, detail: "Retained decisions and call traces" }, { label: "Research mode", value: data.workspace === "demo" ? "Recorded replay" : "Local", detail: "Analysis begins only when requested" }]} />
    {!data.articles.length ? <section className="panel"><Empty title="Your event inbox is empty" description="Start with one dated financial article. Import a file or enter the original article manually, then return here to investigate it." action={<Link className="button primary" href={href("imports")}>Add your first article</Link>} /></section> : <>
    <div className="split-layout"><section className="panel"><div className="panel-heading"><h2>Source inbox</h2><span className="pill neutral">{data.articles.length} articles</span></div><div className="panel-body">
      <label className="field">Search sources<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Company, phrase or article ID" /></label>
      {filterName && <p className="filter-chip">Showing articles about <strong>{filterName}</strong> <Link href={href("events")}>Show all</Link></p>}
      <div className="selection-list">
        {pinned.length > 0 && <p className="selection-group"><Star size={13} aria-hidden="true" />Demo story articles</p>}
        {pinned.map(row => item(row))}
        {pinned.length > 0 && groups.length > 0 && <p className="selection-group">Other articles</p>}
        {groups.map(group => { const [first, ...rest] = group; const open = expanded === first.article_id; return <div key={first.article_id} className="selection-group-items">
          {item(first)}
          {rest.length > 0 && <button type="button" className="text-button duplicates-toggle" aria-expanded={open} onClick={() => setExpanded(open ? null : first.article_id)}>{open ? "Hide" : "Show"} {rest.length} more {rest.length === 1 ? "version" : "versions"} with the same text</button>}
          {open && rest.map(row => item(row))}
        </div>; })}
        {!pinned.length && !groups.length && <p className="muted">No sources match this search.</p>}
      </div></div></section>
      <section className="panel"><div className="panel-heading"><h2>Inspect & analyse</h2><span className={`pill ${articleTitle?.synthetic ? "amber" : "neutral"}`}>{articleTitle?.synthetic || data.workspace === "demo" ? "SYNTHETIC SOURCE" : "IMPORTED SOURCE"}</span></div><div className="panel-body">
        {article && <>{storyItem && <p className="story-note"><Star size={13} aria-hidden="true" />{storyItem.story_title}</p>}<div className="source-meta"><span><Term name="Published / First seen">Published</Term> <Time value={article.published_at} /></span><span>First seen <Time value={article.first_seen_at} /></span>{isSyntheticSource(article.source_url) ? <span>Synthetic article · no web page</span> : <a href={article.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}</div><blockquote className="source-text">{article.text}</blockquote></>}
        <form inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); analyse([policy]); }}>
          <CutoffField label={<Term name="Decision cutoff" />} value={cutoff} onChange={value => { setCutoff(value); setResult(null); setTrio([]); }}
            presets={data.workspace === "demo" ? [{ label: `Use demo cutoff (${formatIst(demoCutoff).replace(/ \d{4},/, ",")})`, value: demoCutoff }] : []} hint="Only articles and prices available before this moment are used" />
          <div className="form-grid two">
            <label className="field">Research method<select value={policy} onChange={e => { setPolicy(e.target.value); setResult(null); }}>{POLICIES.map(each => <option key={each} value={each}>{policyLabel(each)}</option>)}</select><small><Term name={policyLabel(policy)}>What does this method do?</Term></small></label>
            <label className="field">Analysis mode<select value={mode} onChange={e => setMode(e.target.value)}><option value="replay">Recorded replay (demo articles only)</option>{data.workspace !== "demo" && <option value="live">Configured models (sends requests)</option>}</select><small><Term name={mode === "replay" ? "Recorded replay" : "Live (configured models)"}>What does this mode do?</Term></small></label>
          </div>
          <label className="check-label"><input type="checkbox" checked={repeat} onChange={e => setRepeat(e.target.checked)} /><Term name="Explicit repeat experiment">Explicit repeat experiment</Term> (creates a linked run)</label>
          <div className="form-actions"><Submit busy={action.busy} disabled={!cutoff || !articleId}>Analyse and save run</Submit><button type="button" className="button secondary" disabled={action.busy || repeat || !articleId || !cutoff} onClick={() => analyse(POLICIES)}>Analyse under all three methods</button><p>{mode === "live" ? "This sends the article to your configured model providers." : data.workspace === "demo" ? "Recorded replay: no AI model is called." : "Replay only covers the bundled demo articles. Switch to the Synthetic demo, or set up live models in Connections."}</p></div>
        </form>
        <ErrorMessage message={action.error} />
      </div></section></div>
    {(trio.length > 0 || result) && <section className="panel result-panel" aria-live="polite"><div className="panel-heading"><h2>Result</h2>{result && <button className="button secondary" onClick={() => downloadJson(result, `run-${result.run_id}.json`)}><ArrowDownToLine size={15} />Download run snapshot</button>}</div><div className="panel-body">
      {trio.length > 0 && <PolicyTrio runs={trio} />}
      {result && <RunSummary run={result} data={data} onCutoff={setCutoff} article={article} onSelect={select} />}
    </div></section>}
    </>}
  </>;
}

// ============================== Shared result pieces ==============================
const STATUS_COPY: Record<string, { title: string; text: string }> = {
  ineligible: { title: "This article wasn't available yet.", text: "It was first seen after your cutoff. Move the cutoff later to analyse it." },
  irrelevant: { title: "Filtered out: not a market event.", text: "The screening step found nothing that should move this company's stock. No price evidence was needed." },
  duplicate: { title: "Same text as an earlier article.", text: "It reuses that article's result rather than analysing it twice." },
  abstained: { title: "No label: evidence incomplete.", text: "Try a later cutoff or check the price data." },
  failed: { title: "The analysis stopped early.", text: "Nothing was overwritten; you can retry as a linked repeat." },
  partial: { title: "The analysis stopped early.", text: "The call budget ran out. Nothing was overwritten; you can retry as a linked repeat." },
};

function RunSummary({ run, data, article, onCutoff, onSelect }: { run: Run; data: Workspace; article?: Article; onCutoff?: (iso: string) => void; onSelect?: (id: string) => void }) {
  const direction = run.assessment?.direction;
  const tone = direction === "positive" ? "green" : direction === "negative" ? "red" : "neutral";
  const features = Object.entries(run.features?.values || {});
  const reasons = run.plain_reasons?.length ? run.plain_reasons : [...(run.assessment?.conflicts ?? []), ...(run.assessment?.abstention_reasons ?? [])];
  const stateCopy = !run.assessment || direction === "abstain" ? STATUS_COPY[direction === "abstain" ? "abstained" : run.status] : undefined;
  return <div className="run-summary">
    <div className="subheading"><h2>{run.extraction ? human(run.extraction.event_type) : "Research result"}</h2><Term name="Run status"><Status value={run.status} /></Term></div>
    <div className="source-meta"><span><Term name="Recorded replay">{run.mode === "replay" ? "Recorded replay (synthetic fixture outputs)" : "Live model inference"}</Term></span><span>Method: <Term name={policyLabel(run.policy)} /></span><span>Cutoff <Time value={run.decision_time} /></span>{run.extraction?.company_id && <span>{companyName(data, run.extraction.company_id)}</span>}</div>
    {run.plain_summary && <p className="verdict">{run.plain_summary}</p>}
    {stateCopy && <div className="state-card"><strong>{stateCopy.title}</strong><p>{run.status === "ineligible" && article ? <>It was first seen at <Time value={article.first_seen_at} />, after your cutoff (<Time value={run.decision_time} />). Move the cutoff later to analyse it.</> : reasons[0] ?? stateCopy.text}</p>
      <div className="state-actions">
        {run.status === "ineligible" && article && onCutoff && <button type="button" className="button secondary" onClick={() => onCutoff(article.first_seen_at)}>Set cutoff to first-seen time</button>}
        {run.status === "irrelevant" && onSelect && <span className="muted">Try another article from the inbox.</span>}
      </div></div>}
    {run.assessment && <>
      <div className="stat-list"><div className="stat-item"><span><Term name="Evidence label" /></span><strong className={`direction-${tone}`}>{human(run.assessment.direction)}</strong></div><div className="stat-item"><span><Term name="Signed evidence score" /></span><strong>{signedScore(run.assessment.evidence_score)}</strong><small><Term name="Threshold ±0.15" /></small></div><div className="stat-item"><span><Term name="Evidence coverage" /></span><strong>{wholePercent(run.assessment.coverage)}</strong><small><Term name="Minimum 60%" /></small></div></div>
      {run.score_formula && <div className="score-formula"><h3>How the score was built</h3><p><code>{run.score_formula}</code></p></div>}
      {reasons.length > 0 && <><h3>Why this label</h3><ul className="reason-list">{reasons.map((text, index) => <li key={index} className={run.assessment?.conflicts.length ? "conflict" : undefined}>{run.assessment?.conflicts.length && index === 0 ? <><Term name="Conflict" />: </> : null}{text}</li>)}</ul></>}
    </>}
    {run.error && <div className="alert error">{run.error}</div>}
    {features.length > 0 && <><h3>Numbers available at the cutoff</h3><div className="table-scroll"><table className="evidence-table"><thead><tr><th>Input</th><th>Value</th><th><Term name="Available / Missing / Stale / Not applicable">Status</Term></th></tr></thead><tbody>{features.map(([key, value]) => <tr key={key}><td><Term name={FEATURE_LABELS[key] || human(key)} /></td><td className="numeric">{value == null ? "—" : key === "relative_volume" ? `${format(value, 2)}×` : signedPercent(value)}</td><td>{run.features?.missing.includes(key) ? "Missing" : run.features?.stale.includes(key) ? "Stale" : value == null ? "Not applicable" : "Available"}</td></tr>)}</tbody></table></div></>}
    {run.extraction?.source_spans.length ? <><h3><Term name="Supporting source passages" /></h3><ul className="passages">{run.extraction.source_spans.map((text, index) => <li key={index}>{text}</li>)}</ul></> : null}
    <p className="muted footnote">Evidence scores describe collected inputs; they are not probabilities or forecasts.</p><JsonView value={run} title="Inspect saved extraction, numerical evidence and call trace" />
  </div>;
}

function PolicyTrio({ runs }: { runs: Run[] }) {
  const ordered = [...runs].sort((a, b) => POLICIES.indexOf(a.policy as typeof POLICIES[number]) - POLICIES.indexOf(b.policy as typeof POLICIES[number]));
  return <><div className="subheading"><h2>Same article, three methods</h2><span className="pill neutral">SAME CUTOFF</span></div>
    <div className="trio-grid">{ordered.map(run => <article key={run.run_id} className="trio-card">
      <h3><Term name={policyLabel(run.policy)} /></h3>
      <p className="trio-models"><Term name="Filter / Extraction">Filter</Term> {run.calls.find(call => call.task === "filter")?.model || "—"} → extraction {run.calls.find(call => call.task === "extraction")?.model || "—"}</p>
      <dl><div><dt>Evidence label</dt><dd>{run.assessment ? human(run.assessment.direction) : "—"}</dd></div><div><dt>Score</dt><dd>{signedScore(run.assessment?.evidence_score)}</dd></div><div><dt>Coverage</dt><dd>{wholePercent(run.assessment?.coverage)}</dd></div><div><dt>Status</dt><dd><Status value={run.status} /></dd></div></dl>
    </article>)}</div>
    <p className="muted footnote">Replay returns the recorded fixture output for each call, so identical labels here show the pipeline is consistent. They are not evidence of model quality.</p></>;
}

function OutcomeCard({ outcome, synthetic, assessed, href }: { outcome: Outcome | null; synthetic: boolean; assessed: boolean; href: PanelProps["href"] }) {
  if (!assessed) return <div className="outcome-card pending"><h3>No outcome to measure.</h3><p>This run produced no assessment, so there’s nothing to check against later prices.</p></div>;
  if (!outcome) return <div className="outcome-card pending"><h3><Term name="Later outcome" /> · evaluated separately</h3><p>Not evaluated yet. Outcomes use prices <em>after</em> the cutoff and never change the saved decision.</p></div>;
  if (outcome.status === "pending") return <div className="outcome-card pending"><h3>Waiting for five later trading days.</h3><p>Import more prices after the cutoff and evaluate again.</p><Link className="button secondary" href={href("imports")}>Import prices</Link></div>;
  return <div className="outcome-card"><div className="subheading"><h3><Term name="Later outcome" /> · evaluated separately from the decision</h3><Status value={outcome.status} /></div>
    {outcome.status === "completed" ? <div className="stat-list four"><div className="stat-item"><span><Term name="Entry → exit" /></span><strong>{format(outcome.entry_price)} → {format(outcome.exit_price)}</strong><small><Time value={outcome.entry_time} /> → <Time value={outcome.exit_time} /></small></div><div className="stat-item"><span><Term name="Gross / Net return">Net return</Term></span><strong>{signedPercent(outcome.net_return)}</strong><small>Gross {signedPercent(outcome.gross_return)}</small></div><div className="stat-item"><span><Term name="Benchmark return (outcome)">Benchmark return</Term></span><strong>{signedPercent(outcome.benchmark_return)}</strong><small>Same sessions</small></div><div className="stat-item"><span><Term name="Excess return (outcome)">Excess return</Term></span><strong>{signedPercent(outcome.excess_return)}</strong><small><Term name="Outcome label">Outcome label</Term>: {outcome.label ? human(outcome.label) : "—"}</small></div></div> : null}
    <p className="footnote">{synthetic && <strong>Synthetic fixture prices. This is not real-market performance. </strong>}{outcome.reason}</p></div>;
}

// ============================== Saved results ==============================
type Case = { run: Run; article: { text: string; source_url: string } | null; outcome: Record<string, unknown> | null; observations: Record<string, unknown>[]; missing_observation_ids: string[] };
function runOption(run: Run, data: Workspace) {
  const story = data.articles.find(row => row.article_id === run.article_id)?.story_title;
  const company = run.extraction?.company_id ? companyName(data, run.extraction.company_id) : run.article_id;
  const what = story ? story.replace(/\s*\(.*\)$/, "") : run.extraction ? human(run.extraction.event_type) : human(run.status);
  const label = run.assessment ? human(run.assessment.direction) : human(run.status);
  return `${company} · ${what} · ${label[0].toUpperCase()}${label.slice(1)} · ${policyLabel(run.policy)} · ${formatIst(run.decision_time).replace(/ \d{4},/, "")}`;
}
export function SavedPanel({ api, data, refresh, href }: PanelProps) {
  const parameters = useSearchParams();
  const ordered = useMemo(() => data.runs.slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), [data.runs]);
  const wantedArticle = parameters.get("article");
  const initial = parameters.get("run") || ordered.find(run => run.status === "completed" && (!wantedArticle || run.article_id === wantedArticle))?.run_id || ordered.find(run => run.status === "completed")?.run_id || ordered[0]?.run_id || "";
  const [identifier, setIdentifier] = useState(initial);
  const [loaded, setLoaded] = useState<{ id: string; value: Case } | null>(null);
  const [explained, setExplained] = useState<{ id: string; text: string } | null>(null);
  const result = loaded?.id === identifier ? loaded.value : null;
  const setResult = (value: Case) => setLoaded({ id: value.run.run_id, value });
  const explanation = explained?.id === identifier ? explained.text : "";
  const action = useAction();
  const { execute } = action;
  useEffect(() => {
    if (!identifier) return;
    let active = true;
    void execute(async () => { const next = await api<Case>(`case/${encodeURIComponent(identifier)}`); if (active) { setLoaded({ id: identifier, value: next }); markTourStep("case"); } });
    return () => { active = false; };
    // execute is recreated each render; the case only reloads when the selection changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identifier, api]);
  const run = result?.run;
  return <><PageHeading eyebrow="RETAINED RESEARCH" title="Saved results" description={INTROS.saved} />
    <WorkspaceSummary items={[{ label: "Research library", value: data.runs.length, detail: "Immutable saved runs" }, { label: "Completed", value: data.runs.filter(each => each.status === "completed").length, detail: "Completed research attempts" }, { label: "Evidence assessed", value: data.runs.filter(each => each.assessment).length, detail: "Cases with retained assessments" }]} />
    {!data.runs.length ? <section className="panel"><Empty title="No saved decisions yet" description="Investigate an article first. Your saved results will bring the original sources, evidence score, missing inputs and audit trail together here." action={<Link className="button primary" href={href("events")}>Start event research</Link>} /></section> : <><section className="panel"><div className="panel-heading"><h2>Open a saved case</h2><span className="pill neutral">{data.runs.length} runs</span></div><div className="panel-body">
      <label className="field">Saved run (newest first)<select value={identifier} disabled={action.busy} onChange={e => setIdentifier(e.target.value)}>{ordered.map(each => <option key={each.run_id} value={each.run_id}>{runOption(each, data)}</option>)}</select><small>The case opens as soon as you pick it. Reading a case never calls a model.</small></label>
    </div></section><ErrorMessage message={action.error} />
      {action.busy && !result && <div className="loading-state"><LoaderCircle className="spin" size={20} /><p>Opening the saved case…</p></div>}
      {result && run && <section className="panel"><div className="panel-heading"><h2>Saved case</h2><button className="button secondary" onClick={() => downloadJson(result, `case-${run.run_id}.json`)}><ArrowDownToLine size={15} />Download full case</button></div><div className="panel-body"><RunSummary run={run} data={data} />{result.article && <details className="json-view"><summary>Original article</summary><blockquote className="source-text">{result.article.text}</blockquote></details>}<hr className="section-divider" />
        <OutcomeCard outcome={result.outcome as Outcome | null} synthetic={run.mode === "replay" || data.workspace === "demo"} assessed={Boolean(run.assessment)} href={href} />
        {!result.outcome && run.assessment && <div className="form-actions"><button className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => { await api("outcomes", {}); await refresh(); setResult(await api<Case>(`case/${encodeURIComponent(run.run_id)}`)); }); }}><CheckCircle2 size={15} />Evaluate later outcomes</button><p>Uses only sessions after the cutoff. The saved decision stays unchanged.</p></div>}
        <JsonView value={{ observations: result.observations, missing_observation_ids: result.missing_observation_ids, outcome: result.outcome }} title="Original price observations and outcome record" />
        <h3 style={{ marginTop: 20 }}>Model call audit</h3><div className="table-scroll"><table><thead><tr><th><Term name="Filter / Extraction">Task</Term></th><th>Model</th><th>Mode</th><th>Status</th><th><Term name="Input / output tokens" /></th><th>Latency</th></tr></thead><tbody>{run.calls.map((call, index) => <tr key={index}><td>{human(call.task)}</td><td>{call.model}</td><td>{call.mode}</td><td><Status value={call.status} /></td><td>{call.input_tokens == null && call.output_tokens == null ? <span className="muted">{call.mode === "replay" ? "Not recorded (replay)" : "Not reported"}</span> : `${format(call.input_tokens, 0)} / ${format(call.output_tokens, 0)}`}</td><td>{format(call.latency_ms, 0)} ms</td></tr>)}</tbody></table></div><hr className="section-divider" /><div className="toolbar"><div><h3>Optional explanation</h3><p>{run.mode === "replay" ? "Needs configured live models; not available for recorded replay runs." : "Creates a separate linked model trace. The original decision stays immutable."}</p></div><button className="button secondary" disabled={action.busy || !run.assessment || run.mode === "replay"} onClick={() => { void action.execute(async () => { const response = await api<{ text: string }>(`explain/${run.run_id}`, {}); setExplained({ id: run.run_id, text: response.text }); await refresh(); }); }}><Play size={14} />Request model explanation</button></div>{explanation && <p className="result-explanation">{explanation}</p>}</div></section>}
    </>}
  </>;
}


// ============================== Import evidence ==============================
type ImportResult = { added: number; errors: Record<string, unknown>[]; warnings: string[] };
function rowError(error: Record<string, unknown>, index: number) {
  const line = error.line ?? error.row ?? error.line_number ?? index + 1;
  const message = String(error.error ?? error.message ?? error.detail ?? JSON.stringify(error));
  return `Line ${line}: ${message}`;
}
export function ImportsPanel({ api, data, refresh, href }: PanelProps) {
  const [kind, setKind] = useState("articles");
  const [content, setContent] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [allErrors, setAllErrors] = useState(false);
  const action = useAction();
  const [article, setArticle] = useState({ article_id: "", source_url: "", text: "", published_at: "", first_seen_at: "" });
  async function importContent(text: string) {
    setResult(null); setAllErrors(false);
    await action.execute(async () => { setResult(await api<ImportResult>("import", { kind, content: text })); await refresh(); });
  }
  const errors = result?.errors ?? [];
  return <><PageHeading eyebrow="BUILD YOUR EVIDENCE BASE" title="Import evidence" description={INTROS.imports} />
    <WorkspaceSummary items={[{ label: "Article sources", value: data.articles.length, detail: "Original records retained" }, { label: "Market observations", value: data.observations_count, detail: "Saved price evidence" }, { label: "Supported formats", value: "JSONL / CSV", detail: "Articles and daily OHLCV" }]} /><div className="context-banner"><span className="context-icon"><Database size={18} /></span><div><strong>Active workspace: {data.workspace === "demo" ? "Synthetic demo (offline)" : data.universe === "live" ? <>My data – real companies (<Term name="LIVE: identifiers" />)</> : "My data – demo companies"}</strong><p>Imports retain their original availability. Conflicting saved records cannot be overwritten.</p></div></div>
    <section className="panel"><div className="panel-heading"><h2>Import a file or paste records</h2><span className="pill neutral">LOCAL VALIDATION</span></div><div className="panel-body">
      <div className="tabs" role="group" aria-label="What to import">{["articles", "prices"].map(value => <button key={value} type="button" disabled={action.busy} aria-pressed={kind === value} onClick={() => { setKind(value); setContent(""); setResult(null); }}>{value === "articles" ? "Articles (JSONL)" : "Market prices (CSV)"}</button>)}</div>
      <form inert={action.busy} aria-busy={action.busy} onSubmit={e => { e.preventDefault(); void importContent(content); }}><div className="form-grid"><label className="field full">Choose {kind === "articles" ? <Term name="JSONL" /> : <Term name="OHLCV CSV" />} file<input type="file" accept={kind === "articles" ? ".jsonl,.json,.txt" : ".csv"} onChange={e => { const file = e.target.files?.[0]; if (file) { void file.text().then(text => { setContent(text); setResult(null); }); } }} /><small>Maximum 8 million characters. Original files stay on your device.</small></label><label className="field full">Records<textarea required rows={9} value={content} onChange={e => { setContent(e.target.value); setResult(null); }} placeholder={kind === "articles" ? '{"article_id":"LIVE:LOCAL:example","source_url":"https://…","text":"…","published_at":"2020-12-30T10:00:00Z","first_seen_at":"2020-12-30T10:05:00Z"}' : "instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit,contract_id"} /><small>{kind === "articles" ? "One JSON object per physical line. Publication and first-seen timestamps must include a timezone." : "CSV headers: instrument_id, market_family, timestamp, available_at, open, high, low, close, volume, currency, unit; optional contract_id."}</small></label></div><div className="form-actions"><Submit busy={action.busy}>Validate and import</Submit><p>Good rows are kept even when others fail. Every rejected row is listed with its reason.</p></div></form>
      {kind === "articles" && <details className="json-view" open={!data.articles.length}><summary>Add one article manually — no file needed</summary><form inert={action.busy} aria-busy={action.busy} onSubmit={e => { e.preventDefault(); void importContent(JSON.stringify(article)); }}><div className="form-grid two">{(["article_id", "source_url", "published_at", "first_seen_at"] as const).map(field => <label className="field" key={field}>{human(field)}<input required value={article[field]} onChange={e => setArticle({ ...article, [field]: e.target.value })} placeholder={field.includes("_at") ? "2020-12-30T10:00:00Z" : field === "article_id" && data.universe === "live" ? "LIVE:LOCAL:unique-id" : undefined} /></label>)}<label className="field full">Original article text<textarea required rows={5} value={article.text} onChange={e => setArticle({ ...article, text: e.target.value })} /></label></div><div className="form-actions"><Submit busy={action.busy}>Save manual article</Submit></div></form></details>}
    </div></section><ErrorMessage message={action.error} />
    {result && <section className="panel"><div className="panel-heading"><h2>Import report</h2><Status value={errors.length ? "partial" : "completed"} /></div><div className="panel-body">
      <p className="verdict">{errors.length ? `${errors.length} ${errors.length === 1 ? "row was" : "rows were"} rejected; ${result.added} saved.` : `${result.added} ${result.added === 1 ? "record" : "records"} saved. No rows were rejected.`}</p>
      {errors.length > 0 && <><ul className="error-list">{(allErrors ? errors : errors.slice(0, 10)).map((error, index) => <li key={index}>{rowError(error, index)}</li>)}</ul>{errors.length > 10 && <button type="button" className="text-button" onClick={() => setAllErrors(value => !value)}>{allErrors ? "Show fewer errors" : `Show all ${errors.length} errors`}</button>}</>}
      {result.warnings.map(text => <div className="alert warning" key={text}>{text}</div>)}<JsonView value={result} title="Inspect the raw import report" />{result.added > 0 && <div className="form-actions"><Link className="button primary" href={href(kind === "articles" ? "events" : "technicals")}>{kind === "articles" ? "Investigate imported articles" : "Explore imported prices"}</Link></div>}</div></section>}</>;
}

// ============================== Price indicators ==============================
type TechnicalResult = { bars: Bar[]; snapshot: { history_bars: number; values: Record<string, number | null>; missing: string[]; stale: string[]; required_history: Record<string, number>; interpretation: Record<string, string> } };
const INDICATOR_TERMS: [RegExp, string][] = [[/^sma/, "SMA 20/50/200"], [/^ema/, "EMA 20/50"], [/^rsi/, "RSI 14"], [/^macd/, "MACD"], [/^(bb|boll)/, "Bollinger bands"], [/^atr/, "ATR 14"], [/^adx/, "ADX 14"], [/vol/, "Volume"]];
const indicatorTerm = (key: string) => INDICATOR_TERMS.find(([pattern]) => pattern.test(key))?.[1];
/** Just after the last saved price, so the latest bar is eligible and nothing is stale. */
const afterLastPrice = (end: string | null | undefined) => (end ? new Date(Date.parse(end) + 6 * 3_600_000).toISOString().replace(".000Z", "Z") : new Date().toISOString());
export function TechnicalsPanel({ api, data, href }: PanelProps) {
  const richest = [...data.companies].sort((a, b) => b.bars - a.bars)[0];
  const [company, setCompany] = useState(richest?.instrument_id || data.companies[0]?.instrument_id || "");
  const selected = data.companies.find(row => row.instrument_id === company);
  const [cutoff, setCutoff] = useState(data.workspace === "demo" ? afterLastPrice(richest?.end) : new Date().toISOString());
  const [result, setResult] = useState<TechnicalResult | null>(null);
  const action = useAction();
  const noBars = !selected?.bars;
  const stale = result ? Object.keys(result.snapshot.values).filter(key => result.snapshot.stale.includes(key)) : [];
  return <><PageHeading eyebrow="LOCAL PRICE RESEARCH" title="Price indicators" description={INTROS.technicals} />
    <WorkspaceSummary items={[{ label: "Tracked companies", value: data.companies.length, detail: "In the selected workspace" }, { label: "Stored daily bars", value: data.companies.reduce((total, row) => total + row.bars, 0), detail: "Saved daily price history" }, { label: "Computation", value: "On demand", detail: "Uses saved observations only" }]} />
    <section className="panel"><div className="panel-heading"><h2>Select a price series</h2><span className="pill neutral">NO MODEL REQUIRED</span></div><div className="panel-body"><form inert={action.busy} aria-busy={action.busy} onSubmit={e => { e.preventDefault(); setResult(null); void action.execute(async () => setResult(await api<TechnicalResult>("technicals", { company_id: company, decision_time: cutoff }))); }}>
      <div className="form-grid two"><label className="field">Company<select value={company} onChange={e => { setCompany(e.target.value); setResult(null); }}>{data.companies.map(c => <option key={c.instrument_id} value={c.instrument_id}>{c.name} · {c.bars} bars</option>)}</select><small>{selected?.end ? <>Last saved price: <Time value={selected.end} /></> : "No saved prices yet."}</small></label></div>
      <CutoffField label={<Term name="Decision cutoff">Availability cutoff</Term>} value={cutoff} onChange={value => { setCutoff(value); setResult(null); }} presets={selected?.end ? [{ label: "Use last price date", value: afterLastPrice(selected.end) }] : []} />
      {noBars ? <div className="state-card"><strong>No saved prices for this company yet.</strong><p>Import a daily price CSV, or switch to the Synthetic demo.</p><div className="state-actions"><Link className="button secondary" href={href("imports")}>Import prices</Link></div></div> : null}
      <div className="form-actions"><Submit busy={action.busy} disabled={noBars || !cutoff}>Compute price indicators</Submit><p><Term name="History needed / Warm-up missing">Warm-up</Term> values stay empty until enough eligible bars exist.</p></div>
    </form></div></section><ErrorMessage message={action.error} />
    {result && <><section className="panel"><div className="panel-heading"><h2>Saved daily prices</h2><span className="pill neutral"><Term name="Eligible bars">{result.snapshot.history_bars} eligible bars</Term></span></div><div className="panel-body">{result.bars.length ? <PriceChart bars={result.bars} /> : <Empty title="No eligible bars" description="No saved price was available at this cutoff. Move the cutoff later, or import prices." />}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Technical snapshot</h2><button className="button secondary" onClick={() => downloadJson(result, "technical-snapshot.json")}><ArrowDownToLine size={15} />Download snapshot</button></div>
        {stale.length > 0 && selected?.end && <div className="panel-body"><div className="state-card"><strong>The latest price is older than four days before your cutoff,</strong><p>so the values are shown but marked stale. Move the cutoff closer to the last price date (<Time value={selected.end} />).</p><div className="state-actions"><button type="button" className="button secondary" onClick={() => { const next = afterLastPrice(selected.end); setCutoff(next); void action.execute(async () => setResult(await api<TechnicalResult>("technicals", { company_id: company, decision_time: next }))); }}>Use last price date</button></div></div></div>}
        <div className="table-scroll"><table><thead><tr><th>Indicator</th><th>Value</th><th><Term name="History needed / Warm-up missing">History needed</Term></th><th><Term name="Available / Missing / Stale / Not applicable">Availability</Term></th></tr></thead><tbody>{Object.entries(result.snapshot.values).map(([key, value]) => { const term = indicatorTerm(key); return <tr key={key}><td>{term ? <Term name={term}>{human(key).toUpperCase()}</Term> : human(key).toUpperCase()}</td><td className="numeric">{format(value, 3)}</td><td>{result.snapshot.required_history[key]} bars</td><td>{value === null ? "Warm-up missing" : result.snapshot.stale.includes(key) ? "Stale" : "Available"}</td></tr>; })}</tbody></table></div><div className="panel-body"><JsonView value={result.snapshot} title="Inspect missing history, stale values and interpretation" /></div></section></>}</>;
}

type SyncReport = { observations_added: number; articles_added: number; network_requests: number; errors: Record<string, unknown>[]; warnings: string[]; article_ids: string[]; decision_time: string; actual_start?: string | null; actual_end?: string | null };
export function ConnectionsPanel({ api, data, refresh, href }: PanelProps) {
  const [ids, setIds] = useState<string[]>([]);
  const [start, setStart] = useState("2015-01-01");
  const [end, setEnd] = useState("2020-12-31");
  const [news, setNews] = useState(false);
  const [commodities, setCommodities] = useState(true);
  const [days, setDays] = useState(550);
  const [report, setReport] = useState<SyncReport | null>(null);
  const [batch, setBatch] = useState<unknown>(null);
  const action = useAction();
  const canSync = data.workspace === "local" && data.universe === "live" && data.readiness.some(r => r.capability === "market_history" && r.ready);
  const tokenMissing = data.readiness.some(r => r.capability === "market_history" && !r.configured);
  const totalBars = data.companies.reduce((sum, row) => sum + row.bars, 0);
  const blocker = data.workspace === "demo" ? null : data.universe !== "live" ? "Switch to “My data – real companies” to download provider history." : tokenMissing ? "token" : null;
  async function sync(kind: string) {
    setReport(null); setBatch(null);
    await action.execute(async () => { setReport(await api<SyncReport>(`sync/${kind}`, { company_ids: ids, start_date: start, end_date: end, include_news: news, include_commodities: commodities, lookback_days: days })); await refresh(); });
  }
  return <><PageHeading eyebrow="EXPLICIT CONNECTIONS" title="Data connections" description={INTROS.connections} />
    {data.workspace === "demo" && <div className="state-card demo-skip"><strong>You don’t need this page for the demo.</strong><p>It’s only for connecting your own data provider and models.</p><div className="state-actions"><Link className="button secondary" href={href("overview")}>Back to Overview</Link></div></div>}
    <WorkspaceSummary items={[{ label: "Capabilities", value: data.readiness.length, detail: "Available connection checks" }, { label: "Configured", value: data.readiness.filter(row => row.configured).length, detail: "Configuration present; connectivity unverified" }, { label: "Access control", value: "Explicit", detail: "You choose when requests are sent" }]} /><section className="panel"><div className="panel-heading"><h2>Configuration readiness</h2><span className="pill neutral">OFFLINE CHECK</span></div><div className="panel-body">{data.readiness.map(row => <div className="readiness-card" key={row.capability}><PlugZap size={18} /><div><strong>{row.name}</strong><p>{row.reason}</p></div>{row.capability === "technicals" && !totalBars ? <span className="pill neutral">No data yet</span> : <span className={`pill ${row.configured ? "green" : "neutral"}`}>{row.configured ? "Configured" : "Setup needed"}</span>}</div>)}<p className="muted footnote"><Term name="Configured / Setup needed">Configured</Term> means a setting is present. Configuration presence does not verify connectivity or entitlements. Credentials stay in the server environment; they are never entered here.</p></div></section>
    <section className="panel"><div className="panel-heading"><h2>Download historical research data</h2><span className="pill amber">ENDS IN 2020</span></div><div className="panel-body">{blocker === "token" ? <div className="state-card"><strong>Upstox token not set.</strong><p>Add <code>UPSTOX_ANALYTICS_TOKEN</code> to the server’s <code>.env</code>, restart the API, then refresh.</p><div className="state-actions"><button type="button" className="button secondary" onClick={() => { void action.execute(refresh); }}><RefreshCw size={14} />Refresh workspace</button></div></div> : blocker ? <div className="alert warning">{blocker}</div> : null}<form inert={action.busy} aria-busy={action.busy} onSubmit={e => { e.preventDefault(); void sync("historical"); }}><fieldset style={{ border: 0, padding: 0, margin: "0 0 18px" }}><legend className="field-legend">Companies to download (benchmark included automatically)</legend><div className="indicator-select">{data.companies.map(company => <label key={company.instrument_id} className="check-label"><input type="checkbox" checked={ids.includes(company.instrument_id)} onChange={e => setIds(e.target.checked ? [...ids, company.instrument_id] : ids.filter(id => id !== company.instrument_id))} />{company.name}</label>)}</div></fieldset><div className="form-grid two"><label className="field">Requested start<input required type="date" min="2000-01-01" max={end} value={start} onChange={e => setStart(e.target.value)} /></label><label className="field">Requested end<input required type="date" min={start} max="2020-12-31" value={end} onChange={e => setEnd(e.target.value)} /></label></div><div className="form-actions"><button className="button primary" disabled={action.busy || !canSync || !ids.length}>{action.busy ? <LoaderCircle size={15} className="spin" /> : <ArrowDownToLine size={15} />}Download history ending 2020</button><p>Candles only. Server-side request budget and chunk limits apply.</p></div></form>
      <details className="json-view"><summary>Advanced: recent event evidence and news</summary><p className="muted footnote">Recent prices support the event workflow. Post-2020 bars are excluded from historical strategy research. This action can also fetch bounded company news.</p><form inert={action.busy} aria-busy={action.busy} onSubmit={e => { e.preventDefault(); void sync("live"); }}><label className="field">Recent-history lookback (calendar days)<input type="number" required min={1} max={3650} value={days} onChange={e => setDays(Number(e.target.value))} /></label><label className="check-label"><input type="checkbox" checked={news} onChange={e => setNews(e.target.checked)} />Also import provider headline/summary news</label><label className="check-label"><input type="checkbox" checked={commodities} onChange={e => setCommodities(e.target.checked)} />Also refresh the reviewed commodity contracts (e.g. MCX crude oil)</label><button className="button secondary" disabled={action.busy || !canSync || !ids.length}><RefreshCw size={15} />Refresh selected recent evidence</button></form></details>
    </div></section><ErrorMessage message={action.error} />{report && <section className="panel"><div className="panel-heading"><h2>Provider report</h2><button className="button secondary" onClick={() => downloadJson(report, "provider-report.json")}><ArrowDownToLine size={15} />Download report</button></div><div className="panel-body"><div className="stat-list"><div className="stat-item"><span>Added observations</span><strong>{report.observations_added}</strong></div><div className="stat-item"><span>Added articles</span><strong>{report.articles_added}</strong></div><div className="stat-item"><span>Network requests</span><strong>{report.network_requests}</strong></div></div>{report.errors.length > 0 && <div className="alert warning">{report.errors.length} provider or validation errors. Inspect the report; partial results may have been retained.</div>}<JsonView value={report} title="Inspect actual coverage, limits, warnings and errors" />{report.article_ids.length > 0 && <><hr className="section-divider" /><h3>Separate model batch</h3><p className="muted footnote">Explicitly analyse up to 10 article IDs returned by this refresh, at its completion cutoff.</p><button className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => { setBatch(await api("analyse-news", { article_ids: report.article_ids, decision_time: report.decision_time, policy: "slm_delegate", limit: 10 })); await refresh(); }); }}><Play size={15} />Analyse latest synced news (live models)</button>{batch !== null && <JsonView value={batch} title="Inspect every batch item result" />}</>}</div></section>}</>;
}

type PolicyRow = { mode: string; policy: string; runs: number; calls: number; failed_calls: number; input_tokens: number | null; output_tokens: number | null; usage_complete?: boolean; mean_run_latency_ms: number; assessed_runs?: number; abstentions: number; estimated_cost?: number | null; cost_currency?: string | null };
type Matched = { mode: string; article_id: string; decision_time: string; policies: string[]; run_ids: string[]; all_three_policies?: boolean };
type ComparisonOutcome = Outcome & { mode?: string | null; policy?: string | null; article_id?: string | null };
type AgreementGroup = { mode: string; policy: string; runs: number; filter_recall?: number | null; filter_precision?: number | null; uncertain_rate?: number | null; extractions?: number; field_accuracy?: Record<string, number | null>; validation_status_rates?: Record<string, number | null>; abstention_rate?: number | null };
type Agreement = { label?: string; groups?: AgreementGroup[]; notes?: string[]; unlabelled_runs?: number; gold_version?: string | null } | null | undefined;
type Comparisons = { provenance: string; policy_summary: PolicyRow[]; matched_inputs?: Matched[]; outcomes?: ComparisonOutcome[]; extraction_agreement?: Agreement };

const rate = (value: number | null | undefined) => value == null ? "—" : `${Math.round(value * 100)}%`;

export function ComparisonsPanel({ api, data, refresh, href }: PanelProps) {
  const [result, setResult] = useState<Comparisons | null>(null);
  const action = useAction();
  const { execute } = action;
  useEffect(() => {
    if (!data.runs.length) return;
    let active = true;
    void execute(async () => { const next = await api<Comparisons>("comparisons"); if (active) { setResult(next); markTourStep("comparisons"); } });
    return () => { active = false; };
    // Auto-load once per workspace; the comparison is read-only and never calls a model.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api]);
  const runsById = new Map(data.runs.map(run => [run.run_id, run]));
  const order = (policy: string) => { const index = POLICIES.indexOf(policy as typeof POLICIES[number]); return index < 0 ? 99 : index; };
  const tiers = (row: PolicyRow) => {
    const counts = { small: 0, large: 0, other: 0 };
    data.runs.filter(run => run.mode === row.mode && run.policy === row.policy)
      .forEach(run => run.calls.filter(call => call.task === "filter" || call.task === "extraction").forEach(call => { counts[tierOf(call.model)]++; }));
    return counts;
  };
  const policyRows = (result?.policy_summary ?? []).slice().sort((a, b) => order(a.policy) - order(b.policy) || a.mode.localeCompare(b.mode));
  const showCost = policyRows.some(row => row.estimated_cost != null);
  const agreement = result?.extraction_agreement?.groups?.length ? result.extraction_agreement : null;
  const agreementRows = (agreement?.groups ?? []).slice().sort((a, b) => order(a.policy) - order(b.policy));
  const matched = (result?.matched_inputs || []).filter(group => group.policies.length > 1);
  const outcomes = result?.outcomes || [];
  const reload = () => action.execute(async () => { await api("outcomes", {}); await refresh(); setResult(await api<Comparisons>("comparisons")); });
  const methodName = (policy: string, mode?: string) => <><strong><Term name={policyLabel(policy)} /></strong><small className="cell-note">{policy}{mode ? ` · ${mode}` : ""}</small></>;
  return <><PageHeading eyebrow="QUESTION YOUR ASSUMPTIONS" title="Compare research runs" description={INTROS.comparisons} />
    <WorkspaceSummary items={[{ label: "Saved experiments", value: data.runs.length, detail: "Retained policy runs" }, { label: "Assessed cases", value: data.runs.filter(run => run.assessment).length, detail: "Saved numerical evidence" }, { label: "Recorded outcomes", value: data.outcomes.length, detail: "Evaluated separately from decisions" }]} />
    {!data.runs.length ? <section className="panel"><Empty title="Nothing to compare yet." description={<>Analyse at least one article. “Analyse under all three methods” fills this page in one click.</>} action={<Link className="button primary" href={href("events")}>Start event research</Link>} /></section> : <>
    <section className="panel"><div className="panel-heading"><h2>How the three methods handled the same articles</h2><FlaskConical size={20} className="muted" /></div><div className="panel-body"><p className="result-explanation">Loading reads saved runs only; it doesn’t call any model. Replay timings and tokens demonstrate the pipeline, not measured live-model savings.</p><div className="form-actions"><button className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => setResult(await api<Comparisons>("comparisons"))); }}>{action.busy ? <LoaderCircle size={15} className="spin" /> : <FileJson size={15} />}Reload comparisons</button><button className="button secondary" disabled={action.busy} onClick={() => { void reload(); }}><CheckCircle2 size={15} />Evaluate later outcomes</button></div></div></section>
    <ErrorMessage message={action.error} />
    {!result && action.busy && <div className="loading-state"><LoaderCircle className="spin" size={20} /><p>Reading saved runs…</p></div>}
    {result && <><div className="context-banner"><ShieldCheck size={20} /><p>{result.provenance}</p></div>
      {policyRows.length > 0 && <div className="metric-grid method-calls">{POLICIES.map(policy => { const rows = policyRows.filter(row => row.policy === policy); const calls = rows.reduce((sum, row) => sum + row.calls, 0); return <div className="stat-item" key={policy}><span>{policyLabel(policy)}</span><strong><Count value={calls} format={value => format(value, 0)} /> model calls</strong><small>{rows.reduce((sum, row) => sum + row.runs, 0)} runs</small></div>; })}</div>}
      <section className="panel"><div className="panel-heading"><h2>Method usage</h2><button className="button secondary" onClick={() => downloadJson(result, "research-comparisons.json")}><ArrowDownToLine size={15} />Download comparisons</button></div>
        <div className="table-scroll"><table><thead><tr><th>Method</th><th>Runs</th><th><Term name="Model calls (small · large)">Model calls</Term></th><th>Failures</th><th><Term name="Input / output tokens" /></th>{showCost && <th><Term name="Estimated cost" /></th>}<th><Term name="Mean latency" /></th><th><Term name="Abstention rate">Abstentions</Term></th></tr></thead>
          <tbody>{policyRows.map(row => { const tier = tiers(row); return <tr key={`${row.mode}:${row.policy}`}>
            <td>{methodName(row.policy, row.mode)}</td>
            <td className="numeric">{row.runs}</td>
            <td className="numeric">{row.calls}<small className="cell-note">{tier.small} small · {tier.large} large</small></td>
            <td className="numeric">{row.failed_calls}</td>
            <td>{row.input_tokens == null && row.output_tokens == null ? <span className="muted">{row.mode === "replay" ? "Not recorded in replay" : "Usage incomplete"}</span> : `${format(row.input_tokens, 0)} / ${format(row.output_tokens, 0)}`}</td>
            {showCost && <td className="numeric">{row.estimated_cost == null ? <span className="muted">Unavailable</span> : `${row.cost_currency ? `${row.cost_currency} ` : ""}${format(row.estimated_cost, 4)}`}</td>}
            <td className="numeric">{format(row.mean_run_latency_ms)} ms</td>
            <td className="numeric">{row.abstentions}</td>
          </tr>; })}</tbody></table></div>
        <div className="panel-body"><p className="muted footnote">Model calls splits filter and extraction calls by recorded model tier.{showCost && " Estimated cost uses configured per-1k token prices. It appears only for live groups with complete token usage."} Replay latency measures local pipeline overhead, not model speed.</p></div></section>
      {matched.length > 0 && <section className="panel"><div className="panel-heading"><h2>Same article, different methods</h2><span className="pill neutral">{matched.length} MATCHED {matched.length === 1 ? "ARTICLE" : "ARTICLES"}</span></div>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th>Article · cutoff</th>{POLICIES.map(policy => <th key={policy}><Term name={policyLabel(policy)} /></th>)}</tr></thead>
          <tbody>{matched.map(group => <tr key={`${group.mode}:${group.article_id}:${group.decision_time}`}><td><strong>{group.article_id}</strong><small className="cell-note"><Time value={group.decision_time} /> · {group.mode}</small></td>{POLICIES.map(policy => { const run = group.run_ids.map(id => runsById.get(id)).find(item => item?.policy === policy); return <td key={policy}>{run ? <><strong>{run.assessment ? human(run.assessment.direction) : human(run.status)}</strong><small className="cell-note">score {signedScore(run.assessment?.evidence_score)} · coverage {wholePercent(run.assessment?.coverage)}</small></> : <span className="muted">Not run</span>}</td>; })}</tr>)}</tbody></table></div></section>}
      {agreement && <section className="panel"><div className="panel-heading"><h2>Extraction agreement with hand labels</h2><span className="pill amber"><Term name="Synthetic sanity check">SYNTHETIC SANITY CHECK</Term></span></div><div className="panel-body"><p className="result-explanation">{agreement.label || "Synthetic sanity check on authored articles, not a benchmark."}</p></div>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th>Method</th><th>Runs</th><th><Term name="Filter recall" /></th><th><Term name="Filter precision" /></th><th><Term name="Uncertain → escalated" /></th><th><Term name="Event type / Company / Commodity (accuracy)">Event type</Term></th><th><Term name="Event type / Company / Commodity (accuracy)">Company</Term></th><th><Term name="Event type / Company / Commodity (accuracy)">Commodity</Term></th><th><Term name="Validated spans" /></th><th><Term name="Abstention rate" /></th></tr></thead>
          <tbody>{agreementRows.map(row => <tr key={`${row.mode}:${row.policy}`}><td>{methodName(row.policy, row.mode)}</td><td className="numeric">{row.runs}</td><td className="numeric">{rate(row.filter_recall)}</td><td className="numeric">{rate(row.filter_precision)}</td><td className="numeric">{rate(row.uncertain_rate)}</td><td className="numeric">{rate(row.field_accuracy?.event_type)}</td><td className="numeric">{rate(row.field_accuracy?.company_id)}</td><td className="numeric">{rate(row.field_accuracy?.commodity_id)}</td><td className="numeric">{rate(row.validation_status_rates?.validated)}</td><td className="numeric">{rate(row.abstention_rate)}</td></tr>)}</tbody></table></div>
        <div className="panel-body"><p className="muted footnote">Event type, company and commodity columns are field accuracy on saved extractions. {agreement.unlabelled_runs ? `${agreement.unlabelled_runs} saved runs have no hand label and are counted, not scored.` : ""}</p>{agreement.notes?.length ? <ul className="summary-list footnote">{agreement.notes.map(note => <li key={note}>{note}</li>)}</ul> : null}</div></section>}
      {outcomes.length > 0 && <section className="panel"><div className="panel-heading"><h2><Term name="Later outcome">Later outcomes</Term></h2><span className="pill neutral">EVALUATED AFTER THE DECISION</span></div>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th>Article</th><th>Method</th><th>Status</th><th><Term name="Evidence label" /></th><th><Term name="Outcome label" /></th><th><Term name="Gross / Net return">Net return</Term></th><th><Term name="Benchmark return (outcome)">Benchmark</Term></th><th><Term name="Excess return (outcome)">Excess return</Term></th></tr></thead><tbody>{outcomes.slice().sort((a, b) => order(a.policy ?? "") - order(b.policy ?? "")).map(row => { const run = runsById.get(row.run_id); return <tr key={row.run_id}><td><strong>{row.article_id || "—"}</strong><small className="cell-note">run {row.run_id.slice(0, 8)}</small></td><td>{row.policy ? policyLabel(row.policy) : "—"}</td><td><Status value={row.status} /></td><td>{run?.assessment ? human(run.assessment.direction) : "—"}</td><td>{row.label ? human(row.label) : "—"}</td><td className="numeric">{signedPercent(row.net_return)}</td><td className="numeric">{signedPercent(row.benchmark_return)}</td><td className="numeric">{signedPercent(row.excess_return)}</td></tr>; })}</tbody></table></div>
        <div className="panel-body"><p className="muted footnote">Next session open → 5th session close, net of round-trip costs. The evidence label describes the decision; the outcome label measures what holding the stock did next. {data.workspace === "demo" ? "Synthetic fixture prices: these outcomes show how evaluation works. They are not real-market performance." : "Outcomes never modify the saved decision."}</p></div></section>}
      <section className="panel"><div className="panel-body"><JsonView value={result} title="Inspect matched cohorts, run manifest, ablations and later outcomes" /></div></section>
    </>}</>}
  </>;
}
