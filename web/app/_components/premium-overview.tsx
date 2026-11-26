"use client";

// Home (?view=home): "Overview" title with the story count and latest cutoff, the "New here?" tour strip,
// summary tiles (from the latest run per company), every tracked company, the saved portfolio and the five
// newest stories. Everything comes from Workspace data (GET /api/workspace); no extra API calls.
import Link from "next/link";
import { LoaderCircle } from "lucide-react";
import type { Href } from "./research-app";
import { TourStrip } from "./demo-tour";
import { HomePortfolio } from "./home-portfolio";
import { CompanyCard, StatTile, StoryRow, verdictOf, type Verdict } from "./simple-ui";
import { formatIst } from "./ui";
import { type Api, type Run, type Workspace, human, sourceTitle, wholePercent } from "./types";

const shortTime = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
const when = (iso: string) => Number.isNaN(Date.parse(iso)) ? "" : shortTime.format(new Date(iso));
const newest = (a: Run, b: Run) => Date.parse(b.created_at) - Date.parse(a.created_at);

/** The most recent run for each key (company or article). */
function latestBy(runs: Run[], key: (run: Run) => string | null | undefined) {
  const latest = new Map<string, Run>();
  for (const run of [...runs].sort(newest)) {
    const id = key(run);
    if (id && !latest.has(id)) latest.set(id, run);
  }
  return latest;
}

/** Label the largest absolute weighted contribution from the saved verdict. */
function keyDriver(run: Run) {
  const { components = {}, weights = {} } = run.assessment?.inputs ?? {};
  let strongest = 0;
  let driver = "";
  for (const [component, value] of Object.entries(components)) {
    if (value === null || weights[component] == null) continue;
    const magnitude = Math.abs(value * weights[component]);
    if (magnitude > strongest) {
      strongest = magnitude;
      driver = component === "equity" ? "Stock vs benchmark"
        : component === "commodity" ? "Exposure-adjusted commodity move" : human(component);
    }
  }
  return driver;
}

/** One plain line under the score: event type · key driver or abstention reason · coverage. */
function cardLine(run: Run, verdict: Verdict) {
  const parts: string[] = [];
  if (run.extraction?.event_type) parts.push(human(run.extraction.event_type));
  if (verdict === "none") {
    parts.push(run.plain_reasons?.[0] || human(run.assessment?.abstention_reasons?.[0] || run.status));
  } else {
    const driver = keyDriver(run);
    if (driver) parts.push(driver);
    if (run.assessment) parts.push(`coverage ${wholePercent(run.assessment.coverage)}`);
  }
  return parts.join(" · ");
}

export default function Home({ api, data, href, demoHref, realDataHref, onDemo, busy }: {
  api: Api; data: Workspace; href: Href; demoHref: Href; realDataHref: string; onDemo: () => void; busy: boolean;
}) {
  const empty = !data.articles.length;
  const analyses = data.runs.filter(run => !run.parent_run_id);
  const byCompany = latestBy(analyses, run => run.extraction?.company_id);
  const byArticle = latestBy(analyses, run => run.article_id);
  const companies = data.companies.map(company => {
    const run = byCompany.get(company.instrument_id);
    return { company, id: company.instrument_id, run, verdict: verdictOf(run) };
  });
  const analysed = companies.filter(row => row.run);
  const count = (verdict: Verdict) => analysed.filter(row => row.verdict === verdict).length;
  const cutoffs = data.runs.map(run => run.decision_time).filter(time => !Number.isNaN(Date.parse(time)));
  const latestCutoff = cutoffs.sort((a, b) => Date.parse(b) - Date.parse(a))[0];
  const stories = [...data.articles].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)).slice(0, 5);
  const nameOf = (id: string | null | undefined) => data.companies.find(row => row.instrument_id === id)?.name;
  const loadButton = <button type="button" className="button secondary" onClick={onDemo} disabled={busy}>
    {busy && <LoaderCircle className="spin" size={16} aria-hidden="true" />}{busy ? "Loading synthetic demo…" : "Explore demo"}
  </button>;

  return <div className="home">
    <div className="home-head">
      <div>
        <h1>Overview</h1>
        <p className="muted">{data.articles.length} {data.workspace === "demo" ? "demo " : ""}{data.articles.length === 1 ? "story" : "stories"} · {byArticle.size} analysed{latestCutoff ? ` · cutoff ${formatIst(latestCutoff)}` : ""}</p>
      </div>
      <div className="home-actions">
        {!empty && <Link className="button primary" href={href("analyse")}>Analyse a story</Link>}
        {(data.workspace !== "demo" || empty) && loadButton}
        <Link className={empty ? "button primary" : "button secondary"} href={realDataHref}>Connect real data</Link>
      </div>
    </div>

    {data.workspace !== "demo" && data.universe === "live" && <HomePortfolio api={api} href={href} />}

    {(data.workspace === "demo" || !empty) && <TourStrip data={data} href={href} demoHref={demoHref} onDemo={onDemo} busy={busy} />}

    {empty ? <section className="card home-empty" aria-labelledby="home-empty-title">
      <h2 id="home-empty-title">No stories yet</h2>
      <p className="muted">Explore an offline example with synthetic data, connect Upstox, or import your own evidence.</p>
      <Link href={href("settings", { tab: "import" })}>Import news or prices</Link>
    </section> : null}
      <section className="stat-grid" aria-label="Summary">
        <StatTile label="Analysed" value={analysed.length} detail={`of ${companies.length} tracked companies`} />
        <StatTile label="Positive evidence" value={count("positive")} tone="positive" />
        <StatTile label="Mixed" value={count("mixed")} tone="mixed" />
        <StatTile label="Not enough evidence" value={count("none")} tone="neutral" />
      </section>

      <div className="home-columns">
        <section className="home-companies" aria-labelledby="companies-title">
          <h2 id="companies-title">Companies</h2>
          <p className="muted small">{companies.length} tracked · {analysed.length} with saved analysis. Holdings and analysis status are shown separately.</p>
          {companies.length ? <div className="company-grid">{companies.map(({ id, run, verdict, company }) => <CompanyCard key={id}
            href={href("analyse", { ...(run ? { article: run.article_id } : {}), company: id })}
            name={company.name}
            subtitle={company.trading_symbol ? `${id.split(":")[1]} · ${company.trading_symbol}` : company.sector ? `Demo company · ${human(company.sector)}` : id}
            pending={!run} verdict={verdict} score={run?.assessment?.evidence_score} line={run ? cardLine(run, verdict) : "Open this company to refresh news and analyse a story."} />)}</div>
            : <p className="card muted">No tracked companies are available in this workspace.</p>}
        </section>

        <section className="card home-stories" aria-labelledby="stories-title">
          <div className="card-head"><h2 id="stories-title">Latest stories</h2><Link href={href("analyse")}>See all</Link></div>
          {!stories.length && <p className="muted">No imported news yet. Company prices and your saved portfolio remain available.</p>}
          <div className="story-list">{stories.map(article => {
            const run = byArticle.get(article.article_id);
            const verdict = run ? verdictOf(run) : undefined;
            const company = nameOf(run?.extraction?.company_id);
            const meta = verdict === "irrelevant" ? "Filtered as not relevant" : [company, when(article.published_at), !run && "not analysed yet"].filter(Boolean).join(" · ");
            return <StoryRow key={article.article_id} href={href("analyse", { article: article.article_id })} title={sourceTitle(article.text, 90).title} meta={meta} verdict={verdict === "irrelevant" ? undefined : verdict} />;
          })}</div>
        </section>
      </div>
  </div>;
}
