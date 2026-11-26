# Portfolio sprint handoff

## What shipped

Market Events now has a **Portfolio** tab. It reads a holdings CSV in the browser, previews the parsed rows, and requires confirmation before replacing the current portfolio. It values holdings with saved closing prices from the active research workspace and links each holding to its company-filtered Analyse view.

The built-in sample uses the synthetic demo workspace. The new flow needs no broker account, market-data refresh, model call, or database migration. Run the existing Next.js and FastAPI stack to use it locally.

### Indian-stock paper portfolio

In **My data – real companies → Portfolio**, choose **Create ₹1,00,000 paper portfolio**. This explicitly refreshes completed daily prices for Asian Paints, Berger Paints, Pidilite, IndiGo and Reliance through the server's Analytics Token. The practice scenario targets ₹20,000 per company in whole shares, uses the refreshed closes as simulated entry costs, and retains the unspent amount as virtual cash. Prices older than four days, missing prices and failed refreshes block creation.

Review and confirm the holdings preview to create the paper account. Starting balance, unspent cash, and equity are shown above the holdings. The saved browser-tab snapshot retains the virtual cash and entry costs. Current valuation still depends on the workspace's saved closes. **Connect Upstox (optional)** imports an actual broker snapshot separately.

The scenario is built into Market Events. The extension 1.5 **Open paper portfolio** shortcut opens this screen.

## Run and demonstrate

1. From the repository root, run `npm.cmd run dev`. Follow the setup in [the project README](../README.md) if frontend or Python dependencies are missing.
2. Open `http://127.0.0.1:3000` and select **Portfolio** in the main navigation.
3. From a non-demo workspace, select **Try sample in demo**. Select **Load sample CSV** in the demo workspace. **Download sample CSV** provides the same file for a manual import demonstration.
4. Check the three rows in **Import preview**, then select **Import holdings**. The app displays total invested, market value, estimated unrealized P&L, price coverage, and each holding’s allocation and closing-price timestamp.
5. Select **View research** for `ASIANPAINT`. Analyse opens with the Asian Paints company filter and a matching story. If a story has a saved run, Analyse displays its evidence through the existing result components.
6. Return to Portfolio or reload in the same tab. The confirmed demo snapshot is still available. Switch to a different workspace to see that its snapshot is independent.

Direct demo route `/?view=portfolio&workspace=demo&universe=demo`.

The sample fixture currently produces the following results with the bundled demo closes. These prices and holdings are synthetic. If the demo fixture changes, recalculate the expected figures and update the browser assertions together.

| Metric | Expected value |
|---|---:|
| Holdings priced | 3 of 3 |
| Total invested | ₹4,150.00 |
| Market value | ₹4,469.73 |
| Estimated unrealized P&L | +₹319.73 |
| Estimated return | +7.70% |

## CSV contract

The sample also serves as the upload template.

```csv
symbol,exchange,quantity,average_cost
ASIANPAINT,NSE,10,100.00
INDIGO,NSE,5,310.00
PIDILITIND,NSE,8,200.00
```

- Use a UTF-8, comma-separated file up to 128 KiB with 1 to 250 holdings. The parser accepts LF and CRLF, a UTF-8 BOM, blank lines, quoted fields, and reordered headers. Header names, symbols, and exchange names are case-insensitive. Extra or missing columns are rejected.
- `symbol` is a normalized stock symbol. `exchange` is `NSE` or `BSE`. `quantity` is a whole share count from 1 to 100,000,000. `average_cost` is a nonnegative INR amount up to 10,000,000 with up to six decimal places. Enter decimals with a period and omit currency marks and thousands separators.
- `(exchange, symbol)` identifies a holding. A repeated key is a row error. If the CSV has separate lots, aggregate them into a single position with its weighted average cost before importing.
- File-level errors appear above the preview. Row-level errors report the CSV line. Any error blocks the entire import, so a failed replacement preserves the prior confirmed snapshot.
- Use the demo workspace when importing the downloaded synthetic sample. A file chosen through **Choose CSV** uses the current workspace.

