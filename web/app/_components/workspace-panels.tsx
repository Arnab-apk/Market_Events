"use client";

// Screen panels. Analyse (POST /api/analyse), Results › Saved runs (GET /api/case/<id>, POST /api/outcomes,
// /api/explain/<id>), Results › Compare methods (GET /api/comparisons), Lab › Indicators (POST /api/technicals and /api/history),
// Settings › Import data (POST /api/import) and Settings › Connections (POST /api/sync/<kind>, /api/analyse-news).
// VerdictCard is shared by Analyse and Saved runs.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowDownToLine, CheckCircle2, FileJson, LoaderCircle, Play, RefreshCw } from "lucide-react";
import { Empty, JsonView, PanelProps, Status } from "./research-app";
import { HostedChart, PriceChart } from "./research-charts";
import { HoldingChart } from "./paper-live";
import { CutoffField, Term, Time, formatIst } from "./ui";
import { markTourStep } from "./demo-tour";
import { Avatar, ScoreBreakdown, ScoreValue, StatTile, StoryRow, VerdictPill, verdictOf } from "./simple-ui";
import {
  Article, Bar, Company, History, Outcome, POLICY_ORDER, Run, Workspace, downloadJson, format, human, isSyntheticSource,
  policyLabel, signedPercent, signedScore, sourceBody, sourceTitle, wholePercent,
} from "./types";

const POLICIES = POLICY_ORDER;
const FEATURE_LABELS: Record<string, string> = {
  equity_return: "Equity return (reaction day)", benchmark_return: "Sector benchmark return", excess_return: "Equity excess return",
  relative_volume: "Relative volume (context only)", commodity_return: "Commodity return",
};
const COMMODITY_NAMES: Record<string, string> = { "MCX:CRUDEOIL": "Crude oil" };
const tierOf = (model: string) => /slm|small/i.test(model) ? "small" : /llm|large/i.test(model) ? "large" : "other";
const companyName = (data: Workspace, id: string | null | undefined) => data.companies.find(row => row.instrument_id === id)?.name ?? id ?? "Unknown company";
const byNewest = (a: Run, b: Run) => Date.parse(b.created_at) - Date.parse(a.created_at);
/** "NSE:NIFTY_MATERIALS" → "Nifty Materials". Display only. */
const indexName = (id?: string) => id ? (id.split(":").pop() ?? id).split("_").map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(" ") : "its benchmark";
/** Story titles carry a spoiler in brackets ("… (mixed evidence)"); the verdict pill says that instead. */
const storyHeadline = (article: Article) => article.story_title?.replace(/\s*\(.*\)$/, "") ?? sourceTitle(article.text).title;

