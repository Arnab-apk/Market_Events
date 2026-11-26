"use client";

import { useState } from "react";
import type { Api } from "./types";
import type { Holding } from "../_lib/portfolio";

export type StockChoice = Pick<Holding, "symbol" | "exchange">;
type Match = { name: string; trading_symbol: string; exchange: StockChoice["exchange"]; instrument_id: string };

export function PaperStockPicker({ api, disabled, onPreview }: {
  api: Api; disabled: boolean; onPreview: (stocks: StockChoice[]) => Promise<void>;
}) {
  const [exchange, setExchange] = useState<StockChoice["exchange"]>("NSE");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Match[]>([]);
  const [selected, setSelected] = useState<Match[]>([]);
  const [message, setMessage] = useState("");
  const [searching, setSearching] = useState(false);

  async function search() {
    setSearching(true);
    setMatches([]);
    setMessage("");
    try {
      const result = await api<{ matches: Match[] }>("stock-search", { exchange, query: query.trim() });
      setMatches(result.matches);
      if (!result.matches.length) setMessage("No stocks matched. Try an exchange ticker or another company name.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Stock search is unavailable.");
    } finally { setSearching(false); }
  }

  return <details className="card fold">
    <summary>Choose your own paper stocks</summary>
    <p className="muted">Select up to 10 stocks. The ₹1,00,000 virtual budget is divided equally before rounding to whole shares.</p>
    <form className="actions" onSubmit={event => { event.preventDefault(); void search(); }}>
      <label className="field">Exchange<select value={exchange} disabled={searching || disabled} onChange={event => setExchange(event.target.value as StockChoice["exchange"])}><option>NSE</option><option>BSE</option></select></label>
      <label className="field">Stock name or ticker<input value={query} maxLength={60} disabled={searching || disabled} onChange={event => setQuery(event.target.value)} /></label>
      <button type="submit" className="button secondary" disabled={searching || disabled || !query.trim()}>{searching ? "Searching…" : "Search stocks"}</button>
    </form>
    {message && <p role="status" className="muted">{message}</p>}
    {matches.length > 0 && <ul className="stack" aria-label="Matching stocks">{matches.map(match => {
      const added = selected.some(row => row.instrument_id === match.instrument_id);
      return <li key={match.instrument_id}><button type="button" className="button secondary" disabled={disabled || added || selected.length === 10} onClick={() => setSelected(rows => [...rows, match])}>
        {added ? "Added" : "Add"} {match.trading_symbol} · {match.name}
      </button></li>;
    })}</ul>}
    {selected.length > 0 && <ul className="actions" aria-label="Selected paper stocks">{selected.map(stock =>
      <li key={stock.instrument_id}><button type="button" className="button secondary" disabled={disabled} onClick={() => setSelected(rows => rows.filter(row => row.instrument_id !== stock.instrument_id))}>Remove {stock.exchange}:{stock.trading_symbol}</button></li>,
    )}</ul>}
    <button type="button" className="button primary" disabled={disabled || searching || !selected.length} onClick={() => void onPreview(selected.map(stock => ({ symbol: stock.trading_symbol, exchange: stock.exchange })))}>Preview selected paper stocks</button>
  </details>;
}