## Where to work

| File | Responsibility |
|---|---|
| [`web/app/_components/routes.ts`](../web/app/_components/routes.ts) | Registers `portfolio` as a query-based view with no subtabs. Keeps the pre-redesign aliases. |
| [`web/app/_components/research-app.tsx`](../web/app/_components/research-app.tsx) | Adds the main navigation link and renders the lazily loaded Portfolio panel with the active workspace and link builders. |
| [`web/app/_components/portfolio-panel.tsx`](../web/app/_components/portfolio-panel.tsx) | Reads the selected file or the public sample, owns preview and confirmation, and renders the summary and the holdings table. |
| [`web/app/_lib/portfolio.ts`](../web/app/_lib/portfolio.ts) | Parses CSV, normalizes holdings, validates stored snapshots, constructs instrument IDs, and computes valuations independently of React. |
| [`web/app/_components/portfolio-panel.module.css`](../web/app/_components/portfolio-panel.module.css) | Styles allocation bars and long filenames using the shared app theme. Tables use the existing horizontal-scroll pattern. |
| [`web/app/_components/workspace-panels.tsx`](../web/app/_components/workspace-panels.tsx) | Makes `?view=analyse&company=…` open a matching story or an explicit company-specific empty state. An explicit `article` link retains its selection. |
| [`web/public/sample-portfolio.csv`](../web/public/sample-portfolio.csv) | Source for both **Load sample CSV** and **Download sample CSV**. |
| [`src/market_events/api.py`](../src/market_events/api.py) | Existing `GET /api/workspace` supplies `companies[].instrument_id`, `latest_close`, and `end`. No API change was needed. |

## Data flow and formulas

1. The browser reads the selected file with `File.text()`. The sample action fetches the shipped static CSV. The Portfolio panel sends no holdings, filenames, or CSV text to an API.
2. The preview stays in component state until the user confirms. Confirmation saves normalized rows, the filename, and an ISO import timestamp in `sessionStorage` under `market-events-portfolio-v1:<workspace>:<universe>`. The snapshot survives navigating away and reloading in the same tab. Each workspace has one current snapshot. Storage failures fall back to the current view and announce that limitation.
3. The valuation joins holdings to the catalog by exact instrument ID. Demo IDs use `NSE:ASIANPAINT`, while real-data IDs use `LIVE:NSE:ASIANPAINT`. Exchange is part of the key. An NSE price cannot value a BSE holding with the same symbol.
4. A holding is priced when the catalog provides a positive, finite saved close and a valid timestamp. The UI labels synthetic prices and shows the saved close date in IST. Catalog coverage comes from the existing workspace, so an import can include holdings with no saved quote or no supported research data.
5. Research links preserve the workspace and universe and pass only the instrument ID as `company`. Analyse prefers a saved extraction when identifying a story’s company and otherwise uses the existing name and alias matcher. Company-only links start on the newest matching published story with a saved assessment when available, then fall back to the newest matching story. Uncovered holdings open a clearly labelled empty state.

| Metric | Calculation |
|---|---|
| Invested cost | `quantity × average_cost`, summed across all holdings for **Total invested** |
| Market value | `quantity × saved_close`, summed across priced holdings |
| Estimated unrealized P&L | Priced market value minus the invested cost of those same priced holdings |
| Estimated return | Estimated P&L divided by priced holdings’ invested cost, if that cost is positive |
| Allocation | Each priced holding’s market value divided by the total market value of priced holdings |

Unpriced holdings remain visible and count toward invested cost. Their market value, P&L, and allocation are unavailable. The summary labels partial metrics and reports how many positions were priced. It shows unavailable values when coverage is zero. The app rounds currency for display and retains price precision in the estimate. The summary uses the latest saved close per holding, so close timestamps can differ. This is a current snapshot view rather than a historical valuation as of the import timestamp.

## Verification commands

From the repository root using Node.js 24 and the existing web dependencies.