/** Newest saved run per article, for the verdict word in story lists. */
function latestByArticle(runs: Run[]) {
  const map = new Map<string, Run>();
  for (const run of [...runs].sort(byNewest)) if (!map.has(run.article_id)) map.set(run.article_id, run);
  return map;
}
/** The company a story is about: the saved extraction first, else the first company named in the text. */
function companyOf(data: Workspace, article?: Article | null, run?: Run | null): Company | undefined {
  const id = run?.extraction?.company_id;
  if (id) return data.companies.find(row => row.instrument_id === id);
  if (!article) return undefined;
  const text = article.text.toLowerCase();
  return data.companies.find(row => [row.name, ...(row.aliases ?? [])].some(name => text.includes(name.toLowerCase())));
}

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
function Submit({ busy, children, disabled, label }: { busy: boolean; children: ReactNode; disabled?: boolean; label?: string }) {
  return <button type="submit" className="button primary" aria-label={label} disabled={busy || disabled}>{busy && <LoaderCircle className="spin" size={16} aria-hidden="true" />}{busy ? "Working…" : children}</button>;
}
function Loading({ text }: { text: string }) {
  return <p className="loading-line" role="status"><LoaderCircle className="spin" size={18} aria-hidden="true" />{text}</p>;
}
/** Group exact-duplicate article texts so the story list doesn't repeat the same headline. */
function groupArticles(articles: Article[]) {
  const groups = new Map<string, Article[]>();
  for (const row of articles) {
    const key = row.text.trim();
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return [...groups.values()];
}

// ============================== Analyse ==============================
export function EventsPanel(props: PanelProps) {
  const parameters = useSearchParams();
  const initialArticle = parameters.get("article");
  const initialCutoff = parameters.get("cutoff");
  const companyFilter = parameters.get("company");
  return <ArticleAnalysis key={JSON.stringify([initialArticle, initialCutoff, companyFilter])} {...props}
    initialArticle={initialArticle} initialCutoff={initialCutoff} companyFilter={companyFilter} />;
}

function ArticleAnalysis({ api, data, refresh, href, initialArticle, initialCutoff, companyFilter }: PanelProps & {
  initialArticle: string | null; initialCutoff: string | null; companyFilter: string | null;
}) {
  const story = useMemo(() => data.demo_story ?? [], [data.demo_story]);
  const featured = story.map(item => data.articles.find(row => row.article_id === item.article_id)).filter((row): row is Article => Boolean(row));
  const latest = useMemo(() => latestByArticle(data.runs), [data.runs]);
  const filteredCompany = data.companies.find(company => company.instrument_id === companyFilter);
  const filterName = filteredCompany?.name ?? companyFilter?.split(":").slice(-2).join(":");
  const scopedArticles = useMemo(() => companyFilter ? data.articles.filter(row =>
    companyOf(data, row, latest.get(row.article_id))?.instrument_id === companyFilter) : data.articles,
  [companyFilter, data, latest]);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [articleId, setArticleId] = useState(() => {
    const explicit = data.articles.find(row => row.article_id === initialArticle);
    if (explicit) return explicit.article_id;
    if (!companyFilter) return featured[0]?.article_id ?? data.articles[0]?.article_id ?? "";
    const ordered = [...scopedArticles].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at));
    const withEvidence = ordered.find(row => latest.get(row.article_id)?.assessment);
    return withEvidence?.article_id ?? ordered[0]?.article_id ?? "";
  });
  const demoCutoff = story.find(item => item.article_id === articleId)?.suggested_decision_times?.[0] ?? story[0]?.suggested_decision_times?.[0] ?? "2026-01-12T12:00:00Z";
  const [cutoff, setCutoff] = useState(() => initialCutoff || (data.workspace === "demo" ? demoCutoff : new Date().toISOString()));
  const [policy, setPolicy] = useState("slm_delegate");
  const mode = data.workspace === "demo" ? "replay" : "live";
  const [pickerOpen, setPickerOpen] = useState(false);
  const storyHeading = useRef<HTMLHeadingElement>(null);
  const [repeat, setRepeat] = useState(false);
  const [result, setResult] = useState<Run | null>(null);
  const [trio, setTrio] = useState<Run[]>([]);
  const action = useAction();
  const article = data.articles.find(row => row.article_id === articleId);
  const shown = result ?? latest.get(articleId) ?? null;
  const company = companyOf(data, article, shown);
  useEffect(() => { if (story[0] && articleId === story[0].article_id) markTourStep("story"); }, [articleId, story]);
  function select(id: string) {
    setArticleId(id); setResult(null); setTrio([]);
    if (pickerOpen) {
      setPickerOpen(false);
      requestAnimationFrame(() => storyHeading.current?.focus());
    }
  }
  function analyse(policies: readonly string[]) {
    if (!cutoff || !articleId || action.busy) return;
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
    const text = `${row.text} ${row.article_id} ${row.story_title ?? ""}`.toLowerCase();
    return !query || text.includes(query.toLowerCase());
  };
  const featuredIds = new Set(featured.map(row => row.article_id));
  const scopedIds = new Set(scopedArticles.map(row => row.article_id));
  const groups = groupArticles(scopedArticles.filter(row => !featuredIds.has(row.article_id) && matchesFilter(row)));
  const pinned = featured.filter(row => scopedIds.has(row.article_id) && matchesFilter(row));
  const row = (item: Article) => {
    const run = latest.get(item.article_id);
    const who = companyOf(data, item, run)?.name;
    return <StoryRow key={item.article_id} title={storyHeadline(item)} active={item.article_id === articleId} disabled={action.busy} onClick={() => select(item.article_id)}
      meta={who ?? formatIst(item.published_at)} verdict={run ? verdictOf(run) : undefined} />;
  };
  const live = data.workspace === "local" && data.universe === "live";
  if (companyFilter && !article) return <section className="card flow"><Empty title={`No stories for ${filterName}`} description={filteredCompany ? "This workspace has no matching news for the company yet." : "This holding is outside the current research universe."} action={<div className="actions">
    {live && filteredCompany && <Link className="button primary" href={href("settings", { tab: "connections", company: filteredCompany.instrument_id })}>Refresh company news</Link>}
    <Link className="button secondary" href={href("analyse")}>Show all stories</Link>
  </div>} /></section>;
  if (!data.articles.length) return <section className="card flow"><Empty title="No stories yet" description="Add a dated news article to begin your analysis." action={<div className="actions">
    {live && <Link className="button primary" href={href("settings", { tab: "connections" })}>Connect real data</Link>}
    <Link className={`button ${live ? "secondary" : "primary"}`} href={href("settings", { tab: "import" })}>Import news</Link>
  </div>} /></section>;
  const title = article ? sourceTitle(article.text) : null;
  return <div className="analyse-layout">
    <button type="button" className="button secondary story-picker-toggle" aria-expanded={pickerOpen} aria-controls="analyse-story-picker"
      onClick={() => setPickerOpen(open => !open)}>{pickerOpen ? "Close story picker" : "Change story"}</button>
    <aside id="analyse-story-picker" className={`card analyse-stories${pickerOpen ? " is-open" : ""}`} aria-labelledby="stories-title">
      <h2 id="stories-title">Stories <span className="muted">({data.articles.length})</span></h2>
      <label className="field">Search<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Company or phrase" /></label>
      {filterName && <p className="filter-chip">Showing stories about <strong>{filterName}</strong> <Link href={href("analyse")}>Show all</Link></p>}
      <div className="story-rows">
        {pinned.length > 0 && groups.length > 0 && <p className="story-group">Demo story</p>}
        {pinned.map(row)}
        {pinned.length > 0 && groups.length > 0 && <p className="story-group">Other articles</p>}
        {groups.map(group => { const [first, ...rest] = group; const open = expanded === first.article_id; return <div key={first.article_id} className="story-rows">
          {row(first)}
          {rest.length > 0 && <button type="button" className="text-button" aria-expanded={open} onClick={() => setExpanded(open ? null : first.article_id)}>{open ? "Hide" : "Show"} {rest.length} more {rest.length === 1 ? "version" : "versions"} with the same text</button>}
          {open && rest.map(row)}
        </div>; })}
        {!pinned.length && !groups.length && <p className="muted">No stories match this search.</p>}
      </div>
    </aside>

    <div className="analyse-main">
      <section className="company-head" aria-label="Company">
        <Avatar name={company?.name ?? "?"} muted={!company} />
        <div><h1>{company?.name ?? "Unmatched story"}</h1>
          <p className="muted">{company ? [company.instrument_id.split(":")[0], company.trading_symbol ?? company.instrument_id.split(":").pop(), company.sector && human(company.sector), `benchmark ${indexName(company.benchmark_id)}`].filter(Boolean).join(" · ") : "No company in this workspace is named in the article."}</p></div>
      </section>

      <section className="card flow story-card" aria-labelledby="story-title">
        {article && <>
          <h2 id="story-title" ref={storyHeading} tabIndex={-1}>{storyHeadline(article)}</h2>
          <blockquote className="source-text">{sourceBody(article.text)}</blockquote>
          <p className="source-meta"><span><Term name="Published / First seen">Published</Term> <Time value={article.published_at} /></span><span>first seen <Time value={article.first_seen_at} /></span>{isSyntheticSource(article.source_url) ? <span>Synthetic article · no web page</span> : <a href={article.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}{title?.synthetic && <span className="synthetic-tag">Synthetic</span>}</p>
        </>}
        <form className="analyse-form" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); analyse([policy]); }}>
          <CutoffField label={<Term name="Decision cutoff">Decision time</Term>} value={cutoff} onChange={value => { setCutoff(value); setResult(null); setTrio([]); }}
            presets={data.workspace === "demo" ? [{ label: `Use demo cutoff (${formatIst(demoCutoff).replace(/ \d{4},/, ",")})`, value: demoCutoff }] : []} hint="Only news and prices available before the decision time are used." />
          <div className="analyse-controls">
            <label className="field grow">Method<select value={policy} onChange={event => { setPolicy(event.target.value); setResult(null); }}>{POLICIES.map(each => <option key={each} value={each}>{policyLabel(each)}</option>)}</select><small><Term name={policyLabel(policy)}>What does this method do?</Term></small></label>
            <Submit busy={action.busy} disabled={!cutoff || !articleId} label={mode === "replay" ? "Run recorded replay" : "Analyse with configured models"}>{mode === "replay" ? "Run recorded replay" : "Analyse with configured models"}</Submit>
          </div>
          <p className="muted small">{mode === "live" ? "This sends the article to your configured model providers." : "Recorded replay uses saved model responses."}</p>
          <details className="more-options"><summary>More options</summary>
            <div className="more-body">
              <label className="check-label"><input type="checkbox" checked={repeat} onChange={event => setRepeat(event.target.checked)} /><span><Term name="Explicit repeat experiment">Repeat experiment</Term> (creates a linked run)</span></label>
              <div className="actions"><button type="button" className="button secondary" disabled={action.busy || repeat || !articleId || !cutoff} onClick={() => analyse(POLICIES)}>Run all three methods and compare</button></div>
            </div>
          </details>
        </form>
        <ErrorMessage message={action.error} />
      </section>

      <p className="sr-only" role="status">{action.busy ? "Analysing…" : result ? `Analysis saved: ${result.assessment ? human(result.assessment.direction) : human(result.status)}` : ""}</p>
      {shown ? <VerdictCard run={shown} data={data} article={article} trio={trio} fresh={Boolean(result)} href={href} onCutoff={value => { setCutoff(value); setResult(null); }} />
        : <section className="card flow"><p className="muted">No saved run for this story yet. Choose a decision time and a method, then press Analyse.</p></section>}
    </div>
  </div>;
}

// ============================== Verdict card (Analyse + Results) ==============================
const STATUS_COPY: Record<string, { title: string; text: string }> = {
  ineligible: { title: "This article wasn't available yet.", text: "It was first seen after your decision time. Move the decision time later to analyse it." },
  irrelevant: { title: "Not relevant: not a market event.", text: "The screening step found nothing that should move this company's stock. No price evidence was needed." },
  duplicate: { title: "Same text as an earlier article.", text: "It reuses that article's result rather than analysing it twice." },
  abstained: { title: "No verdict: a required condition was not met.", text: "The reasons are listed below. A direction is given only for earnings, orders or commodity supply disruptions with enough fresh price data." },
  failed: { title: "The analysis stopped early.", text: "Nothing was overwritten; you can retry as a linked repeat." },
  partial: { title: "The analysis stopped early.", text: "The call budget ran out. Nothing was overwritten; you can retry as a linked repeat." },
};

/** One row per score component: equity vs benchmark and, for commodity events, the exposure-adjusted commodity move. */
function breakdownRows(run: Run, data: Workspace) {
  const inputs = run.assessment?.inputs;
  const values = run.features?.values ?? {};
  const company = companyOf(data, null, run);
  const rule = inputs?.exposure?.rule;
  return Object.entries(inputs?.components ?? {}).filter((entry): entry is [string, number] => typeof entry[1] === "number").map(([key, contribution]) => ({
    contribution,
    weight: inputs?.weights?.[key],
    label: key === "equity" ? <>Stock vs {indexName(company?.benchmark_id)} · {signedPercent(values.excess_return)}</>
      : key === "commodity" ? <>{COMMODITY_NAMES[rule?.commodity_id ?? run.extraction?.commodity_id ?? ""] ?? "Commodity"} {signedPercent(values.commodity_return)}{rule?.direction ? `, ${rule.direction < 0 ? "a cost" : "a benefit"} for ${company?.name ?? "this company"}` : ""}</>
      : human(key),
  }));
}

