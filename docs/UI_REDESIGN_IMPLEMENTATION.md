# Implementation brief: simple UI redesign (4 tabs, clean white)

> Give this file to Claude Code from the repository root:
> `claude "Read docs/UI_REDESIGN_IMPLEMENTATION.md and implement it fully. Follow every rule in it."`
>
> Approved mockup (Home + Analyse): https://claude.ai/artifact/RfJvgnTcWQMh2tK1DBnw1z
> If you cannot open it, sections 3–5 below describe it fully.

## 0. Goal

Make the Next.js dashboard in `web/` **as simple as possible while keeping every feature**.
Groww-style simplicity is the inspiration (clean white, big numbers, one clear action per screen).
**Do not copy Groww's branding, logo, colours or layouts.** Keep the name "marketevents".

Today: 8 top tabs, 3 stacked banners, a 7-step tour block and a lot of explanatory text.
Target: **4 tabs + a Settings menu**, **one** demo banner line, plain short copy, and the details
folded away in `<details>` sections.

## 1. Hard rules

1. **UI only.** Do not change the Python engine (`src/`), the API contract
   (`web/app/api/research/[...path]/route.ts`, `api.py`), saved data or calculations. Every number
   on screen still comes from the API.
2. **No feature removed.** Everything in the section-7 checklist must still be reachable
   (≤ 2 clicks from the new tab it belongs to).
3. **Keep old URLs working.** `?view=overview|events|technicals|lab|saved|comparisons|imports|connections`
   must redirect or map to the new views (section 2), keeping the other query params
   (`workspace`, `universe`, `article`, …).
4. **Read `web/AGENTS.md` first.** This is Next.js 16: check `node_modules/next/dist/docs/` before
   using any routing or rendering API you are unsure of.
