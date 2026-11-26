"use client";

import { useEffect, useState } from "react";
import type { Api, Company } from "./types";
import { format } from "./types";
import type { PortfolioSnapshot } from "../_lib/portfolio";
import { valuePortfolio } from "../_lib/portfolio";
import { HostedChart } from "./research-charts";

type QuoteSnapshot = { source: string; fetched_at: string; missing: string[];
  quotes: { instrument_id: string; price: number; last_trade_at: string }[] };

const money = (value: number | null) => value == null ? "—" : `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function PaperLive({ snapshot, api }: { snapshot: PortfolioSnapshot; api: Api }) {
  const [enabled, setEnabled] = useState(false);
  const [quotes, setQuotes] = useState<QuoteSnapshot | null>(null);
  const [error, setError] = useState("");
  const [symbol, setSymbol] = useState(`${snapshot.holdings[0].exchange}:${snapshot.holdings[0].symbol}`);
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
  }, [api, enabled]);
  const companies = quotes?.quotes.map(quote => ({ instrument_id: quote.instrument_id,
    latest_close: quote.price, end: quote.last_trade_at })) as Company[] | undefined;
  const valuation = companies ? valuePortfolio(snapshot.holdings, companies, "live") : null;
  const complete = valuation?.pricedCount === snapshot.holdings.length;
  const equity = complete && valuation?.marketValue != null ? valuation.marketValue + (snapshot.paper?.cash ?? 0) : null;
  return <section className="card flow" aria-labelledby="paper-live-title">
    <h2 id="paper-live-title">Live paper demo</h2>
    <p className="muted">Watch TradingView intraday charts alongside Upstox latest-price valuation. TradingView exchange delays and symbol availability apply. This account uses virtual money.</p>
    <label className="check-label"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Refresh paper prices every 15 seconds</label>
    {enabled && <>
      {error && <p className="alert error" role="alert">{error} Displayed quotes may be stale.</p>}
      {!quotes && !error && <p role="status">Loading latest market quotes…</p>}
      {quotes && <>
        <p className="muted small">Upstox snapshot fetched {new Date(quotes.fetched_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST. When markets are closed, the latest traded price remains unchanged. Refresh pauses while this tab is hidden.</p>
        <div className="stats-grid"><div><span>Latest paper equity</span><strong>{equity == null ? "—" : money(equity)}</strong></div><div><span>Unrealized paper P&amp;L</span><strong>{complete && valuation ? money(valuation.pnl) : "—"}</strong></div></div>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Latest paper prices"><table><thead><tr><th>Holding</th><th>Latest traded price</th><th>Last trade (IST)</th><th>Paper value</th></tr></thead><tbody>{snapshot.holdings.map(holding => {
          const quote = quotes.quotes.find(item => item.instrument_id === `LIVE:${holding.exchange}:${holding.symbol}`);
          return <tr key={`${holding.exchange}:${holding.symbol}`}><th>{holding.symbol}</th><td>{quote ? money(quote.price) : "Unavailable"}</td><td>{quote ? new Date(quote.last_trade_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "—"}</td><td>{quote ? money(quote.price * holding.quantity) : "—"}</td></tr>;
        })}</tbody></table></div>
        {!complete && <p className="muted">Only {format(valuation?.pricedCount ?? 0, 0)} of {snapshot.holdings.length} holdings have latest quotes. Account totals are unavailable until coverage is complete.</p>}
      </>}
    </>}
    <label className="field">Chart holding<select value={symbol} onChange={event => setSymbol(event.target.value)}>{snapshot.holdings.map(holding => <option key={`${holding.exchange}:${holding.symbol}`} value={`${holding.exchange}:${holding.symbol}`}>{holding.symbol}</option>)}</select></label>
    <HostedChart key={symbol} initialSymbol={symbol} interval="1" />
    <a className="text-button" href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`} target="_blank" rel="noopener noreferrer">Open this chart on TradingView</a>
  </section>;
}
