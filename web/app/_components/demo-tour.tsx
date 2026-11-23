"use client";

// Guided workflow built on the React Bits Stepper: a 7-step demo tour (workspace=demo) or a 3-step path
// (local workspace) on the Overview, plus a slim tour bar on other demo pages. Step completion comes from the
// Workspace data (GET /api/workspace) where possible; actions that leave no data trace (opening a case,
// loading comparisons, running a backtest) are recorded locally by markTourStep(). Never blocks navigation.
import Link from "next/link";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { ArrowRight, Check, EyeOff, Map as MapIcon, RotateCcw } from "lucide-react";
import Stepper, { Step } from "./react-bits/Stepper";
import Aurora from "./react-bits/Aurora";
import { useTheme } from "./theme-toggle";
import { formatIst, useMotionOff } from "./ui";
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
  listeners.forEach(listener => listener());
}
const subscribe = (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener); };
export const useTourProgress = () => useSyncExternalStore(subscribe, read, () => EMPTY);
/** Record a tour action that leaves no trace in the workspace data ("case", "comparisons", "backtest", "story"). */
export function markTourStep(key: string) {
  const current = read();
  if (!current.done[key]) write({ ...current, done: { ...current.done, [key]: true } });
}
const setSkipped = (skipped: boolean) => write({ ...read(), skipped });

// ---------- step definitions ----------
type TourStep = { key: string; title: string; body: ReactNode; action: ReactNode; done: boolean };
type Hrefs = { href: (view: string) => string; demoHref: (view: string, extra?: Record<string, string>) => string };

function storyFor(data: Workspace) {
  const story = data.demo_story?.[0];
  return { articleId: story?.article_id ?? "syn-002", cutoff: story?.suggested_decision_times?.[0] ?? "2026-01-12T12:00:00Z" };
}

export function useTourSteps(data: Workspace, links: Hrefs, onDemo: () => void, busy: boolean): TourStep[] {
  const progress = useTourProgress();
  const demo = data.workspace === "demo";
  if (!demo) {
    return [
      { key: "add", title: "Add evidence", body: "Import a dated article and market history, or enter an article manually.", done: data.articles.length > 0,
        action: <Link className="button primary" href={links.href("imports")}>Import evidence</Link> },
      { key: "investigate", title: "Investigate", body: "Choose a source and a decision cutoff. See what the available evidence supports.", done: data.runs.length > 0,
        action: <Link className="button primary" href={links.href("events")}>Start event research</Link> },
      { key: "inspect", title: "Inspect", body: "Review the score, missing inputs, original sources and model audit together.", done: Boolean(progress.done.case),
        action: <Link className="button primary" href={links.href("saved")}>Open saved results</Link> },
    ];
  }
  const { articleId, cutoff } = storyFor(data);
  const storyRuns = data.runs.filter(run => run.article_id === articleId && Date.parse(run.decision_time) === Date.parse(cutoff));
  const policies = new Set(storyRuns.map(run => run.policy));
  const storyRunIds = new Set(data.runs.filter(run => run.article_id === articleId).map(run => run.run_id));
  const storyLink = links.demoHref("events", { article: articleId, cutoff });
  return [
    { key: "load", title: "Load the demo", body: "Invented articles and prices, recorded AI answers. Offline and safe.", done: data.articles.length > 0,
      action: <button className="button primary" type="button" disabled={busy} onClick={onDemo}>Load synthetic demo</button> },
    { key: "story", title: "Pick a news story", body: "A crude-oil supply shock hits a paint maker (Berger Paints, syn-002).", done: Boolean(progress.done.story),
      action: <Link className="button primary" href={storyLink}>Open the story</Link> },
    { key: "freeze", title: "Freeze the moment", body: `Set the cutoff to ${formatIst(cutoff)}: only what was known then counts.`, done: policies.size >= 3,
      action: <Link className="button primary" href={storyLink}>Analyse under all three methods</Link> },
    { key: "verdict", title: "Read the verdict", body: "Stock +0.8% vs market, but crude +1.5% hurts paint costs → mixed → Neutral, with a conflict flag.", done: Boolean(progress.done.case),
      action: <Link className="button primary" href={links.demoHref("saved", { article: articleId })}>Open saved result</Link> },
    { key: "next", title: "See what happened next", body: "Five trading days later, measured separately; it can't change the verdict.", done: data.outcomes.some(outcome => storyRunIds.has(outcome.run_id)),
      action: <Link className="button primary" href={links.demoHref("saved", { article: articleId })}>Evaluate later outcomes</Link> },
    { key: "compare", title: "Compare the methods", body: "Same answer from all three methods in replay. The point is cost and agreement, not quality.", done: Boolean(progress.done.comparisons),
      action: <Link className="button primary" href={links.demoHref("comparisons")}>Load comparisons</Link> },
    { key: "lab", title: "Test a price rule", body: "Run a moving-average rule on the synthetic 2015–2020 series, double the costs, then reshuffle returns.", done: Boolean(progress.done.backtest),
      action: <Link className="button primary" href={links.demoHref("lab")}>Open Strategy lab</Link> },
  ];
}

