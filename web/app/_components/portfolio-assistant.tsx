"use client";

import { useState } from "react";
import Link from "next/link";
import { latestPortfolioEvidence, type Holding } from "../_lib/portfolio";
import type { Href, PanelProps } from "./research-app";
import { VerdictPill, verdictOf } from "./simple-ui";
import { sourceTitle, wholePercent, type Run, type Scope, type Workspace } from "./types";
import { Time } from "./ui";
import styles from "./portfolio-panel.module.css";

const QUESTIONS = {
  recent: "Which holdings have recent saved evidence?",
  conflicts: "Where does the evidence conflict?",
  gaps: "Where is the evidence incomplete?",
};
type Topic = keyof typeof QUESTIONS;

function hasGap(run: Run) {
  return Boolean(run.assessment?.abstention_reasons.length || run.assessment?.direction === "abstain"
    || run.features?.missing.length || run.features?.stale.length);
}

export default function PortfolioAssistant({ api, holdings, data, scope, href }: {
  api: PanelProps["api"]; holdings: Holding[]; data: Workspace; scope: Scope; href: Href;
}) {
  const [topic, setTopic] = useState<Topic>("recent");
  const [selected, setSelected] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const evidence = latestPortfolioEvidence(holdings, data.runs, scope.universe);
  const covered = evidence.flatMap(({ holding, run }) => run ? [{ holding, run }] : []);
  const uncovered = evidence.filter(row => !row.run);
  const candidates = covered.filter(({ run }) => topic === "recent"
    || (topic === "conflicts" ? run.assessment?.conflicts.length : hasGap(run)));
  candidates.sort((a, b) => Date.parse(b.run.decision_time) - Date.parse(a.run.decision_time));
  const context = candidates.slice(0, 12);
  const byId = new Map(context.map(row => [row.run.run_id, row]));
  const rows = selected === null ? context : selected.flatMap(id => {
    const row = byId.get(id);
    return row ? [row] : [];
  });
  const live = scope.workspace === "local" && scope.universe === "live";
  const articles = new Map(data.articles.map(article => [article.article_id, article]));

  async function askModel() {
    if (busy || !context.length) return;
    setBusy(true);
    setError("");
    setSelected(null);
    try {
      const result = await api<{ run_ids: string[] }>("portfolio-review", {
        topic, run_ids: context.map(({ run }) => run.run_id),
      });
      setSelected(result.run_ids);
    } catch {
      setError("The configured model could not suggest cases. The saved evidence is still shown below. Check the model settings and try again.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="card flow" aria-labelledby="portfolio-assistant-title">
    <div className="card-head">
      <h2 id="portfolio-assistant-title">Portfolio research assistant</h2>
      <span className="pill neutral">{covered.length} of {holdings.length} holdings with saved assessments</span>
    </div>
    <p className="muted">Review dated evidence for your confirmed holdings. The valuation above uses separately dated closing prices.</p>
    <label className="field">Research question
      <select value={topic} disabled={busy} onChange={event => {
        setTopic(event.target.value as Topic);
        setSelected(null);
        setError("");
      }}>{Object.entries(QUESTIONS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </label>
    {live && context.length > 0 && <>
      <div className="actions">
        <button type="button" className="button secondary" disabled={busy} onClick={() => void askModel()}>
          {busy ? "Asking configured model…" : "Ask AI to suggest cases"}
        </button>
        {selected !== null && <button type="button" className="text-button" disabled={busy} onClick={() => setSelected(null)}>Show matching cases</button>}
        <Link href={href("settings", { tab: "connections" })}>Model setup</Link>
      </div>
      <p className="muted small">The AI option sends the topic and saved case summaries to your configured model. Quantities, costs and account details stay in this tab.</p>
    </>}
    {error && <p className="alert warning" role="alert">{error}</p>}
    <p className="muted small" role="status">{selected !== null ? "Cases suggested by the configured model." : candidates.length > context.length ? `Showing the latest ${context.length} of ${candidates.length} matching cases.` : "Showing the latest matching assessment per holding."}</p>
    {rows.length ? <ol className={styles.evidenceList}>
      {rows.map(({ holding, run }) => {
        const article = articles.get(run.article_id);
        const label = article?.story_title || (article ? sourceTitle(article.text).title : "Saved event assessment");
        return <li key={run.run_id}>
          <div className="card-head"><h3>{holding.symbol} <small className="muted">{holding.exchange}</small></h3><VerdictPill verdict={verdictOf(run)} /></div>
          <Link href={href("results", { tab: "saved", run: run.run_id, article: run.article_id })}>{label}</Link>
          <p className="muted small">Decision cutoff <Time value={run.decision_time} /> · Coverage {wholePercent(run.assessment?.coverage)}</p>
          {run.assessment?.conflicts.length ? <p className="small">Conflicts: {run.assessment.conflicts.join(", ")}</p> : null}
          {hasGap(run) && <p className="small">The case has missing or stale inputs, or the engine withheld a verdict. Open the case for details.</p>}
        </li>;
      })}
    </ol> : <p>{selected === null ? "No saved cases match this question." : "The model did not suggest a case for this question."}</p>}
    {uncovered.length > 0 && <details className="fold"><summary>{uncovered.length} holdings without a saved assessment</summary>
      <ul>{uncovered.map(({ holding }) => <li key={`${holding.exchange}:${holding.symbol}`}>{holding.symbol} · {holding.exchange}</li>)}</ul>
    </details>}
  </section>;
}
