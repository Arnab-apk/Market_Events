"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowDownToLine, FileUp } from "lucide-react";
import { MAX_PORTFOLIO_BYTES, parsePortfolioCsv, portfolioStorageKey, readPortfolioSnapshot, valuePortfolio } from "../_lib/portfolio";
import type { PortfolioPreview, PortfolioSnapshot } from "../_lib/portfolio";
import type { Href, PanelProps } from "./research-app";
import PortfolioAssistant from "./portfolio-assistant";
import { StatTile } from "./simple-ui";
import { format, percent, signedPercent } from "./types";
import type { Scope, Workspace } from "./types";
import { Time } from "./ui";
import styles from "./portfolio-panel.module.css";

const SAMPLE_PATH = "/sample-portfolio.csv";
const BROKER_MESSAGES: Record<string, string> = {
  denied: "Upstox did not authorize the connection. Connect again to retry.",
  expired: "The Upstox connection expired or was opened in another browser session. Connect again.",
  empty: "Upstox returned no holdings. Your current portfolio is unchanged.",
  invalid: "Upstox returned holdings that this app cannot import. Use a holdings CSV instead.",
  "rate-limited": "Upstox is limiting requests. Wait a moment, then connect again.",
  unavailable: "Upstox could not be reached. Connect again or use a holdings CSV.",
};
const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });
const SIGNED_INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", signDisplay: "exceptZero" });
const money = (value: number | null) => value == null ? "—" : INR.format(value);
const signedMoney = (value: number | null) => value == null ? "—" : SIGNED_INR.format(value);
const tone = (value: number | null) => value == null || value === 0 ? undefined : value > 0 ? "positive" : "negative";

