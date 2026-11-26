"use client";

// Shared building blocks for the simple UI (brief §3–5): verdict pill and word, signed score, stat tile,
// company card, story row, sub-tabs, score breakdown, card and toast. Pure display: every number is passed
// in from API data by the caller. Styles live in base.css (primitives) and overview.css (cards/rows).
import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import type { Run } from "./types";
import { Term } from "./ui";

// ---------- verdicts ----------
/** positive / negative / mixed evidence, none (abstained or no label) or irrelevant (filtered out). */
export type Verdict = "positive" | "negative" | "mixed" | "none" | "irrelevant";
type Tone = "positive" | "negative" | "mixed" | "neutral";

export const VERDICT_TEXT: Record<Verdict, { pill: string; word: string; tone: Tone | null }> = {
  positive: { pill: "▲ Positive", word: "Positive", tone: "positive" },
  negative: { pill: "▼ Negative", word: "Negative", tone: "negative" },
  mixed: { pill: "◆ Mixed", word: "Mixed", tone: "mixed" },
  none: { pill: "— No verdict", word: "No verdict", tone: "neutral" },
  irrelevant: { pill: "Not relevant", word: "Not relevant", tone: null },
};

/** The run's verdict: the API's evidence_label when present, else the same rule (direction + conflicts). */
export function verdictOf(run: Pick<Run, "status" | "assessment"> | null | undefined): Verdict {
  if (!run) return "none";
  if (run.status === "irrelevant") return "irrelevant";
  const assessment = run.assessment as (Run["assessment"] & { evidence_label?: string }) | null;
  if (!assessment) return "none";
  const label = assessment.evidence_label;
  if (label === "positive_evidence") return "positive";
  if (label === "negative_evidence") return "negative";
  if (label === "mixed_evidence") return "mixed";
  if (label === "insufficient_evidence") return "none";
  if (assessment.direction === "abstain") return "none";
  if (assessment.conflicts?.length || assessment.direction === "neutral") return "mixed";
  return assessment.direction === "positive" ? "positive" : assessment.direction === "negative" ? "negative" : "none";
}

/** Either a ready `verdict`, or the raw `direction` (positive|negative|neutral|abstain) + run `status`
 * (+ `conflicts`, which turn a direction into "mixed"). */
export type VerdictSource = { verdict?: Verdict; direction?: string | null; status?: string | null; conflicts?: unknown[] | null };
function resolve({ verdict, direction, status, conflicts }: VerdictSource): Verdict {
  if (verdict) return verdict;
  if (status === "irrelevant") return "irrelevant";
  if (!direction || direction === "abstain") return "none";
  if (conflicts?.length || direction === "neutral") return "mixed";
  return direction === "positive" ? "positive" : direction === "negative" ? "negative" : "none";
}

/** Pill with symbol + word, so colour is never the only signal. "Not relevant" is plain muted text. */
export function VerdictPill({ size = "md", large, ...source }: VerdictSource & { size?: "md" | "lg"; large?: boolean }) {
  const { pill, tone } = VERDICT_TEXT[resolve(source)];
  if (!tone) return <span className="verdict-muted">{pill}</span>;
  return <span className={`pill ${tone}${large || size === "lg" ? " large" : ""}`}>{pill}</span>;
}

/** Coloured verdict word for compact rows ("Mixed"). */
export function VerdictWord(source: VerdictSource) {
  const { word, tone } = VERDICT_TEXT[resolve(source)];
  return <span className={`verdict-word${tone ? ` tone-${tone}` : ""}`}>{word}</span>;
}

