"use client";

// Shared UI helpers: <Term> tooltips, <Count> (React Bits CountUp that always lands on the exact value),
// <CutoffField> (date + time + timezone instead of raw ISO text), the glossary drawer, time/number
// formatting and plain-English error messages. No API calls.
import { createContext, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { BookOpen, Search, X } from "lucide-react";
import CountUp from "./react-bits/CountUp";
import { useReducedMotion } from "./use-reduced-motion";
import { GLOSSARY, GLOSSARY_ENTRIES, GLOSSARY_GROUPS } from "./glossary";

/** True when ambient motion should stop: the "Effects" toggle is off or the OS asks for reduced motion. */
export const EffectsPaused = createContext(false);
export function useMotionOff() {
  const paused = useContext(EffectsPaused);
  const reduced = useReducedMotion();
  return paused || reduced;
}

// ---------- formatting ----------
const IST = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
const UTC = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
/** "12 Jan 2026, 17:30 IST" */
export const formatIst = (iso: string | null | undefined) => (iso && !Number.isNaN(Date.parse(iso)) ? `${IST.format(new Date(iso))} IST` : "—");
export const formatUtc = (iso: string | null | undefined) => (iso && !Number.isNaN(Date.parse(iso)) ? `${UTC.format(new Date(iso))} UTC` : "");
/** An IST time with the UTC equivalent as a tooltip. */
export function Time({ value }: { value: string | null | undefined }) {
  return <time dateTime={value || undefined} title={formatUtc(value)}>{formatIst(value)}</time>;
}

/** Plain-English messages for errors the API or browser report (UX_AUDIT §3.5). */
export function friendlyError(message: string): string {
  const text = message || "";
  if (/Python API is unavailable|Failed to fetch|NetworkError|ECONNREFUSED/i.test(text)) {
    return "Can't reach the research engine. The local Python service on port 8000 isn't responding. Start the dev stack with npm.cmd run dev, then retry.";
  }
  if (/decision_time|as_of/i.test(text) && /timezone|time zone/i.test(text)) return "Add a timezone. We need to know whether 12:00 means India time or UTC. India (IST) is selected by default.";
  if (/decision_time|as_of/i.test(text)) return "That date and time isn't readable. Use the date and time pickers, or a timestamp like 2026-01-12 17:30 IST.";
  if (/Research dates must satisfy/i.test(text)) return "Choose study dates between 1 Jan 2000 and 31 Dec 2020, with the start on or before the end.";
  if (/walk_forward_split/i.test(text)) return "The walk-forward split must fall after the study start and no later than the study end.";
  if (/replay/i.test(text) && /(unknown|no recorded|not recorded|fixture)/i.test(text)) return "Replay only covers the bundled demo articles. Switch to the Synthetic demo, or set up live models in Connections.";
  if (/Select a company from the active universe/i.test(text)) return "That company isn't in the selected workspace. Pick one from the list.";
  return text.replace(/^Value error,\s*/i, "").replace(/(^|;\s*)[\w.]+:\s*Value error,\s*/g, "$1");
}

// ---------- tooltips ----------
/** A term with a dotted underline; hover or focus shows its one-line explanation from the glossary. */
export function Term({ name, children, tip }: { name: string; children?: ReactNode; tip?: string }) {
  const id = useId();
  const ref = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const text = tip ?? GLOSSARY[name]?.text;
  if (!text) return <>{children ?? name}</>;
  const show = () => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const width = Math.min(300, window.innerWidth - 24);
    const left = Math.max(12, Math.min(box.left, window.innerWidth - width - 12));
    const below = box.bottom + 8;
    setPosition({ left, top: below + 140 > window.innerHeight ? Math.max(12, box.top - 8 - 120) : below });
  };
  return <>
    <button ref={ref} type="button" className="term" aria-describedby={id} onMouseEnter={show} onFocus={show} onMouseLeave={() => setPosition(null)} onBlur={() => setPosition(null)}
      onKeyDown={event => { if (event.key === "Escape") setPosition(null); }} onClick={event => { event.preventDefault(); if (position) setPosition(null); else show(); }}>{children ?? name}</button>
    <span role="tooltip" id={id} className="term-tip" data-open={position ? "" : undefined} style={position ? { left: position.left, top: position.top } : undefined}>{text}</span>
  </>;
}

// ---------- numbers ----------
/** React Bits CountUp for headline numbers. Always ends on exactly format(value); static when motion is off. */
export function Count({ value, format }: { value: number | null | undefined; format: (value: number) => string }) {
  const motionOff = useMotionOff();
  if (value == null || !Number.isFinite(value)) return <>—</>;
  if (motionOff) return <>{format(value)}</>;
  return <CountUp key={value} to={value} from={0} duration={0.4} trigger="view" formatter={format} />;
}