async function brokerRequest(action: "start" | "preview") {
  const response = await fetch(`/api/portfolio/upstox?action=${action}`, { method: "POST", cache: "no-store" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "Upstox could not be reached.");
  return result;
}

export default function PortfolioPanel({ api, data, scope, href, demoHref }: { api: PanelProps["api"]; data: Workspace; scope: Scope; href: Href; demoHref: Href }) {
  const storageKey = portfolioStorageKey(scope);
  const [snapshot, setSnapshot] = useState(() => {
    try { return readPortfolioSnapshot(window.sessionStorage.getItem(storageKey)); }
    catch { return null; }
  });
  const [draft, setDraft] = useState<(PortfolioPreview & { name: string }) | null>(null);
  const [reading, setReading] = useState(false);
  const [status, setStatus] = useState("");
  const [brokerError, setBrokerError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const demo = scope.workspace === "demo";
  const live = !demo && scope.universe === "live";
  const brokerStatus = useSearchParams().get("upstox") ?? "";
  const invalid = draft?.rows.filter(row => "error" in row).length ?? 0;

  function clearBrokerStatus() {
    const url = new URL(window.location.href);
    if (url.searchParams.has("upstox")) {
      url.searchParams.delete("upstox");
      window.history.replaceState(null, "", url);
    }
  }

  async function connect() {
    setReading(true);
    setBrokerError("");
    clearBrokerStatus();
    try {
      const { url } = await brokerRequest("start");
      window.location.assign(url);
    } catch (error) {
      setBrokerError(error instanceof Error ? error.message : "Could not start the Upstox connection.");
      setReading(false);
    }
  }

  async function preview(name: string, read: () => Promise<string>) {
    setReading(true);
    setStatus("");
    setDraft(null);
    try { setDraft({ name, ...parsePortfolioCsv(await read()) }); }
    catch (error) { setDraft({ name, rows: [], fileError: error instanceof Error ? error.message : "Could not read the CSV." }); }
    finally { setReading(false); }
  }

  function confirm() {
    if (!draft || draft.fileError || invalid || !draft.rows.length) return;
    const next = { source: draft.name, importedAt: new Date().toISOString(), holdings: draft.rows.flatMap(row => "holding" in row ? [row.holding] : []) };
    setSnapshot(next);
    setDraft(null);
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(next));
      setStatus(`${next.holdings.length} holdings imported.`);
    } catch {
      setStatus("Holdings imported for this view. Browser storage is unavailable, so they will clear when you leave this page.");
    }
  }

  function clearHoldings() {
    try {
      window.sessionStorage.removeItem(storageKey);
      setSnapshot(null);
      setStatus("Holdings cleared.");
    } catch {
      setStatus("Could not clear browser storage. Close this tab to end the session.");
    }
  }

  return <div className="view-stack">
    <header className="page-title"><h1>Portfolio</h1><p>Import holdings, check their value, and open the research behind each company.</p></header>
    <section className={`card flow ${styles.import}`} aria-labelledby="portfolio-import-title">
      <div>
        <h2 id="portfolio-import-title">Import holdings</h2>
        <p className="muted">Your CSV stays in this browser tab. The next confirmed import replaces this tab’s portfolio for the current workspace.</p>
      </div>
      <div className="actions">
        <input ref={input} type="file" hidden aria-label="Holdings CSV" accept=".csv,text/csv" disabled={reading} onChange={event => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (!file) return;
          void preview(file.name, async () => {
            if (file.size > MAX_PORTFOLIO_BYTES) throw new Error("Choose a CSV file no larger than 128 KB.");
            return file.text();
          });
        }} />
        <button type="button" className="button primary" disabled={reading} onClick={() => input.current?.click()}><FileUp size={16} aria-hidden="true" />Choose CSV</button>
        {live && <button type="button" className="button secondary" disabled={reading} onClick={() => void connect()}>Connect Upstox</button>}
        {demo ? <button type="button" className="button secondary" disabled={reading} onClick={() => void preview("sample-portfolio.csv", async () => {
          const response = await fetch(SAMPLE_PATH);
          if (!response.ok) throw new Error("Could not load the sample CSV. Try again or choose a file.");
          return response.text();
        })}>Load sample CSV</button> : <Link className="button secondary" href={demoHref("portfolio")}>Try sample in demo</Link>}
        <a className="text-button" href={SAMPLE_PATH} download><ArrowDownToLine size={16} aria-hidden="true" />Download sample CSV</a>
      </div>
      {live && brokerStatus === "ready" && <div className="state-card">
        <p>Your Upstox holdings are ready to preview. Confirm the import to replace this tab’s portfolio.</p>
        <button type="button" className="button secondary" disabled={reading} onClick={() => {
          clearBrokerStatus();
          void preview("Upstox holdings", async () => (await brokerRequest("preview")).csv);
        }}>Preview Upstox holdings</button>
      </div>}
      {live && (brokerError || Object.hasOwn(BROKER_MESSAGES, brokerStatus)) && <p className="alert warning" role="alert">{brokerError || BROKER_MESSAGES[brokerStatus]}</p>}
      <p className="muted small">CSV columns <code>symbol</code>, <code>exchange</code>, <code>quantity</code>, <code>average_cost</code> in INR. The sample is synthetic.</p>
      <p className={reading || status ? "muted small" : "sr-only"} role="status">{reading ? "Preparing holdings…" : status}</p>
    </section>

    {draft && <section className="card flow" aria-labelledby="portfolio-preview-title">
      <div className="card-head">
        <h2 id="portfolio-preview-title">Import preview</h2>
        <span className={`muted small ${styles.filename}`}>{draft.name}</span>
      </div>
      {draft.fileError ? <p className="alert error" role="alert">{draft.fileError}</p> : <>
        {invalid > 0 && <p className="alert error" role="alert">Fix {invalid} {invalid === 1 ? "row" : "rows"} in the CSV and choose the file again.</p>}
        <div className="table-scroll" tabIndex={0} role="region" aria-label="CSV preview rows">
          <table><thead><tr><th scope="col">Line</th><th scope="col">Symbol</th><th scope="col">Exchange</th><th scope="col" className="numeric">Quantity</th><th scope="col" className="numeric">Average cost</th></tr></thead>
            <tbody>{draft.rows.map(row => <tr key={row.line}>
              <td>{row.line}</td>
              {"holding" in row ? <><td>{row.holding.symbol}</td><td>{row.holding.exchange}</td><td className="numeric">{format(row.holding.quantity, 0)}</td><td className="numeric">{money(row.holding.averageCost)}</td></> : <td colSpan={4} className={styles.rowError}>{row.error}</td>}
            </tr>)}</tbody>
          </table>
        </div>
      </>}
      <div className="actions">
        <button type="button" className="button primary" disabled={Boolean(draft.fileError || invalid || !draft.rows.length)} onClick={confirm}>Import holdings</button>
        <button type="button" className="button secondary" onClick={() => setDraft(null)}>Cancel preview</button>
      </div>
    </section>}

    {snapshot ? <>
      <Holdings snapshot={snapshot} data={data} scope={scope} href={href} onClear={clearHoldings} />
      <PortfolioAssistant key={snapshot.importedAt} api={api} holdings={snapshot.holdings} data={data} scope={scope} href={href} />
    </> :
      <section className="card flow"><h2>No holdings imported</h2><p className="muted">Choose a CSV to preview the holdings before adding them to your portfolio.</p></section>}
  </div>;
}

