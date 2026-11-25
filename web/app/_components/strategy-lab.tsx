"use client";

// Lab › Backtest and Lab › Monte Carlo. Local price history with indicators (POST /api/history), an optional
// explicit provider download (POST /api/sync/historical), a backtest with fees and slippage (POST /api/backtest,
// optional walk-forward split) and a Monte Carlo bootstrap of the backtest's own returns (POST /api/monte-carlo).
// `tab` picks the part to show; state lives here, so switching between the two tabs keeps it.
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowDownToLine, LoaderCircle, Pause, Play, RotateCcw } from "lucide-react";
import type { PanelProps } from "./research-app";
import { downloadJson, format, percent, rupees } from "./types";
import { GLOSSARY } from "./glossary";
import { Term } from "./ui";
import { markTourStep } from "./demo-tour";
import type { Backtest, History, Simulation } from "./types";
import { EquityChart, PriceChart } from "./research-charts";
import { StatTile } from "./simple-ui";

type Manifest = Record<string, unknown>;
type StudyHistory = History & { manifest?: Manifest };
type Segment = { actual_start: string; actual_end: string; bars: number; metrics: Record<string, number | null>; open_position: Record<string, unknown> | null };
type StudyBacktest = Backtest & { manifest?: Manifest; walk_forward?: { split_date: string; in_sample: Segment; out_of_sample: Segment; assumptions: string[] } | null };
type StudySimulation = Simulation & { manifest?: Manifest };
export type LabTab = "backtest" | "montecarlo";
const END = "2020-12-31";
const INDICATORS = [ ["sma20", "SMA 20"], ["sma50", "SMA 50"], ["sma200", "SMA 200"], ["ema20", "EMA 20"], ["ema50", "EMA 50"], ["rsi14", "RSI 14"], ["macd", "MACD"], ["bollinger", "Bollinger bands"], ["atr14", "ATR 14"], ["adx14", "ADX 14"], ["volume", "Volume"] ];
const STRATEGIES = [ ["sma_cross", "SMA crossover"], ["ema_cross", "EMA crossover"], ["buy_hold", "Buy and hold"], ["rsi_reversion", "RSI reversion"], ["macd_cross", "MACD crossover"], ["bollinger_reversion", "Bollinger reversion"] ];
/** One plain sentence per rule, including the fixed rules that have no parameters (UX_AUDIT §3.4). */
const RULES: Record<string, string> = { sma_cross: GLOSSARY["SMA / EMA crossover"].text, ema_cross: GLOSSARY["SMA / EMA crossover"].text, buy_hold: GLOSSARY["Buy and hold"].text, rsi_reversion: GLOSSARY["RSI reversion"].text, macd_cross: GLOSSARY["MACD crossover"].text, bollinger_reversion: GLOSSARY["Bollinger reversion"].text };
const LOW_SAMPLE = 30;
const signed = (value: number | null | undefined) => value == null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
const message = (reason: unknown) => reason instanceof Error ? reason.message : "The request could not be completed.";
const tone = (value: number | null | undefined) => value == null || value === 0 ? undefined : value > 0 ? "success" as const : "danger" as const;
const lowSample = (result: StudyBacktest) => result.metrics.closed_trades != null && result.metrics.closed_trades < LOW_SAMPLE;

export default function StrategyLab(props: PanelProps & { tab?: string }) {
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const identity = JSON.stringify([props.data.workspace, props.data.universe, props.data.observations_count, props.data.companies.map(company => [company.instrument_id, company.bars, company.end])]);
  return <Study key={identity} {...props} tab={props.tab === "montecarlo" ? "montecarlo" : "backtest"} receipt={receipt} onReceipt={setReceipt} />;
}

