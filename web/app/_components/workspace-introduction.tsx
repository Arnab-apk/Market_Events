"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Clock3, FileText, FolderCheck } from "lucide-react";

const seenKey = "market-events:intro-seen:v1";
let seenThisSession = false;

function firstVisit() {
  if (seenThisSession) return false;
  try { return localStorage.getItem(seenKey) !== "1"; }
  catch { return true; }
}

/** Home mounts after the workspace loads on the client. Deep links open their requested view directly. */
export function WorkspaceIntroduction({ aboutHref }: { aboutHref: string }) {
  const [visible, setVisible] = useState(firstVisit);
  useEffect(() => {
    if (!visible) return;
    seenThisSession = true;
    try { localStorage.setItem(seenKey, "1"); }
    catch { /* The in-memory flag still lasts for this session. */ }
  }, [visible]);
  if (!visible) return null;

  function dismiss() {
    setVisible(false);
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }

  return <section className="desk-intro" aria-labelledby="intro-title">
    <div className="intro-copy">
      <h2 id="intro-title">From headline<br />to <em>evidence.</em></h2>
      <p>Pick a company story, set a decision time, and see which prices and sources support the verdict. Save the analysis to compare it with what happened next.</p>
      <div className="intro-actions">
        <Link className="button intro-cta" href={aboutHref} onClick={dismiss}>How it works <ArrowRight size={16} aria-hidden="true" /></Link>
        <button className="intro-skip" type="button" onClick={dismiss}>Skip introduction</button>
      </div>
    </div>
    <div className="intro-figure" aria-hidden="true">
      <div className="intro-sheet intro-source">
        <span><FileText size={16} />News story</span>
        <div className="intro-lines"><i /><i /><i /></div>
      </div>
      <div className="intro-sheet intro-cutoff">
        <span><Clock3 size={16} />Decision cutoff</span>
        <div className="intro-axis" />
      </div>
      <div className="intro-sheet intro-verdict">
        <span><FolderCheck size={16} />Saved verdict</span>
        <div className="intro-lines"><i /><i /></div>
      </div>
    </div>
  </section>;
}
