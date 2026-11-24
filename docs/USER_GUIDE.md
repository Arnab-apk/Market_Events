# Market Events: user guide

How to use the **Market Events** website, the implementation of *A Heterogeneous Multi-Agent
Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets*.

This guide is written for anyone opening the site for the first time: a teammate, an examiner or you
on presentation day. No finance or AI background is assumed. Words in *italics* have a tooltip on the
site (dotted underline) and an entry in the **Glossary**.

> The previous guide (Streamlit-first, written 2026-11-21) is kept unchanged at
> [archive/USER_GUIDE_2026-11-21.md](archive/USER_GUIDE_2026-11-21.md).

---

## Contents

1. [What the website does](#1-what-the-website-does)
2. [Start and stop the website](#2-start-and-stop-the-website)
3. [Find your way around the screen](#3-find-your-way-around-the-screen)
4. [Choose a workspace](#4-choose-a-workspace)
5. [Quick start: the 7-step demo tour](#5-quick-start-the-7-step-demo-tour)
6. [Every section in detail](#6-every-section-in-detail)
7. [How to read a result](#7-how-to-read-a-result)
8. [Use your own data](#8-use-your-own-data)
9. [Real market data and real AI models (optional)](#9-real-market-data-and-real-ai-models-optional)
10. [Where your data lives, and how to reset it](#10-where-your-data-lives-and-how-to-reset-it)
11. [Troubleshooting](#11-troubleshooting)
12. [What the website does not do](#12-what-the-website-does-not-do)
13. [Other ways to run it: Streamlit and the command line](#13-other-ways-to-run-it-streamlit-and-the-command-line)

---

## 1. What the website does

You give it a **dated news article** about an Indian listed company, plus the **prices** around that
date. You also pick a moment in time, the *decision cutoff*. The website then answers one question:

> "Using only what was knowable at that moment, what does the evidence say about this company's stock?"

It does this in four stages, and shows every stage on screen:

| Stage | Who does it | What happens |
| --- | --- | --- |
| 1. Screen | Small AI model | Is this article about a market-relevant event at all? |
| 2. Extract | Large AI model | Which company, which event, which commodity? Every claim must quote the article word for word. |
| 3. Fuse | Fixed Python rules (no AI) | Combine the stock's move against its benchmark (60%) with the related commodity's move, such as crude oil (40%), into one *signed evidence score* and an *evidence label*. |
| 4. Check later | Python, separately | What did the stock actually do over the next five trading days? This is stored apart and can never change the label. |

The result is **evidence you can audit**, not a forecast and not a trading signal.

There are also two supporting tools:

- **Price indicators**: chart indicators such as RSI and moving averages, computed from saved prices.
- **Strategy lab**: test a simple buy/sell rule on daily prices up to 31 Dec 2020, with trading costs
  and a Monte Carlo spread of outcomes.

---

## 2. Start and stop the website

### First-time setup (once per computer)

From the project folder `D:\projects\Final_Yr_Proj` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e ".[web,dev]"
npm.cmd --prefix web install
```

### Start it

```powershell
npm.cmd run dev
```

This one command starts two programs:

| Program | Address | Job |
| --- | --- | --- |
| Website (Next.js) | http://127.0.0.1:3000 | What you open in the browser |
| Research engine (Python API) | http://127.0.0.1:8000 | Does the actual analysis and stores results |

Wait about 10–20 seconds, then open **http://127.0.0.1:3000**. The top bar should say **API connected**.

> **Use `npm.cmd`, not `npm`.** In Windows PowerShell, plain `npm` runs a script that the execution
> policy often blocks.

### Presentation mode

```powershell
npm.cmd run dev -- --stage
```

This serves the optimised production build. There is no developer overlay and no auto-reload, so
nothing restarts mid-demo. Use it on presentation day.

### Stop it

Press **Ctrl+C** in the window where you started it. Both programs stop together.

> If `npm run dev` fails straight away, the website is usually **already running** in another window
> or herdr tab: ports 3000 and 8000 are taken. Either use the running copy or stop it first. See
> [Troubleshooting](#11-troubleshooting).

---

## 3. Find your way around the screen

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Top bar: section name │ Overview Research Indicators Strategy lab Results ... │
│                       │ [Workspace ▾] [☀/☾ theme] [Effects on] [API connected] │
├───────────────────────────────────────────────────────────────────────────────┤
│ Synthetic demo · recorded replay — Invented articles and prices ...   (banner)│
├───────────────────────────────────────────────────────────────────────────────┤
│ Page heading + one-paragraph explanation of the page                          │
│ (demo pages only) slim tour bar: "Step n of 7 · next action"                  │
│ ... page content ...                                                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

| Element | What it does |
| --- | --- |
| **Navigation** | Eight sections: **Overview**, **Research** (Event research), **Indicators**, **Strategy lab**, **Results** (Saved results), **Compare**, **Import**, **Connections**. On a phone, use the ☰ menu button. The last two sit under **DATA & SETUP**. **Results** shows a count of saved runs. |
| **Workspace selector** | Switches between the synthetic demo and your own data. See [section 4](#4-choose-a-workspace). |
| **Theme button** | **Dark mode** / **Light mode**. The first visit follows your system setting; your choice is then remembered on this device. |
| **Effects on / Effects paused** | Pauses the animated background and the number count-ups. It is hidden if your system asks for reduced motion. |
| **API connected** | Shows that the Python research engine is reachable. If it isn't, you see **Can't reach the research engine.** with a **Retry** button. |
| **Synthetic banner** | Always shown in the demo workspace and cannot be dismissed. It reminds everyone that the data is invented. |
| **Dotted terms** | Hover or focus any dotted-underlined word for a one-line explanation. |
| **Glossary** | Opens a searchable list of every term (**Search the glossary**), grouped by topic. |
| **Notices** | Green or amber messages after an action, such as "Synthetic replay demo loaded". Close one with ×. |
| **Download buttons** | Most results can be saved as JSON (**Download full case**, **Download comparisons**, **Backtest + manifest JSON** and others). |

Keyboard users: press **Tab** once on a new page to show **Skip to content**.

---

## 4. Choose a workspace

A *workspace* is a separate database. Nothing leaks between them.

| Workspace | Use it for | Data |
| --- | --- | --- |
| **Synthetic demo (offline)** | Learning the tool and presenting. **Start here.** | 35 invented articles, invented prices, pre-recorded AI answers. No internet, no keys. |
| **My data – real companies** | Your own imported or downloaded data for the live universe (5 NSE stocks, the NIFTY 50 benchmark and MCX crude oil). | Whatever you import or sync. Identifiers start with `LIVE:`. |
| **My data – demo companies** | Your own data for the five demo companies. | Whatever you import. |

Opening a page never writes anything. Data appears only when you click an action such as **Load
synthetic demo**, **Import prices** or **Analyse**.

---

## 5. Quick start: the 7-step demo tour

The fastest way to learn the site is the **Demo tour** card on the **Overview** page (demo workspace).
It walks from a headline to checked evidence in seven steps. A tick appears as you finish each one,
and a slim tour bar on the other pages shows the next action.

| Step | Click | What you should see |
| --- | --- | --- |
| **1. Load the demo** | **Load synthetic demo** | Notice "Synthetic replay demo loaded…". The summary cards show 35 articles and 1,694 price records. |
| **2. Pick a news story** | **Open the story** | **Event research** opens on the Berger Paints crude-oil story (`syn-002`), with *Published* 12 Jan 2026 13:30 IST and *First seen* 13:35 IST. |
| **3. Freeze the moment** | Check that the cutoff is 12-01-2026, 17:30, India (IST), or click **Use demo cutoff (12 Jan, 17:30 IST)**. Then click **Analyse under all three methods**. | **Same article, three methods**: all three show **Neutral**, **+0.04**, **100%**, **completed**, followed by a plain-English summary. |
| **4. Read the verdict** | **Open saved result** | **Evidence label: Neutral**, how the score was built, **Why this label: Conflict**, the numbers used and the quoted article sentences. |
| **5. See what happened next** | **Evaluate later outcomes** | A **Later outcome** card: net return about +4.48% against a +0.90% benchmark. It is measured separately. |
| **6. Compare the methods** | **Load comparisons** | Calls and runs per method, and agreement with hand labels (**SYNTHETIC SANITY CHECK**). |
| **7. Test a price rule** | **Open Strategy lab** → **Load local history** → **Run backtest** | An SMA-crossover rule on a synthetic random walk. It loses to buy-and-hold, which is the correct result for random data. |

Other tour controls:

- **Skip tour** hides the card; **Show demo tour** brings it back.
- **Restart tour** clears the ticks (stored in your browser only).
- When all steps are done, the card shows **Tour complete**.

In a *My data* workspace, the card becomes a 3-step path instead: **Add evidence → Investigate →
Inspect**.

> For the full presenter script with timings and fallbacks, see
> [presentation/DEMO_SCRIPT.md](presentation/DEMO_SCRIPT.md).

---

## 6. Every section in detail

Each page opens with a short paragraph explaining what it is for. This section adds the details.

### 6.1 Overview

The home page. Its parts are:

- **Workspace summary cards**: counts of articles, price records, saved runs and outcomes.
- **Evidence coverage ring**: the average *evidence coverage* across saved, assessed cases. It shows
  how complete the evidence was, not how confident or correct the system is. Runs that were filtered
  out or stopped early count as **Not assessed**. That is often the correct outcome, not an error.
- **Saved price history**: an area chart of saved closing prices. Choose a company with **Chart
  company** and a time range. The chart uses saved data only (**SAVED DATA / NOT LIVE**) and never contacts a provider or AI model.
- **Companies in your workspace**: a searchable watchlist (**Search watchlist**). Click a row to
  chart that company.
- **From your research desk**: your most recent saved cases, with **Open saved results**.

### 6.2 Event research: analyse an article

This is the core of the project.

1. **Source inbox / Demo story articles.** Find an article with **Search sources**. Synthetic
   articles show a **SYNTHETIC SOURCE** badge. If the inbox is empty, use **Add your first article**,
   which takes you to Import.
2. **Read the source.** Expand **Original article** to read the full text. Check both times:
   - *Published*: when the article came out.
   - *First seen*: when this dataset first had it.
3. **Set the decision cutoff** (date, time, timezone). Only articles and prices available **before**
   this moment are used. Helpful buttons:
   - **Set cutoff to first-seen time**: the earliest moment the article could be analysed.
   - **Use demo cutoff (12 Jan, 17:30 IST)**: in the demo only.
4. **Choose the research method** (who does the screening and extraction):

   | Method on screen | Meaning |
   | --- | --- |
   | **Large model does both steps** | The baseline. The large model screens and extracts. |
   | **Small model screens → large model extracts** | A cheap small model drops irrelevant articles first. |
   | **Small model screens and hands over hints → large model extracts** | As above, but the small model also passes verified quotes and company names as hints. |

5. **Choose the analysis mode**:
   - **Recorded replay (demo articles only)**: uses saved AI answers. Offline, free and repeatable.
   - **Configured models (sends requests)**: calls the real AI models set up on the server. See
     [section 9](#9-real-market-data-and-real-ai-models-optional).
6. Click **Analyse and save run** (one method) or **Analyse under all three methods** (side by side).
7. Read the **Result** panel: label, score, coverage and status for each method, plus a one-sentence
   plain-English summary. Then click **Open saved result** for the full case.

**Running the same request twice** reuses the saved result instead of recomputing it. To force a new,
linked record, tick *Explicit repeat experiment* (under the advanced options).

**Messages you may see**, all of which are normal:

| Message | Meaning | What to do |
| --- | --- | --- |
| **No label: evidence incomplete.** | A required price was missing or too old at the cutoff. | Try a later cutoff, or check the price data. |
| **This article wasn't available yet.** | It was first seen after your cutoff. | Move the cutoff later. |
| **Filtered out: not a market event.** | The screening step found nothing market-relevant. | Try another article. |
| **Same text as an earlier article.** | A duplicate. It reuses the earlier article's result. | Nothing. |
| **The analysis stopped early.** | The call budget ran out or an error occurred. Nothing was overwritten. | Retry; this creates a linked record. |

Try this in the demo to see look-ahead protection: set the cutoff to **16:00** instead of 17:30 and
analyse again. You get **No label: evidence incomplete**, because crude oil's price for that day was
not yet available at 4 pm. The system refuses to guess.

### 6.3 Saved results: open a case

Every analysis is stored permanently. Pick one from **Saved run (newest first)** to open the
**Saved case**. From top to bottom it shows:

| Part | What it tells you |
| --- | --- |
| **Evidence label**, **Signed evidence score**, **Evidence coverage** | The verdict, with its threshold (±0.15) and minimum coverage (60%). |
| **How the score was built** | The exact sum, for example `0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral`. |
| **Why this label** | Reasons in plain words: conflicts, missing or stale inputs, abstention reasons. |
| **Numbers available at the cutoff** | Each input: *equity excess return*, *commodity return*, *relative volume (context only)*, with status *Available / Missing / Stale / Not applicable*. |
| **Supporting source passages** | The exact sentences the AI quoted. Quotes that are not word for word in the article are rejected. |
| **Original article** | The full source, kept with the case. |
| **Model call audit** | Every AI call: model, method, time and tokens. In replay, tokens show **Not recorded (replay)**. They are never faked as zero. |
| **Later outcome · evaluated separately from the decision** | Click **Evaluate later outcomes**. See [section 7.3](#73-later-outcomes). |
| **Optional explanation** | **Request model explanation** asks a live model to explain the case in prose. It is disabled for replay runs, and saved as a separate linked record. |

Use **Download full case** to save everything (source, numbers, configuration and audit) as JSON.

### 6.4 Comparisons: compare the three methods

Click **Load comparisons**. You get:

- **Call cards** for each method: runs, model calls split by small and large model, failures.
- **Method usage**: tokens, estimated cost and mean latency. Cost is shown only for live runs with
  complete token counts; replay shows **Not recorded in replay**.
- **Same article, different methods** / **How the three methods handled the same articles**: a
  like-for-like table of articles that every method analysed.
- **Extraction agreement with hand labels**: *filter recall*, *filter precision*, and field accuracy for
  event type, company and commodity, plus *validated spans* and *abstention rate*. In the demo these
  are tagged **SYNTHETIC SANITY CHECK**: they check the plumbing, not model quality.
- Later outcomes per method, and commodity sensitivity.

**Download comparisons** exports it all with run details. Viewing or exporting never changes saved
results.

> In replay, all three methods get the same recorded answer, so they agree by design. The page shows
> *how* the comparison works, not which method is better.

### 6.5 Price indicators

Chart indicators calculated from saved daily prices. No articles, AI or keys are needed (**NO MODEL
REQUIRED**).

1. **Select a price series** (a company).
2. Set a cutoff. **Use last price date** picks the latest saved bar.
3. Click **Compute price indicators**.

You get a price chart and a **Technical snapshot**: *SMA 20/50/200*, *EMA 20/50*, *RSI 14*, *MACD*,
*Bollinger bands*, *ATR 14*, *ADX 14* and *Volume*. Each indicator needs enough history first; for
example SMA 200 needs 200 trading days. Until then it shows *Warm-up missing* / **Insufficient warmup
observations.** The demo's event prices are too short for most indicators, so use imported history.

Indicators are **context only**. They never change an event's evidence score. Use **Download
snapshot** to save one.

### 6.6 Strategy lab: backtest a price rule

Studies stop at **31 Dec 2020** by design (the **2020** tag in the navigation).

**1. Choose your historical evidence**

- **Instrument**: pick a series, or click **Pick demo series** for **Synthetic lab series (QA only) ·
  1566 pre-2021 bars**. It is labelled **SYNTHETIC QA HISTORY**: a random walk generated for testing.
- Set **Study start** (default 01-01-2015) and **Study end** (at most 31-12-2020), then click **Load
  local history**.
- Optional: **Download historical candles from Upstox · explicit action**. This needs a token; see
  [section 9](#9-real-market-data-and-real-ai-models-optional). **History JSON** / **Download receipt
  JSON** record exactly what was loaded.

**2. Backtest a strategy**

| Setting | Meaning |
| --- | --- |
| **Strategy** | *SMA crossover* (default), *EMA crossover*, *Buy and hold*, *RSI reversion*, *MACD crossover*, *Bollinger reversion*. |
| **Initial capital (INR)** | Pretend starting money (default 100000). |
| **Fee per fill (bps)** | Brokerage on each buy or sell. 10 bps = 0.10%. |
| **Slippage per fill (bps)** | Extra price lost on each fill (default 5). |
| **Fast / Slow period** | Moving-average lengths in trading days (default 20 / 50). For RSI: buy and sell levels (default 30 / 70). |
| **Also test a walk-forward split** | Tests the same fixed rule separately before and after **Out-of-sample starts** (for example 2020-01-01). |

Click **Run backtest**. The **Equity & execution report** shows *strategy return* against *buy & hold
return*, *maximum drawdown*, *Sharpe ratio*, *Probabilistic Sharpe (PSR)*, *CAGR*, *win rate / closed
trades*, the equity curve and a table of trade fills. An amber **Low sample** note appears with fewer
than 30 closed trades. **Execution and research assumptions** spells out how trades are filled: at the
next session's open, with fees and slippage, long or cash only.

**3. Monte Carlo**

Click **Simulate return paths**, then **Play** / **Pause** to animate. It reshuffles chunks of the
strategy's own daily returns (*block bootstrap*) to show the spread of luck. You can set *simulated
paths*, *horizon*, *random seed* and *block size*. The results are *median*, *p05 / p95 terminal
capital* and *resampled loss frequency*. **Accessible percentile bands and assumptions** gives the same
data as a table. This is **not a forecast**.

Downloads: **Backtest + manifest JSON** and **Monte Carlo + manifest JSON**.

**Optional TradingView chart.** **Load external TradingView hosted widget** shows TradingView's own
chart for any `exchange:ticker`. It is an outside service with its own data. It ignores the 2020
cutoff and is not used for backtests. Nothing loads until you click.

> Good habit: decide your settings **before** looking at results. Then check that doubling costs and
> the walk-forward split don't destroy the result. On the synthetic random walk, *every* rule should
> show no edge. If one did, that would point to a bug.

### 6.7 Import evidence

Add your own articles or prices. Pick a type first:

- **Articles (JSONL)**: one JSON object per line.
- **Market prices (CSV)**: daily open, high, low, close and volume (OHLCV).

Then **Import a file or paste records**, or use **Add one article manually — no file needed**. The
manual form opens automatically when the inbox is empty. Formats are in
[section 8](#8-use-your-own-data).

The **Import report** shows **Added articles / Added observations** and any **row errors**, each with a
reason. Good rows are kept even when other rows fail; use **Show all** / **Show fewer errors** to see
the list. Successful imports link to the next step.

### 6.8 Connections

Not needed for the demo. This page shows:

- **Configuration readiness** (**OFFLINE CHECK**): which keys and models are set on the server.
  *Configured* means a setting exists; it does **not** prove the service works.
- **Refresh selected recent evidence**: downloads recent prices (and optionally news, with **Also
  import provider headline/summary news**) from Upstox for the live universe. Set the
  **Recent-history lookback (calendar days)**. It only runs when you click.
- **Separate model batch** → **Analyse latest synced news (live models)**: sends recently downloaded
  news through the real AI models in a small, bounded batch.
- **Provider report**: what was fetched, and when. **Download report** saves it.

If no token is set, you'll see **Upstox token not set.** That is expected until you complete
[section 9](#9-real-market-data-and-real-ai-models-optional).

---

## 7. How to read a result

### 7.1 Evidence label

| Label | Meaning |
| --- | --- |
| **Positive** | Combined score is **+0.15 or higher**. The evidence leans favourable for the stock. |
| **Negative** | Combined score is **−0.15 or lower**. |
| **Neutral** | Evidence exists but is too weak or too mixed (between −0.15 and +0.15), often a *conflict*. |
| **Abstain / No label** | Required evidence was missing, stale, unverified, or coverage was below 60%. The system refuses to guess. |

### 7.2 Score and coverage

- **Signed evidence score** (−1 to +1) = **0.6 × equity signal + 0.4 × commodity signal**.
  - The equity signal is the stock's move minus its benchmark's move, scaled so that ±2% gives ±1.
  - The commodity signal is the commodity's move, scaled so that ±3% gives ±1, with its sign flipped
    if the company is hurt by a rise. Crude up is bad for a paint maker. This comes from a reviewed,
    dated *exposure rule*.
- **Evidence coverage** = the share of required inputs that were actually available at the cutoff.
  Below 60%, the system abstains.
- **Relative volume** is shown for context and never affects the score.
- The score is **evidence strength, not a probability**.

### 7.3 Later outcomes

Clicking **Evaluate later outcomes** simulates holding the stock: **buy at the next trading day's open**
after the cutoff, **sell at the close of the 5th trading day**. It reports:

- **Gross return**, and **Net return** (after 0.10% round-trip costs).
- **Benchmark return** over the same days, and **Excess return** (stock minus benchmark).

Statuses: *completed*, **Waiting for five later trading days.** (pending: import later prices and
evaluate again), or **No outcome to measure.** (the run abstained). The outcome **never changes** the
saved label.

### 7.4 Run status

| Status | Meaning |
| --- | --- |
| completed | Got a label |
| abstained | Withheld a label on purpose |
| irrelevant | Filtered out as not a market event |
| duplicate | Same text as an earlier article |
| ineligible | Article not available at the cutoff |
| partial | Stopped by the call budget |
| failed | An error occurred |
| interrupted | Stopped by the user |

---

## 8. Use your own data

1. Switch the workspace to **My data – real companies** (or **My data – demo companies**).
2. Go to **Import** and add articles and prices as below.
3. Go to **Research**, pick your article, set a cutoff after its *first seen* time, and analyse.
   Replay works only for the bundled demo articles. Your own articles need **Configured models**
   ([section 9](#9-real-market-data-and-real-ai-models-optional)).
4. Import prices for at least five trading days after the cutoff, then evaluate outcomes.

**Always include a timezone in times**, for example `2026-01-12T13:30:00+05:30` or
`2026-01-12T08:00:00Z`.

### Articles (JSONL, one per line)

```json
{"article_id": "my-001", "source_url": "https://example.com/news/123", "text": "Full article text…", "published_at": "2026-01-12T13:30:00+05:30", "first_seen_at": "2026-01-12T13:35:00+05:30", "source_version": "1"}
```

Required fields: `article_id`, `source_url`, `text`, `published_at`, `first_seen_at`. The fields
`source_version` and `predecessor_id` (for a corrected version) are optional.

### Prices (CSV)

```csv
instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit,contract_id
NSE:BERGEPAINT,equity,2026-01-12T10:00:00Z,2026-01-12T10:05:00Z,149.25,151.5,147.76,150.0,1000,INR,share,
```

- `timestamp` is the trading session; `available_at` is when the bar could first be known.
- Prices must be positive and volume zero or more.
- Commodities need an explicit `contract_id`; different contracts are never mixed.
- A **benchmark** series and, for commodity-linked stocks, the **commodity** series are needed to
  reach 100% coverage.

Full field definitions: [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

---

## 9. Real market data and real AI models (optional)

The demo needs none of this. Real data has been tested only with simulated (mocked) responses, so
treat it as a pilot, and never rely on it during a live presentation.

1. **Prices and news**: create a free, read-only **Upstox Analytics Token** (it cannot place orders).
   Put it in the project's `.env` file **yourself**:
   ```dotenv
   UPSTOX_ANALYTICS_TOKEN=your_token_here
   ```
   Never paste the token into the website, chat, screenshots or exports. `.env` is excluded from git.
2. **AI models**: install Ollama, run `ollama serve`, and pull the models (small `qwen3.5:2b`, large
   `gemma4:e4b`), then set `SLM_*` / `LLM_*` in `.env`.
3. **Restart** the website (`Ctrl+C`, then `npm.cmd run dev`). Settings are read only at start-up.
4. Check readiness without any network calls:
   ```powershell
   .\.venv\Scripts\python.exe -m market_events readiness
   ```
5. In **My data – real companies**, open **Connections** → **Refresh selected recent evidence**, then
   analyse with **Configured models (sends requests)**.

Full instructions: [LIVE_SETUP.md](LIVE_SETUP.md).

---

## 10. Where your data lives, and how to reset it

| File | Workspace |
| --- | --- |
| `data/web_demo.sqlite` | **Synthetic demo (offline)** |
| `data/market_events.sqlite` | **My data** workspaces |

Each file holds that workspace's whole state.

**Reset the demo** to a clean state (for example before presenting):

```powershell
# 1. Stop the website (Ctrl+C). 2. Keep the old demo as a dated backup:
Move-Item data\web_demo.sqlite ("data\web_demo.backup-" + (Get-Date -Format yyyyMMdd-HHmm) + ".sqlite")
# 3. Start again, then click "Load synthetic demo" and "Restart tour".
npm.cmd run dev
```

This never touches *My data*. To undo it, stop the website and move the backup back to
`data\web_demo.sqlite`.

Tour ticks, theme and the effects setting are stored only in your browser. **Restart tour** clears
the ticks.

---

## 11. Troubleshooting

| Problem | Cause | Fix |
| --- | --- | --- |
| `npm run dev` exits immediately, or says the port is in use | The website is already running elsewhere (another window or herdr tab) on ports 3000/8000. | Open http://127.0.0.1:3000 and use it, or stop the other copy (Ctrl+C there) and start again. |
| `npm : … running scripts is disabled on this system` | PowerShell blocks `npm.ps1`. | Use `npm.cmd run dev`. |
| **Can't reach the research engine.** banner | The Python API on port 8000 isn't running or crashed. | Click **Retry**. If that fails, stop and rerun `npm.cmd run dev` (about 20 s). Check that the `.venv` is installed. |
| Page loads but shows **No data yet** | The workspace is empty. | Demo: click **Load synthetic demo**. My data: use **Import**. |
| Analysis says **No label: evidence incomplete.** | A required price was missing or stale at the cutoff. | Use a later cutoff, or import the benchmark or commodity prices. This is a correct result, not a bug. |
| Replay fails on your own article | Replay has answers only for the bundled demo articles. | Use **Configured models** (section 9). |
| Outcome stays **Waiting for five later trading days.** | Not enough prices after the cutoff. | Import later prices, then click **Evaluate later outcomes** again. |
| Indicators show **Insufficient warmup observations.** | Too few days of history. | Import longer history (SMA 200 needs 200 days). |
| Strategy lab has no instrument | No pre-2021 history in this workspace. | Click **Pick demo series** (demo), or import pre-2021 prices. |
| **Upstox token not set.** | No token in `.env`. | Expected for the demo. See section 9 if you want real data. |
| Animations are distracting on a projector | | Click **Effects on** to pause them, or switch to light mode. |
| Counts differ from the demo script | The demo database has extra runs from earlier clicks. | Reset the demo (section 10). |

---

## 12. What the website does not do

- **It does not predict prices or give trading advice.** Labels describe evidence at a past moment.
- **The demo is entirely synthetic.** Its results show how the software behaves, not how markets do.
  In replay, all three methods agree by design.
- **It has no live quote feed**, and nothing updates on its own. Every network or model action is a
  button you press.
- **It cannot place orders.** The Upstox token is read-only.
- **It runs locally only**, on your own computer, with no logins or user accounts.
- **Real-provider data is not yet verified** against a real account.
- **Backtests are retrospective experiments** on data up to 2020. PSR is not adjusted for trying many
  settings, and Monte Carlo shows the spread of luck, not future probabilities.

---

## 13. Other ways to run it: Streamlit and the command line

The same Python engine also powers an older Streamlit interface and a command-line tool. They are
useful as fallbacks.

### Start locally (Streamlit)

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501 and click **Load synthetic demo (replay)**. Its main pages are **Import
local evidence**, **Analyse an article**, **Review saved results**, **Explore price indicators**,
**Connect and refresh data**, **Compare research runs** and **Charts, backtests and Monte Carlo**.

### Command line

```powershell
$db = "data/cli_demo.sqlite"
.\.venv\Scripts\python.exe -m market_events --database $db demo
.\.venv\Scripts\python.exe -m market_events --database $db analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_filter --mode replay
.\.venv\Scripts\python.exe -m market_events --database $db outcomes
.\.venv\Scripts\python.exe -m market_events --database $db export --output runs/export.json
.\.venv\Scripts\python.exe -m market_events --database $db experiments --output runs/experiments.json
.\.venv\Scripts\python.exe -m market_events readiness
```

Policies: `llm_only` (large model does both steps), `slm_filter` (small model screens), `slm_delegate`
(small model screens and hands over hints). Modes: `replay` or `live`.

### For developers

| Command | Checks |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | Python test suite (561 tests on 2026-11-23) |
| `npm.cmd run check` (in `web/`) | TypeScript and ESLint |
| `npm.cmd run build` (in `web/`) | Production build |

**More documentation:** [code map](CODEBASE_GUIDE.md) · [architecture](SYSTEM_ARCHITECTURE.md) ·
[data dictionary](DATA_DICTIONARY.md) · [real-data setup](LIVE_SETUP.md) ·
[demo script](presentation/DEMO_SCRIPT.md) · [viva Q&A](presentation/VIVA_QA.md).