// ---------- cutoff field ----------
type Zone = "IST" | "UTC";
const OFFSET: Record<Zone, number> = { IST: 330, UTC: 0 };
function split(iso: string, zone: Zone) {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return { date: "", time: "" };
  const shifted = new Date(time + OFFSET[zone] * 60_000).toISOString();
  return { date: shifted.slice(0, 10), time: shifted.slice(11, 16) };
}
function compose(date: string, time: string, zone: Zone) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return "";
  const utc = Date.parse(`${date}T${time}:00Z`) - OFFSET[zone] * 60_000;
  return Number.isNaN(utc) ? "" : new Date(utc).toISOString().replace(".000Z", "Z");
}
/** Date + time + timezone (IST by default). Emits an ISO UTC timestamp, or "" while incomplete. */
export function CutoffField({ label, value, onChange, presets = [], hint }: {
  label: ReactNode; value: string; onChange: (iso: string) => void; presets?: { label: string; value: string }[]; hint?: string;
}) {
  const id = useId();
  const [zone, setZone] = useState<Zone>("IST");
  const [fields, setFields] = useState(() => split(value, "IST"));
  const [synced, setSynced] = useState(value);
  if (value !== synced) { setSynced(value); if (value) setFields(split(value, zone)); }
  const invalid = !value;
  const update = (next: { date: string; time: string }, nextZone = zone) => {
    setFields(next);
    const iso = compose(next.date, next.time, nextZone);
    setSynced(iso); onChange(iso);
  };
  return <fieldset className="cutoff-field">
    <legend>{label}</legend>
    <div className="cutoff-inputs">
      <label><span className="sr-only">Date</span><input type="date" value={fields.date} aria-invalid={invalid || undefined} aria-describedby={`${id}-note`} onChange={event => update({ ...fields, date: event.target.value })} /></label>
      <label><span className="sr-only">Time</span><input type="time" value={fields.time} aria-invalid={invalid || undefined} aria-describedby={`${id}-note`} onChange={event => update({ ...fields, time: event.target.value })} /></label>
      <label><span className="sr-only">Timezone</span><select value={zone} onChange={event => { const next = event.target.value as Zone; setZone(next); update(fields, next); }}><option value="IST">India (IST)</option><option value="UTC">UTC</option></select></label>
      {presets.map(preset => <button key={preset.value} type="button" className="chip" onClick={() => { setFields(split(preset.value, zone)); setSynced(preset.value); onChange(preset.value); }}>{preset.label}</button>)}
    </div>
    <p id={`${id}-note`} className={invalid ? "field-error" : "field-note"} role={invalid ? "alert" : undefined}>
      {invalid ? "That date and time isn't readable. Use the date and time pickers, or a timestamp like 2026-01-12 17:30 IST." : <>= {formatIst(value)} ({formatUtc(value)}){hint ? `. ${hint}` : ""}</>}
    </p>
  </fieldset>;
}

// ---------- glossary drawer ----------
export function GlossaryButton({ className = "icon-button", label = "Glossary" }: { className?: string; label?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState("");
  const matches = useMemo(() => GLOSSARY_ENTRIES.filter(entry => `${entry.term} ${entry.text}`.toLowerCase().includes(query.toLowerCase())), [query]);
  useEffect(() => {
    const dialog = ref.current;
    const close = (event: MouseEvent) => { if (event.target === dialog) dialog?.close(); };
    dialog?.addEventListener("click", close);
    return () => dialog?.removeEventListener("click", close);
  }, []);
  return <>
    <button type="button" className={className} onClick={() => ref.current?.showModal()} title="What do these terms mean?"><BookOpen size={15} aria-hidden="true" /><span>{label}</span></button>
    <dialog ref={ref} className="glossary-drawer" aria-labelledby="glossary-title">
      <div className="glossary-head"><h2 id="glossary-title">Glossary</h2><button type="button" className="icon-button" aria-label="Close glossary" onClick={() => ref.current?.close()}><X size={16} /></button></div>
      <p className="glossary-intro">Every number and label in this workspace, in plain English. Underlined terms on each page show the same text on hover or focus.</p>
      <label className="glossary-search"><Search size={14} aria-hidden="true" /><span className="sr-only">Search the glossary</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search terms…" /></label>
      {GLOSSARY_GROUPS.map(group => { const list = matches.filter(entry => entry.group === group); return list.length ? <section key={group}><h3>{group}</h3><dl>{list.map(entry => <div key={entry.term}><dt>{entry.term}</dt><dd>{entry.text}</dd></div>)}</dl></section> : null; })}
      {!matches.length && <p className="muted">No terms match “{query}”.</p>}
    </dialog>
  </>;
}
