import type { Company, Run, Scope } from "../_components/types";

export const MAX_PORTFOLIO_BYTES = 128 * 1024;
const MAX_HOLDINGS = 250;
const MAX_QUANTITY = 100_000_000;
const MAX_COST = 10_000_000;
const COLUMNS = ["symbol", "exchange", "quantity", "average_cost"] as const;

export type Holding = { symbol: string; exchange: "NSE" | "BSE"; quantity: number; averageCost: number };
export type PaperAccount = { startingCash: number; cash: number };
export type PortfolioSnapshot = { source: string; importedAt: string; holdings: Holding[]; paper?: PaperAccount };
type CsvRow = { line: number; values: string[] };
type PreviewRow = { line: number; holding: Holding } | { line: number; error: string };
export type PortfolioPreview = { rows: PreviewRow[]; fileError?: string };

function readCsv(csv: string): CsvRow[] {
  const rows: CsvRow[] = [];
  let values: string[] = [];
  let value = "";
  let line = 1;
  let rowLine = 1;
  let state: "unquoted" | "quoted" | "closed" = "unquoted";
  for (let index = 0; index < csv.length; index++) {
    const char = csv[index];
    if (state === "quoted") {
      if (char === '"') {
        if (csv[index + 1] === '"') { value += '"'; index++; }
        else state = "closed";
      } else {
        value += char;
        if (char === "\n") line++;
      }
    } else if (char === "," || char === "\n") {
      values.push(value);
      value = "";
      state = "unquoted";
      if (char === "\n") {
        if (values.length > 1 || values.some(field => field.trim())) rows.push({ line: rowLine, values });
        values = [];
        rowLine = ++line;
      }
    } else if (state === "closed") {
      if (char !== " " && char !== "\t") throw new Error(`Unexpected character after a quote on line ${line}.`);
    } else if (char === '"') {
      if (value) throw new Error(`Unexpected quote on line ${line}.`);
      state = "quoted";
    } else {
      value += char;
    }
  }
  if (state === "quoted") throw new Error(`Unclosed quote in the row starting on line ${rowLine}.`);
  return rows;
}

function isHolding(value: unknown): value is Holding {
  if (!value || typeof value !== "object") return false;
  const { symbol, exchange, quantity, averageCost } = value as Partial<Holding>;
  return typeof symbol === "string" && /^[A-Z0-9][A-Z0-9&._-]{0,31}$/.test(symbol)
    && (exchange === "NSE" || exchange === "BSE")
    && typeof quantity === "number" && Number.isInteger(quantity) && quantity > 0 && quantity <= MAX_QUANTITY
    && typeof averageCost === "number" && Number.isFinite(averageCost) && averageCost >= 0 && averageCost <= MAX_COST;
}

function holdingFromRow(values: string[], order: number[]): Holding {
  if (values.length !== COLUMNS.length) throw new Error("Expected four fields.");
  const [symbol, exchange, quantity, cost] = order.map(index => values[index].trim());
  if (!/^[A-Z0-9][A-Z0-9&._-]{0,31}$/i.test(symbol)) throw new Error("Enter a valid stock symbol.");
  const market = exchange.toUpperCase();
  if (market !== "NSE" && market !== "BSE") throw new Error("Exchange must be NSE or BSE.");
  if (!/^\d+$/.test(quantity) || Number(quantity) < 1 || Number(quantity) > MAX_QUANTITY) {
    throw new Error("Quantity must be a whole number between 1 and 100,000,000.");
  }
  if (!/^\d+(?:\.\d{1,6})?$/.test(cost) || Number(cost) > MAX_COST) {
    throw new Error("Enter an average cost between 0 and 10,000,000, with up to six decimal places.");
  }
  return { symbol: symbol.toUpperCase(), exchange: market, quantity: Number(quantity), averageCost: Number(cost) };
}