```powershell
npm.cmd run check
node.exe --test web/tests/portfolio.test.mjs web/tests/routes.test.mjs web/tests/request-origin.test.mjs web/tests/theme.test.mjs
npm.cmd run build
```

With the dev stack running in another terminal and Chrome installed.

```powershell
npm.cmd --prefix web run test:e2e -- portfolio.spec.ts
```

The portfolio unit tests cover fixture totals, missing quotes, exchange and universe isolation, zero cost, CSV validation, and restored snapshot validation. The browser tests cover navigation, sample preview, confirmation, persistence, workspace separation, the research deep link, malformed uploads, and the narrow viewport. The portfolio browser tests only read the app’s workspace API. Existing research walkthrough tests may write to the demo database, so use a disposable copy when running those alongside this sprint.

Sprint verification passed TypeScript, ESLint, the production build, all 67 selected Node tests, and four Chrome tests covering Portfolio and existing navigation. The Chrome run used the production build and a disposable copy of the demo database. Desktop and 390-pixel layouts were also inspected.

## Follow-up work for agents

Use this document and the checked-in tests as the behavior contract. Keep the sample path runnable without any external accounts. Verify any changes against both the synthetic workspace and the real-company workspace.

| Follow-up | What to verify before shipping |
|---|---|
| Groww statement adapter | Check a redacted real export for exchange, symbol or ISIN, quantity, and cost fields. Feed normalized records through the same preview and confirmation. Require the user to resolve missing fields. |
| Multi-user storage | Add authenticated, durable portfolio snapshots and server-side validation. Test ownership from the API, idempotent imports, and deletion before migrating browser-only data. |
| Market-data improvements | Confirm display and storage rights for the chosen feed. Preserve source and close timestamps. Add an exchange-session-aware freshness policy if offering recent valuations. |
| Portfolio research enhancements | Reuse the existing Analyse evidence and verdict components. If adding an event summary to Portfolio, test that it cites its article, preserves the decision cutoff, and handles holdings without evidence. |

## Portfolio assistant and broker setup

### Run the offline demo