function ModelCalls({ run }: { run: Run }) {
  return <div className="table-scroll"><table><thead><tr><th scope="col"><Term name="Filter / Extraction">Task</Term></th><th scope="col">Model</th><th scope="col">Mode</th><th scope="col">Status</th><th scope="col"><Term name="Input / output tokens" /></th><th scope="col">Latency</th></tr></thead><tbody>{run.calls.map((call, index) => <tr key={index}><td>{human(call.task)}</td><td>{call.model}</td><td>{call.mode}</td><td><Status value={call.status} /></td><td>{call.input_tokens == null && call.output_tokens == null ? <span className="muted">{call.mode === "replay" ? "Not recorded (replay)" : "Not reported"}</span> : `${format(call.input_tokens, 0)} / ${format(call.output_tokens, 0)}`}</td><td className="numeric">{format(call.latency_ms, 0)} ms</td></tr>)}</tbody></table></div>;
}

export function VerdictCard({ run, data, article, trio = [], fresh = false, href, onCutoff, auditOpen = false, inResults = false, snapshot, children }: {
  run: Run; data: Workspace; article?: Article; trio?: Run[]; fresh?: boolean; href: PanelProps["href"]; onCutoff?: (iso: string) => void;
  auditOpen?: boolean; inResults?: boolean; snapshot?: { value: unknown; name: string; label: string }; children?: ReactNode;
}) {
  const assessment = run.assessment;
  const direction = assessment?.direction;
  const outcome = data.outcomes.find(row => row.run_id === run.run_id);
  const features = Object.entries(run.features?.values || {});
  const reasons = run.plain_reasons?.length ? run.plain_reasons : [...(assessment?.conflicts ?? []), ...(assessment?.abstention_reasons ?? [])];
  const stateCopy = !assessment || direction === "abstain" ? STATUS_COPY[direction === "abstain" ? "abstained" : run.status] : undefined;
  const rows = breakdownRows(run, data);
  const extraction = run.extraction;
  const verdict = verdictOf(run);
  const notes = reasons.map((text, index) => assessment?.conflicts.length && index === 0 ? <><Term name="Conflict" />: {text}</> : text);
  return <section className="card flow verdict-card" aria-labelledby={`verdict-${run.run_id}`}>
    <div className="card-head"><h2 id={`verdict-${run.run_id}`}>Verdict</h2><span className="muted small">{fresh ? "New run" : "Saved run"} · <Time value={run.decision_time} /> · {policyLabel(run.policy)}{run.mode === "replay" ? " · recorded replay" : " · live models"}</span></div>
    {stateCopy && <div className="state-card"><strong>{stateCopy.title}</strong><p>{run.status === "ineligible" && article ? <>It was first seen at <Time value={article.first_seen_at} />, after your decision time (<Time value={run.decision_time} />).</> : assessment ? stateCopy.text : reasons[0] ?? run.plain_summary ?? stateCopy.text}</p>
      {run.status === "ineligible" && article && onCutoff && <div className="actions"><button type="button" className="button secondary" onClick={() => onCutoff(article.first_seen_at)}>Set decision time to first-seen time</button></div>}
      {run.status !== "completed" && <p className="muted small"><Term name="Run status">Status</Term>: <Status value={run.status} /></p>}</div>}
    {assessment && <>
      <div className="stat-grid">
        <StatTile label={<Term name="Evidence label">Evidence</Term>} value={<VerdictPill verdict={verdict} size="lg" />} />
        <StatTile label={<><Term name="Signed evidence score" /> (−1 to +1)</>} value={<ScoreValue value={assessment.evidence_score} verdict={verdict} />} detail={<Term name="Threshold ±0.15" />} />
        <StatTile label={<Term name="Evidence coverage">Data coverage</Term>} value={wholePercent(assessment.coverage)} detail={<Term name="Minimum 60%" />} />
      </div>
      {run.plain_summary && <p className="verdict">{run.plain_summary}</p>}
      {rows.length > 0 ? <ScoreBreakdown rows={rows} formula={run.score_formula && <code className="score-formula">{run.score_formula}</code>} notes={notes} />
        : <>{run.score_formula && <p><code className="score-formula">{run.score_formula}</code></p>}{notes.length > 0 && <ul className="breakdown-notes">{notes.map((item, index) => <li key={index}>{item}</li>)}</ul>}</>}
    </>}
    {run.error && <div className="alert error">{run.error}</div>}
    {outcome?.status === "completed" && <p className="next-line"><span><Term name="Later outcome">What happened next</Term> <span className="muted">(next open → 5th close, after costs)</span></span><strong className={(outcome.net_return ?? 0) >= 0 ? "tone-success" : "tone-danger"}>{(outcome.net_return ?? 0) >= 0 ? "▲" : "▼"} {signedPercent(outcome.net_return)}</strong></p>}
    {outcome?.status === "pending" && <p className="next-line"><span><Term name="Later outcome">What happened next</Term></span><span className="muted">Waiting for five later trading days</span></p>}

    {features.length > 0 && <details className="fold"><summary>Numbers at the decision time</summary><div className="table-scroll"><table><thead><tr><th scope="col">Input</th><th scope="col">Value</th><th scope="col"><Term name="Available / Missing / Stale / Not applicable">Status</Term></th></tr></thead><tbody>{features.map(([key, value]) => <tr key={key}><td><Term name={FEATURE_LABELS[key] || human(key)} /></td><td className="numeric">{value == null ? "—" : key === "relative_volume" ? `${format(value, 2)}×` : signedPercent(value)}</td><td>{run.features?.missing.includes(key) ? "Missing" : run.features?.stale.includes(key) ? "Stale" : value == null ? "Not applicable" : "Available"}</td></tr>)}</tbody></table></div></details>}
    <details className="fold" open={auditOpen}><summary>Full audit trail (sources, model calls, rules)</summary>
      {extraction?.source_spans.length ? <><h3><Term name="Supporting source passages" /></h3><ul className="passages">{extraction.source_spans.map((text, index) => <li key={index}>{text}</li>)}</ul></> : null}
      {extraction && <dl className="facts"><div><dt>Event type</dt><dd>{human(extraction.event_type)}</dd></div><div><dt>Company</dt><dd>{companyName(data, extraction.company_id)}</dd></div><div><dt><Term name="Validated / Unsupported / Unresolved">Quote check</Term></dt><dd>{human(extraction.validation_status)}</dd></div>{assessment?.inputs?.exposure?.rule?.relationship && <div><dt><Term name="Exposure rule" /></dt><dd>{assessment.inputs.exposure.rule.relationship}</dd></div>}</dl>}
      <h3>Model call audit</h3><ModelCalls run={run} />
      <JsonView value={run} title="Inspect saved extraction, numbers and call trace (JSON)" />
    </details>
    {trio.length > 0 && <details className="fold" open><summary>Compare 3 methods</summary><PolicyTrio runs={trio} /></details>}
    {children}
    <div className="actions">
      <button type="button" className="button secondary" onClick={() => snapshot ? downloadJson(snapshot.value, snapshot.name) : downloadJson(run, `run-${run.run_id}.json`)}><ArrowDownToLine size={15} aria-hidden="true" />{snapshot?.label ?? "Download snapshot"}</button>
      {!inResults && <Link className="button secondary" href={href("results", { tab: "saved", run: run.run_id })}>Open in Results</Link>}
    </div>
    <p className="muted small">The score measures evidence strength. It is not a probability or a forecast.</p>
  </section>;
}

function PolicyTrio({ runs }: { runs: Run[] }) {
  const ordered = [...runs].sort((a, b) => POLICIES.indexOf(a.policy as typeof POLICIES[number]) - POLICIES.indexOf(b.policy as typeof POLICIES[number]));
  return <><div className="trio-grid">{ordered.map(run => <article key={run.run_id} className="trio-card">
    <h3><Term name={policyLabel(run.policy)} /></h3>
    <p className="muted small"><Term name="Filter / Extraction">Filter</Term> {run.calls.find(call => call.task === "filter")?.model || "—"} → extraction {run.calls.find(call => call.task === "extraction")?.model || "—"}</p>
    <dl><div><dt>Evidence</dt><dd><VerdictPill verdict={verdictOf(run)} /></dd></div><div><dt>Score</dt><dd>{signedScore(run.assessment?.evidence_score)}</dd></div><div><dt>Coverage</dt><dd>{wholePercent(run.assessment?.coverage)}</dd></div><div><dt>Status</dt><dd><Status value={run.status} /></dd></div></dl>
  </article>)}</div>
    <p className="muted small">Replay returns the recorded answer for each call, so matching verdicts show the pipeline is consistent. They are not evidence of model quality.</p></>;
}