5. **No new dependencies.** Keep `lightweight-charts` and `lucide-react`. Remove the decorative
   `react-bits` effects (Aurora, ShinyText, SpotlightCard, CountUp animations, AnimatedContent) from the
   screens. Delete their files only if nothing imports them any more, and keep their LICENSE note
   in the git history (just delete the folder; don't edit licences).
6. **Accessibility stays at least as good:** real `<button>`/`<a>`/`<label>`, visible focus ring,
   44 px touch targets, text contrast ≥ 4.5:1 (`web/tests/theme.test.mjs` or the existing contrast
   test must pass with the new tokens), green/red always paired with ▲/▼ or a word, `prefers-reduced-motion` respected.
7. **Works on a phone** (360 px wide): nav wraps or becomes a menu, grids collapse to one column,
   tables scroll inside their box.
8. **Git:** create branch `feat/simple-ui` first. Do not commit or push unless the user asks.
9. **Research labels stay:** "Demo mode / synthetic", "not advice", "evidence score is not a
   probability", "history ends 31 Dec 2020", "no order execution" must remain visible where they are
   today (shorter wording is fine).

## 2. New information architecture

| New tab | `?view=` | Contains (old sections) | Old views mapped here |
|---|---|---|---|
| **Home** | `home` | overview, summary numbers, company cards, latest stories, 3-step start strip | `overview` |
| **Analyse** | `analyse` | event research: story list, decision time, method, Analyse, verdict | `events` |
| **Results** | `results` | sub-tabs **Saved runs** (old saved) and **Compare methods** (old comparisons + outcomes) | `saved`, `comparisons` |
| **Lab** | `lab` | sub-tabs **Indicators** (old technicals), **Backtest**, **Monte Carlo** (old strategy lab) | `technicals`, `lab` |
| ⚙ **Settings** (icon button, not a tab) | `settings` | sub-tabs **Import data** (old imports), **Connections**, **Glossary**, **Appearance** (light/dark) | `imports`, `connections` |

Sub-tabs use a `tab=` query param (e.g. `?view=results&tab=compare`), are real links or
`role="tablist"` buttons, and keep their state in the URL so the back button works.

Implement the mapping in one place (e.g. `app/_components/routes.ts`): `normalizeView(view, tab)` →
`{ view, tab }`, used by `research-app.tsx`. Unit-test it in `web/tests/routes.test.mjs` with the Node test runner, like
`tests/request-origin.test.mjs`.

## 3. Visual design (tokens)

Rewrite `web/app/tokens.css` values; keep the variable **names** so components keep working.
**Light is the default**: change `THEME_INIT_SCRIPT` in `app/theme-config.ts` so that with no saved
choice the theme is `light` (dark only when the user picks it in Settings → Appearance).

Light palette:

| Token | Value | Use |
|---|---|---|
| `--mode-bg`, `--mode-shell`, `--mode-panel` | `#FFFFFF` | page and cards |
| `--mode-raised` | `#F7F8FA` | soft blocks, banner, quote |
| `--mode-hover` | `#F0F2F6` | hover |
| `--mode-border` | `#E6E8EC` | card borders, dividers |
| `--mode-input-border` | `#D5D9E0` | inputs, secondary buttons |
| `--mode-text` | `#111827` | text |
| `--mode-muted` | `#5B6472` | secondary text |
| `--mode-primary` / `--mode-primary-ink` | `#2F55D4` / `#FFFFFF` | the one accent: primary buttons, active tab text `#1F3FA8` on `#EEF2FD` |
| `--mode-link` | `#2F55D4` | links |
| `--mode-success` / `-bg` | `#0F7A4A` / `#E7F6EE` | positive, ▲ |
| `--mode-danger` / `-bg` | `#B42318` / `#FDECEA` | negative, ▼ |
| `--mode-warning` / `-bg` | `#8A5A00` / `#FFF4DC` | mixed, demo badge |
| neutral pill | `#374151` on `#F1F2F4` | no verdict / abstained |

Dark palette: same roles on `#0E1116` bg, `#161A21` panels, `#2A303A` borders, `#E8EAED` text,
`#A3ABB8` muted, accent `#7B97F0`; pass the same contrast test.

Type: **Inter** (Google Fonts via `next/font/google` if available offline in build, else keep the
system stack `Inter, "Segoe UI", system-ui, sans-serif`). Sizes: page title 26–28 px/700, section
title 17–18 px/600, body 15 px, small 13 px, big numbers 26–30 px/700. Radius: cards 14 px, inputs and
buttons 10 px, pills 999 px. Spacing scale 4/8/12/16/20/24/32. No gradients, glows, aurora or
shadows heavier than `0 1px 2px #0000000d`.

Verdict pill mapping (use everywhere: Home cards, story lists, Results tables):
`positive_evidence` → "▲ Positive" (success) · `negative_evidence` → "▼ Negative" (danger) ·
`mixed_evidence` → "◆ Mixed" (warning) · `insufficient_evidence`/abstain → "— No verdict" (neutral) ·
filtered irrelevant → "Not relevant" (muted text, no pill).

## 4. Shared shell (all views)

- **Top bar** (64 px, white, bottom border): logo left → 4 tabs (pill style, active = `#EEF2FD`
  bg + `#1F3FA8` text + `aria-current="page"`) → right side: workspace `<select>` (labels:
  "Demo data (offline)", "My data – real companies", "My data – demo companies") and a 44 px ⚙
  icon button (`aria-label="Settings: import data, connections, glossary"`) linking to `?view=settings`.
  Keep the small "API connected" status as a dot + text inside Settings → Connections and as a
  tooltip on the ⚙ button; show a visible red notice in the shell only when the API is down.
- **Remove** the left sidebar and the duplicated desktop nav; on phones the tabs wrap.
- **One banner line** under the top bar, only in demo workspaces: badge "Demo mode" + "All articles,
  prices and model answers are invented test data. Not advice; nothing here places orders." +
  link "What does this mean?" (opens the glossary entry). Replace today's yellow banner, the green
  dismissible notice and the tour block. Action notices (e.g. "demo loaded") become a small toast
  `role="status"` that auto-hides after 5 s and can be dismissed.
- **Footer:** "Research tool, not advice · Strategy history ends 31 Dec 2020 · No order execution".
- Content width `max-width: 1160px`, side padding 24 px.

## 5. Screens

### 5.1 Home (`?view=home`) — matches mockup artboard "Home"
1. Title "Overview" + one line: "`N` stories · `M` analysed · cutoff `<latest cutoff>`".
   Right: secondary "Import news" (→ Settings › Import data) and primary "Analyse a story" (→ Analyse).
   When the workspace is empty, the primary button becomes **"Load synthetic demo (replay)"**
   (keep this exact label: the e2e test uses it).
2. **"New here?"** strip: 3 steps — Load the demo · Pick a story · Read the verdict — with ✓ for
   done steps and a "Continue tour →" link. Reuse the step-tracking from `demo-tour.tsx`
   (`markTourStep`, `useTourSteps`), mapping its 7 steps onto these 3 (steps 4–7 live as a
   "Next: compare methods / see what happened / test a price rule" link list shown after step 3 is done).
   "Skip tour" hides the strip (persisted as today).
3. **Summary:** 4 tiles — Analysed · Positive evidence · Mixed · Not enough evidence (counts from
   the latest run per company).
4. **Companies:** responsive grid of cards (`repeat(auto-fit, minmax(260px, 1fr))`), one per company
   with a saved run: initials avatar, name, `NSE · SYMBOL`, verdict pill, big signed score
   (2 decimals, coloured by verdict) + "evidence score", one line: event type · key driver ·
   coverage. Card links to Analyse for that company's latest article. Abstained cards show "—" and
   the abstention reason in plain words.
5. **Latest stories** (side column, stacks under on phones): 5 newest articles, title, company ·
   time · verdict word; "See all" → Analyse.
6. Keep the price/coverage visual from `premium-overview.tsx` only if it fits as a small card;
   otherwise drop it from Home (the price chart lives in Lab › Indicators).

### 5.2 Analyse (`?view=analyse`) — matches mockup artboard "Analyse"
Two columns (stacks on phone): **left** story list (search box, rows with title + company +
verdict word, selected row `#EEF2FD`), **right**:
1. Company header: avatar, name (h1), `NSE · SYMBOL · sector · benchmark`.
2. **Story card:** headline (h2), quoted source sentence, published / first seen / synthetic note.
   Controls in one row: **Decision time** (reuse `CutoffField` with its presets incl.
   "Use demo cutoff"), **Method** select (3 policies, plain names), primary **Analyse** button
   (keep the existing request and the accessible name "Analyse and save run" via `aria-label` if
   tests rely on it). Hint below: "Only news and prices available before the decision time are used."
   `<details>` "More options": **Analysis mode** select (recorded replay / live model),
   "Run all three methods and compare" (keeps "Analyse under all three methods" behaviour),
   "Repeat experiment (creates a linked run)".
3. **Verdict card** (after a run or when a saved run exists):
   - 3 tiles: Evidence (verdict pill, big) · Score (−1 to +1) · Data coverage.
   - One plain-language sentence (from `plain_language.py` output already in the API).
   - **"What pushed the score"**: one row per component with ▲/▼, plain label, weight and signed
     contribution (e.g. "Stock vs Nifty 50 · +0.80% (weight 60%) +0.40"; "Crude oil +1.50%, a cost
     for paint makers (weight 40%) −0.50"), then the formula line in monospace
     ("0.6 × 0.40 + 0.4 × (−0.50) = +0.04 · inside ±0.15, so mixed").
   - Conflicts / abstention reasons as a short bullet list under the formula.
   - **"What happened next"** row when an outcome exists (next open → 5th close, after costs).
   - `<details>` "Numbers at the decision time" (the inputs table).
   - `<details>` "Full audit trail" (source passages, extraction, model call trace, JSON via `JsonView`).
   - When three methods ran: a compact 3-column comparison inside a `<details>` "Compare 3 methods".
   - Buttons: "Download snapshot", "Open in Results".
   - Footnote: "The score measures evidence strength. It is not a probability or a forecast."

### 5.3 Results (`?view=results`)
Same shell and card style. Sub-tabs:
- **Saved runs** (`tab=saved`): searchable table (company, story, cutoff, method, verdict pill,
  score, coverage, outcome) → row opens the same verdict card as Analyse (reuse the component).
  Keep "Model call audit", outcome card and snapshot download.
- **Compare methods** (`tab=compare`): "Method usage" summary as 3–4 tiles, then the comparison
  tables, "Evaluate later outcomes" button, matched cohorts / ablations / agreement checks each in
  a `<details>`. Keep the exact headings the e2e test uses ("Method usage", column "Evidence label")
  or update the test.

### 5.4 Lab (`?view=lab`)
Banner inside the tab: "Historical study · data ends 31 Dec 2020 · not a forecast".
Sub-tabs:
- **Indicators** (`tab=indicators`): company select, indicator chips (SMA20/50/200, EMA20/50,
  RSI14, MACD, Bollinger, ATR14, ADX14, volume), the Lightweight Charts price chart, plain reading
  of each indicator. Hosted TradingView widget stays opt-in in a `<details>`.
- **Backtest** (`tab=backtest`): one form card (company, dates, strategy, capital, costs) with
  advanced parameters in `<details>`, primary "Run backtest", result: verdict line, 4 metric tiles
  (return, max drawdown, Sharpe, trades), equity chart, trades table, walk-forward in `<details>`,
  download. Keep "Load local history" and the heading "Equity & execution report" (e2e test).
- **Monte Carlo** (`tab=montecarlo`): seed / paths / horizon form, chart with pause / replay,
  reduced-motion respected, text summary.

### 5.5 Settings (`?view=settings`)
Left list of sub-tabs on desktop, top tabs on phone:
- **Import data** (`tab=import`): today's import forms (articles, prices), heading stays
  "Import evidence" or update the e2e test.
- **Connections** (`tab=connections`): API status, Upstox / model server setup and sync buttons
  (today's ConnectionsPanel). Never show secrets.
- **Glossary** (`tab=glossary`): the glossary list from `glossary.ts`, searchable. The `Term`
  tooltips elsewhere stay.
- **Appearance** (`tab=appearance`): Light / Dark / System radio (reuse `theme-toggle.tsx` logic).
- **About** : research-only notice, licences (react-bits removal noted), version.

## 6. Code plan

1. Branch; read `web/AGENTS.md`, `research-app.tsx`, `workspace-panels.tsx`, `strategy-lab.tsx`,
   `premium-overview.tsx`, `demo-tour.tsx`, `ui.tsx`, the CSS files and `tests/demo-walkthrough.spec.ts`.
2. Add `routes.ts` (view/tab mapping) + its unit test; switch `research-app.tsx` to it.
3. New tokens + light default; run the contrast test.
4. New shell (top bar, banner, toast, footer); remove sidebar.
5. Shared small components in `ui.tsx` (or a new `simple-ui.tsx`): `VerdictPill`, `ScoreValue`,
   `StatTile`, `CompanyCard`, `StoryRow`, `SubTabs`, `ScoreBreakdown`, `VerdictCard`.
6. Rebuild screens in this order: Analyse → Home → Results → Lab → Settings. Move logic, don't
   rewrite it: keep the existing API calls and state, change markup and CSS.
7. CSS: aim to **shrink** the six CSS files (today ~2,900 lines). Delete unused rules; target
   under 1,500 lines total. Keep the file split and import order in `layout.tsx`.
8. Update `tests/demo-walkthrough.spec.ts` to the new navigation (via the old URLs **and** the new
   tabs), then regenerate `tests/screenshots/` for 1366×768 and 1920×1080, light and dark, plus add
   390×844 (phone) light.
9. Update `web/README.md`, `docs/USER_GUIDE.md`, `docs/DEMO_AND_VIVA.md` and append a dated entry to
   `docs/DECISIONS.md` ("Simplified UI: 4 tabs + Settings, light default; no engine change").

## 7. Feature checklist (all must still work)

- [ ] Load synthetic demo (replay) · workspace switcher (3 options) · API status
- [ ] Guided tour progress (3 visible steps + later steps) · skip/restart tour
- [ ] Story inbox search · story details (published / first seen / synthetic)
- [ ] Decision cutoff with presets · 3 methods · analysis mode (replay / live) · repeat experiment
- [ ] Analyse one method · analyse all three · verdict, score, coverage, conflicts, abstention reasons
- [ ] Score formula · inputs at cutoff · source passages · extraction · model call audit · JSON view
- [ ] Outcomes (evaluate later outcomes, what happened next) · download run snapshot
- [ ] Saved runs list · method comparisons, usage, matched cohorts, ablations, agreement
- [ ] Technical indicators + price chart · TradingView opt-in widget
- [ ] Load local history · historical sync (explicit) · backtest · walk-forward · trades · downloads
- [ ] Monte Carlo with pause / replay / reduced motion
- [ ] Import articles and prices · connections / live sync · glossary · light/dark theme
- [ ] All research / not-advice / 2020 / no-orders labels

## 8. Done checklist (Windows, repo root)

```powershell
npm.cmd --prefix web run check          # tsc + eslint
node --test web/tests/request-origin.test.mjs web/tests/theme.test.mjs web/tests/routes.test.mjs
npm.cmd --prefix web run test:e2e       # Playwright walkthrough (start the app first if the config needs it)
.\.venv\Scripts\python.exe -m pytest -q # engine untouched, must stay green
npm.cmd run dev                         # open http://127.0.0.1:3000 and click through all 4 tabs + Settings
```
- [ ] Every item in section 7 ticked by actually using it in the browser (demo workspace).
- [ ] Old `?view=` URLs land on the right new tab.
- [ ] Phone width (390 px): no horizontal page scroll; nav usable.
- [ ] Light default; dark mode works; contrast test passes.
- [ ] Screenshots regenerated; docs updated; nothing committed unless asked.
- [ ] Final message: files changed, CSS lines before → after, test results, anything not done.
