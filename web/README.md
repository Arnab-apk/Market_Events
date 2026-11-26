# Market Events: web dashboard

A Next.js (App Router) front end for the Python research pipeline in `src/market_events/`.
The dashboard navigation has **Home**, **Portfolio**, **Analyse**, **Results** and **Lab**, plus a
**Settings** gear. **Portfolio** creates an Indian-stock paper account, imports a holdings CSV or optionally connects Upstox, and opens saved company research. Confirmed private-workspace holdings are saved server-side; the synthetic demo remains isolated to the browser tab.
**Home** opens **Overview**. **Results** opens **Saved runs**, with **Compare methods** alongside it.
**Lab** opens **Indicators**, alongside **Backtest** and **Monte Carlo**. **Settings** opens
**Import data**, alongside **Connections**, **Glossary**, **Appearance** and **About**.

`?view=` selects the main view and `?tab=` selects a section inside Results, Lab or Settings.
`?workspace=` and `?universe=` select the database and company universe the Python API reads.
Old links still open the corresponding new section, including `?view=events` for Analyse,
`?view=saved` for Saved runs and `?view=lab` without a tab for Backtest. The **Lab** tab in the
header links to `?view=lab&tab=indicators`.

## Folder structure

```
web/
├─ app/
│  ├─ layout.tsx            Root HTML; imports the stylesheets in cascade order; sets the theme before paint
│  ├─ page.tsx              Route "/" → <ResearchApp />
│  ├─ theme-config.ts       Theme storage key + inline pre-paint script
│  ├─ icon.svg              Favicon
│  ├─ api/research/[...path]/route.ts   Proxy from the browser to the Python API (see below)
│  ├─ _lib/request-origin.ts            Same-machine origin check used by the proxy
│  ├─ _components/
│  │  ├─ research-app.tsx       App shell, navigation, workspace loading, shared UI pieces
│  │  ├─ routes.ts              Current routes and legacy URL mapping
│  │  ├─ premium-overview.tsx   Home overview, company cards and latest stories
│  │  ├─ demo-tour.tsx          Home quick start and tour progress
│  │  ├─ glossary.ts            Plain-English intros and term definitions (from UX_AUDIT.md §3)
│  │  ├─ ui.tsx                 Term tooltips, decision-time field, glossary search and error messages
│  │  ├─ simple-ui.tsx          Shared verdict, score, card, sub-tab and toast components
│  │  ├─ workspace-panels.tsx   Analyse, Results, Indicators, Import data and Connections
│  │  ├─ strategy-lab.tsx       Historical prices, Backtest and Monte Carlo
│  │  ├─ research-charts.tsx    Price and equity charts plus opt-in TradingView
│  │  ├─ theme-toggle.tsx       Light, Dark and System settings
│  │  ├─ use-reduced-motion.ts  Reduced-motion hook
│  │  └─ types.ts               API response types and formatting helpers
│  └─ *.css                 Stylesheets, imported in this order by layout.tsx:
│     ├─ tokens.css         Design tokens (CSS custom properties) for dark and light mode
│     ├─ base.css           Element defaults, accessibility helpers, keyframes
│     ├─ layout.css         App shell, top bar, page headings and footer
│     ├─ components.css     Panels, forms, buttons, tables, pills, alerts, charts, result cards
│     ├─ overview.css       Overview section and research guide
│     ├─ presentation.css   Projector readability overrides
│     └─ research-desk.css  Shared visual system, first-visit introduction and reduced-motion-aware animation
├─ tests/
│  ├─ demo-walkthrough.spec.ts   Playwright: desktop light/dark, phone, navigation and demo flows
│  ├─ screenshots/               Output of the walkthrough
│  ├─ request-origin.test.mjs    Node unit tests for the origin guard
│  ├─ routes.test.mjs            Node unit tests for current and legacy navigation
│  └─ theme.test.mjs             Node unit tests for theme logic and colour-contrast thresholds (reads tokens.css)
├─ playwright.config.ts
└─ package.json
```

Light is the default. **Settings › Appearance** offers **Light**, **Dark** and **System** and saves
the choice in the current browser. Use **Settings › About › Restart the tour** to restore the
**New here?** strip after skipping it. Keep the stylesheet import order in `layout.tsx`.

## How the front end talks to the Python API

```
Browser ──fetch──▶ /api/research/<endpoint>?workspace=…&universe=…   (Next.js route handler)
                        │  allow-listed endpoint? same-machine origin for writes?
                        ▼
                   http://127.0.0.1:8000/api/<endpoint>               (FastAPI: src/market_events/api.py)
```

- Every panel calls the `api` helper created in `research-app.tsx`. A call with no body is a GET;
  a call with a body is a POST with JSON.
- Reads: `workspace`, `comparisons`, `health`, `case/<run_id>`.
- Writes: `demo`, `import`, `analyse`, `technicals`, `history`, `backtest`, `monte-carlo`, `outcomes`,
  `analyse-news`, `explain/<run_id>`, `sync/historical`, `sync/live`.
- The proxy target comes from `MARKET_EVENTS_API_URL` (default `http://127.0.0.1:8000`).
- On Vercel (`vercel.json` at the project root), the Python API runs as a private `api` service and
  Vercel fills in `MARKET_EVENTS_API_URL` itself. `vercel_app.py` copies the demo database to `/tmp`, so
  changes reset whenever a new instance starts. Writes are accepted only from the site's own origin.
- **Demo data (offline)** uses `workspace=demo` and the synthetic replay database
  (`data/web_demo.sqlite` by default). Both **My data** options use `workspace=local` and select
  their company universe with `universe=live` or `universe=demo`. Provider, model and hosted
  TradingView requests each require an explicit action.

## Run, check and test

Run these from the project root (Windows: `npm.cmd`). Install the dependencies once with `npm.cmd --prefix web install`.

| Task | Command |
| --- | --- |
| Dev stack (Python API on :8000 + Next.js on :3000) | `npm.cmd run dev` |
| Same, for a presentation (production build, no dev overlay, no API hot reload) | `npm.cmd run build` then `npm.cmd run dev -- --stage` |
| Type check + lint | `npm.cmd run check` |
| Production build | `npm.cmd run build` |
| Demo walkthrough (needs the dev stack running) | `npm.cmd --prefix web run test:e2e` |
| Unit tests (origin guard, theme, routes) | `node --test web/tests/request-origin.test.mjs web/tests/theme.test.mjs web/tests/routes.test.mjs` |

`scripts/dev-web.mjs` starts both servers and restarts either one if it crashes. To keep the Python API
running across source edits, set `MARKET_EVENTS_API_RELOAD=0`, which turns off its hot reload.
Playwright uses the locally installed Chrome. Set `PLAYWRIGHT_CHANNEL=msedge` for Microsoft Edge
or `PLAYWRIGHT_CHANNEL=chromium` for Playwright's bundled browser. Set `PLAYWRIGHT_BASE_URL` to
test a separate dev stack. The walkthrough creates synthetic runs and writes screenshots under
`web/tests/screenshots/` for 1366×768 and 1920×1080 in both themes, and 390×844 in light.