function OutcomeCard({ outcome, synthetic, assessed, href }: { outcome: Outcome | null; synthetic: boolean; assessed: boolean; href: PanelProps["href"] }) {
  if (!assessed) return <div className="outcome-card"><h3>No outcome to measure</h3><p className="muted">This run has no verdict, so there’s nothing to check against later prices.</p></div>;
  if (!outcome) return <div className="outcome-card"><h3><Term name="Later outcome" /> · checked separately</h3><p className="muted">Not evaluated yet. Outcomes use prices <em>after</em> the decision time and never change the saved verdict.</p></div>;
  if (outcome.status === "pending") return <div className="outcome-card"><h3>Waiting for five later trading days</h3><p className="muted">Import more prices after the decision time and evaluate again.</p><Link className="button secondary" href={href("settings", { tab: "import" })}>Import prices</Link></div>;
  return <div className="outcome-card"><div className="card-head"><h3><Term name="Later outcome" /> · checked separately from the verdict</h3><Status value={outcome.status} /></div>
    {outcome.status === "completed" && <div className="stat-grid">
      <StatTile label={<Term name="Entry → exit" />} value={`${format(outcome.entry_price)} → ${format(outcome.exit_price)}`} detail={<><Time value={outcome.entry_time} /> → <Time value={outcome.exit_time} /></>} />
      <StatTile label={<Term name="Gross / Net return">Net return</Term>} value={signedPercent(outcome.net_return)} detail={`Gross ${signedPercent(outcome.gross_return)}`} />
      <StatTile label={<Term name="Benchmark return (outcome)">Benchmark return</Term>} value={signedPercent(outcome.benchmark_return)} detail="Same sessions" />
      <StatTile label={<Term name="Excess return (outcome)">Excess return</Term>} value={signedPercent(outcome.excess_return)} detail={<><Term name="Outcome label" />: {outcome.label ? human(outcome.label) : "—"}</>} />
    </div>}
    <p className="muted small">{synthetic && <strong>Synthetic test prices, not real-market performance. </strong>}{outcome.reason}</p></div>;
}

// ============================== Results › Saved runs ==============================
type Case = { run: Run; article: { text: string; source_url: string } | null; outcome: Record<string, unknown> | null; observations: Record<string, unknown>[]; missing_observation_ids: string[] };
export function SavedPanel(props: PanelProps) {
  const parameters = useSearchParams();
  const wantedArticle = parameters.get("article");
  const wantedRun = parameters.get("run");
  return <SavedRuns key={JSON.stringify([wantedArticle, wantedRun])} {...props} wantedArticle={wantedArticle} wantedRun={wantedRun} />;
}

function SavedRuns({ api, data, refresh, href, wantedArticle, wantedRun }: PanelProps & { wantedArticle: string | null; wantedRun: string | null }) {
  const ordered = useMemo(() => data.runs.slice().sort(byNewest), [data.runs]);
  const initial = wantedRun || ordered.find(run => run.status === "completed" && (!wantedArticle || run.article_id === wantedArticle))?.run_id || ordered.find(run => run.status === "completed")?.run_id || ordered[0]?.run_id || "";
  const [identifier, setIdentifier] = useState(initial);
  const [query, setQuery] = useState("");
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
  const describe = (each: Run) => {
    const item = data.articles.find(row => row.article_id === each.article_id);
    return { company: each.extraction?.company_id ? companyName(data, each.extraction.company_id) : companyOf(data, item)?.name ?? "—", story: item ? storyHeadline(item) : each.article_id };
  };
  const rows = ordered.filter(each => { if (!query) return true; const text = describe(each); return `${text.company} ${text.story} ${policyLabel(each.policy)} ${each.article_id}`.toLowerCase().includes(query.toLowerCase()); });
  if (!data.runs.length) return <section className="card flow"><Empty title="No saved runs yet" description="Analyse a story first. Every run is saved here with its sources, numbers and audit trail." action={<Link className="button primary" href={href("analyse")}>Analyse a story</Link>} /></section>;
  return <>
    {wantedRun ? <div className="actions"><Link className="button secondary" href={href("results", { tab: "saved" })}>Browse saved runs</Link></div> : <section className="card flow">
      <div className="card-head"><h2>Saved runs <span className="muted">({data.runs.length})</span></h2><label className="field inline">Search<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Company, story or method" /></label></div>
      <div className="table-scroll tall"><table className="runs-table"><thead><tr><th scope="col">Company</th><th scope="col">Story</th><th scope="col">Cutoff</th><th scope="col">Method</th><th scope="col"><Term name="Evidence label">Verdict</Term></th><th scope="col">Score</th><th scope="col">Coverage</th><th scope="col"><Term name="Later outcome">Outcome</Term></th></tr></thead>
        <tbody>{rows.map(each => { const text = describe(each); const outcome = data.outcomes.find(row => row.run_id === each.run_id); const selected = each.run_id === identifier; return <tr key={each.run_id} className={selected ? "is-selected" : undefined}>
          <td>{text.company}</td>
          <td><button type="button" className="row-button" aria-pressed={selected} disabled={action.busy && selected} onClick={() => setIdentifier(each.run_id)}>{text.story}</button></td>
          <td><Time value={each.decision_time} /></td>
          <td>{policyLabel(each.policy)}</td>
          <td><VerdictPill verdict={verdictOf(each)} /></td>
          <td className="numeric">{signedScore(each.assessment?.evidence_score)}</td>
          <td className="numeric">{wholePercent(each.assessment?.coverage)}</td>
          <td className="numeric">{outcome?.status === "completed" ? `${(outcome.net_return ?? 0) >= 0 ? "▲" : "▼"} ${signedPercent(outcome.net_return)}` : outcome ? human(outcome.status) : "—"}</td>
        </tr>; })}{!rows.length && <tr><td colSpan={8} className="muted">No saved runs match this search.</td></tr>}</tbody></table></div>
      <p className="muted small">Pick a story to open its verdict. Reading a saved run never calls a model.</p>
    </section>}
    <ErrorMessage message={action.error} />
    {action.busy && !result && <Loading text="Opening the saved run…" />}
    {result && run && <VerdictCard run={run} data={data} href={href} auditOpen inResults snapshot={{ value: result, name: `case-${run.run_id}.json`, label: "Download snapshot" }}>
      {wantedRun && <p className="muted">Story <strong>{describe(run).story}</strong></p>}
      {result.article && <details className="fold"><summary>Original article</summary><blockquote className="source-text">{result.article.text}</blockquote></details>}
      <OutcomeCard outcome={result.outcome as Outcome | null} synthetic={run.mode === "replay" || data.workspace === "demo"} assessed={Boolean(run.assessment)} href={href} />
      {!result.outcome && run.assessment && <div className="actions"><button type="button" className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => { await api("outcomes", {}); await refresh(); setResult(await api<Case>(`case/${encodeURIComponent(run.run_id)}`)); }); }}><CheckCircle2 size={15} aria-hidden="true" />Evaluate later outcomes</button><p className="muted small">Uses only sessions after the decision time. The saved verdict stays unchanged.</p></div>}
      <JsonView value={{ observations: result.observations, missing_observation_ids: result.missing_observation_ids, outcome: result.outcome }} title="Original price observations and outcome record (JSON)" />
      <div className="explain"><div><h3>Optional explanation</h3><p className="muted small">{run.mode === "replay" ? "Needs configured live models; not available for recorded replay runs." : "Creates a separate linked model trace. The original verdict stays unchanged."}</p></div><button type="button" className="button secondary" disabled={action.busy || !run.assessment || run.mode === "replay"} onClick={() => { void action.execute(async () => { const response = await api<{ text: string }>(`explain/${run.run_id}`, {}); setExplained({ id: run.run_id, text: response.text }); await refresh(); }); }}><Play size={14} aria-hidden="true" />Request model explanation</button></div>
      {explanation && <p className="verdict">{explanation}</p>}
    </VerdictCard>}
  </>;
}

