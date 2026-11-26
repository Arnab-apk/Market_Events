# Market Events mentor showcase

Use the deployed website at https://final-yr-proj.vercel.app and sign in to Vercel before presenting. Use **My data – real companies** for live evidence. Keep **Demo data (offline)** clearly labelled when presenting recorded or synthetic examples.

## The story to tell

“Market Events links company news to dated market evidence, saves an auditable analysis, and shows its relevance to a practice portfolio. Upstox supplies market data and news; Sarvam supplies structured language analysis. Portfolio and analysis records are saved in a managed Postgres database. TradingView provides an independent chart view.”

The paper account holds whole shares of five Indian stocks with a ₹1,00,000 virtual starting balance. The initial cost uses completed daily closes. Latest-price valuation is a separate view refreshed from Upstox every 15 seconds while the page is visible. No real orders are placed.

## Presentation flow (about 10 minutes)

| Step | What to do on screen | What this proves |
|---|---|---|
| 1. Introduce the product | Open Home. Show the first-visit introduction, then **How it works** or **Skip introduction**. | The purpose and workflow are understandable; navigation is immediately usable. |
| 2. Show the paper account | Open Portfolio. Show the five holdings, quantities, starting balance and unspent cash. If there is no saved account, choose **Create ₹1,00,000 paper portfolio**, review the preview and confirm **Import holdings**. | Real instrument prices create a simulated, budget-conserving portfolio. Broker sign-in is optional. |
| 3. Show changing market prices | Enable **Refresh paper prices every 15 seconds** under **Live paper demo**. Leave the tab visible for at least two refreshes. Point to the fetch time, last-trade timestamps, latest paper equity and P&L. | Current Upstox responses update the valuation. Prices can remain unchanged outside market hours or between trades; do not manufacture movement. |
| 4. Show the independent chart | Pick **Chart holding**, expand **TradingView chart**, then enable **Load the TradingView widget**. Use **Open this chart on TradingView** if an exchange symbol is unavailable in the embed. | The selected stock opens an intraday TradingView chart. TradingView exchange entitlements/delays apply; its chart does not feed portfolio calculations. |
| 5. Import real evidence | Open Settings → Connections. Select companies, use a 90-calendar-day recent-history lookback, leave provider news enabled, and refresh selected recent evidence. Inspect the report, errors, source timestamps and imported counts. | The backend actually contacts the provider and persists dated records. A configuration badge alone is not connectivity proof. |
| 6. Run live analysis | Open Analyse, choose an imported story, set a decision time after its first-seen time, and click **Analyse with configured models**. Start with one method; optionally compare all three afterward. | Sarvam performs relevance/extraction and the deterministic engine combines cutoff-eligible evidence. |
| 7. Inspect the saved result | Show the verdict, evidence coverage, missing/stale inputs, source spans and model-call audit. Open Results and download the case snapshot. Optionally request the explanation. | The result is tied to sources, observations, model calls and a saved run ID. An abstention is a valid output when evidence is insufficient. An optional explanation does not overwrite the original verdict. |
| 8. Show portfolio relevance | Return to Portfolio and choose a research question. Open a matching saved assessment, or show which holdings lack relevant evidence. | The assistant uses saved cases and makes gaps visible. A news article can mention a company outside the tracked universe, so it may legitimately produce no holding match. |
| 9. Prove persistence | Record the run ID, holdings and cash. Open the website in a fresh tab and show the same records. Use the release verification evidence to show the records survived a later Vercel deployment. | The database is independent of browser-tab memory and Vercel instance files. |
| 10. Show the research lab | Demonstrate indicators, one backtest/walk-forward run, and a seeded Monte Carlo scenario. Download a report. | The separate historical research tools work. Strategy history ends 31 December 2020; it is not the current live feed. Monte Carlo illustrates uncertainty. |

## Before meeting your mentor

- Present while the exchange is trading if you want naturally changing Indian stock quotes. Check the actual exchange calendar rather than assuming every weekday is open.
- Sign in to the protected deployment and load the website first. Do not display keys or the Vercel environment-variable values.
- Keep a completed saved analysis and its downloaded case available, then perform a fresh live request during the presentation.
- Show live and recorded modes honestly. Actual Sarvam usage is visible in the saved call audit; replay timing does not demonstrate live model savings.
- Treat broker import as optional. Enter any Upstox PIN only on Upstox's own page. The extension does not collect the PIN.
- Keep the same private workspace for the demo. Current production access uses Vercel project authentication; authorized project visitors share this workspace, rather than separate personal accounts.

## Observed live proof during release verification

On 26 November 2026, the staged production build saved all five paper positions to Neon with ₹93,966.65 invested and ₹6,033.35 virtual cash. Upstox latest-price valuation changed from ₹99,547.55 at 10:00:13 IST to ₹99,564.20 at 10:00:29 IST, with updated last-trade timestamps. These are observed historical verification values, not a promise of the values during a later presentation.

The final release verification and remaining limits are recorded in `PORTFOLIO_SPRINT_HANDOFF.md`.
