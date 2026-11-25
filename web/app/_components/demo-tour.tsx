"use client";

// "New here?" strip on Home: three visible steps (Load the demo · Pick a story · Read the verdict) with ✓ for
// done steps, a "Continue tour →" link, and, after step 3, a "Next:" list (see what happened · compare
// methods · test a price rule). Step completion comes from Workspace data (GET /api/workspace) where
// possible; actions that leave no data trace are recorded locally by markTourStep(). Never blocks navigation.
import Link from "next/link";
import { useSyncExternalStore, type ReactNode } from "react";
import { Check } from "lucide-react";
import type { Workspace } from "./types";

// ---------- local progress (skip choice + click-only steps) ----------
const KEY = "market-events-tour";
type Progress = { skipped: boolean; done: Record<string, boolean> };
const EMPTY: Progress = { skipped: false, done: {} };
let cache: { raw: string | null; value: Progress } = { raw: null, value: EMPTY };
const listeners = new Set<() => void>();
function read(): Progress {
  let raw: string | null = null;
  try { raw = localStorage.getItem(KEY); } catch { /* storage blocked */ }
  if (raw === cache.raw) return cache.value;
  let value = EMPTY;
  try { value = raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY; } catch { /* ignore corrupt value */ }
  cache = { raw, value };
  return value;
}
function write(next: Progress) {
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage blocked */ }
  cache = { raw: JSON.stringify(next), value: next };
  listeners.forEach(listener => listener());
}
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export const useTourProgress = () => useSyncExternalStore(subscribe, read, () => EMPTY);
/** Record a tour action that leaves no trace in the workspace data ("story", "case", "comparisons", "backtest"). */
export function markTourStep(key: string) {
  const current = read();
  if (!current.done[key]) write({ ...current, done: { ...current.done, [key]: true } });
}
export const setTourSkipped = (skipped: boolean) => write({ ...read(), skipped });
/** Forget all saved tour progress (clicked steps and the skip choice). */
export const resetTour = () => write(EMPTY);

// ---------- steps ----------
type Href = (view: string, extra?: Record<string, string>) => string;
export type TourStep = { key: string; title: string; done: boolean; href?: string; onClick?: () => void };

function storyFor(data: Workspace) {
  const story = data.demo_story?.[0];
  return { articleId: story?.article_id ?? "syn-002", cutoff: story?.suggested_decision_times?.[0] ?? "2026-01-12T12:00:00Z" };
}

/** Three visible steps and the later "Next:" links. A step only counts once every earlier one is done. */
export function useTour(data: Workspace, href: Href, demoHref: Href, onDemo: () => void) {
  const progress = useTourProgress();
  let steps: TourStep[];
  let later: TourStep[] = [];
  const demo = data.workspace === "demo";
  // A local workspace with its own stories gets its own three steps; an empty one is offered the demo.
  if (!demo && data.articles.length > 0) {
    steps = [
      { key: "add", title: "Add a news story", done: data.articles.length > 0, href: href("settings", { tab: "import" }) },
      { key: "investigate", title: "Analyse it", done: data.runs.length > 0, href: href("analyse") },
      { key: "inspect", title: "Read the verdict", done: Boolean(progress.done.case), href: href("results", { tab: "saved" }) },
    ];
  } else {
    const { articleId, cutoff } = storyFor(data);
    const storyRuns = data.runs.filter(run => run.article_id === articleId);
    const storyRunIds = new Set(storyRuns.map(run => run.run_id));
    const storyLink = demoHref("analyse", { article: articleId, cutoff });
    steps = [
      { key: "load", title: "Load the demo", done: demo && data.articles.length > 0, onClick: onDemo },
      { key: "story", title: "Pick a story", done: Boolean(progress.done.story) || storyRuns.length > 0, href: storyLink },
      { key: "verdict", title: "Read the verdict", done: storyRuns.length > 0 || Boolean(progress.done.case), href: storyLink },
    ];
    later = [
      { key: "next", title: "see what happened", done: data.outcomes.some(outcome => storyRunIds.has(outcome.run_id)), href: demoHref("results", { tab: "saved", article: articleId }) },
      { key: "compare", title: "compare methods", done: Boolean(progress.done.comparisons), href: demoHref("results", { tab: "compare" }) },
      { key: "lab", title: "test a price rule", done: Boolean(progress.done.backtest), href: demoHref("lab", { tab: "backtest" }) },
    ];
  }
  steps = steps.map((step, index) => ({ ...step, done: steps.slice(0, index + 1).every(each => each.done) }));
  return { steps, later, skipped: progress.skipped };
}

function StepAction({ step, children }: { step: TourStep; children: ReactNode }) {
  if (step.href) return <Link className="tour-continue" href={step.href}>{children}</Link>;
  return <button type="button" className="text-button tour-continue" onClick={step.onClick}>{children}</button>;
}

export function TourStrip({ data, href, demoHref, onDemo, busy }: { data: Workspace; href: Href; demoHref: Href; onDemo: () => void; busy: boolean }) {
  const { steps, later, skipped } = useTour(data, href, demoHref, onDemo);
  if (skipped) return null;
  const next = steps.find(step => !step.done);
  const done = !next;
  const allLater = later.every(step => step.done);
  return <section className="tour-strip" aria-label="Get started">
    <strong className="tour-title">{done && allLater ? "Tour complete" : "New here?"}</strong>
    <ol className="tour-steps">{steps.map((step, index) => <li key={step.key} data-done={step.done ? "" : undefined}>
      <span className="tour-badge" aria-hidden="true">{step.done ? <Check size={13} /> : index + 1}</span>
      {step.title}<span className="sr-only">{step.done ? " (done)" : " (to do)"}</span>
    </li>)}</ol>
    {next && <StepAction step={{ ...next, onClick: busy ? undefined : next.onClick }}>{next.key === "load" ? (busy ? "Loading…" : "Start the tour →") : "Continue tour →"}</StepAction>}
    {done && later.length > 0 && <p className="tour-later">Next:{" "}{later.map((step, index) => <span key={step.key}>{index > 0 && " / "}<Link href={step.href!}>{step.title}</Link>{step.done && <span className="tour-tick"> ✓<span className="sr-only"> done</span></span>}</span>)}</p>}
    <span className="tour-controls">
      {steps.some(step => step.done) && <button type="button" className="text-button" onClick={resetTour}>Restart tour</button>}
      <button type="button" className="text-button" onClick={() => setTourSkipped(true)}>Skip tour</button>
    </span>
  </section>;
}