// ============================== Settings › Import data ==============================
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
  return <>
    <section className="card flow">
      <div className="card-head"><h2>Import evidence</h2><span className="muted small">{data.articles.length} articles · {format(data.observations_count, 0)} price rows saved</span></div>
      <p className="muted">Into: <strong>{data.workspace === "demo" ? "Demo data (offline)" : data.universe === "live" ? <>My data – real companies (<Term name="LIVE: identifiers" />)</> : "My data – demo companies"}</strong>. Each record keeps when it was published and first seen; saved records are never overwritten.</p>
      <div className="segmented" role="group" aria-label="What to import">{["articles", "prices"].map(value => <button key={value} type="button" disabled={action.busy} aria-pressed={kind === value} onClick={() => { setKind(value); setContent(""); setResult(null); }}>{value === "articles" ? "Articles (JSONL)" : "Market prices (CSV)"}</button>)}</div>
      <form className="stack" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); void importContent(content); }}>
        <label className="field"><span>Choose {kind === "articles" ? <Term name="JSONL" /> : <Term name="OHLCV CSV" />} file</span><input type="file" accept={kind === "articles" ? ".jsonl,.json,.txt" : ".csv"} onChange={event => { const file = event.target.files?.[0]; if (file) { void file.text().then(text => { setContent(text); setResult(null); }); } }} /><small>Maximum 8 million characters. Files stay on your device until you import.</small></label>
        <label className="field">Records<textarea required rows={8} value={content} onChange={event => { setContent(event.target.value); setResult(null); }} placeholder={kind === "articles" ? '{"article_id":"LIVE:LOCAL:example","source_url":"https://…","text":"…","published_at":"2020-12-30T10:00:00Z","first_seen_at":"2020-12-30T10:05:00Z"}' : "instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit,contract_id"} /><small>{kind === "articles" ? "One JSON object per line. Publication and first-seen times must include a timezone." : "CSV headers: instrument_id, market_family, timestamp, available_at, open, high, low, close, volume, currency, unit; optional contract_id."}</small></label>
        <div className="actions"><Submit busy={action.busy}>Validate and import</Submit><p className="muted small">Good rows are kept even when others fail; every rejected row is listed with its reason.</p></div>
      </form>
      {kind === "articles" && <details className="fold" open={!data.articles.length}><summary>Add one article by hand</summary><form className="stack" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); void importContent(JSON.stringify(article)); }}>
        <div className="form-grid">{(["article_id", "source_url", "published_at", "first_seen_at"] as const).map(field => <label className="field" key={field}>{human(field)}<input required value={article[field]} onChange={event => setArticle({ ...article, [field]: event.target.value })} placeholder={field.includes("_at") ? "2020-12-30T10:00:00Z" : field === "article_id" && data.universe === "live" ? "LIVE:LOCAL:unique-id" : undefined} /></label>)}</div>
        <label className="field">Original article text<textarea required rows={5} value={article.text} onChange={event => setArticle({ ...article, text: event.target.value })} /></label>
        <div className="actions"><Submit busy={action.busy}>Save manual article</Submit></div>
      </form></details>}
      <ErrorMessage message={action.error} />
    </section>
    {result && <section className="card flow" aria-live="polite"><div className="card-head"><h2>Import report</h2><Status value={errors.length ? "partial" : "completed"} /></div>
      <p className="verdict">{errors.length ? `${errors.length} ${errors.length === 1 ? "row was" : "rows were"} rejected; ${result.added} saved.` : `${result.added} ${result.added === 1 ? "record" : "records"} saved. No rows were rejected.`}</p>
      {errors.length > 0 && <><ul className="error-list">{(allErrors ? errors : errors.slice(0, 10)).map((error, index) => <li key={index}>{rowError(error, index)}</li>)}</ul>{errors.length > 10 && <button type="button" className="text-button" onClick={() => setAllErrors(value => !value)}>{allErrors ? "Show fewer errors" : `Show all ${errors.length} errors`}</button>}</>}
      {result.warnings.map(text => <div className="alert warning" key={text}>{text}</div>)}
      <JsonView value={result} title="Inspect the raw import report (JSON)" />
      {result.added > 0 && <div className="actions"><Link className="button primary" href={kind === "articles" ? href("analyse") : href("lab", { tab: "indicators" })}>{kind === "articles" ? "Analyse imported articles" : "See imported prices"}</Link></div>}
    </section>}
  </>;
}

