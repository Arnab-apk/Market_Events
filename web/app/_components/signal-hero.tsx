"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowDownToLine, ArrowUpRight, BookOpen, Fingerprint, LoaderCircle, Radio, Sparkles } from "lucide-react";
import { useSyncExternalStore } from "react";
import type { Workspace } from "./types";

const Aurora = dynamic(() => import("./react-bits/Aurora"), { ssr: false });
const subscribeMotion = (notify: () => void) => {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const readMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const serverMotion = () => true;

export function useReducedMotion() {
  return useSyncExternalStore(subscribeMotion, readMotion, serverMotion);
}

export default function SignalHero({ data, paused, busy, onDemo, importHref, labHref }: {
  data: Workspace; paused: boolean; busy: boolean; onDemo: () => void; importHref: string; labHref: string;
}) {
  const reduced = useReducedMotion();
  return <section className="signal-hero" aria-labelledby="signal-title">
    <div className="hero-aurora" aria-hidden="true">
      <Aurora colorStops={["#b9ff66", "#4df3c8", "#6ce5f1", "#775bff"]} height={0.6} amplitude={1.2} blend={0.65} speed={0.45} brightness={0.85} glow={0.7} layers={2} dpr={1} intro={false} paused={paused || reduced} />
    </div>
    <div className="hero-grain" aria-hidden="true" />
    <div className="hero-copy">
      <div className="hero-kicker"><span className="status-dot" />THE MARKET IS NOISY. YOUR RESEARCH SHOULDN’T BE.</div>
      <h1 id="signal-title">Find the signal.<br /><span>Own the insight.</span></h1>
      <p>Connect the headlines to the hard numbers.<br className="desktop-break" /> One workspace for evidence, charts, and your next hypothesis.</p>
      <div className="hero-actions"><Link className="button primary" href={importHref}><ArrowDownToLine size={16} aria-hidden="true" />Import evidence<ArrowUpRight size={15} aria-hidden="true" /></Link><button className="button hero-secondary" disabled={busy} onClick={onDemo}>{busy ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <BookOpen size={16} aria-hidden="true" />}Explore the demo</button></div>
      <div className="hero-proof"><Fingerprint size={15} aria-hidden="true" /><span>Every insight. Every source. Fully traceable.</span></div>
    </div>
    <div className="hero-visual">
      <div className="signal-instrument">
        <div className="instrument-heading"><span><Radio size={13} aria-hidden="true" />EVIDENCE ENGINE</span><span className="instrument-tag">LOCAL</span></div>
        <div className="signal-orbit" aria-hidden="true"><div className="orbit-ring ring-outer" /><div className="orbit-ring ring-inner" /><div className="orbit-sweep" /><div className="orbit-axis horizontal" /><div className="orbit-axis vertical" /><span className="orbit-point point-one" /><span className="orbit-point point-two" /><span className="orbit-point point-three" /><div className="signal-core"><Sparkles size={29} /><span>me<span> / </span></span></div><span className="orbit-coordinate coord-top">SOURCE</span><span className="orbit-coordinate coord-bottom">SIGNAL</span></div>
        <div className="instrument-flow"><span>01 / INGEST</span><i /><span>02 / VERIFY</span><i /><span>03 / RESEARCH</span></div>
        <div className="instrument-foot"><span className="status-dot" />{data.workspace === "demo" ? "SYNTHETIC REPLAY" : "YOUR DATA. YOUR WORKSPACE."}<Fingerprint size={14} aria-hidden="true" /></div>
      </div>
      <Link href={labHref} className="hero-lab-link"><span>Test the thesis in Strategy Lab</span><ArrowUpRight size={16} aria-hidden="true" /></Link>
    </div>
    <span className="hero-edition" aria-hidden="true">MARKET EVENTS / RESEARCH TERMINAL</span>
  </section>;
}