/** Signed evidence score, 2 decimals ("+0.40", "−0.12"), coloured by verdict. "—" when there is none. */
export function ScoreValue({ value, size = "large", ...source }: VerdictSource & { value: number | null | undefined; size?: "large" | "medium" | "small" }) {
  const tone = VERDICT_TEXT[resolve(source)].tone ?? "neutral";
  const text = value == null || !Number.isFinite(value) ? "—" : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)}`;
  return <span className={`score-value ${size} tone-${tone}`}>{text}</span>;
}

// ---------- tiles and cards ----------
const TONE_ALIAS: Record<string, Tone> = { success: "positive", danger: "negative", warning: "mixed" };
/** Small label over a big number. `tone` colours the number (positive|negative|mixed|neutral, or
 * success|danger|warning); `term` links the label to the glossary. */
export function StatTile({ label, value, detail, tone, term, className = "" }: {
  label: ReactNode; value: ReactNode; detail?: ReactNode; tone?: Tone | "success" | "danger" | "warning"; term?: string; className?: string;
}) {
  const shade = tone ? TONE_ALIAS[tone] ?? tone : undefined;
  return <div className={`stat-tile ${className}`.trim()}>
    <span className="stat-label">{term ? <Term name={term}>{label}</Term> : label}</span>
    <strong className={`stat-value${shade ? ` tone-${shade}` : ""}`}>{value}</strong>
    {detail && <span className="stat-detail">{detail}</span>}
  </div>;
}

/** A plain bordered card. `title` renders an h2; `actions` sit to its right. */
export function Card({ title, actions, children, className = "", id, labelledBy }: {
  title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string; labelledBy?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return <section className={`card ${className}`.trim()} id={id} aria-labelledby={labelledBy ?? (title ? headingId : undefined)}>
    {(title || actions) && <div className="card-head">{title && <h2 id={headingId}>{title}</h2>}{actions && <div className="card-actions">{actions}</div>}</div>}
    {children}
  </section>;
}

/** Two-letter avatar from a company name ("Asian Paints" → "AP"). */
export function initials(name: string) {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2)).toUpperCase();
}
export function Avatar({ name, muted = false }: { name: string; muted?: boolean }) {
  return <span className={`avatar${muted ? " muted" : ""}`} aria-hidden="true">{initials(name)}</span>;
}

/** One company with its latest verdict. The whole card is one link. */
export function CompanyCard({ href, name, subtitle, verdict, score, line, selected = false, pending = false }: {
  href: string; name: string; subtitle: ReactNode; verdict: Verdict; score: number | null | undefined; line: ReactNode; selected?: boolean; pending?: boolean;
}) {
  const scored = score != null && verdict !== "none" && verdict !== "irrelevant";
  return <Link className={`company-card${selected ? " selected" : ""}`} href={href} aria-current={selected ? "true" : undefined}>
    <span className="company-card-head"><Avatar name={name} muted={!scored} /><span className="company-card-name"><strong>{name}</strong><small>{subtitle}</small></span>{pending ? <span className="pill neutral">Not analysed yet</span> : <VerdictPill verdict={verdict} />}</span>
    <span className="company-card-score"><ScoreValue value={scored ? score : null} verdict={verdict} /><small>{pending ? "no saved analysis" : scored ? "evidence score" : "not enough evidence"}</small></span>
    <span className="company-card-line">{line}</span>
  </Link>;
}

/** A story in a list: title, then a muted meta line ending in the verdict word. A link when `href` is
 * given, otherwise a `<button aria-pressed>` calling `onClick`. `active` marks the selected row. */
export function StoryRow({ title, meta, verdict, href, onClick, active = false, disabled = false }: {
  title: ReactNode; meta?: ReactNode; verdict?: Verdict; href?: string; onClick?: () => void; active?: boolean; disabled?: boolean;
}) {
  const body = <><span className="story-row-title">{title}</span>{(meta || verdict) && <span className="story-row-meta">{meta}{meta && verdict && " · "}{verdict && <VerdictWord verdict={verdict} />}</span>}</>;
  const className = `story-row${active ? " selected" : ""}`;
  if (href) return <Link className={className} href={href} aria-current={active ? "true" : undefined}>{body}</Link>;
  return <button type="button" className={className} aria-pressed={active} disabled={disabled} onClick={onClick}>{body}</button>;
}

// ---------- sub-tabs ----------
/** Sub-navigation inside a tab. Real links (state lives in ?tab=), current one marked aria-current="page". */
export function SubTabs({ label, tabs, current, vertical = false }: {
  label: string; tabs: { id: string; label: ReactNode; href: string }[]; current: string; vertical?: boolean;
}) {
  return <nav className={`subtabs${vertical ? " vertical" : ""}`} aria-label={label}>
    {tabs.map(tab => <Link key={tab.id} href={tab.href} aria-current={tab.id === current ? "page" : undefined}>{tab.label}</Link>)}
  </nav>;
}

// ---------- score breakdown ----------
export type BreakdownRow = { label: ReactNode; weight?: number | null; contribution: number | null | undefined };
/** "What pushed the score": one row per component (▲/▼, label, weight, signed contribution), the formula
 * in monospace and any conflicts or abstention reasons as bullets. */
export function ScoreBreakdown({ rows, formula, note, notes = [], title = "What pushed the score" }: {
  rows: BreakdownRow[]; formula?: ReactNode; note?: ReactNode; notes?: ReactNode[]; title?: ReactNode;
}) {
  return <div className="score-breakdown">
    <h3>{title}</h3>
    <ul className="breakdown-rows">{rows.map((row, index) => {
      const value = row.contribution;
      const known = value != null && Number.isFinite(value);
      const tone = !known || value === 0 ? "neutral" : value > 0 ? "positive" : "negative";
      return <li key={index}>
        <span className={`breakdown-arrow tone-${tone}`} aria-hidden="true">{!known || value === 0 ? "•" : value > 0 ? "▲" : "▼"}</span>
        <span className="breakdown-label">{row.label}{row.weight != null && <small> (weight {Math.round(row.weight * 100)}%)</small>}</span>
        <strong className={`breakdown-value tone-${tone}`}>{known ? `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)}` : "missing"}</strong>
      </li>;
    })}</ul>
    {formula && <p className="breakdown-formula">{formula}</p>}
    {notes.length > 0 && <ul className="breakdown-notes">{notes.map((item, index) => <li key={index}>{item}</li>)}</ul>}
    {note && <div className="breakdown-note">{note}</div>}
  </div>;
}

// ---------- toast ----------
/** Small notice that hides itself after `timeout` ms (default 5 s) and can be dismissed.
 * Keep the wrapper mounted (it is the live region); pass an empty message to hide. */
export function Toast({ message, onDismiss, timeout = 5000 }: { message: ReactNode; onDismiss: () => void; timeout?: number }) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onDismiss, timeout);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss, timeout]);
  return <div className="toast-region" role="status" aria-live="polite">
    {message ? <div className="toast"><span>{message}</span><button type="button" className="icon-button" aria-label="Dismiss notice" onClick={onDismiss}><X size={16} aria-hidden="true" /></button></div> : null}
  </div>;
}