// ============================== Lab › Indicators ==============================
type TechnicalResult = { bars: Bar[]; snapshot: { history_bars: number; values: Record<string, number | null>; missing: string[]; stale: string[]; required_history: Record<string, number>; interpretation: Record<string, string> } };
type IndicatorHistory = { status: "ready"; data: History; partial: boolean } | { status: "no-range" | "mismatch" | "failed" };
const HISTORY_START = "2000-01-01";
const HISTORY_END = "2020-12-31";
const HISTORY_NOTICE = {
  "no-range": "Indicator lines are available only for sessions from 2000 through 2020.",
  mismatch: "Historical candles differ from the cutoff snapshot. Recompute to try loading the indicator lines again.",
  failed: "Indicator lines could not be loaded. Recompute to try again.",
};
/** Indicator chips control both the chart layers and their corresponding readings. */
const INDICATOR_CHIPS = [
  { id: "sma20", label: "SMA 20", term: "SMA 20/50/200" },
  { id: "sma50", label: "SMA 50", term: "SMA 20/50/200" },
  { id: "sma200", label: "SMA 200", term: "SMA 20/50/200" },
  { id: "ema20", label: "EMA 20", term: "EMA 20/50" },
  { id: "ema50", label: "EMA 50", term: "EMA 20/50" },
  { id: "rsi14", label: "RSI 14", term: "RSI 14" },
  { id: "macd", label: "MACD", term: "MACD" },
  { id: "bollinger", label: "Bollinger", term: "Bollinger bands" },
  { id: "atr14", label: "ATR 14", term: "ATR 14" },
  { id: "adx14", label: "ADX 14", term: "ADX 14" },
  { id: "volume", label: "Volume", term: "Volume" },
];
const chipOf = (key: string) => INDICATOR_CHIPS.find(chip => chip.id === key.split("_", 1)[0] || (chip.id === "bollinger" && key.startsWith("bollinger20_")));
/** Just after the last saved price, so the latest bar is eligible and nothing is stale. */
const afterLastPrice = (end: string | null | undefined) => (end ? new Date(Date.parse(end) + 6 * 3_600_000).toISOString().replace(".000Z", "Z") : new Date().toISOString());
export function TechnicalsPanel({ api, data, href }: PanelProps) {
  const richest = [...data.companies].sort((a, b) => b.bars - a.bars)[0];
  const [company, setCompany] = useState(richest?.instrument_id || data.companies[0]?.instrument_id || "");
  const selected = data.companies.find(row => row.instrument_id === company);
  const [cutoff, setCutoff] = useState(data.workspace === "demo" ? afterLastPrice(richest?.end) : new Date().toISOString());
  const [result, setResult] = useState<{ technicals: TechnicalResult; history: IndicatorHistory } | null>(null);
  const [chips, setChips] = useState(() => INDICATOR_CHIPS.map(chip => chip.id));
  const [showIntraday, setShowIntraday] = useState(false);
  const action = useAction();
  const noBars = !selected?.bars;
  const compute = (at: string) => {
    setResult(null);
    void action.execute(async () => {
      const technicals = await api<TechnicalResult>("technicals", { company_id: company, decision_time: at });
      const eligible = technicals.bars.filter(bar => bar.time >= HISTORY_START && bar.time <= HISTORY_END);
      const start = eligible[0]?.time;
      const end = eligible.at(-1)?.time;
      let history: IndicatorHistory = { status: "no-range" };
      if (start && end) {
        const historical = await api<History>("history", { company_id: company, start_date: start, end_date: end, as_of: at }).catch(() => null);
        if (!historical) {
          history = { status: "failed" };
        } else {
          // An import can change the available candles between the two requests.
          const sameCandles = historical.bars.length === eligible.length && historical.bars.every((bar, index) => {
            const candle = eligible[index];
            return bar.time === candle.time && bar.open === candle.open && bar.high === candle.high && bar.low === candle.low
              && bar.close === candle.close && bar.volume === candle.volume && bar.available_at === candle.available_at;
          });
          history = sameCandles ? { status: "ready", data: historical, partial: eligible.length !== technicals.bars.length } : { status: "mismatch" };
        }
      }
      setResult({ technicals, history });
    });
  };
  const technicals = result?.technicals;
  const history = result?.history;
  const indicatorData = history?.status === "ready" ? history.data : undefined;
  const chartSelection = useMemo(() => INDICATOR_CHIPS.filter(({ id }) => chips.includes(id) && (indicatorData || id === "volume")).map(({ id }) => id), [chips, indicatorData]);
  const values = technicals ? Object.entries(technicals.snapshot.values) : [];
  const stale = values.filter(([key]) => technicals?.snapshot.stale.includes(key));
  const shown = values.filter(([key]) => { const chip = chipOf(key); return !chip || chips.includes(chip.id); });
  const latestBar = technicals?.bars.at(-1);
  const extraReadings = ["sma200", "ema50"].filter(id => chips.includes(id)).map(id => {
    const point = indicatorData?.indicators[id]?.at(-1);
    const value = point && point.time === latestBar?.time ? point.value : null;
    return { id, value, detail: value !== null ? "At the latest eligible close" : latestBar && indicatorData?.actual_end === latestBar.time ? "Warm-up missing" : "No series at this cutoff" };
  });
  if (chips.includes("volume") && latestBar) extraReadings.push({ id: "volume", value: latestBar.volume, detail: "Shares traded in the latest eligible session" });
  return <>
    <section className="card flow">
      <div className="card-head"><h2>Price indicators</h2><span className="muted small">From saved daily prices · no model needed</span></div>
      <form className="stack" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); compute(cutoff); }}>
        <label className="field">Company<select value={company} onChange={event => { setCompany(event.target.value); setResult(null); }}>{data.companies.map(row => <option key={row.instrument_id} value={row.instrument_id}>{row.name} · {row.bars} days of prices</option>)}</select><small>{selected?.end ? <>Last saved price: <Time value={selected.end} /></> : "No saved prices yet."}</small></label>
        <CutoffField label={<Term name="Decision cutoff">Prices up to</Term>} value={cutoff} onChange={value => { setCutoff(value); setResult(null); }} presets={selected?.end ? [{ label: "Use last price date", value: afterLastPrice(selected.end) }] : []} />
        {noBars && <div className="state-card"><strong>No saved prices for this company yet.</strong><p>Import a daily price CSV, or switch to the demo data.</p><div className="actions"><Link className="button secondary" href={href("settings", { tab: "import" })}>Import prices</Link></div></div>}
        <div className="actions"><Submit busy={action.busy} disabled={noBars || !cutoff}>Compute price indicators</Submit><p className="muted small"><Term name="History needed / Warm-up missing">Warm-up</Term> values stay empty until enough days of prices exist.</p></div>
      </form>
      <ErrorMessage message={action.error} />
    </section>
    {history && technicals && <section className="card flow">
      <div className="card-head"><h2>{selected?.name ?? company}</h2><span className="muted small"><Term name="Eligible bars">{technicals.snapshot.history_bars} days of prices</Term></span></div>
      <div className="chips" role="group" aria-label="Indicators to show">{INDICATOR_CHIPS.map(chip => <button key={chip.id} type="button" className="chip" aria-pressed={chips.includes(chip.id)} onClick={() => setChips(list => list.includes(chip.id) ? list.filter(id => id !== chip.id) : [...list, chip.id])}>{chip.label}</button>)}</div>
      {technicals.bars.length ? <>
        {history.status !== "ready" ? <p className="muted small" role="status">{HISTORY_NOTICE[history.status]}</p> : history.partial && <p className="muted small" role="status">Indicator lines use saved sessions from {history.data.actual_start} through {history.data.actual_end}. Candles and volume use all eligible sessions.</p>}
        <PriceChart bars={technicals.bars} indicators={indicatorData?.indicators} selected={chartSelection} />
      </> : <Empty title="No prices at this time" description="No saved price was available yet. Move the time later, or import prices." />}
    </section>}
    {technicals && <section className="card flow">
      <div className="card-head"><h2>What the indicators say</h2><button type="button" className="button secondary" onClick={() => downloadJson(technicals, "technical-snapshot.json")}><ArrowDownToLine size={15} aria-hidden="true" />Download snapshot</button></div>
      {stale.length > 0 && selected?.end && <div className="state-card"><strong>The latest price is more than four days before your chosen time,</strong><p>so the values are marked stale. Move the time closer to the last price (<Time value={selected.end} />).</p><div className="actions"><button type="button" className="button secondary" onClick={() => { const next = afterLastPrice(selected.end); setCutoff(next); compute(next); }}>Use last price date</button></div></div>}
      <ul className="readings">{shown.map(([key, value]) => { const chip = chipOf(key); return <li key={key}>
        <span className="reading-name">{chip ? <Term name={chip.term}>{human(key).toUpperCase()}</Term> : human(key).toUpperCase()}</span>
        <strong className="numeric">{format(value, 3)}</strong>
        <span className="muted small">{value === null ? "Warm-up missing" : technicals.snapshot.stale.includes(key) ? "Stale" : technicals.snapshot.interpretation[key] ?? "Available"}</span>
      </li>; })}{extraReadings.map(({ id, value, detail }) => {
        const chip = chipOf(id);
        return <li key={id}><span className="reading-name"><Term name={chip?.term ?? id}>{chip?.label ?? id}</Term></span><strong className="numeric">{format(value, id === "volume" ? 0 : 3)}</strong><span className="muted small">{detail}</span></li>;
      })}</ul>
      {technicals.snapshot.interpretation.context && <p className="muted small">{technicals.snapshot.interpretation.context}</p>}
      <details className="fold"><summary>All values with history needed</summary><div className="table-scroll"><table><thead><tr><th scope="col">Indicator</th><th scope="col">Value</th><th scope="col"><Term name="History needed / Warm-up missing">History needed</Term></th><th scope="col"><Term name="Available / Missing / Stale / Not applicable">Availability</Term></th></tr></thead><tbody>{values.map(([key, value]) => <tr key={key}><td>{human(key).toUpperCase()}</td><td className="numeric">{format(value, 3)}</td><td>{technicals.snapshot.required_history[key]} days</td><td>{value === null ? "Warm-up missing" : technicals.snapshot.stale.includes(key) ? "Stale" : "Available"}</td></tr>)}</tbody></table></div><JsonView value={technicals.snapshot} title="Inspect missing history, stale values and reading (JSON)" /></details>
    </section>}
    {data.workspace === "local" && data.universe === "live" && selected ? <section className="card flow">
      <div className="card-head"><h2>Intraday chart</h2><button type="button" className="button secondary" onClick={() => setShowIntraday(value => !value)}>{showIntraday ? "Hide intraday chart" : "Load intraday chart"}</button></div>
      {showIntraday && <HoldingChart key={company} api={api} market={selected.instrument_id.split(":")[1]} ticker={selected.trading_symbol || selected.instrument_id.split(":")[2]} enabled={false} />}
    </section> : <HostedChart initialSymbol="NASDAQ:AAPL" />}
  </>;
}

