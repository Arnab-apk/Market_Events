"use client";

import { useEffect, useState } from "react";
import type { Api, Company } from "./types";
import { format } from "./types";
import type { PortfolioSnapshot } from "../_lib/portfolio";
import { valuePortfolio } from "../_lib/portfolio";
import { IntradayChart, type IntradayBar } from "./research-charts";

type QuoteSnapshot = { source: string; fetched_at: string; missing: string[];
  quotes: { instrument_id: string; price: number; last_trade_at: string }[] };

const money = (value: number | null) => value == null ? "—" : `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
type ChartData = { source: string; session: string; bars: IntradayBar[]; fetched_at: string };

export function HoldingChart({ api, market, ticker, enabled }: { api: Api; market: string; ticker: string; enabled: boolean }) {
  const [data, setData] = useState<ChartData | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load(first: boolean) {
      try {
        if (first || document.visibilityState === "visible") {
          const result = await api<ChartData>("portfolio-chart", { exchange: market, symbol: ticker });
          if (active) { setData(result); setError(""); }
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load chart prices.");
      } finally {
        if (active && enabled) timer = setTimeout(() => void load(false), 60_000);
      }
    }
    void load(true);
    return () => { active = false; clearTimeout(timer); };
  }, [api, market, ticker, enabled, attempt]);

  return <section className="flow" aria-labelledby="holding-chart-title">
    <h3 id="holding-chart-title">{ticker} intraday chart</h3>
    {!data && !error && <p role="status">Loading Upstox candles…</p>}
    {error && <p role="alert" className="alert warning">{error}{data ? " Showing the last loaded chart." : ""}</p>}
    {data && !data.bars.length && <p className="muted" role="status">Upstox did not return candles for this stock.</p>}
    {!!data?.bars.length && <>
      <p className="muted small">Showing the {data.session}. {enabled ? "Chart candles refresh every minute while this tab is visible." : "Turn on price refresh to update this chart every minute."}</p>
      <IntradayChart bars={data.bars} symbol={`${market}:${ticker}`} />
    </>}
    <div className="actions">
      <button type="button" className="button secondary" onClick={() => setAttempt(value => value + 1)}>Reload chart</button>
      <a className="text-button" href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(`${market}:${ticker}`)}`} target="_blank" rel="noopener noreferrer">Open this chart on TradingView</a>
    </div>
  </section>;
}

export function PaperLive({ snapshot, api }: { snapshot: PortfolioSnapshot; api: Api }) {
  const [enabled, setEnabled] = useState(false);
  const [quotes, setQuotes] = useState<QuoteSnapshot | null>(null);
  const [error, setError] = useState("");
  // Derive the charted holding from the current snapshot so a new import never shows a removed stock.
  const choices = snapshot.holdings.map(holding => `${holding.exchange}:${holding.symbol}`);
  const [picked, setSymbol] = useState(choices[0] ?? "");
  const symbol = choices.includes(picked) ? picked : choices[0] ?? "";
  const [market, ticker] = symbol.split(":");
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function update() {
      try {
        if (document.visibilityState === "visible") {
          const next = await api<QuoteSnapshot>("paper-quotes", {});
          if (active) { setQuotes(next); setError(""); }
        }
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "Quote refresh failed."); }
      finally { if (active) timer = setTimeout(() => void update(), 15_000); }
    }
    void update();
    return () => { active = false; clearTimeout(timer); };
  }, [api, enabled, snapshot.importedAt]);
  const companies = quotes?.quotes.map(quote => ({ instrument_id: quote.instrument_id,
    latest_close: quote.price, end: quote.last_trade_at })) as Company[] | undefined;
  const valuation = companies ? valuePortfolio(snapshot.holdings, companies, "live") : null;
  const complete = valuation?.pricedCount === snapshot.holdings.length;
  const equity = complete && valuation?.marketValue != null ? valuation.marketValue + (snapshot.paper?.cash ?? 0) : null;
  return <section className="card flow" aria-labelledby="paper-live-title">
    <h2 id="paper-live-title">{snapshot.paper ? "Live paper demo" : "Live holdings and charts"}</h2>
    <p className="muted">Upstox supplies the latest prices and intraday candles. {snapshot.paper ? "Holdings and cash are simulated." : "Values use the quantities and costs from your saved import."}</p>
    <label className="check-label"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />{snapshot.paper ? "Refresh paper prices every 15 seconds" : "Refresh holdings prices every 15 seconds"}</label>
    {enabled && <>
      {error && <p className="alert error" role="alert">{error} Displayed quotes may be stale.</p>}
      {!quotes && !error && <p role="status">Loading latest market quotes…</p>}
      {quotes && <>
        <p className="muted small">Upstox snapshot fetched {new Date(quotes.fetched_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST. When markets are closed, the latest traded price remains unchanged. Refresh pauses while this tab is hidden.</p>
        <div className="stats-grid"><div><span>{snapshot.paper ? "Latest paper equity" : "Latest holdings value"}</span><strong>{money(equity)}</strong></div><div><span>{snapshot.paper ? "Unrealized paper P&L" : "Unrealized P&L"}</span><strong>{complete && valuation ? money(valuation.pnl) : "—"}</strong></div></div>
        <div className="table-scroll" tabIndex={0} role="region" aria-label={snapshot.paper ? "Latest paper prices" : "Latest holdings prices"}><table><thead><tr><th>Holding</th><th>Latest traded price</th><th>Last trade (IST)</th><th>Position value</th></tr></thead><tbody>{snapshot.holdings.map(holding => {
          const quote = quotes.quotes.find(item => item.instrument_id === `LIVE:${holding.exchange}:${holding.symbol}`);
          return <tr key={`${holding.exchange}:${holding.symbol}`}><th>{holding.symbol}</th><td>{quote ? money(quote.price) : "Unavailable"}</td><td>{quote ? new Date(quote.last_trade_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "—"}</td><td>{quote ? money(quote.price * holding.quantity) : "—"}</td></tr>;
        })}</tbody></table></div>
        {!complete && <p className="muted">Only {format(valuation?.pricedCount ?? 0, 0)} of {snapshot.holdings.length} holdings have latest quotes. Account totals are unavailable until coverage is complete.</p>}
      </>}
    </>}
    <label className="field">Chart holding<select value={symbol} onChange={event => setSymbol(event.target.value)}>{snapshot.holdings.map(holding => <option key={`${holding.exchange}:${holding.symbol}`} value={`${holding.exchange}:${holding.symbol}`}>{holding.symbol}</option>)}</select></label>
    {symbol && <HoldingChart key={symbol} api={api} market={market} ticker={ticker} enabled={enabled} />}
  </section>;
}