export function parsePortfolioCsv(text: string): PortfolioPreview {
  let csvRows: CsvRow[];
  try {
    csvRows = readCsv(text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n") + "\n");
  } catch (error) {
    return { rows: [], fileError: (error as Error).message };
  }
  const [header, ...records] = csvRows;
  const headers = header?.values.map(value => value.trim().toLowerCase());
  const order = COLUMNS.map(name => headers?.indexOf(name) ?? -1);
  if (headers?.length !== COLUMNS.length || order.includes(-1)) {
    return { rows: [], fileError: `Use these CSV headers: ${COLUMNS.join(", ")}.` };
  }
  if (!records.length) return { rows: [], fileError: "The CSV has no holdings. Add at least one row." };
  if (records.length > MAX_HOLDINGS) return { rows: [], fileError: `Import up to ${MAX_HOLDINGS} holdings at a time.` };

  const seen = new Set<string>();
  return { rows: records.map(({ line, values }) => {
    try {
      const holding = holdingFromRow(values, order);
      const key = portfolioInstrumentId(holding, "demo");
      if (seen.has(key)) throw new Error(`Duplicate holding ${holding.symbol} on ${holding.exchange}. Combine the rows before importing.`);
      seen.add(key);
      return { line, holding };
    } catch (error) {
      return { line, error: (error as Error).message };
    }
  }) };
}

export function portfolioInstrumentId(holding: Holding, universe: Scope["universe"]) {
  return `${universe === "live" ? "LIVE:" : ""}${holding.exchange}:${holding.symbol}`;
}

export function latestPortfolioEvidence(holdings: Holding[], runs: Run[], universe: Scope["universe"]) {
  const byCompany = new Map<string, Run>();
  for (const run of runs) {
    const company = run.extraction?.company_id;
    if (!company || !run.assessment || run.parent_run_id) continue;
    const previous = byCompany.get(company);
    if (!previous || Date.parse(run.decision_time) > Date.parse(previous.decision_time)
      || (run.decision_time === previous.decision_time && Date.parse(run.created_at) > Date.parse(previous.created_at))) {
      byCompany.set(company, run);
    }
  }
  return holdings.map(holding => ({
    holding,
    run: byCompany.get(portfolioInstrumentId(holding, universe)),
  }));
}

export function portfolioStorageKey(scope: Scope) {
  return `market-events-portfolio-v1:${scope.workspace}:${scope.universe}`;
}

export function readPortfolioSnapshot(raw: string | null): PortfolioSnapshot | null {
  if (!raw) return null;
  try {
    const snapshot = JSON.parse(raw) as Partial<PortfolioSnapshot> | null;
    if (!snapshot || typeof snapshot.source !== "string" || typeof snapshot.importedAt !== "string"
      || !Number.isFinite(Date.parse(snapshot.importedAt)) || !Array.isArray(snapshot.holdings)
      || !snapshot.holdings.length || snapshot.holdings.length > MAX_HOLDINGS || !snapshot.holdings.every(isHolding)) return null;
    const keys = new Set(snapshot.holdings.map(holding => portfolioInstrumentId(holding, "demo")));
    if (keys.size !== snapshot.holdings.length) return null;
    if (snapshot.paper) {
      const { startingCash, cash } = snapshot.paper;
      const invested = snapshot.holdings.reduce((total, holding) => total + holding.quantity * holding.averageCost, 0);
      if (!Number.isFinite(startingCash) || startingCash <= 0 || !Number.isFinite(cash) || cash < 0
        || Math.abs(startingCash - cash - invested) > 0.01) return null;
    }
    return { source: snapshot.source, importedAt: snapshot.importedAt, holdings: snapshot.holdings,
      ...(snapshot.paper ? { paper: snapshot.paper } : {}) };
  } catch {
    return null;
  }
}

export function valuePortfolio(holdings: Holding[], companies: Company[], universe: Scope["universe"]) {
  const catalog = new Map(companies.map(company => [company.instrument_id, company]));
  let invested = 0;
  let pricedCost = 0;
  let marketValue = 0;
  let pricedCount = 0;
  const rows = holdings.map(holding => {
    const id = portfolioInstrumentId(holding, universe);
    const company = catalog.get(id);
    const cost = holding.quantity * holding.averageCost;
    const close = company?.latest_close;
    const asOf = company?.end;
    const price = close != null && Number.isFinite(close) && close > 0 && asOf && Number.isFinite(Date.parse(asOf)) ? close : null;
    const value = price == null ? null : holding.quantity * price;
    invested += cost;
    if (value != null) {
      pricedCost += cost;
      marketValue += value;
      pricedCount++;
    }
    return { id, holding, company, price, asOf, value, pnl: value == null ? null : value - cost };
  });
  const pnl = pricedCount ? marketValue - pricedCost : null;
  return {
    invested, pricedCost, pricedCount, marketValue: pricedCount ? marketValue : null, pnl,
    returnRatio: pnl != null && pricedCost > 0 ? pnl / pricedCost : null,
    rows: rows.map(row => ({ ...row, weight: row.value != null ? row.value / marketValue : null })),
  };
}
