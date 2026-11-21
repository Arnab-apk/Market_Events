"use client";

// The three-step "Your research path" card on the overview (import → investigate → inspect).
// Reads article and run counts from the Workspace data; no API calls.
import Link from "next/link";
import { ArrowRight, Check, FilePlus2, SearchCheck, BookOpenCheck, Sparkles } from "lucide-react";
import type { Workspace } from "./types";
import SpotlightCard from "./react-bits/SpotlightCard";
import Aurora from "./react-bits/Aurora";
import { useTheme } from "./theme-toggle";

export default function ResearchGuide({ data, href, paused }: {
  data: Workspace; href: (view: string) => string; paused: boolean;
}) {
  const theme = useTheme();
  const hasSources = data.articles.length > 0;
  const hasResults = data.runs.length > 0;
  const nextStep = !hasSources ? 0 : !hasResults ? 1 : 2;
  const steps = [
    { view: "imports", icon: FilePlus2, title: "Add your evidence", description: "Import a dated article and market history, or enter an article manually.", action: "Import evidence", done: hasSources },
    { view: "events", icon: SearchCheck, title: "Investigate an event", description: "Choose a source and a decision cutoff. See what the available evidence supports.", action: "Start event research", done: hasResults },
    { view: "saved", icon: BookOpenCheck, title: "Inspect the result", description: "Review the score, missing inputs, original sources and model audit together.", action: "Open saved results", done: false },
  ];
  return <section className="research-guide" aria-labelledby="research-guide-title">
    <div className="research-guide-atmosphere" aria-hidden="true"><Aurora colorStops={["#8aa34a", "#d5b864", "#657c39"]} paused mouseInteraction={false} intro={false} time={1} lightMode={theme === "light"} opacity={0.18} amplitude={0.4} layers={1} /></div>
    <div className="research-guide-heading"><div><span className="research-kicker"><Sparkles size={12} aria-hidden="true" />YOUR RESEARCH PATH</span><h2 id="research-guide-title">From a market headline to evidence you can inspect.</h2><p>Follow a source, examine its market context, and keep a record of how you reached a conclusion.</p></div><span className="research-mode-label">{data.workspace === "demo" ? "Synthetic demo · recorded replay" : "Your local research workspace"}</span></div>
    <ol className="research-steps">{steps.map((step, index) => <li key={step.view}>
      <SpotlightCard className={`research-step ${nextStep === index ? "is-next" : ""}`} theme={theme} paused={paused} spotlightColor={theme === "dark" ? "#c9f56b" : "#6b8d28"} intensity={0.12} borderGlow={0.35} flare={false} proximity={30}>
        <Link href={href(step.view)} aria-current={nextStep === index ? "step" : undefined}>
          <div className="research-step-top"><span className="research-step-icon"><step.icon size={19} aria-hidden="true" /></span><span className="research-step-state">{step.done ? <><Check size={12} aria-hidden="true" />Ready</> : nextStep === index ? "Start here" : `Step ${index + 1}`}</span></div>
          <h3><span>0{index + 1}</span>{step.title}</h3><p>{step.description}</p><span className="research-step-action">{step.action}<ArrowRight size={14} aria-hidden="true" /></span>
        </Link>
      </SpotlightCard>
    </li>)}</ol>
    <div className="research-guide-foot"><span>Want to test a price-based hypothesis?</span><Link href={href("lab")}>Explore historical strategies<ArrowRight size={13} aria-hidden="true" /></Link><span>Saved observations. Traceable sources. No order execution.</span></div>
  </section>;
}
