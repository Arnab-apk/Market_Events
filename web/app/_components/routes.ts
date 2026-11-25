// URL routing for the single-page app: maps ?view= and ?tab= (new names and the old pre-redesign
// names) onto the main tabs and Settings. Pure functions, no React.

export const VIEWS = ["home", "portfolio", "analyse", "results", "lab", "settings"] as const;
export type View = (typeof VIEWS)[number];

export const TABS = {
  home: [],
  portfolio: [],
  analyse: [],
  results: ["saved", "compare"],
  lab: ["indicators", "backtest", "montecarlo"],
  settings: ["import", "connections", "glossary", "appearance", "about"],
} as const satisfies Record<View, readonly string[]>;

export const DEFAULT_TAB = { results: "saved", lab: "indicators", settings: "import" } as const;

/** Pre-redesign ?view= values. `lab` is both: with no tab it is the old Strategy lab (backtest). */
const LEGACY: Record<string, { view: View; tab: string }> = {
  overview: { view: "home", tab: "" },
  events: { view: "analyse", tab: "" },
  technicals: { view: "lab", tab: "indicators" },
  saved: { view: "results", tab: "saved" },
  comparisons: { view: "results", tab: "compare" },
  imports: { view: "settings", tab: "import" },
  connections: { view: "settings", tab: "connections" },
};

const own = (record: object, key: string) => Object.prototype.hasOwnProperty.call(record, key);
const isView = (value: string): value is View => (VIEWS as readonly string[]).includes(value);

export function normalizeView(view: string | null | undefined, tab: string | null | undefined): { view: View; tab: string } {
  const requested = view || "";
  const wanted = tab || "";
  if (requested === "lab" && !wanted) return { view: "lab", tab: "backtest" };
  if (own(LEGACY, requested)) return { ...LEGACY[requested] };
  if (!isView(requested)) return { view: "home", tab: "" };
  const tabs: readonly string[] = TABS[requested];
  if (!tabs.length) return { view: requested, tab: "" };
  return { view: requested, tab: tabs.includes(wanted) ? wanted : DEFAULT_TAB[requested as keyof typeof DEFAULT_TAB] };
}

/** A copy of the query with view/tab normalized; every other parameter is kept. */
export function normalizeQuery(parameters: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(parameters);
  const { view, tab } = normalizeView(parameters.get("view"), parameters.get("tab"));
  next.set("view", view);
  if (tab) next.set("tab", tab); else next.delete("tab");
  return next;
}
