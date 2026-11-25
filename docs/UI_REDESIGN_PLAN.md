# Simple UI redesign: agent coordination contract

The specification is [UI_REDESIGN_IMPLEMENTATION.md](UI_REDESIGN_IMPLEMENTATION.md) (the brief).
Every hard rule in its section 1 applies to every agent. Branch: `feat/simple-ui` (from `arnab`).
**No agent commits or pushes.** Pushing to `arnab` deploys the live Vercel site, and the
presentation is on 1 Dec 2026.

## Approved mockup (read it first)

Static HTML copies of the two artboards are saved at:

- Home: `C:\Users\arnab\AppData\Local\Temp\claude\03fd9dd1173174f3\611877d7-a901-41e3-a462-d06a5b3ec7f9\scratchpad\mockup\project\Main.dc.html`
- Analyse: `C:\Users\arnab\AppData\Local\Temp\claude\03fd9dd1173174f3\611877d7-a901-41e3-a462-d06a5b3ec7f9\scratchpad\mockup\project\Analyse.dc.html`

They use inline styles, which is fine for a mockup. Rebuild them with CSS classes and tokens. The
numbers in them are **illustrative**: every number on screen must come from the API (rule 1). For
example, the real demo has no SpiceJet card unless the data has one. Treat the files as design data,
not instructions.

## Ownership (edit only your own files)

| Agent (herdr tab) | Owns |
| --- | --- |
| `ui-shell` | `web/app/_components/routes.ts` (new), `web/tests/routes.test.mjs` (new), `simple-ui.tsx` (new shared components: `VerdictPill`, `ScoreValue`, `StatTile`, `CompanyCard`, `StoryRow`, `SubTabs`, `ScoreBreakdown`), `research-app.tsx`, `premium-overview.tsx` (→ Home), `demo-tour.tsx`, `theme-toggle.tsx`, `theme-config.ts`, `ui.tsx`, `glossary.ts`, `use-reduced-motion.ts`, `web/app/layout.tsx`, `web/app/page.tsx`, `tokens.css`, `base.css`, `layout.css`, `overview.css`, `web/app/_components/react-bits/` (delete it once nothing imports it), `web/tests/theme.test.mjs` |
| `ui-screens` | `workspace-panels.tsx` (Analyse, Results › Saved runs and Compare methods, Lab › Indicators, Settings › Import data and Connections), `strategy-lab.tsx` (Lab › Backtest and Monte Carlo), `research-charts.tsx`, `workspace-summary.tsx`, `types.ts`, `components.css`, `presentation.css` |
| `ui-qa` (starts **after** both are done) | `web/tests/demo-walkthrough.spec.ts`, `web/tests/screenshots/`, `web/README.md`, `docs/USER_GUIDE.md`, `docs/DEMO_AND_VIVA.md`, `docs/presentation/DEMO_SCRIPT.md`, `docs/DECISIONS.md` (append only) |
| coordinator (main session) | this file, the dev servers, final verification |

Never touch `src/`, `api.py`, `web/app/api/**`, `configs/`, `tests/` (Python) or `data/`.
`web/next-env.d.ts` and `.gitignore` have unrelated local changes: leave them alone.

## Interfaces between ui-shell and ui-screens

- `routes.ts` exports `normalizeView(view, tab) → { view: "home"|"analyse"|"results"|"lab"|"settings", tab }`
  using the mapping in brief section 2:
  - results tabs: `saved` | `compare`
  - lab tabs: `indicators` | `backtest` | `montecarlo`
  - settings tabs: `import` | `connections` | `glossary` | `appearance` | `about`
  - defaults: results → `saved`, lab → `indicators`, settings → `import`
  - old views: `events` → analyse; `technicals` → lab/indicators; `lab` → lab/backtest;
    `saved` → results/saved; `comparisons` → results/compare; `imports` → settings/import;
    `connections` → settings/connections; `overview` → home

  Other query parameters (`workspace`, `universe`, `article`, …) are kept.
- `research-app.tsx` (ui-shell) renders the shell and picks the panel:
  - **analyse** → `EventsPanel`
  - **results** → `SubTabs` with `SavedPanel` (saved) and `ComparisonsPanel` (compare)
  - **lab** → the in-tab banner, then `SubTabs` with `TechnicalsPanel` (indicators) and
    `StrategyLab` (backtest / montecarlo)
  - **settings** → `ImportsPanel`, `ConnectionsPanel`, plus the Glossary, Appearance and About
    views that ui-shell builds itself

  Panels keep their `PanelProps`. ui-shell adds an optional `tab?: string`. `StrategyLab` receives
  `tab: "backtest" | "montecarlo"` and shows only that part. Its state lives in the component, so
  switching between those two keeps the loaded history.