// ---------- overview tour card ----------
export function GuidedTour({ data, links, onDemo, busy }: { data: Workspace; links: Hrefs; onDemo: () => void; busy: boolean }) {
  const steps = useTourSteps(data, links, onDemo, busy);
  const progress = useTourProgress();
  const theme = useTheme();
  const motionOff = useMotionOff();
  const firstOpen = Math.max(0, steps.findIndex(step => !step.done));
  const [viewing, setViewing] = useState<number | null>(null);
  const current = viewing ?? (steps.every(step => step.done) ? steps.length : firstOpen + 1);
  const demo = data.workspace === "demo";
  const doneCount = steps.filter(step => step.done).length;
  if (demo && progress.skipped) {
    return <section className="tour-card tour-card--collapsed" aria-label="Demo tour"><MapIcon size={16} aria-hidden="true" /><p>Demo tour hidden. {doneCount} of {steps.length} steps done.</p><button type="button" className="text-button" onClick={() => setSkipped(false)}>Show demo tour</button></section>;
  }
  return <section className="tour-card" aria-labelledby="tour-title">
    <div className="tour-atmosphere" aria-hidden="true"><Aurora colorStops={["#8aa34a", "#d5b864", "#657c39"]} paused={motionOff} mouseInteraction={false} intro={false} lightMode={theme === "light"} opacity={0.2} amplitude={0.5} layers={1} /></div>
    <div className="tour-heading">
      <div><h2 id="tour-title">{demo ? "Demo tour: from a headline to evidence you can check" : "Your research path"}</h2>
        <p>{demo ? "Seven short steps through the whole workflow. Each step opens the right page with the fields filled in; you can leave the tour at any time." : "Three steps from an article to an auditable result."}</p></div>
      <div className="tour-meta"><span className="tour-progress">{doneCount} of {steps.length} done</span>{demo && <button type="button" className="text-button" onClick={() => setSkipped(true)}><EyeOff size={13} aria-hidden="true" />Skip tour</button>}</div>
    </div>
    <Stepper className="tour-stepper" step={current} onStepChange={setViewing} onFinalStepCompleted={() => setViewing(steps.length + 1)}
      theme={theme} frame={false} width="100%" transition="slide" backButtonText="Back" nextButtonText="Next step" completeButtonText="Finish tour"
      style={{ "--stepper-solid": "var(--mode-primary)", "--stepper-solid-ink": "var(--mode-primary-ink)", "--stepper-ink": "var(--mode-text)", "--stepper-muted": "var(--mode-muted)", "--stepper-well": "var(--mode-raised)", "--stepper-tile": "var(--mode-panel)", "--stepper-tile-edge": "var(--mode-border)", "--stepper-track": "var(--mode-border)" } as React.CSSProperties}
      renderStepIndicator={({ step, currentStep, onStepClick }) => { const item = steps[step - 1]; return <button type="button" className="tour-badge" data-done={item.done ? "" : undefined} aria-current={step === currentStep ? "step" : undefined}
        aria-label={`Step ${step}: ${item.title}${item.done ? " (done)" : ""}`} onClick={() => onStepClick(step)}>{item.done ? <Check size={14} aria-hidden="true" /> : step}</button>; }}
      completedContent={<div className="tour-pane"><h3>Tour complete</h3><p>You have seen the whole workflow. Every result stays in Saved results; use the glossary for any term.</p><button type="button" className="button secondary" onClick={() => setViewing(1)}><RotateCcw size={14} aria-hidden="true" />Restart tour</button></div>}>
      {steps.map((step, index) => <Step key={step.key} title={step.title}>
        <div className="tour-pane">
          <p className="tour-step-label">Step {index + 1} of {steps.length}{step.done && <span className="tour-done"><Check size={12} aria-hidden="true" />Done</span>}</p>
          <h3>{step.title}</h3><p>{step.body}</p>
          <div className="tour-action">{step.action}</div>
        </div>
      </Step>)}
    </Stepper>
  </section>;
}

// ---------- slim bar on other demo pages ----------
export function TourBar({ data, links, onDemo, busy }: { data: Workspace; links: Hrefs; onDemo: () => void; busy: boolean }) {
  const steps = useTourSteps(data, links, onDemo, busy);
  const progress = useTourProgress();
  const [open, setOpen] = useState(true);
  if (data.workspace !== "demo" || progress.skipped) return null;
  const index = steps.findIndex(step => !step.done);
  if (index < 0) return null;
  const step = steps[index];
  return <aside className="tour-bar" aria-label="Demo tour">
    <MapIcon size={15} aria-hidden="true" />
    <span className="tour-bar-step">Demo tour · step {index + 1} of {steps.length}</span>
    {open ? <><strong>{step.title}</strong><span className="tour-bar-body">{step.body}</span><span className="tour-bar-action">{step.action}</span></> : null}
    <span className="tour-bar-links"><Link href={links.href("overview")}>Full tour<ArrowRight size={12} aria-hidden="true" /></Link><button type="button" className="text-button" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Collapse" : "Expand"}</button></span>
  </aside>;
}