// ============================== Settings › Connections ==============================
type SyncReport = { observations_added: number; articles_added: number; network_requests: number; errors: Record<string, unknown>[]; warnings: string[]; article_ids: string[]; decision_time: string; actual_start?: string | null; actual_end?: string | null };
export function ConnectionsPanel({ api, data, refresh, href }: PanelProps) {
  const company = useSearchParams().get("company");
  const [ids, setIds] = useState<string[]>([]);
  const [recentIds, setRecentIds] = useState<string[]>(() =>
    company && data.companies.some(row => row.instrument_id === company) ? [company] : []);
  const [start, setStart] = useState("2015-01-01");
  const [end, setEnd] = useState("2020-12-31");
  const [news, setNews] = useState(true);
  const [commodities, setCommodities] = useState(true);
  const [days, setDays] = useState(550);
  const [report, setReport] = useState<SyncReport | null>(null);
  const [batch, setBatch] = useState<{ article_id: string; run_id: string | null; status: string; error: string | null }[] | null>(null);
  const action = useAction();
  const canSync = data.workspace === "local" && data.universe === "live" && data.readiness.some(row => row.capability === "market_history" && row.ready);
  const tokenMissing = data.readiness.some(row => row.capability === "market_history" && !row.configured);
  const totalBars = data.companies.reduce((sum, row) => sum + row.bars, 0);
  const blocker = data.workspace === "demo" ? null : data.universe !== "live" ? "Switch to “My data – real companies” to download provider history." : tokenMissing ? "token" : null;
  const latestCandle = data.companies.reduce((latest, company) => company.end && company.end > latest ? company.end : latest, "");
  async function sync(kind: "live" | "historical") {
    const selected = kind === "live" ? recentIds : ids;
    if (!canSync || !selected.length || action.busy) return;
    setReport(null); setBatch(null);
    await action.execute(async () => { setReport(await api<SyncReport>(`sync/${kind}`, { company_ids: selected, start_date: start, end_date: end, include_news: news, include_commodities: commodities, lookback_days: days })); await refresh(); });
  }
  return <>
    <section className="card flow">
      <div className="card-head"><h2>Connections</h2><span className="api-state"><i aria-hidden="true" />API connected</span></div>
      {data.workspace === "demo" && <div className="state-card"><strong>You don’t need this page for the demo.</strong><p>It’s only for connecting your own data provider and models. The demo runs offline.</p><div className="actions"><Link className="button secondary" href={href("home")}>Back to Home</Link></div></div>}
      <ul className="readiness">{data.readiness.map(row => <li key={row.capability}><div><strong>{row.name}</strong><p className="muted small">{row.reason}</p></div>{row.capability === "technicals" && !totalBars ? <span className="pill neutral">No data yet</span> : <span className={`pill ${row.configured ? "green" : "neutral"}`}>{row.configured ? "Configured" : "Setup needed"}</span>}</li>)}</ul>
      <p className="muted small"><Term name="Configured / Setup needed">Configured</Term> means a setting is present on the server; it does not prove the service works. Keys stay in the server environment and are never shown or entered here.</p>
    </section>
    <section className="card flow">
      <div className="card-head"><h2>Refresh recent prices and news</h2></div>
      <p className="muted">Fetch completed daily candles and recent company news from Upstox. {latestCandle ? `Latest saved candle across companies: ${latestCandle}.` : "No daily candles saved yet."}</p>
      {blocker === "token" ? <div className="state-card"><strong>Upstox token not set.</strong><p>Add <code>UPSTOX_ANALYTICS_TOKEN</code> to the server’s <code>.env</code>, restart the API, then refresh.</p><div className="actions"><button type="button" className="button secondary" onClick={() => { void action.execute(refresh); }}><RefreshCw size={14} aria-hidden="true" />Refresh workspace</button></div></div> : blocker ? <div className="alert warning">{blocker}</div> : null}
      <form className="stack" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); void sync("live"); }}>
        <fieldset className="plain"><legend className="field-legend">Companies to refresh</legend><div className="check-grid">{data.companies.map(company => <label key={company.instrument_id} className="check-label"><input type="checkbox" checked={recentIds.includes(company.instrument_id)} onChange={event => setRecentIds(event.target.checked ? [...recentIds, company.instrument_id] : recentIds.filter(id => id !== company.instrument_id))} />{company.name}</label>)}</div></fieldset>
        <label className="field">Recent-history lookback (calendar days)<input type="number" required min={1} max={3650} value={days} onChange={event => setDays(Number(event.target.value))} /></label>
        <label className="check-label"><input type="checkbox" checked={news} onChange={event => setNews(event.target.checked)} />Also import provider headline/summary news</label>
        <label className="check-label"><input type="checkbox" checked={commodities} onChange={event => setCommodities(event.target.checked)} />Also refresh the reviewed commodity contracts (e.g. MCX crude oil)</label>
        <div className="actions"><button type="submit" className="button primary" disabled={action.busy || !canSync || !recentIds.length}><RefreshCw size={15} aria-hidden="true" />Refresh selected recent evidence</button></div>
      </form>
    </section>
    <section className="card flow">
      <div className="card-head"><h2>Download historical prices for the Lab</h2><span className="pill amber">Ends 31 Dec 2020</span></div>
      <form className="stack" inert={action.busy} aria-busy={action.busy} onSubmit={event => { event.preventDefault(); void sync("historical"); }}>
        <fieldset className="plain"><legend className="field-legend">Companies to download (the benchmark is included automatically)</legend><div className="check-grid">{data.companies.map(company => <label key={company.instrument_id} className="check-label"><input type="checkbox" checked={ids.includes(company.instrument_id)} onChange={event => setIds(event.target.checked ? [...ids, company.instrument_id] : ids.filter(id => id !== company.instrument_id))} />{company.name}</label>)}</div></fieldset>
        <div className="form-grid"><label className="field">Requested start<input required type="date" min="2000-01-01" max={end} value={start} onChange={event => setStart(event.target.value)} /></label><label className="field">Requested end<input required type="date" min={start} max="2020-12-31" value={end} onChange={event => setEnd(event.target.value)} /></label></div>
        <div className="actions"><button type="submit" className="button secondary" disabled={action.busy || !canSync || !ids.length}><ArrowDownToLine size={15} aria-hidden="true" />Download history ending 2020</button><p className="muted small">Daily candles only. Server-side request limits apply.</p></div>
      </form>
      <p role="status" className="muted small">{action.busy ? "Working. This may take a moment." : ""}</p>
      <ErrorMessage message={action.error} />
    </section>
    {report && <section className="card flow" aria-live="polite"><div className="card-head"><h2>Provider report</h2><button type="button" className="button secondary" onClick={() => downloadJson(report, "provider-report.json")}><ArrowDownToLine size={15} aria-hidden="true" />Download report</button></div>
      <div className="stat-grid"><StatTile label="Added price rows" value={format(report.observations_added, 0)} /><StatTile label="Added articles" value={format(report.articles_added, 0)} /><StatTile label="Network requests" value={format(report.network_requests, 0)} /></div>
      <p className="muted">Finished <Time value={report.decision_time} />.{!report.errors.length && !report.observations_added && !report.articles_added ? " No new rows were added. Check the saved coverage before refreshing again." : ""}</p>
      {report.errors.length > 0 && <div className="alert warning">
        <p>{report.errors.length} provider or validation errors. The counts above show what was saved.</p>
        {report.errors.some(error => /HTTP (401|403)\b/.test(String(error.message))) && <p>Upstox rejected the credentials or access. Check the token and its permissions, restart the API after updating it, then try again.</p>}
        {report.errors.some(error => /HTTP 429\b/.test(String(error.message))) && <p>Upstox rate-limited the request. Wait before retrying and select fewer companies.</p>}
        <p>Open the coverage report below for the affected instruments and request details.</p>
      </div>}
      <JsonView value={report} title="Inspect actual coverage, limits, warnings and errors (JSON)" />
      {report.article_ids[0] && <div className="actions"><Link className="button secondary" href={href("analyse", { article: report.article_ids[0] })}>Open imported news</Link></div>}
      {report.article_ids.length > 0 && <div className="explain"><div><h3>Separate model batch</h3><p className="muted small">Analyse up to 10 article IDs returned by this refresh, at its completion time.</p></div><button type="button" className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => { setBatch(await api("analyse-news", { article_ids: report.article_ids, decision_time: report.decision_time, policy: "slm_delegate", limit: 10 })); await refresh(); }); }}><Play size={15} aria-hidden="true" />Analyse latest synced news (live models)</button></div>}
      {batch !== null && <div className="flow">
        <h3>News analysis results</h3>
        {batch.length ? <ul>{batch.map(item => {
          const article = data.articles.find(row => row.article_id === item.article_id);
          const title = article ? storyHeadline(article) : item.article_id;
          return <li key={item.article_id}>
            {item.run_id ? <Link href={href("results", { tab: "saved", run: item.run_id })}>{title}</Link> : title}
            {" · "}{human(item.status)}{item.error ? ` · ${item.error}` : ""}
          </li>;
        })}</ul> : <p>No articles were analysed. Refresh recent news and try again.</p>}
        <JsonView value={batch} title="Inspect every batch item result (JSON)" />
      </div>}
    </section>}
  </>;
}