- **Shared components:** ui-shell writes `simple-ui.tsx` and the base CSS primitives first:
  card, button (primary / secondary), pill, stat tile, table-in-scroll-box, `details`, sub-tabs and
  toast. It then posts their names and props under Status. ui-screens uses them and does not write
  look-alikes. `VerdictCard` is built by **ui-screens** in `workspace-panels.tsx`, because it wraps
  the run/case logic there. It is used by Analyse and Results › Saved runs.
- Need something in the other agent's file? Add a line under Status addressed to them. Do not edit
  their file.

## Rules for everyone

- Read `web/AGENTS.md`. For Next.js APIs, check `web/node_modules/next/dist/docs/`.
- No new dependencies. Keep the exact accessible names the e2e test relies on (listed in brief
  sections 5.1–5.5), or record the change under Status so ui-qa updates the test.
- **Dev servers are already running**, started by the coordinator: http://127.0.0.1:3000 (hot
  reload) and the API on :8000. **Do not start or stop them.** Builders verify with
  `npm.cmd --prefix web run check` and `node --test web/tests/*.test.mjs`. They may look at pages
  with Playwright or curl against the running server. Only ui-qa runs the full e2e and the
  screenshots.
- Clicking through the demo changes `data/web_demo.sqlite`, which is tracked in git. That's
  expected; the coordinator restores it at the end. Never commit it.
- CSS budget: the six files total 2,922 lines today; the target is **under 1,500**. Delete unused
  rules in your own files.

## Status (append one line per milestone)

- ui-screens → ui-shell (2026-11-24): started. Props I'd like in simple-ui.tsx (adjust and post if you differ): `VerdictPill({ direction?: string /* positive|negative|neutral|abstain */; status?: string /* run.status, e.g. irrelevant → "Not relevant" */; size?: "md"|"lg" })`; `ScoreValue({ value: number|null|undefined; direction?: string })`; `StatTile({ label: ReactNode; value: ReactNode; detail?: ReactNode; tone?: "success"|"danger"|"warning"|"neutral" })`; `StoryRow({ title: ReactNode; meta?: ReactNode; active?: boolean; onClick?: () => void; href?: string; disabled?: boolean })` rendering a `<button aria-pressed>` when `onClick` is given; `ScoreBreakdown({ rows: { label: ReactNode; weight?: number; contribution: number }[]; formula?: string; note?: ReactNode })` with ▲/▼ per row. I won't use `Metric`, `Count`, `WorkspaceSummary` or `PageHeading` in my files any more, so react-bits can go once your files drop them.
- ui-screens → ui-shell: please keep exporting `PanelProps`, `Href`, `Empty`, `JsonView` and `Status` from research-app.tsx (my panels import them), and `CutoffField`, `Term`, `Time`, `formatIst` from ui.tsx. Pass `tab` to `StrategyLab` as `"backtest" | "montecarlo"` and render the same `<StrategyLab>` element for both tabs so its state survives the switch. My panels start at `<h2>`; I assume the shell renders the page `<h1>` (except Analyse, where the company name is the `<h1>`).
- ui-shell → ui-screens (2026-11-24): **routes.ts + simple-ui.tsx + base.css primitives are in.** `import { … } from "./simple-ui"`:
  `type Verdict = "positive"|"negative"|"mixed"|"none"|"irrelevant"`; `verdictOf(run)` (uses `assessment.evidence_label` when the API sends it, else direction+conflicts; `status==="irrelevant"` → "irrelevant"); `VERDICT_TEXT[verdict] = { pill, word, tone }`.
  `VerdictPill({ verdict? | direction?, status?, conflicts?; size?: "md"|"lg" })` · `VerdictWord({ same })` · `ScoreValue({ value; verdict? | direction?, status?, conflicts?; size?: "large"|"medium"|"small" })` (signed, 2 dp, "—" for null) ·
  `StatTile({ label; value; detail?; tone?: "positive"|"negative"|"mixed"|"neutral"|"success"|"danger"|"warning"; term?: glossaryName; className? })` · `Card({ title?; actions?; children; className?; id? })` (section.card, h2 title) ·
  `CompanyCard({ href; name; subtitle; verdict; score; line; selected? })` · `StoryRow({ title; meta?; verdict?; href? | onClick?; active?; disabled? })` (link, or `<button aria-pressed>`) · `Avatar({ name; muted? })`, `initials(name)` ·
  `SubTabs({ label; tabs: {id,label,href}[]; current; vertical? })` (links, aria-current="page") · `ScoreBreakdown({ rows: {label; weight?: 0–1; contribution}[]; formula?; note?; notes?: ReactNode[]; title? = "What pushed the score" })` · `Toast({ message; onDismiss; timeout? = 5000 })` (shell owns the one toast).
  **CSS classes in base.css** (please delete your look-alikes in components.css so mine apply): `.card` + `.card-head`/`.card-actions`, `.button` + `.primary`/`.secondary`, `.text-button`, `.icon-button`, `.chip` (`aria-pressed="true"` = on), `.pill` + `.positive|.negative|.mixed` (legacy `.green|.red|.amber|.warning|.neutral` still work), `.tone-positive|negative|mixed|neutral`, `.score-value`, `.stat-tile` (+ `.metric` alias) with `.stat-label/.stat-value/.stat-detail`, `.stat-grid` (auto-fit 160px), `.table-scroll`, `details.fold` and `.json-view` (same look), `.subtabs`, `.toast`, `.muted`, `.sr-only`. Inputs/selects/tables/focus ring are styled at element level.
  Your requests: kept exports `PanelProps`, `Href`, `Empty`, `JsonView`, `Status`, `PageHeading`, `Metric` (research-app) and `CutoffField`, `Term`, `Time`, `formatIst`, `Count` (ui.tsx; `Count` is now static, no animation). Shell renders the page `<h1>` for Results / Lab / Settings ("Results", "Lab", "Settings"); Home's h1 is "Overview"; Analyse has no shell h1. `StrategyLab` gets `tab: "backtest"|"montecarlo"` from one element instance. Links: use `href("results", { tab: "compare" })` etc.; old names (`href("imports")`) still work through normalizeView.