function Study({ api, data, refresh, href, tab, receipt, onReceipt }: PanelProps & {
  tab: LabTab; receipt: Record<string, unknown> | null; onReceipt: (value: Record<string, unknown> | null) => void;
}) {
  const [company, setCompany] = useState(data.companies.find(item => item.research_bars > 0)?.instrument_id || data.companies[0]?.instrument_id || "");
  const [start, setStart] = useState("2015-01-01"), [end, setEnd] = useState(END);
  const [strategy, setStrategy] = useState("sma_cross");
  const [capital, setCapital] = useState(100000), [fee, setFee] = useState(10), [slippage, setSlippage] = useState(5);
  const [fast, setFast] = useState(20), [slow, setSlow] = useState(50), [buy, setBuy] = useState(30), [sell, setSell] = useState(70);
  const [selected, setSelected] = useState(["sma20", "sma50", "volume"]);
  const [walkForward, setWalkForward] = useState(false), [split, setSplit] = useState("2020-01-01");
  const [history, setHistory] = useState<StudyHistory | null>(null);
  const [result, setResult] = useState<StudyBacktest | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const sequence = useRef(0), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const request = { company_id: company, start_date: start, end_date: end };
  const params = { strategy, initial_capital: capital, cost_bps: fee, slippage_bps: slippage, fast_period: fast, slow_period: slow, rsi_buy: buy, rsi_sell: sell, ...(walkForward ? { walk_forward_split: split } : {}) };
  const resultScope = JSON.stringify({ ...request, ...params });
  function invalidate(historyToo = false) {
    sequence.current++; setResult(null); setError(""); setBusy("");
    if (historyToo) { setHistory(null); onReceipt(null); }
  }
  const validDates = Boolean(company && start && end && start >= "2000-01-01" && start <= end && end <= END);
  const selectedCompany = data.companies.find(item => item.instrument_id === company);
  const demoSeries = data.companies.find(item => item.instrument_id.startsWith("SYNTHETIC:") && item.research_bars > 0);
  const providerAllowed = data.workspace === "local" && data.universe === "live";
  const provider = data.readiness.find(item => /upstox|market.data|historical/i.test(`${item.capability} ${item.name}`));
  async function load(kind: "history" | "backtest") {
    if (!validDates) { setError("Select a company and dates between 2000-01-01 and 2020-12-31, with start on or before end."); return; }
    if (kind === "backtest" && ((strategy.includes("cross") && strategy !== "macd_cross" && fast >= slow) || buy >= sell)) {
      setError("Fast period must be below slow period, and RSI buy must be below RSI sell."); return;
    }
    const ticket = ++sequence.current;
    setBusy(kind); setError(""); setResult(null);
    try {
      if (kind === "history") {
        setHistory(null);
        const next = await api<StudyHistory>("history", request);
        if (mounted.current && ticket === sequence.current) setHistory(next);
      } else {
        const [next, prices] = await Promise.all([
          api<StudyBacktest>("backtest", { ...request, ...params }),
          history ? Promise.resolve(history) : api<StudyHistory>("history", request),
        ]);
        if (mounted.current && ticket === sequence.current) { setResult(next); setHistory(prices); markTourStep("backtest"); }
      }
    } catch (reason) { if (mounted.current && ticket === sequence.current) setError(message(reason)); }
    finally { if (mounted.current && ticket === sequence.current) setBusy(""); }
  }
  async function downloadHistory() {
    if (!validDates) { setError("Select an instrument and a valid historical date range first."); return; }
    const ticket = ++sequence.current;
    setBusy("download"); setError(""); setResult(null); setHistory(null); onReceipt(null);
    try {
      const report = await api<Record<string, unknown>>("sync/historical", { company_ids: [company], start_date: start, end_date: end, include_news: false });
      if (mounted.current && ticket === sequence.current) { onReceipt(report); await refresh(); }
    } catch (reason) { if (mounted.current && ticket === sequence.current) setError(message(reason)); }
    finally { if (mounted.current && ticket === sequence.current) setBusy(""); }
  }
  function toggleIndicator(key: string) { setSelected(previous => previous.includes(key) ? previous.filter(item => item !== key) : [...previous, key]); }
  const strategyName = STRATEGIES.find(([key]) => key === strategy)?.[1] ?? strategy;
  const warnings = <>
    {(data.workspace === "demo" || data.universe === "demo") && !data.companies.some(item => item.research_bars > 0) && <div className="alert warning">This demo has no prices before 2021, so the Lab has nothing to study. Switch to “My data – real companies” to download history.</div>}
    {company.startsWith("SYNTHETIC:") && <div className="alert warning">Synthetic test series: for trying the tool only, not evidence of performance.</div>}
  </>;
  const errorLine = error && <div className="alert error" role="alert">{error}</div>;
  const monteCarlo = result && <MonteCarlo key={resultScope} api={api} backtest={result} study={request} params={params} historyManifest={history?.manifest} />;

  const intro = !result && <section className="card flow"><div className="card-head"><h2><Term name="Monte Carlo (block bootstrap)">Monte Carlo</Term></h2></div>
      <p>Monte Carlo reshuffles a backtest’s own past daily returns to show the spread of luck, so it needs a backtest first.</p>
      <p className="muted small">Current settings: {selectedCompany?.name ?? "no company"} · {start} → {end} · {strategyName} · {rupees(capital)} · costs {fee} + {slippage} bps</p>
      <div className="actions"><button type="button" className="button primary" disabled={Boolean(busy) || !validDates} onClick={() => void load("backtest")}>{busy === "backtest" && <LoaderCircle className="spin" size={15} aria-hidden="true" />}Run backtest with these settings</button><Link className="button secondary" href={href("lab", { tab: "backtest" })}>Change settings</Link></div>
      {errorLine}
    </section>;

  const backtestView = <>
    <section className="card flow">
      <div className="card-head"><h2>Backtest a rule</h2><span className="muted small">Long or cash · signal at close → trade at next open · costs on every fill</span></div>
      <form className="stack" onSubmit={event => { event.preventDefault(); void load("backtest"); }}>
        <div className="form-grid">
          <label className="field">Company<select required value={company} onChange={event => { invalidate(true); setCompany(event.target.value); }}><option value="" disabled>Select a company</option>{data.companies.map(item => <option key={item.instrument_id} value={item.instrument_id}>{item.name} · {item.research_bars} days before 2021</option>)}</select></label>
          <label className="field">Start<input type="date" required min="2000-01-01" max={END} value={start} onChange={event => { invalidate(true); setStart(event.target.value); }} /></label>
          <label className="field"><span>End (latest <Term name="2020 boundary">31 Dec 2020</Term>)</span><input type="date" required min={start || "2000-01-01"} max={END} value={end} onChange={event => { invalidate(true); setEnd(event.target.value); }} /></label>
          <label className="field">Strategy<select value={strategy} onChange={event => { invalidate(); setStrategy(event.target.value); }}>{STRATEGIES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><small>Rule: {RULES[strategy]}</small></label>
          <NumberField term="Initial capital (INR)" label="Initial capital (INR)" value={capital} min={1000} max={1e12} step={1000} onChange={value => { invalidate(); setCapital(value); }} />
          <NumberField term="Fee per fill (bps)" label="Fee per fill (bps)" value={fee} min={0} max={9999} step={0.1} onChange={value => { invalidate(); setFee(value); }} />
          <NumberField term="Slippage per fill (bps)" label="Slippage per fill (bps)" value={slippage} min={0} max={9999} step={0.1} onChange={value => { invalidate(); setSlippage(value); }} />
        </div>
        <details className="fold"><summary>Advanced parameters</summary><div className="form-grid">
          {["sma_cross", "ema_cross"].includes(strategy) && <><NumberField term="Fast / Slow period" label="Fast period (sessions)" value={fast} min={1} max={9999} onChange={value => { invalidate(); setFast(value); }} /><NumberField term="Fast / Slow period" label="Slow period (sessions)" value={slow} min={2} max={10000} onChange={value => { invalidate(); setSlow(value); }} /></>}
          {strategy === "rsi_reversion" && <><NumberField label="RSI buy at or below" value={buy} min={0} max={100} onChange={value => { invalidate(); setBuy(value); }} /><NumberField label="RSI sell at or above" value={sell} min={0} max={100} onChange={value => { invalidate(); setSell(value); }} /></>}
          <label className="check-label"><input type="checkbox" checked={walkForward} onChange={event => { invalidate(); setWalkForward(event.target.checked); }} /><Term name="Walk-forward split">Also test a walk-forward split</Term></label>
          {walkForward && <label className="field">Out-of-sample starts<input type="date" required min={start} max={end} value={split} onChange={event => { invalidate(); setSplit(event.target.value); }} /><small>Chosen in advance. The same fixed rule runs separately before and after this date; nothing is tuned.</small></label>}
        </div></details>
        <div className="actions">
          <button type="submit" className="button primary" disabled={Boolean(busy) || !validDates}>{busy === "backtest" ? <LoaderCircle className="spin" size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}Run backtest</button>
          <button type="button" className="button secondary" disabled={Boolean(busy) || !validDates} onClick={() => void load("history")}>{busy === "history" && <LoaderCircle size={15} className="spin" aria-hidden="true" />}Load local history</button>
          <p className="muted small">{selectedCompany?.research_bars || 0} saved days before 2021 · reads saved prices only · 1 bp = 0.01%</p>
        </div>
      </form>
      {!selectedCompany?.research_bars && <div className="state-card"><strong>No prices before 2021 for this company.</strong><p>In the demo, pick the synthetic lab series. For real data, add an Upstox token in Settings › Connections and download history.</p><div className="actions">{demoSeries && <button type="button" className="button secondary" onClick={() => { invalidate(true); setCompany(demoSeries.instrument_id); }}>Pick demo series</button>}<Link className="button secondary" href={href("settings", { tab: "connections" })}>Open Connections</Link></div></div>}
      <details className="fold" open={!selectedCompany?.research_bars && providerAllowed}><summary>Download daily prices from Upstox (explicit action)</summary>
        <p className="muted small">Uses the company and dates above. Candles only; benchmarks are included. Provider keys stay on the Python server.</p>
        {!providerAllowed ? <p className="alert warning">Downloads need the “My data – real companies” workspace.</p> : provider && !provider.configured ? <p className="alert warning">Upstox token missing. Set it up in Settings › Connections, then refresh. No token is shown or exported.</p> : null}
        <div className="actions"><button type="button" className="button secondary" disabled={Boolean(busy) || !validDates || !providerAllowed} onClick={() => void downloadHistory()}>{busy === "download" ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <ArrowDownToLine size={15} aria-hidden="true" />}Download historical candles</button><p className="muted small">Dates capped at 2020-12-31. Downloads keep their actual receipt time.</p></div>
        {receipt && <div role="status"><p>{String(receipt.observations_added ?? 0)} price rows added · {String(receipt.network_requests ?? 0)} provider requests</p><pre className="json">{JSON.stringify({ errors: receipt.errors, coverage: receipt.coverage }, null, 2)}</pre><button type="button" className="button secondary" onClick={() => downloadJson(receipt, "history-receipt.json")}>Download receipt JSON</button></div>}
      </details>
      {errorLine}
    </section>

    {result && <>
      <ResultVerdict result={result} />
      <div className="stat-grid">
        <StatTile label={<Term name="Strategy return" />} value={signed(result.metrics.total_return)} tone={tone(result.metrics.total_return)} detail="After fees and slippage" />
        <StatTile label={<Term name="Maximum drawdown" />} value={signed(result.metrics.max_drawdown)} detail="Worst fall from a peak" />
        <StatTile label={<Term name="Sharpe ratio" />} value={format(result.metrics.sharpe)} detail={lowSample(result) ? <span className="low-sample-flag">Low sample</span> : "Zero risk-free rate"} />
        <StatTile label={<Term name="Win rate / Closed trades">Closed trades</Term>} value={format(result.metrics.closed_trades, 0)} detail={`Win rate ${percent(result.metrics.win_rate)}`} />
      </div>
      <dl className="facts"><div><dt><Term name="Buy & hold return" /></dt><dd>{signed(result.metrics.benchmark_return)}</dd></div>{result.metrics.probabilistic_sharpe != null && <div><dt><Term name="Probabilistic Sharpe (PSR)" /></dt><dd>{percent(result.metrics.probabilistic_sharpe)} <span className="muted small">(one configuration; not adjusted for settings tried)</span></dd></div>}<div><dt><Term name="CAGR" /></dt><dd>{percent(result.metrics.cagr)}</dd></div></dl>
      {lowSample(result) && <div className="alert warning low-sample" role="note"><strong>Low sample size — fewer than {LOW_SAMPLE} closed trades.</strong> This backtest closed only {format(result.metrics.closed_trades, 0)} {result.metrics.closed_trades === 1 ? "trade" : "trades"}, so the Sharpe ratio, PSR and win rate can swing a lot on a few trades. Treat them as descriptive, not as evidence of an edge.</div>}
      <section className="card flow"><div className="card-head"><h2>Equity & execution report</h2><button type="button" className="button secondary" onClick={() => downloadJson(enrichReport(result, request, params, history?.manifest), "backtest.json")}><ArrowDownToLine size={14} aria-hidden="true" />Download backtest JSON</button></div>
        <EquityChart points={result.equity} />
        <p className="muted">{result.open_position ? <><Term name="Open position">The position is still open</Term> at the end. Equity uses its last close; no exit fee is charged.</> : "No open position at the end."}</p>
        <details className="fold"><summary>Trades ({result.trades.length})</summary><RecordTable rows={result.trades} empty="No trades. The rule never triggered in this window, so the strategy stayed in cash." /></details>
        {result.walk_forward && <WalkForward split={result.walk_forward} />}
        <details className="fold"><summary>Execution and research assumptions</summary><ul className="summary-list">{result.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
        <p className="muted small">Next: <Link href={href("lab", { tab: "montecarlo" })}>see how much luck could change this (Monte Carlo)</Link>.</p>
      </section>
    </>}

    {history ? <section className="card flow"><div className="card-head"><h2>{selectedCompany?.name || company} · prices</h2><button type="button" className="button secondary" onClick={() => downloadJson(history, "study-history.json")}><ArrowDownToLine size={14} aria-hidden="true" />History JSON</button></div>
      <p className="muted small">{history.bars.length} trading days · {history.actual_start} to {history.actual_end}</p>
      <div className="chips" role="group" aria-label="Chart indicators">{INDICATORS.map(([key, label]) => <button type="button" className="chip" key={key} aria-pressed={selected.includes(key)} onClick={() => toggleIndicator(key)}>{label}</button>)}</div>
      <PriceChart bars={history.bars} indicators={history.indicators} selected={selected} />
      <p className="muted small">Indicators without enough history are left out. RSI, MACD, ATR, ADX and volume get their own panes.</p>
    </section> : null}
  </>;
  // Same tree position on both tabs, so the Monte Carlo state survives switching tabs.
  return <>
    {warnings}
    {tab === "montecarlo" ? intro : backtestView}
    {monteCarlo && <div hidden={tab !== "montecarlo"}>{monteCarlo}</div>}
  </>;
}

/** One plain sentence: what the rule did against simply holding. */
function ResultVerdict({ result }: { result: StudyBacktest }) {
  const m = result.metrics;
  if (!result.trades.length) return <p className="verdict">The rule never triggered in this window, so the strategy stayed in cash. Try a longer window or different thresholds.</p>;
  const beat = (m.total_return ?? 0) > (m.benchmark_return ?? 0);
  return <p className="verdict">After all costs the rule returned <strong>{signed(m.total_return ?? 0)}</strong>, {beat ? "ahead of" : "behind"} buy and hold at <strong>{signed(m.benchmark_return ?? 0)}</strong>, with a worst fall of <strong>{signed(m.max_drawdown ?? 0)}</strong> along the way.</p>;
}

/** In-sample vs out-of-sample metrics for one fixed configuration. */
function WalkForward({ split }: { split: NonNullable<StudyBacktest["walk_forward"]> }) {
  const rows: [string, string, (value: number | null | undefined) => string][] = [["Strategy return", "total_return", signed], ["Buy & hold return", "benchmark_return", signed], ["Maximum drawdown", "max_drawdown", signed], ["Sharpe ratio", "sharpe", value => format(value)], ["Probabilistic Sharpe (PSR)", "probabilistic_sharpe", value => percent(value)], ["Win rate / Closed trades", "closed_trades", value => format(value, 0)]];
  const segments: [string, Segment][] = [["In-sample", split.in_sample], ["Out-of-sample", split.out_of_sample]];
  return <details className="fold walk-forward" open><summary><Term name="Walk-forward split">Walk-forward check</Term> · split on {split.split_date}</summary>
    <p className="muted small">The settings were fixed in advance, not tuned on either part.</p>
    <div className="table-scroll"><table className="fit-table"><thead><tr><th scope="col">Metric</th>{segments.map(([label, segment]) => <th scope="col" key={label}>{label}<small className="cell-note">{segment.actual_start} → {segment.actual_end} · {segment.bars} sessions</small></th>)}</tr></thead>
      <tbody>{rows.map(([label, key, show]) => <tr key={key}><td><Term name={label}>{key === "closed_trades" ? "Closed trades" : label}</Term></td>{segments.map(([name, segment]) => <td key={name} className="numeric">{show(segment.metrics[key])}{key === "closed_trades" && (segment.metrics[key] ?? 0) < LOW_SAMPLE ? <small className="cell-note low-sample-flag">Low sample</small> : null}</td>)}</tr>)}</tbody></table></div>
    <ul className="summary-list">{split.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>;
}

function NumberField({ label, term, value, min, max, step = 1, onChange }: { label: string; term?: string; value: number; min: number; max: number; step?: number; onChange: (value: number) => void }) {
  return <label className="field">{term ? <Term name={term}>{label}</Term> : label}<input type="number" required min={min} max={max} step={step} value={Number.isFinite(value) ? value : ""} onChange={event => onChange(event.target.valueAsNumber)} /></label>;
}

function enrichReport<T extends { manifest?: Manifest }>(result: T, study: { company_id: string; start_date: string; end_date: string }, params: object, supporting?: Manifest) {
  return { ...result, manifest: { ...supporting, ...result.manifest, params: { ...study, ...params }, study_dates: { requested_start: study.start_date, requested_end: study.end_date, actual_start: result.manifest?.actual_start || supporting?.actual_start, actual_end: result.manifest?.actual_end || supporting?.actual_end }, supporting_observation_ids: result.manifest?.supporting_observation_ids || supporting?.supporting_observation_ids || [], synthetic: study.company_id.startsWith("SYNTHETIC:") } };
}

function RecordTable({ rows, empty }: { rows: Record<string, unknown>[]; empty: string }) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  const columns = Object.keys(rows[0]);
  return <div className="table-scroll"><table><thead><tr>{columns.map(key => <th scope="col" key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map(key => <td key={key}>{typeof row[key] === "number" ? format(row[key] as number, 4) : row[key] == null ? "—" : String(row[key])}</td>)}</tr>)}</tbody></table></div>;
}

function MonteCarlo({ api, backtest, study, params, historyManifest }: { api: PanelProps["api"]; backtest: StudyBacktest; study: { company_id: string; start_date: string; end_date: string }; params: object; historyManifest?: Manifest }) {
  const [paths, setPaths] = useState(300), [horizon, setHorizon] = useState(252), [seed, setSeed] = useState(42), [block, setBlock] = useState(Math.min(5, backtest.daily_returns.length));
  const [result, setResult] = useState<StudySimulation | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const sequence = useRef(0), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const initial = Number((params as { initial_capital: number }).initial_capital);
  const simulationParams = { initial_capital: initial, simulations: paths, horizon, seed, block_size: block };
  function invalidate() { sequence.current++; setResult(null); setError(""); setBusy(false); }
  async function simulate() {
    const ticket = ++sequence.current; setBusy(true); setError(""); setResult(null);
    try {
      const next = await api<StudySimulation>("monte-carlo", { daily_returns: backtest.daily_returns, ...simulationParams });
      if (mounted.current && ticket === sequence.current) setResult(next);
    } catch (reason) { if (mounted.current && ticket === sequence.current) setError(message(reason)); }
    finally { if (mounted.current && ticket === sequence.current) setBusy(false); }
  }
  return <section className="card flow"><div className="card-head"><h2><Term name="Monte Carlo (block bootstrap)">Monte Carlo</Term></h2><span className="muted small">Reshuffles chunks of this backtest’s own daily returns · not a forecast</span></div>
    <form className="stack" onSubmit={event => { event.preventDefault(); void simulate(); }}>
      <div className="form-grid"><NumberField term="Random seed" label="Random seed" value={seed} min={0} max={4294967295} onChange={value => { invalidate(); setSeed(value); }} /><NumberField term="Simulated paths / Horizon" label="Simulated paths" value={paths} min={10} max={1000} onChange={value => { invalidate(); setPaths(value); }} /><NumberField term="Simulated paths / Horizon" label="Horizon (trading days)" value={horizon} min={1} max={1000} onChange={value => { invalidate(); setHorizon(value); }} /><NumberField term="Block size" label="Block size (returns)" value={block} min={1} max={Math.min(252, backtest.daily_returns.length)} onChange={value => { invalidate(); setBlock(value); }} /></div>
      <div className="actions"><button type="submit" className="button primary" disabled={busy || backtest.daily_returns.length < 5}>{busy ? <LoaderCircle className="spin" size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}Simulate return paths</button><p className="muted small">{backtest.daily_returns.length} daily returns from the backtest · starts paused · no provider or model calls</p></div>
    </form>
    {backtest.daily_returns.length < 5 && <p className="alert warning">At least five daily returns are needed. Use a longer backtest window.</p>}
    {error && <p className="alert error" role="alert">{error}</p>}
    {result && <>
      <div className="stat-grid">
        <StatTile label={<Term name="Resampled loss frequency" />} value={percent(result.metrics.probability_loss)} />
        <StatTile label={<Term name="Median terminal capital" />} value={rupees(result.metrics.median_terminal)} />
        <StatTile label={<Term name="p05 / p95 terminal capital">p05 terminal capital</Term>} value={rupees(result.metrics.p05_terminal)} />
        <StatTile label={<Term name="p05 / p95 terminal capital">p95 terminal capital</Term>} value={rupees(result.metrics.p95_terminal)} />
      </div>
      <MonteCarloChart result={result} start={initial} />
      <p className="muted">{paths} reshuffled paths over {horizon} trading days. In {percent(result.metrics.probability_loss)} of them the account ended below the starting {rupees(initial)}; the middle path ended at {rupees(result.metrics.median_terminal)}. Shaded band: middle 90% of paths. These are reshuffled scenarios, not forecasts.</p>
      <div className="actions"><button type="button" className="button secondary" onClick={() => { const report = enrichReport(result, study, simulationParams, backtest.manifest || historyManifest); downloadJson({ ...report, manifest: { ...report.manifest, parent_backtest: enrichReport(backtest, study, params, historyManifest).manifest, params: simulationParams } }, "monte-carlo.json"); }}><ArrowDownToLine size={14} aria-hidden="true" />Download Monte Carlo JSON</button></div>
      <details className="fold"><summary>Percentile bands as a table, and assumptions</summary><RecordTable rows={result.bands} empty="No bands returned" /><ul className="summary-list">{result.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
    </>}
  </section>;
}

function MonteCarloChart({ result, start }: { result: Simulation; start: number }) {
  const maximum = result.bands.length - 1;
  const [frame, setFrame] = useState(maximum), [playing, setPlaying] = useState(false), [reduced, setReduced] = useState(false), [systemReduced, setSystemReduced] = useState(false);
  const [announcement, setAnnouncement] = useState("Complete paths. Animation paused.");
  const [replayVersion, setReplayVersion] = useState(0);
  const effectiveReduced = reduced || systemReduced;
  const visible = effectiveReduced ? maximum : frame;
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    function sync() { setSystemReduced(media.matches); if (media.matches) { setPlaying(false); setFrame(maximum); setAnnouncement("Reduced motion. Complete paths displayed."); } }
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [maximum]);
  useEffect(() => {
    function pauseHidden() { if (document.hidden) { setPlaying(false); setAnnouncement("Animation paused while the page is hidden."); } }
    document.addEventListener("visibilitychange", pauseHidden);
    return () => document.removeEventListener("visibilitychange", pauseHidden);
  }, []);
  useEffect(() => {
    if (!playing || effectiveReduced) return;
    let id = 0, last = 0, current = frame;
    function tick(time: number) {
      if (time - last >= 45) { current = Math.min(maximum, current + Math.max(1, Math.ceil(maximum / 180))); setFrame(current); last = time; }
      if (current >= maximum) { setPlaying(false); setAnnouncement(`Complete. Step ${maximum} of ${maximum}.`); return; }
      id = requestAnimationFrame(tick);
    }
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
    // frame changes are animation output; starting or pausing creates a fresh loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, effectiveReduced, maximum, replayVersion]);
  const extent = useMemo(() => {
    let low = Infinity, high = -Infinity;
    result.paths.slice(0, 50).forEach(path => path.forEach(value => { low = Math.min(low, value); high = Math.max(high, value); }));
    result.bands.forEach(band => { low = Math.min(low, band.p05); high = Math.max(high, band.p95); });
    if (Number.isFinite(start)) { low = Math.min(low, start); high = Math.max(high, start); }
    const pad = (high - low) * 0.06 || 1;
    return { low: low - pad, high: high + pad };
  }, [result, start]);
  const x = (step: number) => 82 + step / Math.max(1, maximum) * 790;
  const y = (value: number) => 324 - (value - extent.low) / (extent.high - extent.low) * 292;
  const line = (values: number[]) => values.slice(0, visible + 1).map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const band = line(result.bands.map(point => point.p95)) + result.bands.slice(0, visible + 1).reverse().map(point => `L${x(point.step).toFixed(1)},${y(point.p05).toFixed(1)}`).join(" ") + " Z";
  function play() { if (effectiveReduced) return; if (frame >= maximum) setFrame(0); setPlaying(true); setAnnouncement("Playing simulated paths."); }
  function pause() { setPlaying(false); setAnnouncement(`Paused. Step ${visible} of ${maximum}.`); }
  return <><svg className="simulation-svg" viewBox="0 0 900 365" role="img" aria-label={`Resampled strategy paths and percentile bands. Step ${visible} of ${maximum}.`}><title>Monte Carlo historical-return scenarios</title>{[0, 1, 2, 3, 4].map(index => { const value = extent.low + (extent.high - extent.low) * index / 4; return <g key={index}><line x1="82" x2="872" y1={y(value)} y2={y(value)} stroke="var(--chart-grid)" /><text x="72" y={y(value) + 4} textAnchor="end" fill="var(--chart-text)" fontSize="12">{rupees(value)}</text></g>; })}<path d={band} fill="var(--chart-gold)" fillOpacity="0.13" />{result.paths.slice(0, 50).map((path, index) => <path key={index} d={line(path)} fill="none" stroke="var(--chart-up)" strokeOpacity="0.25" strokeWidth="1" />)}<path d={line(result.bands.map(point => point.p50))} fill="none" stroke="var(--chart-gold)" strokeWidth="2.5" />{Number.isFinite(start) && <><line x1="82" x2="872" y1={y(start)} y2={y(start)} stroke="var(--chart-text)" strokeWidth="1.5" strokeDasharray="6 5" /><text x="868" y={y(start) - 6} textAnchor="end" fill="var(--chart-text)" fontSize="12">Starting capital {rupees(start)}</text></>}<text x="82" y="350" fill="var(--chart-text)" fontSize="12">Day 0</text><text x="872" y="350" textAnchor="end" fill="var(--chart-text)" fontSize="12">Day {maximum}</text></svg><ul className="chart-legend" aria-label="Chart legend"><li><i className="legend-band" />Middle 90% of paths</li><li><i className="legend-median" />Median path</li><li><i className="legend-sample" />Sample paths</li><li><i className="legend-start" />Starting capital</li></ul><div className="animation-controls"><button className="button secondary" type="button" disabled={effectiveReduced} aria-pressed={playing} onClick={() => playing ? pause() : play()}>{playing ? <Pause size={14} /> : <Play size={14} />}{playing ? "Pause" : "Play"}</button><button type="button" className="button secondary" disabled={effectiveReduced} onClick={() => { setFrame(0); setPlaying(true); setReplayVersion(value => value + 1); setAnnouncement("Replaying simulated paths."); }}><RotateCcw size={14} />Replay</button><label className="check-label"><input type="checkbox" checked={reduced} onChange={event => { setReduced(event.target.checked); setFrame(maximum); setPlaying(false); setAnnouncement("Complete paths displayed. Animation paused."); }} />Reduced motion</label><span aria-live="off">Step {visible} of {maximum}</span></div><label className="field">Displayed simulation step<input type="range" min={0} max={maximum} value={visible} disabled={effectiveReduced} onChange={event => { setPlaying(false); setFrame(Number(event.target.value)); }} /></label><span className="sr-only" role="status" aria-live="polite">{announcement}</span>{systemReduced && <p className="muted">System reduced-motion preference is active. Complete static paths are displayed.</p>}</>;
}