1. Run `npm.cmd run dev` from the repository root and open [Portfolio](http://127.0.0.1:3000/?view=portfolio).
2. Choose **Try sample in demo**, load the sample CSV, and confirm **Import holdings**.
3. Under **Portfolio research assistant**, pick a question about recent saved evidence, conflicts, or gaps. Each result opens a saved case with the original decision cutoff and coverage. The demo uses saved assessments and works without a model server.

In the real-company workspace, **Ask AI to suggest cases** requests a short list of relevant case IDs from the configured model. The app supplies the topic and bounded case facts from the saved ledger. It validates that the returned IDs belong to that set. Holding quantities, cost, weights, broker credentials and raw articles are excluded from the model request. Configure the existing `LLM_*` settings in the root `.env` and restart the app. Optionally set `PORTFOLIO_MODEL` to an installed model on the same endpoint. The saved-case review remains available if the model is offline.

### Connect Upstox for a holdings snapshot

Create an app in [Upstox Developer Apps](https://account.upstox.com/developer/apps) and register this exact redirect URI for the default local launcher.

```text
http://127.0.0.1:3000/api/portfolio/upstox
```

Set these server-only variables in `web/.env.local` and restart Next.js. Open the same host and port as the registered callback.

```dotenv
UPSTOX_CLIENT_ID=
UPSTOX_CLIENT_SECRET=
UPSTOX_REDIRECT_URI=http://127.0.0.1:3000/api/portfolio/upstox
```

In **My data – real companies → Portfolio**, click **Connect Upstox**, sign in on Upstox, then choose **Preview Upstox holdings → Import holdings**. Repeat the connection to retrieve a new snapshot. Use **Choose CSV** for Groww and other sources after mapping the export to the four supported columns.

The connector exchanges the authorization code server-side when the holdings preview opens and uses the access token for one holdings request. OAuth state and the authorization code use a ten-minute encrypted, HttpOnly cookie, so the flow can cross Vercel instances. Upstox consumes the code once. Confirmed holdings stay in browser-tab storage. Register `https://final-yr-proj.vercel.app/api/portfolio/upstox` for the deployed app and configure its OAuth secrets in Vercel Production. Broker OAuth credentials are separate from `UPSTOX_ANALYTICS_TOKEN`, which powers recent prices and news. Real holdings outside the workspace universe still appear in the table, with saved prices and research marked unavailable where applicable.

### Install the Chrome shortcut locally

In Chrome, open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the repository’s `extension` folder. If it is already installed, click **Reload** on its extension card. Pin **Market Events Portfolio** and click its toolbar icon. Version 1.4 defaults to the deployed website, with **Local workspace** available in the website selector.

Choose **Connect Upstox** to open a compact sign-in window. Vercel may first ask you to sign in. Enter your mobile verification and PIN on Upstox's page. After Upstox redirects back, the extension moves Portfolio to the original browser window and the website automatically previews the holdings. Select **Import holdings** to confirm the replacement and open the portfolio research. The extension stores only the temporary window/tab routing information in session storage.

Switch between **Real data** and **Demo** to preview saved assessments. **Open for analysis** opens the saved case, and **Open Portfolio** opens the selected workspace. A protected deployed workspace may require opening and signing into the website before saved previews become available in the extension.

### Current verification

The extension 1.4 handoff changed `extension/manifest.json`, `popup.html`, `popup.css`, `popup.js`, the new `background.js`, the Portfolio panel, and the Upstox route. Verification passed TypeScript and ESLint, four Playwright browser/OAuth checks, and the extension worker routing test. The website update was deployed to production and its extension entry reached Upstox's PIN screen. Next open item is reloading extension 1.4 in Chrome and completing real-account PIN verification to check the popup-to-main-window transition.

The Portfolio browser checks and mocked OAuth checks passed. The review API also returned the expected case from a disposable synthetic ledger using local Qwen on CPU. Next open item is verification with an authenticated Upstox account and configured market-data credentials.

### 26 November 2026 initial paper release verification (superseded below)

The current release uses Sarvam's hosted models; the local Qwen result above describes an earlier checkpoint. Extension 1.5 adds **Open paper portfolio** and labels broker connection optional. Changed runtime files for the paper account are `web/app/_lib/paper-portfolio.ts`, `portfolio.ts`, `portfolio-panel.tsx`, and `research-app.tsx`, plus the extension popup and manifest.

Verification passed 564 Python tests, 69 JavaScript tests, all 20 Playwright scenarios, TypeScript, ESLint, and a production build. Browser coverage includes imports, saved cases and exports, indicators, backtest/walk-forward, Monte Carlo, mobile layouts, paper account confirmation/persistence, and mocked OAuth/extension routing. The TradingView widget's external loading was stubbed in browser tests. Separate disposable-database integration checks exercised real Upstox prices/news and Sarvam structured extraction and explanation.

Production was deployed and promoted to `https://final-yr-proj.vercel.app`. A fresh authenticated Brave tab created and confirmed the five-stock paper portfolio from completed 25 November daily closes. All five positions were priced; invested cost was ₹93,966.65 and unspent virtual cash ₹6,033.35, conserving the ₹1,00,000 balance. The holdings and cash survived reloading and returning to Portfolio.

Open items: reload extension 1.5 in Chrome and complete the real Upstox PIN flow to verify actual holdings and the installed extension's window transition. Live research storage on Vercel remains temporary and can reset across deployments or instances; durable authenticated storage is still needed. Paper holdings and cash persist in the browser tab, while current valuations depend on saved server prices.

### 26 November 2026 durable-storage and live-demo release

Production now uses a connected free Neon Postgres database for private portfolios, articles, observations, runs, model traces and outcomes. The database URL is excluded from saved configuration and never sent to the browser. SQLite remains supported locally and for the isolated synthetic demo. Hosted startup requires a persistent database; it no longer silently saves private data under `/tmp`. The existing Vercel project authentication remains required for all deployments, with zero protection-bypass credentials.

Confirmed private portfolios load from the server in new tabs and after deployments. Previously confirmed browser-tab holdings migrate only into an empty server snapshot. Revision checks reject stale writes from other tabs, and clearing retains a tombstone to prevent old cached holdings from reappearing. Authorized project visitors share the private workspace; per-user ownership is a separate future feature.

The live paper section refreshes bounded Upstox latest-price snapshots every 15 seconds while visible, shows trade/fetch timestamps and missing coverage, and leaves immutable daily research observations unchanged. It offers a selected one-minute TradingView chart and a direct TradingView link. The hosted widget was observed loading its external frame, but complete real chart rendering was not confirmed; exchange entitlements and availability remain external constraints. No real orders are executed.

Both hosted Sarvam analysis roles succeeded on imported provider news, saving parent run `63500fcf-d195-4464-ac1f-688069e62fc6` and successful explanation child `9623a56b-a3b5-4eee-9d03-141b8ac4bd8b`. The parent abstained because the news described an unsupported event family. A second production deployment restored the same five positions, cash, 424 observations and both runs. The full saved case payload and portfolio matched the before-deployment copy.

The combined release passed 570 Python tests (three opt-in Postgres variants skipped in that offline run), 69 JavaScript tests, all 22 Playwright scenarios, TypeScript, ESLint and the production build. A separate database integration run passed all seven persistence checks, including the three Postgres variants in isolated temporary schemas. Visual review checked 13 views/subtabs at three widths: 39 layout checks passed; intro dismissal, reduced motion and theme contrast were also checked.

The visual release gives every page a shared theme and motion system plus a skippable first-visit Home introduction. Runtime files include the Postgres/quote adapters, API schemas/routes, portfolio persistence hook, live paper panel, shared styles and introduction. Deployment `dpl_HH6o5opB2Cw1hhuw1MwjYKWj7bd2` was promoted to `https://final-yr-proj.vercel.app` after the redeploy check.

Troubleshooting and verification are centralized in [diagnostics](../diagnostics/README.md), with [sanitized redeploy proof](../diagnostics/evidence/2026-11-26/redeploy-proof.json). Complete local outputs and the pre-cleanup synthetic database were archived under ignored `diagnostics/local/2026-11-26/`. The bundled demo fixture was restored to the committed synthetic baseline instead of shipping extra test runs. The old scratch export left the project root. Credentials, private data, local agent skills, caches and diagnostic archives remain excluded from Git/Vercel.

Next open items: installed Chrome extension and authenticated broker holdings verification after user PIN entry. The [extension review](EXTENSION_INTEGRATION_IDEAS.md) proposes future selected-news capture and a side panel; those features are not shipped. Use [MENTOR_SHOWCASE.md](MENTOR_SHOWCASE.md) for the complete demonstration flow.

### Follow-up stock and chart release

Home shows the full tracked company list and distinguishes companies with saved analysis from companies awaiting analysis. A separate card links to the saved paper portfolio and displays its virtual balance and cash. The Portfolio picker searches the Upstox NSE and BSE directories and previews up to 10 selected stocks at completed daily prices. A confirmed snapshot registers the provider-matched stocks for research in the active workspace.

Portfolio and the real-company Lab render five-minute Upstox candles with TradingView Lightweight Charts. The public TradingView widget refused the NSE Asian Paints symbol during reproduction. The site now provides an external TradingView link alongside the in-app chart. Prices and candles work with paper and broker-style imports, with missing coverage reported when Upstox cannot match or price a holding.

Verification passed 26 browser scenarios, 570 Python tests, 69 JavaScript tests, type checking, lint and the production build. A disposable workspace saved Infosys on NSE and TCS on BSE, priced and charted both in paper and broker-style flows, and imported nine news items with no provider errors. Brave confirmed real charts for Asian Paints and Reliance, the Lab chart, BSE ticker search, and the loaded Geist font. The actual Upstox account's OTP/PIN flow remains to be verified by the account holder.