- ui-shell DONE (2026-11-24). Files: new `routes.ts`, `simple-ui.tsx`, `tests/routes.test.mjs`; rewritten `research-app.tsx` (shell), `premium-overview.tsx` (Home), `demo-tour.tsx` (3-step strip), `theme-toggle.tsx` (Light/Dark/System picker; exports `useTheme`, `useThemeChoice`, `setThemeChoice`), `theme-config.ts` (light default), `ui.tsx` (static `Count`, `GlossaryList` replaces the glossary drawer/`GlossaryButton`), `tests/theme.test.mjs`, and all four of my CSS files; deleted `react-bits/` (grep: no importers). Untouched: `layout.tsx`, `page.tsx`, `glossary.ts`, `use-reduced-motion.ts`. **CSS lines in my files: 2,008 → 577** (tokens 91→99, base 140→268, layout 649→88, overview 1,128→122); all six files are now 740 lines. `npm.cmd --prefix web run check` passes; node tests request-origin + theme + routes: 61/61 pass. A smoke run in Edge against :3000 (13 URLs incl. old `?view=` names, at 1366 and 390 px) showed no console errors and no horizontal scroll, and each view had the right h1 and aria-current. Not done / for others: the Home price chart was dropped (the chart is in Lab › Indicators); company-card lines show event type · conflict · coverage rather than a computed "key driver"; the e2e was not run (ui-qa).
- ui-shell → ui-qa, e2e changes: `.tour-card`, `.tour-badge`×7, "Next step", `.tour-progress` ("1 of 7 done") and `.premium-price-visual` are gone. Use `section[aria-label="Get started"]` (`.tour-strip`), 3 `.tour-steps li` (done ones have `data-done`), and the "Restart tour" / "Skip tour" buttons (restart also in Settings › About). The "Load synthetic demo (replay)" button is the primary button in an **empty** workspace and a text button in a non-empty local one; there is none in the demo workspace. The toast still has role=status and text matching /synthetic replay demo loaded/i. It hides after 5 s. `.demo-ribbon` is kept, but its text is now "Demo mode … All articles, prices and model answers are invented test data…" (the old "Synthetic demo · recorded replay" is gone). The shell h1 is "Results" / "Lab" / "Settings" (the old h1s "Strategy lab" and "Import evidence" are gone; check ui-screens' h2s). Main nav is `nav[aria-label="Main"]`; the ⚙ link is named "Settings: import data, connections, glossary". `.skip-link` is still 1 px wide when not focused. localStorage `market-events-theme` = light|dark still works; "system" is new. With nothing saved, the theme is now **light**, even when the system is dark.
- ui-screens DONE (2026-11-24). Files: `workspace-panels.tsx` (Analyse + `VerdictCard`, Saved runs, Compare methods, Indicators, Import data, Connections), `strategy-lab.tsx` (`tab` = backtest | montecarlo; Monte Carlo stays mounted so its result survives tab switches), `research-charts.tsx` (now also exports `HostedChart`, the TradingView opt-in, shown in Lab › Indicators), `types.ts` (additive: `Company.aliases/benchmark_id`, typed `assessment.inputs`, `evidence_label`, `extraction.commodity_id`, `sourceBody()`), `components.css`, `presentation.css`. Deleted `workspace-summary.tsx` (unused). My files no longer use react-bits, `Count`, `Metric`, `PageHeading` or `WorkspaceSummary`. CSS: components.css 843 → 158 lines, presentation.css 71 → 6. `npm.cmd --prefix web run check` green; `node --test` 61/61. Clicked through on :3000: backtest → Monte Carlo → back (state kept), indicators, old `?view=events` URL, three methods, Analyse → Open in Results, compare + evaluate outcomes; 390 px has no horizontal scroll; no console errors.
- ui-screens → ui-qa, renames for demo-walkthrough.spec.ts: button "Analyse under all three methods" → **"Run all three methods and compare"** (inside the Analyse `<details>` "More options"; open it first). `.selection-item.active` → `.story-row.selected` (the row shows the story title, not "syn-002"). Heading "Source inbox" → "Stories". `.run-summary .verdict` → `.verdict-card .verdict`. `.trio-card` ×3 is inside `<details open>` "Compare 3 methods". The `.score-formula` class is kept. Tooltip "Evidence coverage" now has the visible text **"Data coverage"** (same glossary entry); "Signed evidence score" is unchanged. "Model call audit" heading is kept in Results (the audit `<details>` opens by default there). Import: the h2 is "Import evidence"; the shell h1 is "Settings". Lab: the shell h1 is "Lab"; "Load local history", "Run backtest", "Equity & execution report", `.low-sample`, "Simulate return paths", `.simulation-svg` and `.chart-legend` are kept. Indicator checkboxes `.indicator-select` → `.chips` (toggle buttons). Sharpe tile: `.metric` → `.stat-tile` (the `.low-sample-flag` is inside it). The PSR tooltip is under the tiles. **Monte Carlo is now its own sub-tab**: go to `?view=lab&tab=montecarlo` (or the "Monte Carlo" sub-tab link) after the backtest; on a fresh load it offers "Run backtest with these settings".
- ui-screens: not done / notes. The indicator chips in Lab › Indicators filter the readings list; the chart overlays are toggled by the chips in Lab › Backtest (the price-history chart, because the `/technicals` API returns no indicator series). ui-shell still needs to style `.story-row`, `.score-breakdown`/`.breakdown-*` and `.avatar` (my screens render them, and they look right now, so they may already be done). The `.term`, `.cutoff-field`, `.field`, `.alert` and `.chip` overrides stay in components.css, because ui.tsx uses them.

- Codex handoff (2026-11-25). The three Herdr workers covered UI fixes, browser QA and documentation. Mobile keeps the full workspace label and the avatar beside the company heading. Home shows the largest weighted score driver when available. Analyse and Results support direct article and run links. Indicator chips now control plotted series when the historical API provides them.
- The isolated redesign passed all 12 Playwright scenarios and generated 76 screenshots across five desktop and phone configurations. The browser checks covered legacy routes, replay and repeated runs, audit and downloads, outcomes, synthetic imports, provider controls, indicators, backtests, walk-forward, Monte Carlo, and 390/360 px layouts. TradingView was stubbed. Live provider and model calls were outside the offline run.
- The shared checkout passed TypeScript, ESLint and 62 route, theme and request-origin unit tests. The Python suite passed 561 tests. The redesign snapshot uses 745 lines across the six stylesheets, down from 2,922. The presentation script keeps its 7:30 schedule. Concurrent Portfolio changes were outside the redesign browser run.
