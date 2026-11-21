# UX audit: Market Events web workspace

Auditor: `research`, 2026-11-21. Read-only audit: I edited no code and started or stopped no servers.

**Method.** I used the running dev stack at `http://127.0.0.1:3000`. A Playwright script (Chrome channel, run from `web/`'s dependencies) walked all 8 views:
- at 1366×768 in dark and light, plus 390×844 (mobile) and 1920×1080 spot checks;
- as a first-time visitor in the empty local workspace, then after **Load synthetic demo (replay)**;
- clicking every safe button and link, and entering invalid input on every form;
- injecting axe-core (WCAG 2.0/2.1 A and AA rules);
- tabbing through the overview 45 times with a focus-ring check;
- running an approximate text-contrast scan.

I read every file in `web/app/_components/*.tsx` to cover states the walkthrough could not reach.

**Deliberately not clicked:** provider **Download/Refresh** (it would contact Upstox), the TradingView widget (an external service), and any valid import into the local workspace (it would write to the user's database). I could not test "API down" without stopping servers, so the copy for that state below comes from reading the code.

**Personas.** **(A)** A first-time visitor with no finance background. **(B)** An examiner evaluating rigour, honesty and whether the demo story works.

Severity: **P0** breaks the demo or misleads. **P1** confuses a first-time visitor or examiner on stage. **P2** polish. **P3** nice to have.

---

## 1. Screen-by-screen inventory

The shell is the same on every view: a top bar with brand, eight nav links, theme toggle, effects toggle, workspace select, API status dot and a "me" monogram. The sidebar takes over below 1100 px. The footer shows "Research, with a record", the 2020 boundary note and **Refresh workspace**.

| View (URL `view=`) | Sections | States observed | Persona notes |
| --- | --- | --- | --- |
| **Overview** (`overview`) | Hero with **Load synthetic demo** and **Import evidence**; 3-card "Your research path"; workspace stats (articles, runs, records, pre-2021 bars); Strategy-lab teaser; company ticker; saved price chart with All/10/30 ranges; evidence-coverage ring; company watchlist with search; "From your research desk" (last 2 articles); provenance card | Empty local: all tickers say "No prices", and the chart says "More history is needed" after clicking. Demo: 35 articles, 651 records, ring 100%. Loading: "Opening…". Error: inline alert. | A: hero copy is generic; nothing says what an "event" or "evidence" is. The chart stays empty until one of **two** identical buttons is clicked ("Load local chart" and "Open local history"). B: the ring is good, but "Needs review" counts irrelevant and ineligible runs as problems. |
| **Event research** (`events`) | Summary strip; source inbox with search (35 demo articles); Inspect & analyse (article metadata, **Open source ↗**, text, free-text ISO cutoff, Research method, Analysis mode, Explicit repeat, **Analyse and save run**, **Analyse under all three policies**); results: policy trio table, run summary, **Download run snapshot** | Empty: "Your event inbox is empty" plus **Add your first article** (good). Success: syn-002 neutral 0.04 with a conflict warning. Ineligible: cutoff before publication shows status "ineligible" and the reason. Errors: raw Pydantic text, e.g. `decision_time: Input should be a valid datetime or date, invalid character in year`. | A: "ISO timestamp with timezone" is jargon. The inbox repeats the same headline many times (syn-001 = syn-006 …). The score 0.04 is not explained, because the components (+0.40 equity, −0.50 crude) are never shown. B: policy labels are **inaccurate** (§2, P0-3). The trio table is cut off at 1366 px. |
| **Price indicators** (`technicals`) | Summary; company + availability-cutoff form; candlestick chart; snapshot table (indicator, value, history needed, availability); JSON | Empty local (0 bars): the button is still enabled, and the result shows "No eligible bars" **plus** a full table of "Warm-up missing". Demo default (Asian Paints, 16 bars, cutoff = now): RSI14 = 100 and ATR are "Stale"; everything else is "Warm-up missing". The lab series (523 bars) shows every value "Stale" at cutoff = now. | A: the first thing they see is a table of "Warm-up missing" and "Stale" with no explanation, and "RSI14 100" looks like a bug. Indicator acronyms are unexplained. |
| **Strategy lab** (`lab`) | Summary; boundary banner; SYNTHETIC QA banner; 01 study window (instrument, dates, **Load local history**, collapsible Upstox download); 02 price structure (11 indicator toggles, chart, data tables); TradingView (opt-in); 03 backtest (strategy, capital, fee, slippage, conditional parameters); metrics (return, buy & hold, drawdown, Sharpe, PSR); equity report; 04 Monte Carlo (paths, horizon, seed, block, play/replay/scrub) | Empty local: two stacked alerts ("Missing Upstox credentials…" and "No eligible historical bars…"). Demo: auto-selects `SYNTHETIC:LAB_DEMO`. All 6 strategies ran (e.g. SMA cross −36.91% vs buy & hold +26.11%, PSR 2.36%). Fast ≥ slow validation works. End 2021 disables Load. | A: dense; every field is a finance term. Strategy results need a one-line verdict. MACD and Bollinger have hidden fixed rules. The Monte Carlo chart has no legend on the chart and no starting-capital line. B: honest labelling is strong (PSR note, SYNTHETIC QA banner). |
| **Saved results** (`saved`) | Summary; run select + **Open saved evidence**; retained case (run summary, original article, outcome card, **Evaluate later outcomes**, price-observation JSON, model call audit, optional explanation (disabled in replay), **Download full case**) | Empty: "No saved decisions yet" plus **Start event research** (good). The default selection is the newest run, which was an *ineligible* test run, and nothing shows until clicked. Completed: syn-001 outcome +4.48% net, +3.68% excess. | A: option text is machine-like (`syn-002 · ineligible · slm_delegate · no assessment · saved 2026-11-21 10:19`). B: **Evaluate later outcomes** on an ineligible run does nothing visible (§6, F-4). |
| **Comparisons** (`comparisons`) | Summary; intro; **Load saved comparisons** and **Evaluate later outcomes**; provenance; Policy usage table; Same article, different policies; Extraction agreement (gold labels); Later outcomes; JSON | Before loading: just two buttons and no hint of what will appear. Local with 0 runs: "No saved runs to compare", with no action link, under a provenance line about *synthetic replay*. Demo: all tables render. | A: needs a reason to press "Load". B: the outcomes table omits the decision's evidence label, so you cannot see whether the label and the outcome agreed. Policy row order (alphabetical) differs from column order elsewhere. |
| **Import evidence** (`imports`) | Summary; universe banner; Articles/Prices tabs; file picker; records textarea; **Validate and import**; manual-article form (collapsible); import report | Invalid JSONL: report says "partial · 0 added · 2 row errors", with errors only in a collapsed JSON. Manual summary text reads **"Add one article manually ? no file needed"** (mojibake). | A: row errors should be listed in plain language, not in JSON. B: the tabs are `role="tab"` without `tabpanel`, `aria-controls` or arrow-key support. |
| **Connections** (`connections`) | Summary; readiness cards; historical download form; advanced recent-evidence form; provider report; model batch | Local:live without token: the warning says "Select your workspace and provider universe, then configure…" even though both are already selected. "Local technical analysis" is green **Configured** while 0 bars exist. Demo: everything disabled, with no "not needed for the demo" message. | A: this page should tell demo users they can skip it. |

Global states:
- **Loading:** "Opening your research workspace…" with a spinner. Good.
- **API error:** "Could not complete the request" with the raw message and **Retry connection**.
- **Unknown `view=`:** silently falls back to Overview. Acceptable.
- **Mobile:** the menu opens, focus moves into the drawer, Escape closes it and returns focus to the trigger. Good.
- **Console:** no JavaScript errors in any walk. The only console entries were the HTTP 422s that my invalid-input tests caused on purpose.

---

## 2. Top usability problems, ranked

| # | Sev | Problem | Where | Fix (summary) |
| --- | --- | --- | --- | --- |
| 1 | P0 | **Result tables are cut off at 1366×768.** The policy-trio table hides Coverage and Status behind a horizontal scroll inside the right-hand panel, so on a projector the audience never sees them. | Event research → trio table (also the matched-policy and agreement tables on Comparisons) | Let the result block span the full width under both columns, or stack the trio as cards below 1500 px. |
| 2 | P0 | **The score is unexplained.** "Neutral 0.04" appears with no breakdown, yet `assessment.inputs` already holds `components` (equity +0.40, commodity −0.50) and `weights` (0.6/0.4). The raw explanation string prints `0.03999999035395829`. | Run summary (Events, Saved) | Add a "How the score was built" row: `0.6 × (+0.40 equity) + 0.4 × (−0.50 crude, exposure-adjusted) = +0.04 → neutral (needs ±0.15)`. Backend: round the float and add the missing full stop (already requested). |
| 3 | P0 | **Policy labels are wrong or inconsistent.** `slm_delegate` is called "Small model with delegated extraction", but the *large* model still does the extraction; the small model only screens and passes checked hints. `llm_only` is "Large-model extraction only" in the select but "Large model only" in the tables. `slm_filter` uses "+" in one place and "→" in another. An examiner who knows the architecture will notice. | `types.ts` `POLICY_LABELS`, Events select, all tables | One label set, used everywhere (§3.3). |
| 4 | P1 | **Synthetic status disappears.** The green "Synthetic replay demo loaded" notice is dismissible and gone after navigating. Afterwards only the small header select says "Synthetic demo". The plan requires "synthetic/replay status always visible". | Shell | Add a persistent, non-dismissible top-bar badge: **SYNTHETIC DEMO · RECORDED REPLAY**. |
| 5 | P1 | **Cutoff input is raw ISO text, and errors are Pydantic messages.** | Events, Price indicators | Use date and time fields plus a timezone (default IST), show "= 12 Jan 2026 17:30 IST" beside the field, validate on the client, and add a **Use demo cutoff** chip. Errors in plain English (§3.5). |
| 6 | P1 | **Price indicators open on a misleading state.** In the demo the default is a 16-bar company and cutoff = now, so the table shows "Warm-up missing"/"Stale" everywhere and RSI = 100. | Price indicators | In demo, default to the company with the most bars and a cutoff equal to its last bar's availability. Explain "Stale" and "Warm-up" inline. |
| 7 | P1 | **The demo inbox repeats headlines.** 35 articles, many with identical text (dedup and update test cases). A visitor cannot tell which ones tell the story. | Event research | Pin and tag the five story articles (earnings, crude shock, order, irrelevant, unconfirmed). Group or collapse exact duplicates as "3 more versions". |
| 8 | P1 | **Saved results opens on nothing**, defaults to the newest run (possibly a failed or ineligible test), and the option text is machine-like. | Saved results | Auto-open the selected case. Default to the most recent *completed* run. Use readable option text (§3.5). |
| 9 | P1 | **"Evaluate later outcomes" silently does nothing** for ineligible, irrelevant, duplicate or failed runs, because the backend only evaluates completed or abstained runs. | Saved results | Hide the button for those statuses and show "No outcome is measured because this run produced no assessment." |
| 10 | P1 | **Comparisons outcome table lacks the evidence label**, so the audience can't compare "what the evidence said" with "what happened next". The page is also empty until **Load** is pressed. | Comparisons | Add an "Evidence label" column next to "Outcome label" (from `runsById`). Auto-load the read-only comparison. Keep **Evaluate later outcomes** explicit. |
| 11 | P1 | **Two workspace switchers with different vocabularies.** The sidebar has "Your workspace / Synthetic demo" plus a separate universe select; the header has "My workspace / Local / demo universe / Synthetic demo". | Shell | One switcher with three plainly named options (§3.5). |
| 12 | P1 | **"Open source ↗" goes to `https://example.invalid/...`** for synthetic articles, giving a browser DNS error if clicked on stage. | Event research | For synthetic or `example.invalid` sources, show "Synthetic article · no web page" instead of a link. |
| 13 | P2 | Overview **"Needs review"** counts every non-completed run, including correct "irrelevant" and "duplicate" outcomes. | Overview ring legend | Rename to "Not assessed" with a tooltip. Optionally split into abstained vs filtered out. |
| 14 | P2 | **Connections copy is wrong for the local-without-token case**, and a green "Configured" shows for technical analysis with 0 bars. No "skip this in the demo" message. | Connections | Use reason-specific warnings. Show a neutral "No data yet" pill when bars = 0. Add a demo note. |
| 15 | P2 | **Overview chart needs a click and has two identical buttons.** | Overview | Auto-load the saved chart for the first company that has bars, and keep one button. |
| 16 | P2 | **Strategy lab hidden rules.** MACD and Bollinger have no visible parameters. The Monte Carlo chart has no legend on the chart, no starting-capital line and no ₹ on the axis. | Strategy lab | Show the fixed rules in one line each (§3.3). Add a legend and a dashed "starting capital" line. |
| 17 | P2 | **Import errors are only in JSON.** | Import | Render the first 10 row errors as a list: "Line 2: not valid JSON." |
| 18 | P2 | **Number and time formatting.** Coverage shows "100.00%". The score is unsigned ("0.04", not "+0.04"). Times are raw UTC ISO strings. Monte Carlo capital is "1,00,805.59" with no ₹. | Everywhere | Coverage as a whole %; signed score to 2 dp; times as "12 Jan 2026, 17:30 IST" (UTC in a tooltip); ₹ on money. |
| 19 | P2 | **Decorative elements that look interactive:** the sidebar-footer `?` icon, the "AR Local researcher" card, the "me" monogram, and the API dot (colour only). | Shell | Make `?` open the glossary drawer (§3), or remove it. Give the API dot a text label ("API connected"). |
| 20 | P3 | Local Comparisons empty state has no action link and shows "synthetic replay is not real-data validation" in a non-demo workspace. | Comparisons | Add **Start event research**, and show provenance only when runs exist. |
| 21 | P3 | `signal-hero.tsx` exports an unused `SignalHero` component (only `useReducedMotion` is imported). | Code hygiene | Cleanup-phase item for `demo-ui`. Not a UX issue. |

---

## 3. Exact copy

### 3.1 "What is this screen" intros

One or two sentences each, placed under the H1. They replace or extend the current descriptions. Keep the eyebrows.

- **Overview.** "This workspace turns a dated news article into an auditable piece of evidence about one company's stock. Start with the synthetic demo: everything in it is invented test data, so you can explore safely without accounts or keys."
- **Event research.** "Pick a news article and a moment in time (the *cutoff*). The system checks only what was knowable at that moment: a language model finds the event and quotes the article, then fixed rules combine price moves into an evidence label. Nothing here is a forecast or a trading signal."
- **Price indicators.** "Common chart indicators (moving averages, RSI, MACD and others) calculated from saved daily prices up to a cutoff you choose. They add context only and never change an event's evidence score."
- **Strategy lab.** "Test a simple buy/sell rule on historical daily prices (up to 31 Dec 2020), including trading costs, then see how much its results could vary by reshuffling its own past returns. The demo series is synthetic: use it to learn the tool, not to judge a strategy."
- **Saved results.** "Every analysis is saved permanently with its source article, the numbers it used, each model call and its settings. Open one to see why it got its label and, separately, what the price did over the next five trading days."
- **Comparisons.** "Run the same article through three ways of splitting the work between a small and a large language model, then compare calls, cost, agreement with hand-made labels, and later outcomes. In the demo these are recorded responses, so they show how the comparison works, not which model is better."
- **Import evidence.** "Add your own news articles (one JSON object per line) or daily prices (CSV). Each record keeps when it was published and when it became available, so later analyses can't accidentally use information from the future."
- **Connections.** "Check which outside services are configured and choose exactly when to contact them. **Not needed for the synthetic demo:** everything in the demo runs offline."

### 3.2 One-line tooltips: evidence and decision

| Term (as shown) | Tooltip |
| --- | --- |
| Evidence label | The final verdict from fixed rules: positive, negative, neutral (mixed or weak) or abstain. It describes the evidence, not a prediction. |
| Positive / Negative | The combined evidence score reached +0.15 or above (positive) or −0.15 or below (negative). |
| Neutral | Evidence was available but too weak or too mixed to cross ±0.15. |
| Abstain | The system refused to give a label because required evidence was missing, out of date, not verified in the article, or the article's history was unclear. |
| Signed evidence score | A number from −1 to +1 built from price moves: 60% the stock's move versus its benchmark, 40% the commodity move adjusted for whether the company gains or loses from it. It is not a probability. |
| Threshold ±0.15 | How far from zero the score must be before it counts as positive or negative. |
| Evidence coverage | The share of the evidence the rules wanted that was actually available at the cutoff (100% = nothing missing). |
| Minimum 60% | Below this coverage the system abstains, whatever the score. |
| Conflict | Two pieces of evidence point in opposite directions, e.g. the stock rose while a cost-raising crude spike says it should fall. |
| Decision cutoff | The moment the analysis pretends to be standing at. Only articles and prices available before this moment are used. |
| Published / First seen | When the article was published, and when this dataset first had it. Both must be before the cutoff. |
| Equity return (reaction day) | How much the stock's closing price changed on the latest trading day before the cutoff. |
| Sector benchmark return | The same-day move of the comparison index (the demo uses a synthetic sector index). |
| Equity excess return | The stock's move minus the benchmark's move: how much it beat or lagged the market that day. |
| Commodity return | The latest daily move in the related commodity contract (crude oil in the demo). |
| Exposure-adjusted commodity | The commodity move with its sign flipped when the company is hurt by it. A crude rise counts as negative for a paint maker. |
| Exposure rule | A reviewed, dated statement such as "Berger Paints is hurt when crude rises". The demo rules are synthetic assumptions. |
| Relative volume (context only) | Today's trading volume divided by the average of the previous five sessions. It is shown for context and does not affect the score. |
| Available / Missing / Stale / Not applicable | Usable / no data / data older than four calendar days before the cutoff, so it is ignored / not needed for this event type. |
| Supporting source passages | Exact sentences copied from the article that the model used. The system rejects any quote that isn't word-for-word in the source. |
| Validated / Unsupported / Unresolved | The extraction's quotes and amounts match the article / they don't / the company could not be identified with certainty. |
| Replay / Recorded replay | Uses pre-recorded model answers for the bundled synthetic articles. No AI model is actually called. |
| Live (configured models) | Sends the article to the language models configured on the server. |
| Explicit repeat experiment | Runs the same request again as a new, linked record, instead of reusing the saved result. |
| Run status: completed / abstained / irrelevant / duplicate / ineligible / partial / failed / interrupted | Got a label / withheld a label / filtered out as not a market event / same text as an earlier article / article not available at the cutoff / stopped by the call budget / an error occurred / stopped by the user. |

### 3.3 Policies and model metrics

| Term | Label to use everywhere | Tooltip |
| --- | --- | --- |
| `llm_only` | **Large model does both steps** | The large model decides whether the article matters and then extracts the event. Most expensive; the baseline. |
| `slm_filter` | **Small model screens → large model extracts** | A cheaper small model discards irrelevant articles first; the large model extracts only what passes. |
| `slm_delegate` | **Small model screens and hands over hints → large model extracts** | Like screening, but the small model's verified quotes and company names are passed to the large model as hints. The large model still reads the full article. |
| Filter / Extraction | — | Filter: "is this article about a market-relevant event?" Extraction: "which company, what event, which quotes?" |
| Model calls (small · large) | — | How many model requests each method made, split by small and large model. |
| Input / output tokens | — | The amount of text sent to and received from the model. It drives cost. Replay records none. |
| Estimated cost | — | Tokens × configured price per 1,000 tokens. Shown only for live runs with complete token counts. |
| Mean latency | — | Average time per analysis. In replay this measures the app, not the model. |
| Filter recall | — | Of the articles that really matter (hand labels), the share the filter let through. A miss here can't be recovered later. |
| Filter precision | — | Of the articles the filter let through, the share that really mattered. |
| Uncertain → escalated | — | Share of articles where the small model wasn't sure and passed the decision to the next step. |
| Event type / Company / Commodity (accuracy) | — | Share of extractions where this field matched the hand label. |
| Validated spans | — | Share of extractions whose quotes were all found word-for-word in the article. |
| Abstention rate | — | Share of runs where the rules withheld a label. |
| Synthetic sanity check | — | Hand labels for invented test articles. This checks the plumbing; it is not a benchmark of model quality. |

### 3.4 Outcomes, indicators and strategy lab

| Term | Tooltip |
| --- | --- |
| Later outcome | What the stock did *after* the cutoff, measured separately. It never changes the saved label. |
| Entry → exit | Bought at the next trading day's opening price after the cutoff, sold at the close of the 5th trading day (the entry day counts as day 1). |
| Gross / Net return | Price change from entry to exit / the same after subtracting 0.10% round-trip trading costs. |
| Benchmark return (outcome) | The benchmark's move over exactly the same days. |
| Excess return (outcome) | The stock's gross return minus the benchmark's: did it beat the market over those five days? |
| Outcome label | Positive if the net return of holding the stock was above zero, negative if below. It always measures *holding* the stock, even for negative evidence. |
| Pending / Invalid | Not enough later trading days yet / no measurable decision (e.g. the run abstained). |
| Eligible bars | Daily price records dated, and available, on or before the cutoff. |
| History needed / Warm-up missing | How many trading days an indicator needs before it can be computed / not enough days yet. |
| SMA 20/50/200 | Average closing price over the last 20/50/200 trading days. It smooths out daily noise. |
| EMA 20/50 | A moving average that gives more weight to recent days. |
| RSI 14 | A 0–100 momentum gauge over 14 days. Above 70 is often read as "overbought", below 30 as "oversold". 100 means the price only rose. |
| MACD line / signal / histogram | The gap between a fast and a slow average (line), its 9-day average (signal), and the difference between the two (histogram). It shows momentum turning. |
| Bollinger bands | A 20-day average with bands two standard deviations above and below. Prices outside the bands are unusually far from the average. |
| ATR 14 | Average True Range: the typical daily price swing over 14 days, in rupees. |
| ADX 14 | Trend strength from 0 to 100. Above about 25 usually means a strong trend, in either direction. |
| Volume | Number of shares traded that day. |
| SMA / EMA crossover | Hold the stock while the fast average is above the slow one; otherwise hold cash. |
| Buy and hold | Buy on the first day and keep the stock to the end. This is the yardstick. |
| RSI reversion | Buy when RSI falls to the "buy" level or below; sell when it reaches the "sell" level or above. |
| MACD crossover | Hold while the MACD line is above its signal line. |
| Bollinger reversion | Buy when the close falls below the lower band; sell when it gets back to the middle band. |
| Initial capital (INR) | Pretend starting money. |
| Fee per fill (bps) | Brokerage and charges on each buy or sell. 1 bp = 0.01%, so 10 bps = 0.10%. |
| Slippage per fill (bps) | Extra price paid when buying or lost when selling, because real orders don't fill at the exact open. |
| Fast / Slow period | Lengths, in trading days, of the two moving averages being compared. |
| Strategy return | Total gain or loss over the study after all costs. |
| Buy & hold return | What simply holding the stock would have returned, with the same costs. |
| Maximum drawdown | The worst fall from a previous high in the strategy's account value. It measures the pain along the way. |
| Sharpe ratio | Average daily return divided by its variability, scaled to a year. Higher is better; below 0 means it lost money on average. |
| Probabilistic Sharpe (PSR) | The estimated chance that the strategy's true Sharpe is above zero, allowing for short samples and unusual returns. It does not account for trying many settings. |
| CAGR | Compound annual growth rate: the steady yearly return that would give the same end result. |
| Win rate / Closed trades | Share of completed buy-then-sell trades that made money / how many such trades there were. With few trades, the win rate means little. |
| Open position | The strategy still holds the stock at the end. It is valued at the last close, with no exit fee charged. |
| Monte Carlo (block bootstrap) | Builds many alternative histories by reshuffling chunks of the strategy's own past daily returns. This shows the spread of luck, not a forecast. |
| Simulated paths / Horizon | How many alternative histories / how many trading days each one lasts. |
| Random seed | A number that makes the reshuffling repeatable. The same seed gives the same result. |
| Block size | How many consecutive days are kept together when reshuffling, preserving short streaks. |
| Resampled loss frequency | Share of simulated paths that ended below the starting capital. It is not the probability of a real loss. |
| Median terminal capital | The middle ending value across all simulated paths. |
| p05 / p95 terminal capital | 5% of paths ended below the first number; 5% ended above the second. |
| Shaded band / gold line / thin lines | Middle 90% of paths at each day / the median path / a sample of individual paths. |
| 2020 boundary | Historical strategy studies stop at 31 Dec 2020 by design, so results can be compared on a fixed past window. |

Shell, overview, import and connections:

| Term | Tooltip |
| --- | --- |
| Evidence coverage (ring) | Average coverage across saved assessed cases: how complete the evidence was, not how confident or correct. |
| Pre-2021 bars | Daily prices usable in the Strategy lab. |
| Saved data / not live | Prices come from your saved files, not a live market feed. |
| JSONL | A text file with one article per line, written as JSON. |
| OHLCV CSV | A spreadsheet of daily Open, High, Low, Close and Volume. |
| Added records / Row errors | Rows saved / rows rejected, each with a reason. Good rows are kept even when others fail. |
| `LIVE:` identifiers | Records from the real-provider universe. Kept separate from demo data. |
| Configured / Setup needed | A setting or key is present on the server / missing. "Configured" does not prove the service works. |

### 3.5 Empty, error and state copy ("what happened, what to do next")

| Situation | Proposed copy | Action |
| --- | --- | --- |
| API unreachable (global) | **Can't reach the research engine.** The local Python service on port 8000 isn't responding. Start the dev stack with `npm.cmd run dev`, then retry. | **Retry** |
| Cutoff not parseable | **That date and time isn't readable.** Use the date and time pickers, or a timestamp like 2026-01-12 17:30 IST. | **Use demo cutoff** |
| Cutoff without timezone | **Add a timezone.** We need to know whether 12:00 means India time or UTC. India (IST) is selected by default. | — |
| Ineligible run | **This article wasn't available yet.** It was first seen at 12 Jan 2026 13:35 IST, after your cutoff (…). Move the cutoff later to analyse it. | **Set cutoff to first-seen time** |
| Irrelevant run | **Filtered out: not a market event.** The screening step found nothing that should move this company's stock (quoted reason). No price evidence was needed. | **Try another article** |
| Duplicate run | **Same text as an earlier article.** It reuses that article's result rather than analysing it twice. | **Open the original** |
| Abstained | **No label: evidence incomplete.** (Plain reason, e.g. "The crude-oil price for this day wasn't available yet at the cutoff.") Try a later cutoff or check the price data. | — |
| Failed / partial | **The analysis stopped early.** (Reason.) Nothing was overwritten; you can retry as a linked repeat. | **Retry as repeat** |
| Replay on a non-demo article | **Replay only covers the bundled demo articles.** Switch to the Synthetic demo, or set up live models in Connections. | **Open Connections** |
| Saved results: none | (Keep the current copy.) | **Start event research** |
| Saved run option text | `Berger Paints · crude-oil shock · Neutral · Small model screens → large model extracts · 12 Jan 17:30 IST` | — |
| Outcome not applicable | **No outcome to measure.** This run produced no assessment, so there's nothing to check against later prices. | (hide button) |
| Outcome pending | **Waiting for five later trading days.** Import more prices after the cutoff and evaluate again. | **Import prices** |
| Price indicators: 0 bars | **No saved prices for this company yet.** Import a daily price CSV, or switch to the Synthetic demo. | **Import prices** (disable Compute) |
| Price indicators: stale | **The latest price is older than four days before your cutoff,** so the values are shown but marked stale. Move the cutoff closer to the last price date (shown). | **Use last price date** |
| Strategy lab: no pre-2021 bars | **No historical prices before 2021 for this instrument.** In the demo, pick "Synthetic lab series". For real data, add an Upstox token in Connections and download history. | **Pick demo series** / **Open Connections** |
| Backtest: no trades | **The rule never triggered in this window,** so the strategy stayed in cash. Try a longer window or different thresholds. | — |
| Monte Carlo: < 5 returns | (Keep the current copy) plus **Extend the study window above.** | — |
| Comparisons before loading | **Compare how the three methods handled the same articles.** Loading reads saved runs only; it doesn't call any model. | **Load comparisons** (or auto-load) |
| Comparisons: no runs | **Nothing to compare yet.** Analyse at least one article. "Analyse under all three methods" fills this page in one click. | **Start event research** |
| Import: row errors | **2 rows were rejected; 0 saved.** Line 1: missing source_url, text, published_at, first_seen_at. Line 2: not valid JSON. | **Show all errors** |
| Connections in demo | **You don't need this page for the demo.** It's only for connecting your own data provider and models. | **Back to Overview** |
| Connections: token missing | **Upstox token not set.** Add `UPSTOX_ANALYTICS_TOKEN` to the server's `.env`, restart the API, then refresh. | **Refresh workspace** |
| Workspace switcher (single) | Options: **Synthetic demo (offline)** · **My data – real companies** · **My data – demo companies** | — |

---

## 4. Guided workflow for a React Bits Stepper

Put a **"Demo tour"** Stepper on the Overview, replacing the 3-card research path when `workspace=demo`, and as a slim collapsible bar on other demo pages. It must never block free navigation. Each step's **Next** deep-links to the right view with fields pre-filled. That needs `demo-ui` to accept `article=` and `cutoff=` query parameters on Event research.

| Step | Title | One-line body | Primary action | Done when |
| --- | --- | --- | --- | --- |
| 1 | Load the demo | Invented articles and prices, recorded AI answers. Offline and safe. | **Load synthetic demo** | `workspace=demo` and articles > 0 |
| 2 | Pick a news story | A crude-oil supply shock hits a paint maker (Berger Paints, syn-002). | **Open the story** (`events&article=syn-002`) | Article selected |
| 3 | Freeze the moment | Set the cutoff to 12 Jan 2026, 17:30 IST: only what was known then counts. | **Analyse under all three methods** | Trio returned |
| 4 | Read the verdict | Stock +0.8% vs market, but crude +1.5% hurts paint costs → mixed → Neutral, with a conflict flag. | **Open saved result** | A case is opened |
| 5 | See what happened next | Five trading days later, measured separately; it can't change the verdict. | **Evaluate later outcomes** | Outcomes > 0 |
| 6 | Compare the methods | Same answer from all three methods in replay. The point is cost and agreement, not quality. | **Load comparisons** | Comparisons loaded |
| 7 | Test a price rule | Run a moving-average rule on the synthetic 2019–2020 series, double the costs, then reshuffle returns. | **Open Strategy lab** | A backtest has run |

Stepper rules:
- Step state comes from real data, not from clicks.
- **Back** and **Next** stay visible.
- The current step is announced with `aria-current="step"`.
- Transitions are 400 ms or less and are skipped under `prefers-reduced-motion`.
- A "Skip tour" link persists the choice in `localStorage`.

The non-demo (local) workspace keeps a 3-step version: Add evidence → Investigate → Inspect.

---

## 5. Which numbers suit a CountUp

Use CountUp only where a number is a headline count or KPI the eye should land on. It must always end on the exact formatted value. Render the final value immediately under reduced motion or when effects are paused.

**Yes:**
- Overview stats: source articles, saved runs, market records, pre-2021 bars.
- The coverage-ring percentage.
- Values in every `WorkspaceSummary` strip.
- Strategy-lab metric cards: strategy return, buy & hold, maximum drawdown, PSR. Apply the green or red colour only at the final value.
- Monte Carlo summary: loss frequency, median, p05 and p95 terminal capital.
- Comparisons: total model calls per method.

**No:**
- The signed **evidence score** and **coverage** in a result. Animating through ±0.15 would briefly show the wrong label.
- Outcome returns for a case.
- Anything inside a table.
- Prices, timestamps, thresholds ("±0.15", "60%") and parameter inputs.
- Values that refresh while the user is reading (chart readouts).

---

## 6. Functional bugs found by clicking

| ID | Sev | Bug | Repro |
| --- | --- | --- | --- |
| F-1 | P0 | Policy-trio table cut off: the Coverage and Status columns are hidden at 1366 px. | Events → syn-002 → **Analyse under all three policies** (screenshot `flow-events-trio`). |
| F-2 | P1 | Summary text shows literal mojibake: **"Add one article manually ? no file needed"**. The source file contains a literal `?`. | Import evidence (articles tab). |
| F-3 | P1 | **Open source ↗** links to `https://example.invalid/synthetic/syn-00x` (a dead domain). | Events, any synthetic article. |
| F-4 | P1 | **Evaluate later outcomes** on an ineligible, irrelevant, duplicate or failed run: nothing happens and no message appears. | Saved → select an `ineligible` run → Open → Evaluate. |
| F-5 | P1 | Policy labels inconsistent between the select and the tables, and `slm_delegate` is mislabelled. | Events select vs trio table. |
| F-6 | P1 | Errors from the API are shown raw, e.g. `decision_time: Input should be a valid datetime or date, invalid character in year`. | Events or Indicators, cutoff "12 Jan 2026 5pm". |
| F-7 | P2 | Price indicators: **Compute** is enabled with 0 bars; the result shows "No eligible bars" plus a full warm-up table. | Local workspace → Price indicators → Compute. |
| F-8 | P2 | Strategy lab (local, no token): two stacked alerts, the first about the token, even before the user tried to download. | Local → Strategy lab → Run backtest. |
| F-9 | P2 | Connections (local:live, no token): the warning tells the user to select the workspace and universe they already selected. | Local → Connections. |
| F-10 | P2 | Overview chart: "Load local chart" and "Open local history" do the same thing; the chart is empty until one is clicked. | Overview after demo load. |
| F-11 | P2 | Overview watchlist **Explore** links all go to the generic Event research page, not filtered to that company. | Overview → watchlist → Explore. |
| F-12 | P2 | The Comparisons outcomes table can't be read against the decision because the evidence-label column is missing. | Comparisons → Load. |
| F-13 | P3 | Comparisons policy rows are ordered alphabetically (`llm_only`, `slm_delegate`, `slm_filter`), unlike the column order elsewhere. | Comparisons → Load. |
| F-14 | P3 | Run explanation text prints unrounded floats and runs two sentences together. (Already requested of `demo-backend`.) | Any assessed run. |

What worked: demo load (about 0.3–0.6 s); search; single and trio analysis; ineligible handling; Saved case with outcome; explanation correctly disabled in replay; all 6 backtests; 2× cost rerun; fast ≥ slow validation; the date cap at 2020; Monte Carlo play, pause and replay; theme toggle; mobile menu focus trap and Escape; Refresh workspace. No JavaScript console errors.

---

## 7. Accessibility

| Issue | Sev | Detail | Fix |
| --- | --- | --- | --- |
| Label-in-name mismatch (axe `label-content-name-mismatch`, serious, every page) | P1 | Desktop nav: visible "Strategies", "Compare" and "Setup" vs accessible names "Strategy lab", "Comparisons" and "Connections". The brand's visible "marketevents" vs "Market Events home". Speech-input users who say "click Strategies" fail. | Make visible text and `aria-label` match (or drop the `aria-label`). |
| Low contrast, light mode | P1 | The "Assessed cases" and "Needs review" legend labels under the coverage ring measured about 1.9:1 (screenshot `light-01-demo-overview`). axe did not flag them, likely because of layered or gradient backgrounds, so verify by eye. Small 9–11 px uppercase mini-labels (e.g. "SAVED CASES", "LOCAL PRICES") are borderline in both themes. | Raise to 4.5:1; avoid text below 11 px on projector-bound screens. |
| Colour-only meaning | P2 | API status dot; green/red for evidence direction and returns; Monte Carlo series named by colour ("gold line", "lime lines"). | Add text ("API connected") and +/− signs (already present for returns), plus a chart legend with line styles. |
| Tabs pattern incomplete | P2 | Import tabs use `role="tab"` without a `tablist` → `tabpanel` relationship (`aria-controls`) or arrow-key navigation. | Implement the full ARIA tabs pattern, or use plain toggle buttons with `aria-pressed`. |
| Free-text timestamp fields | P2 | The only hint for format is in the label; errors are not tied to the field with `aria-describedby`. | Use date and time inputs and connect errors with `aria-invalid` and `aria-describedby`. |
| Icon-only and disabled controls | P3 | Under reduced motion the effects toggle is disabled with no visible text at 1366 px. The sidebar `?` icon is not a control. | Hide the toggle when the system forces reduced motion; make `?` a real glossary button. |
| Focus | OK | Every focus stop on the overview (45 tabs) had a visible ring. The skip link works. The mobile drawer traps focus and returns it on close. | Keep. Note that the skip link, when focused, overlaps the "Source inbox" heading. |
| Charts | OK | Lightweight Charts and Monte Carlo have `role="img"` labels and table fallbacks. The overview chart is keyboard-inspectable with arrow keys. | Keep. |

---

## 8. Must-fix list, mapped to cross-agent requests

Everything ranked P0 or P1 above has a one-line request under **Cross-agent requests** in `docs/PRESENTATION_PLAN.md`. Most go to `demo-ui`. Two need new API data and go to `demo-backend`:
- a plain-English summary field;
- a featured flag for the demo-story articles.

P2 and P3 items are recommendations for `demo-ui` to take if time allows.

Artefacts from this audit (screenshots and the JSON report) are in the auditor's scratchpad, not the repo, and can be regenerated with the existing `web/tests/demo-walkthrough.spec.ts`.
