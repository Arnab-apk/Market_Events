# Portfolio sprint handoff

## What shipped

Market Events now has a **Portfolio** tab. It reads a holdings CSV in the browser, previews the parsed rows, and requires confirmation before replacing the current portfolio. It values holdings with saved closing prices from the active research workspace and links each holding to its company-filtered Analyse view.

The built-in sample uses the synthetic demo workspace. The new flow needs no broker account, market-data refresh, model call, or database migration. Run the existing Next.js and FastAPI stack to use it locally.

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

The local connector exchanges the authorization code server-side and uses the access token for one holdings request. The normalized draft expires within ten minutes and can be opened once in the same browser. Confirmed holdings stay in browser-tab storage. The connector accepts the registered loopback origin and needs a single running Next.js instance. Broker OAuth credentials are separate from `UPSTOX_ANALYTICS_TOKEN`, which powers recent prices and news. Real holdings outside the workspace universe still appear in the table, with saved prices and research marked unavailable where applicable.

### Install the Chrome shortcut locally

In Chrome, open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the repository’s `extension` folder. If it is already installed, click **Reload** on its extension card. Pin **Market Events Portfolio** and click its toolbar icon. Switch between **Real data** and **Demo** in the popup. When no real assessment exists, the popup starts in Demo. Choose **Real data → Set up real data** to open Connections without losing access to the demo. Click **Open for analysis** to open the exact verdict, or **Open Portfolio** to open holdings in the selected workspace. The popup requests loopback access to read saved evidence from Market Events. Upstox OAuth and holdings import happen on the website.

### Current verification

The Portfolio browser checks and mocked OAuth checks passed. The review API also returned the expected case from a disposable synthetic ledger using local Qwen on CPU. Next open item is verification with an authenticated Upstox account and configured market-data credentials.