// ============================== Results › Compare methods ==============================
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
  if (!data.runs.length) return <section className="card flow"><Empty title="Nothing to compare yet" description={<>Analyse at least one story. “Run all three methods and compare” (Analyse › More options) fills this page in one click.</>} action={<Link className="button primary" href={href("analyse")}>Analyse a story</Link>} /></section>;
  return <>
    <section className="card flow">
      <div className="card-head"><h2>Compare methods</h2><div className="actions">
        <button type="button" className="button secondary" disabled={action.busy} onClick={() => { void action.execute(async () => setResult(await api<Comparisons>("comparisons"))); }}>{action.busy ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <FileJson size={15} aria-hidden="true" />}Reload comparisons</button>
        <button type="button" className="button primary" disabled={action.busy} onClick={() => { void reload(); }}><CheckCircle2 size={15} aria-hidden="true" />Evaluate later outcomes</button>
      </div></div>
      <p className="muted">The same stories, run three ways of splitting work between a small and a large model. Loading reads saved runs only and never calls a model. Replay timings show the pipeline, not real model savings.</p>
      {result && <p className="muted small">{result.provenance}</p>}
      <ErrorMessage message={action.error} />
    </section>
    {!result && action.busy && <Loading text="Reading saved runs…" />}
    {result && <>
      {policyRows.length > 0 && <div className="stat-grid">{POLICIES.map(policy => { const rows = policyRows.filter(row => row.policy === policy); return <StatTile key={policy} label={<Term name={policyLabel(policy)} />} value={`${format(rows.reduce((sum, row) => sum + row.calls, 0), 0)} model calls`} detail={`${rows.reduce((sum, row) => sum + row.runs, 0)} runs · ${rows.reduce((sum, row) => sum + row.abstentions, 0)} abstained`} />; })}<StatTile label={<Term name="Later outcome">Later outcomes</Term>} value={format(outcomes.length, 0)} detail="Checked after the decision" /></div>}
      <section className="card flow"><div className="card-head"><h2>Method usage</h2><button type="button" className="button secondary" onClick={() => downloadJson(result, "research-comparisons.json")}><ArrowDownToLine size={15} aria-hidden="true" />Download comparisons</button></div>
        <div className="table-scroll"><table><thead><tr><th scope="col">Method</th><th scope="col">Runs</th><th scope="col"><Term name="Model calls (small · large)">Model calls</Term></th><th scope="col">Failures</th><th scope="col"><Term name="Input / output tokens" /></th>{showCost && <th scope="col"><Term name="Estimated cost" /></th>}<th scope="col"><Term name="Mean latency" /></th><th scope="col"><Term name="Abstention rate">Abstentions</Term></th></tr></thead>
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
        <p className="muted small">Model calls splits filter and extraction calls by recorded model size.{showCost && " Estimated cost uses configured per-1k token prices and appears only for live groups with complete token counts."} Replay latency measures the app, not model speed.</p></section>
      {outcomes.length > 0 && <section className="card flow"><div className="card-head"><h2><Term name="Later outcome">Later outcomes</Term></h2><span className="muted small">Checked after the decision</span></div>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th scope="col">Article</th><th scope="col">Method</th><th scope="col">Status</th><th scope="col"><Term name="Evidence label" /></th><th scope="col"><Term name="Outcome label" /></th><th scope="col"><Term name="Gross / Net return">Net return</Term></th><th scope="col"><Term name="Benchmark return (outcome)">Benchmark</Term></th><th scope="col"><Term name="Excess return (outcome)">Excess return</Term></th></tr></thead><tbody>{outcomes.slice().sort((a, b) => order(a.policy ?? "") - order(b.policy ?? "")).map(row => { const run = runsById.get(row.run_id); return <tr key={row.run_id}><td><strong>{row.article_id || "—"}</strong><small className="cell-note">run {row.run_id.slice(0, 8)}</small></td><td>{row.policy ? policyLabel(row.policy) : "—"}</td><td><Status value={row.status} /></td><td>{run ? <VerdictPill verdict={verdictOf(run)} /> : "—"}</td><td>{row.label ? human(row.label) : "—"}</td><td className="numeric">{signedPercent(row.net_return)}</td><td className="numeric">{signedPercent(row.benchmark_return)}</td><td className="numeric">{signedPercent(row.excess_return)}</td></tr>; })}</tbody></table></div>
        <p className="muted small">Next session open → 5th session close, after round-trip costs. The evidence label describes the decision; the outcome label measures what holding the stock did next. {data.workspace === "demo" ? "Synthetic test prices: these show how checking works, not real-market performance." : "Outcomes never change the saved verdict."}</p></section>}
      {matched.length > 0 && <details className="card fold"><summary>Same article, different methods ({matched.length} matched {matched.length === 1 ? "article" : "articles"})</summary>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th scope="col">Article · cutoff</th>{POLICIES.map(policy => <th scope="col" key={policy}><Term name={policyLabel(policy)} /></th>)}</tr></thead>
          <tbody>{matched.map(group => <tr key={`${group.mode}:${group.article_id}:${group.decision_time}`}><td><strong>{group.article_id}</strong><small className="cell-note"><Time value={group.decision_time} /> · {group.mode}</small></td>{POLICIES.map(policy => { const run = group.run_ids.map(id => runsById.get(id)).find(item => item?.policy === policy); return <td key={policy}>{run ? <><VerdictPill verdict={verdictOf(run)} /><small className="cell-note">score {signedScore(run.assessment?.evidence_score)} · coverage {wholePercent(run.assessment?.coverage)}</small></> : <span className="muted">Not run</span>}</td>; })}</tr>)}</tbody></table></div></details>}
      {agreement && <details className="card fold"><summary>Agreement with hand labels · <Term name="Synthetic sanity check">synthetic sanity check</Term></summary>
        <p className="muted">{agreement.label || "Synthetic sanity check on authored articles, not a benchmark."}</p>
        <div className="table-scroll"><table className="fit-table"><thead><tr><th scope="col">Method</th><th scope="col">Runs</th><th scope="col"><Term name="Filter recall" /></th><th scope="col"><Term name="Filter precision" /></th><th scope="col"><Term name="Uncertain → escalated" /></th><th scope="col"><Term name="Event type / Company / Commodity (accuracy)">Event type</Term></th><th scope="col"><Term name="Event type / Company / Commodity (accuracy)">Company</Term></th><th scope="col"><Term name="Event type / Company / Commodity (accuracy)">Commodity</Term></th><th scope="col"><Term name="Validated spans" /></th><th scope="col"><Term name="Abstention rate" /></th></tr></thead>
          <tbody>{agreementRows.map(row => <tr key={`${row.mode}:${row.policy}`}><td>{methodName(row.policy, row.mode)}</td><td className="numeric">{row.runs}</td><td className="numeric">{rate(row.filter_recall)}</td><td className="numeric">{rate(row.filter_precision)}</td><td className="numeric">{rate(row.uncertain_rate)}</td><td className="numeric">{rate(row.field_accuracy?.event_type)}</td><td className="numeric">{rate(row.field_accuracy?.company_id)}</td><td className="numeric">{rate(row.field_accuracy?.commodity_id)}</td><td className="numeric">{rate(row.validation_status_rates?.validated)}</td><td className="numeric">{rate(row.abstention_rate)}</td></tr>)}</tbody></table></div>
        <p className="muted small">Event type, company and commodity columns are field accuracy on saved extractions. {agreement.unlabelled_runs ? `${agreement.unlabelled_runs} saved runs have no hand label and are counted, not scored.` : ""}</p>{agreement.notes?.length ? <ul className="summary-list">{agreement.notes.map(note => <li key={note}>{note}</li>)}</ul> : null}</details>}
      <details className="card fold"><summary>Matched cohorts, run manifest and ablations (JSON)</summary><pre className="json">{JSON.stringify(result, null, 2)}</pre></details>
    </>}
  </>;
}