function Holdings({ snapshot, data, scope, href, onClear }: { snapshot: PortfolioSnapshot; data: Workspace; scope: Scope; href: Href; onClear: () => void }) {
  const { rows, invested, marketValue, pricedCost, pricedCount, pnl, returnRatio } = valuePortfolio(snapshot.holdings, data.companies, scope.universe);
  const partial = pricedCount < rows.length;
  return <section className="card flow" aria-labelledby="portfolio-holdings-title">
    <div className="card-head">
      <h2 id="portfolio-holdings-title">Holdings</h2>
      <span className="pill neutral">{scope.workspace === "demo" ? "Synthetic demo closes" : "Workspace saved closes"}</span>
    </div>
    <p className={`muted small ${styles.filename}`}>{snapshot.source} · Imported <Time value={snapshot.importedAt} /></p>
    <div className="stat-grid">
      <StatTile label="Total invested" value={money(invested)} detail={`All ${rows.length} holdings`} />
      <StatTile label={partial ? "Market value (partial)" : "Market value"} value={money(marketValue)} detail={`${pricedCount} of ${rows.length} holdings priced`} />
      <StatTile label={partial ? "Estimated unrealized P&L (partial)" : "Estimated unrealized P&L"} value={signedMoney(pnl)} tone={tone(pnl)}
        detail={pricedCount ? `${returnRatio == null ? "Return unavailable" : signedPercent(returnRatio)} on ${money(pricedCost)} invested` : "No saved closing prices"} />
    </div>
    <p className="muted small">Allocation uses market value for priced holdings. Closing prices are dated snapshots and can be stale.</p>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Portfolio holdings table">
      <table>
        <thead><tr><th scope="col">Holding</th><th scope="col" className="numeric">Quantity</th><th scope="col" className="numeric">Average cost</th><th scope="col" className="numeric">Saved close</th><th scope="col" className="numeric">Market value</th><th scope="col" className="numeric">Unrealized P&L</th><th scope="col">Allocation</th><th scope="col">Research</th></tr></thead>
        <tbody>{rows.map(({ id, holding, company, price, asOf, value, pnl: holdingPnl, weight }) => <tr key={id}>
          <th scope="row"><strong>{holding.symbol}</strong><small className="cell-note">{holding.exchange}{company ? ` · ${company.name}` : ""}</small></th>
          <td className="numeric">{format(holding.quantity, 0)}</td>
          <td className="numeric">{money(holding.averageCost)}</td>
          <td className="numeric">{price == null ? <span className="muted">Unavailable</span> : <>{money(price)}<small className="cell-note"><Time value={asOf} /></small></>}</td>
          <td className="numeric">{money(value)}</td>
          <td className={`numeric${tone(holdingPnl) ? ` tone-${tone(holdingPnl)}` : ""}`}>{signedMoney(holdingPnl)}</td>
          <td>{weight == null ? "—" : <div className={styles.allocation}><span>{percent(weight)}</span><span className={styles.track} aria-hidden="true"><span style={{ width: `${weight * 100}%` }} /></span></div>}</td>
          <td><Link href={href("analyse", { company: id })} aria-label={`View research for ${holding.symbol} on ${holding.exchange}`}>View research</Link>{!company && <small className="cell-note">Outside this workspace</small>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <div className="actions"><button type="button" className="text-button" onClick={onClear}>Clear holdings from this tab</button></div>
  </section>;
}
