# Market Events: web dashboard

A Next.js (App Router) front end for the Python research pipeline in `src/market_events/`.
It is a single page: the `?view=` query selects a section, and `?workspace=` / `?universe=`
select which local database and company universe the Python API reads.

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
│  │  ├─ premium-overview.tsx   Overview section
│  │  ├─ research-guide.tsx     "Your research path" card on the overview
│  │  ├─ workspace-panels.tsx   Event research, Saved results, Import, Indicators, Connections, Comparisons
│  │  ├─ strategy-lab.tsx       Strategy lab: history, backtest, Monte Carlo
│  │  ├─ research-charts.tsx    PriceChart / EquityChart (lightweight-charts)
│  │  ├─ workspace-summary.tsx  Summary strip under section headings
│  │  ├─ theme-toggle.tsx       Light/dark toggle + useTheme()
│  │  ├─ use-reduced-motion.ts  Reduced-motion hook
│  │  ├─ types.ts               API response types + formatting helpers
│  │  └─ react-bits/            Third-party visual effects (Aurora, SpotlightCard), MIT, see its LICENSE.md
│  └─ *.css                 Stylesheets, imported in this order by layout.tsx:
│     ├─ tokens.css         Design tokens (CSS custom properties) for dark and light mode
│     ├─ base.css           Element defaults, accessibility helpers, keyframes
│     ├─ layout.css         App shell: sidebar, top bar, page heading, footer
│     ├─ components.css     Panels, forms, buttons, tables, pills, alerts, charts, result cards
│     ├─ overview.css       Overview section and research guide
│     └─ presentation.css   Projector readability overrides (loaded last)
├─ tests/
│  ├─ demo-walkthrough.spec.ts   Playwright: the 7-step demo story in light/dark at 1366×768 and 1920×1080
│  ├─ screenshots/               Output of the walkthrough
│  ├─ request-origin.test.mjs    Node unit tests for the origin guard
│  └─ theme.test.mjs             Node unit tests for theme logic and colour-contrast thresholds (reads tokens.css)
├─ playwright.config.ts
└─ package.json
```

Some rules carry a `:root` prefix (for example `:root .panel`). This raises their specificity so the
light/dark colour rules win over earlier structural rules. Keep the stylesheet import order unchanged.

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
- Workspaces: `workspace=demo` uses the synthetic replay database (`data/web_demo.sqlite`);
  `workspace=local` uses your own database. Nothing contacts a market data provider or a model
  unless you press the button for that explicit action.

## Run, check and test

Run these from the project root (Windows: `npm.cmd`). Install the dependencies once with `npm.cmd --prefix web install`.

| Task | Command |
| --- | --- |
| Dev stack (Python API on :8000 + Next.js on :3000) | `npm.cmd run dev` |
| Same, for a presentation (production build, no dev overlay, no API hot reload) | `npm.cmd run build` then `npm.cmd run dev -- --stage` |
| Type check + lint | `npm.cmd run check` |
| Production build | `npm.cmd run build` |
| Demo walkthrough (needs the dev stack running) | `cd web` then `npx playwright test` |
| Unit tests (origin guard, theme) | `node --test web/tests/request-origin.test.mjs web/tests/theme.test.mjs` |

`scripts/dev-web.mjs` starts both servers and restarts either one if it crashes. To keep the Python API
running across source edits, set `MARKET_EVENTS_API_RELOAD=0`, which turns off its hot reload.
Playwright uses the locally installed Chrome. Set `PLAYWRIGHT_CHANNEL=chromium` to use Playwright's
bundled browser instead.
