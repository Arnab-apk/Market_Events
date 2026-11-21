export type Scope = { workspace: "local" | "demo"; universe: "live" | "demo" };
export type Company = {
  instrument_id: string; name: string; sector?: string; trading_symbol?: string;
  bars: number; research_bars: number; start: string | null; end: string | null; latest_close: number | null;
};
export type Article = { article_id: string; text: string; published_at: string; first_seen_at: string; source_url: string };
export type Run = {
  run_id: string; article_id: string; status: string; mode: string; policy: string;
  decision_time: string; created_at: string; error: string | null; latency_ms: number;
  parent_run_id?: string | null;
  extraction: { company_id: string | null; event_type: string; direction: string; source_spans: string[]; validation_status: string } | null;
  assessment: { direction: string; evidence_score: number | null; coverage: number; explanation: string; conflicts: string[]; abstention_reasons: string[]; inputs: Record<string, unknown> } | null;
  features: { values: Record<string, number | null>; missing: string[]; stale: string[]; observation_ids: string[] } | null;
  calls: { task: string; model: string; provider: string; status: string; input_tokens: number | null; output_tokens: number | null; latency_ms: number; error: string | null; mode: string }[];
};
export type Outcome = {
  run_id: string; status: string; reason: string; label?: string | null;
  entry_time?: string | null; exit_time?: string | null; entry_price?: number | null; exit_price?: number | null;
  gross_return?: number | null; net_return: number | null; benchmark_return?: number | null; excess_return?: number | null;
};
export type Workspace = {
  workspace: string; universe: string; provenance: string; exists: boolean; mode: string;
  companies: Company[]; articles: Article[]; runs: Run[]; observations_count: number;
  outcomes: Outcome[];
  readiness: { capability: string; name: string; configured: boolean; ready: boolean; reason: string }[];
};
export type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number; available_at?: string };
export type Point = { time: string; value: number };
export type History = { bars: Bar[]; indicators: Record<string, Point[]>; actual_start: string; actual_end: string };
export type Backtest = {
  strategy: string; assumptions: string[]; equity: { time: string; value: number; benchmark: number }[];
  trades: Record<string, unknown>[]; daily_returns: number[]; metrics: Record<string, number | null>;
  open_position: Record<string, unknown> | null;
};
export type Simulation = {
  paths: number[][]; bands: { step: number; p05: number; p50: number; p95: number }[];
  metrics: Record<string, number>; assumptions: string[];
};
export type Api = <T>(endpoint: string, body?: unknown) => Promise<T>;

export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export const format = (value: number | null | undefined, decimals = 2) => value == null ? "—" : new Intl.NumberFormat("en-IN", { maximumFractionDigits: decimals }).format(value);
export const percent = (value: number | null | undefined) => value == null ? "—" : `${(value * 100).toFixed(2)}%`;
export const human = (text: string) => text.replaceAll("_", " ");
const SYNTHETIC_PREFIX = /^\s*EXPLICITLY SYNTHETIC FIXTURE\.\s*/i;
/** Readable first line for an article; the synthetic marker becomes a separate visible label. */
export function sourceTitle(text: string, length = 125) {
  const synthetic = SYNTHETIC_PREFIX.test(text);
  const line = text.replace(SYNTHETIC_PREFIX, "").split("\n")[0];
  return { synthetic, title: line.length > length ? `${line.slice(0, length - 1)}…` : line };
}
export const POLICY_LABELS: Record<string, string> = {
  llm_only: "Large model only",
  slm_filter: "Small-model filter → large-model extraction",
  slm_delegate: "Small model with delegated extraction",
};
export const policyLabel = (policy: string) => POLICY_LABELS[policy] || human(policy);
/** Signed percentage with an explicit plus sign, for returns. */
export const signedPercent = (value: number | null | undefined) => value == null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
