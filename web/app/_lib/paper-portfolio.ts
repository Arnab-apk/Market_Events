import type { Company } from "../_components/types";
import type { Holding, PortfolioSnapshot } from "./portfolio";

export const PAPER_CAPITAL = 100_000;
export const PAPER_SYMBOLS = ["ASIANPAINT", "BERGEPAINT", "PIDILITIND", "INDIGO", "RELIANCE"] as const;
export const PAPER_COMPANIES = PAPER_SYMBOLS.map(symbol => `LIVE:NSE:${symbol}`);

export function createPaperPortfolio(companies: Company[], now = new Date()): PortfolioSnapshot {
  const budgetPerCompany = PAPER_CAPITAL / PAPER_SYMBOLS.length;
  const holdings: Holding[] = PAPER_SYMBOLS.map(symbol => {
    const company = companies.find(item => item.instrument_id === `LIVE:NSE:${symbol}`);
    const timestamp = Date.parse(company?.end ?? "");
    const close = company?.latest_close;
    if (close == null || !Number.isFinite(close) || close <= 0
      || !Number.isFinite(timestamp) || timestamp > now.getTime()
      || now.getTime() - timestamp > 4 * 86400_000) {
      throw new Error(`A recent completed daily price is unavailable for ${symbol}. Refresh prices in Connections, then try again.`);
    }
    const averageCost = Math.round(close * 1_000_000) / 1_000_000;
    const quantity = Math.floor(budgetPerCompany / averageCost);
    if (!Number.isSafeInteger(quantity) || quantity < 1 || quantity > 100_000_000) {
      throw new Error(`The saved price for ${symbol} cannot form a valid ₹20,000 whole-share allocation.`);
    }
    return { symbol, exchange: "NSE", quantity, averageCost };
  });
  const invested = holdings.reduce((total, holding) => total + holding.quantity * holding.averageCost, 0);
  return {
    source: "Indian stocks · paper money",
    importedAt: now.toISOString(),
    holdings,
    paper: { startingCash: PAPER_CAPITAL, cash: PAPER_CAPITAL - invested },
  };
}
