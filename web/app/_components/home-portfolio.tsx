"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Api } from "./types";
import type { Href } from "./research-app";
import type { PortfolioSnapshot } from "../_lib/portfolio";
import { StatTile } from "./simple-ui";

const money = (value: number) => value.toLocaleString("en-IN", { style: "currency", currency: "INR" });

export function HomePortfolio({ api, href }: { api: Api; href: Href }) {
  const [saved, setSaved] = useState<{ snapshot: PortfolioSnapshot | null } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<{ snapshot: PortfolioSnapshot | null }>("portfolio")
      .then(result => { if (active) setSaved(result); })
      .catch(() => { if (active) setError("Could not load your saved portfolio summary. Open Portfolio to retry."); });
    return () => { active = false; };
  }, [api]);
  const snapshot = saved?.snapshot;
  const paper = snapshot?.paper;
  return <section className="card flow" aria-labelledby="home-portfolio-title">
    <div className="card-head">
      <h2 id="home-portfolio-title">{paper ? "Your paper portfolio" : "Your portfolio"}</h2>
      {paper && <span className="pill neutral">Virtual money · saved</span>}
    </div>
    {!saved && !error && <p className="muted" role="status">Loading your saved portfolio…</p>}
    {error && <p className="muted" role="status">{error}</p>}
    {snapshot && <>
      {paper && <div className="stat-grid">
        <StatTile label="Starting virtual balance" value={money(paper.startingCash)} />
        <StatTile label="Available virtual cash" value={money(paper.cash)} />
        <StatTile label="Paper holdings" value={snapshot.holdings.length} />
      </div>}
      <p className="muted">{snapshot.holdings.map(holding => holding.symbol).join(" · ")}</p>
      {paper && <p className="muted small">Open your saved holdings to enable live price refresh, see paper equity and P&amp;L, or view a TradingView chart.</p>}
    </>}
    {saved && !snapshot && <p className="muted">Create a ₹1,00,000 virtual-money portfolio across five Indian stocks. Review the holdings before saving; broker connection is optional.</p>}
    <div className="actions"><Link className="button primary" href={href("portfolio")}>{paper ? "Open paper portfolio" : snapshot ? "Open saved portfolio" : "Set up paper portfolio"}</Link></div>
  </section>;
}
