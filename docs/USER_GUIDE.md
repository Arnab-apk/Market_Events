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
5. [Quick start: the synthetic demo](#5-quick-start-the-synthetic-demo)
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

- In **Lab › Indicators**, compute RSI, moving averages and other indicators from saved daily prices.
- In **Lab › Backtest** and **Lab › Monte Carlo**, test a price rule on daily prices up to 31 Dec 2020,
  with trading costs and a simulation of resampled returns.

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

Wait about 10–20 seconds, then open **http://127.0.0.1:3000**. The dot on the **Settings** gear should
turn green. **Settings › Connections** shows **API connected**.

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

| Element | What it does |
| --- | --- |
| **Home** | Opens the **Overview** page with the quick start, company cards and latest stories. |
| **Portfolio** | Import holdings from a CSV, see estimates based on saved closing prices and open **View research** for a holding. |
| **Analyse** | Choose a story, set its decision time and run a method. |
| **Results** | Opens **Saved runs**. Switch to **Compare methods** to inspect method usage and agreement. |
| **Lab** | Opens **Indicators**. Use the **Backtest** and **Monte Carlo** sub-tabs for historical studies. |
| **Settings** gear | Opens **Import data**. The other sections are **Connections**, **Glossary**, **Appearance** and **About**. |
| **Data** selector | Switches workspaces. See [section 4](#4-choose-a-workspace). |
| **Settings › Appearance** | Choose **Light**, **Dark** or **System**. Light is the default and the browser remembers your choice. |
| **API status** | The dot on the Settings gear shows connection status. If the engine is unreachable, the banner says **Can't reach the research engine.** and offers **Retry**. |
| **Demo mode** | The banner stays visible in the demo workspace. **What does this mean?** opens the glossary entry for synthetic data. |
| **Dotted terms** | Hover or focus any dotted-underlined word for a one-line explanation. |
| **Settings › Glossary** | Use **Search the glossary** to find terms by name or topic. |
| **Notices** | A short confirmation appears after actions such as loading the demo. Close it with ×. |
| **Download buttons** | Save JSON with **Download snapshot**, **Download comparisons** or **Download backtest JSON**, depending on the page. |

The main tabs and the Settings gear are available on desktop and phone. Press **Tab** once on a new
page to show **Skip to content**.

---

## 4. Choose a workspace

The offline demo and the two **My data** options use separate data scopes. The **My data** options
share a local database and select different company universes.

| Workspace | Use it for | Data |
| --- | --- | --- |
| **Demo data (offline)** | Learning the tool and presenting. **Start here.** | 35 invented articles, invented prices, recorded model answers. No internet or keys required. |
| **My data – real companies** | Your own imported or downloaded data for the live universe (5 NSE stocks, the NIFTY 50 benchmark and MCX crude oil). | Whatever you import or sync. Identifiers start with `LIVE:`. |
| **My data – demo companies** | Your own data for the five demo companies. | Whatever you import. |

Opening a page reads saved data. Use **Explore demo**, **Validate and import** or
**Analyse** to create records.

---

## 5. Quick start: the synthetic demo

Select **Demo data (offline)** and open **Home**. The **New here?** strip shows **Load the demo**,
**Pick a story** and **Read the verdict**. Its first button is **Start the tour →**. Use the
following seven steps to work through the full demonstration.

| Step | Click | What you should see |
| --- | --- | --- |
| **1. Load the demo** | **Explore demo** | The notice says “Synthetic replay demo loaded. Everything in it is invented test data.” The **Overview** heading shows 35 demo stories. |
| **2. Pick a news story** | **Continue tour →**, or open **Analyse** and select **Crude-oil supply disruption for a paint maker** under **Demo story**. | **Berger Paints** opens at `syn-002`, with **Published** 12 Jan 2026, 13:30 IST and **first seen** 13:35 IST. |
| **3. Freeze the moment** | Set **Decision time** to 12 Jan 2026, 17:30, **India (IST)**. **Use demo cutoff (12 Jan, 17:30 IST)** sets it for this story. Open **More options** and click **Run all three methods and compare**. | **Compare 3 methods** shows **Mixed**, **+0.04**, **100%** and **completed** for each method. The underlying direction is neutral. |
| **4. Read the verdict** | Click **Open in Results**. In **Saved runs**, select the Berger Paints story at the 17:30 cutoff for **Large model does both steps**. | The **Verdict** shows **What pushed the score** and **Conflict**. Open **Numbers at the decision time** for inputs and read the **Full audit trail (sources, model calls, rules)** for quoted passages and model calls. |
| **5. See what happened next** | On that case, click **Evaluate later outcomes** if it hasn't been evaluated. | **Later outcome · checked separately from the verdict** shows about +4.48% net and +0.90% for the benchmark. |
| **6. Compare the methods** | Open **Results › Compare methods**. | **Method usage** shows calls and runs. Expand **Agreement with hand labels · synthetic sanity check** for the authored labels. |
| **7. Test a price rule** | Open **Lab › Backtest**, select **Synthetic lab series (QA only)**, then click **Load local history** and **Run backtest**. | The default **SMA crossover** rule on the synthetic random walk loses to buy-and-hold. |

Other tour controls:

- Once the first three steps are checked, Home offers **see what happened**, **compare methods**
  and **test a price rule**.
- **Skip tour** hides the strip. Use **Settings › About › Restart the tour** to bring it back.
  **Restart tour** on Home clears browser progress when at least one step is checked. The strip can
  still infer completed steps from saved data.
- When the three main steps and the follow-up actions are checked, the strip shows **Tour complete**.

In a **My data** workspace with imported stories, the steps are **Add a news story**, **Analyse it**
and **Read the verdict**.

> For the full presenter script with timings and fallbacks, see
> [presentation/DEMO_SCRIPT.md](presentation/DEMO_SCRIPT.md).

---

## 6. Every section in detail

### 6.1 Home

The **Overview** heading shows the story count, the number analysed and the latest cutoff when
available. With saved stories, the summary shows **Analysed**, **Positive evidence**, **Mixed** and
**Not enough evidence**. Select a card under **Companies** to open that company's stories in
**Analyse**, or select a story directly under **Latest stories**. **See all** opens the full story list.

### 6.2 Analyse

1. Find an article under **Stories** using **Search**. For an empty workspace, **Import news**
   opens **Settings › Import data**.
2. Read the source text and check **Published** and **first seen**. **Open source ↗** opens the
   original page when available. The demo instead shows **Synthetic article · no web page**.
3. Set **Decision time** using the date, time and timezone controls. The demo offers a **Use demo
   cutoff** preset with the date and time. On a run that was too early, **Set decision time to
   first-seen time** uses the story's first-seen timestamp.
4. Choose a **Method** to set who screens and extracts.

   | Method on screen | Meaning |
   | --- | --- |
   | **Large model does both steps** | The baseline. The large model screens and extracts. |
   | **Small model screens → large model extracts** | A cheap small model drops irrelevant articles first. |
   | **Small model screens and hands over hints → large model extracts** | As above, but the small model also passes verified quotes and company names as hints. |

5. Click **Run recorded replay** in the demo to use saved model responses. In **My data**, click
   **Analyse with configured models** to send the article to the configured providers. See
   [section 9](#9-real-market-data-and-real-ai-models-optional).
6. For a side-by-side comparison, open **More options** and click
   **Run all three methods and compare**.
7. Read the **Verdict** and, if you ran all three, **Compare 3 methods**. Click **Open in Results**
   to inspect the saved case.

Running the same request twice reuses the saved result. **More options › Repeat experiment (creates
a linked run)** saves a new linked run and is available for a single method.

| Message | Meaning | What to do |
| --- | --- | --- |
| **No verdict: evidence incomplete.** | A required price was missing or too old at the cutoff. | Try a later cutoff, or check the price data. |
| **This article wasn't available yet.** | It was first seen after your cutoff. | Move the cutoff later. |
| **Not relevant: not a market event.** | The screening step found nothing market-relevant. | Try another article. |
| **Same text as an earlier article.** | A duplicate. It reuses the earlier article's result. | Nothing. |
| **The analysis stopped early.** | The call budget ran out or an error occurred. Nothing was overwritten. | Retry; this creates a linked record. |

To see look-ahead protection on the Berger Paints story, set **Decision time** to **16:00** IST and
click **Analyse**. The verdict says **No verdict: evidence incomplete.** The crude oil price for that
session became available after 16:00.

### 6.3 Results › Saved runs

Use **Search** to find a company, story or method. Click the story in the matching row to open the
**Verdict**. The table lists the newest runs first.

| Part | What it tells you |
| --- | --- |
| **Evidence**, **Signed evidence score**, **Data coverage** | The evidence label, score threshold (±0.15) and evidence coverage minimum (60%). |
| **What pushed the score** | Contributions, formula and reasons such as **Conflict**. For the crude-oil example, `0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral`. |
| **Numbers at the decision time** | Inputs such as *equity excess return*, *commodity return* and *relative volume (context only)* with status *Available / Missing / Stale / Not applicable*. |
| **Full audit trail (sources, model calls, rules)** | **Supporting source passages** and the **Model call audit**. The audit keeps the task, model, mode, status, tokens and latency. Replay tokens show **Not recorded (replay)**. |
| **Original article** | The full source kept with the case. |
| **Later outcome** | Click **Evaluate later outcomes** if the assessed run has no outcome yet. See [section 7.3](#73-later-outcomes). |
| **Optional explanation** | **Request model explanation** asks a live model to explain the case in prose. It is disabled for replay runs, and saved as a separate linked record. |

Use **Download snapshot** in **Saved runs** to save the full case, including the original price
observations and outcome record, as JSON.

### 6.4 Results › Compare methods

The section reads saved runs automatically. Use **Reload comparisons** to refresh the view.

- **Method usage** lists runs, calls by model size, failures, tokens, latency and abstentions.
  Estimated cost is available for live groups with complete token counts and configured prices.
  Replay tokens show **Not recorded in replay**.
- **Same article, different methods** groups runs with the same article, cutoff and mode.
- **Agreement with hand labels · synthetic sanity check** shows *filter recall*, *filter precision*,
  field accuracy, *validated spans* and *abstention rate* on authored labels.
- **Later outcomes** shows later returns by run. **Matched cohorts, run manifest and ablations
  (JSON)** exposes the underlying comparison data.

**Download comparisons** exports the report. **Evaluate later outcomes** explicitly updates the
workspace's outcome records.

> In replay, all three methods get the same recorded answer. Their agreement checks pipeline
> consistency on synthetic examples.

### 6.5 Lab › Indicators

**Price indicators** are computed from saved daily prices and run locally.

1. Choose a **Company**.
2. Set **Prices up to**. **Use last price date** sets a time just after the latest saved bar.
3. Click **Compute price indicators**.

Use **Indicators to show** to toggle *SMA 20*, *SMA 50*, *SMA 200*, *EMA 20*, *EMA 50*, *RSI 14*,
*MACD*, *Bollinger*, *ATR 14*, *ADX 14* and *Volume*. The price chart can plot indicator lines
for sessions from 2000 through 2020. **What the indicators say** shows the readings at the
selected cutoff. Open **All values with history needed** for the warm-up requirements. SMA 200
needs 200 trading days and shows **Warm-up missing** until enough prices are available.

Indicators are **context only**. They never change an event's evidence score. Use **Download
snapshot** to save the readings.

For a hosted chart, expand **TradingView chart (optional, external service)** and check **Load the
TradingView widget**. It loads TradingView's own chart for an exchange and ticker. The widget uses
external data independently of the saved study and its 2020 cutoff.

### 6.6 Lab › Backtest and Monte Carlo

The **Historical study** banner gives the 31 Dec 2020 cutoff for backtests.

**1. Choose your historical evidence**

- In **Company**, choose **Synthetic lab series (QA only) · 1566 days before 2021** for the demo's
  random walk. **Pick demo series** also appears when the selected company has no pre-2021 prices.
- Set **Start** (default 01-01-2015) and **End (latest 31 Dec 2020)**, then click **Load
  local history**.
- In **My data – real companies**, expand **Download daily prices from Upstox (explicit action)**
  and click **Download historical candles** if you have a token. See
  [section 9](#9-real-market-data-and-real-ai-models-optional). **History JSON** saves the loaded prices.
  **Download receipt JSON** saves the provider receipt when available.

**2. Backtest a strategy**

| Setting | Meaning |
| --- | --- |
| **Strategy** | *SMA crossover* (default), *EMA crossover*, *Buy and hold*, *RSI reversion*, *MACD crossover*, *Bollinger reversion*. |
| **Initial capital (INR)** | Pretend starting money (default 100000). |
| **Fee per fill (bps)** | Brokerage on each buy or sell. 10 bps = 0.10%. |
| **Slippage per fill (bps)** | Extra price lost on each fill (default 5). |
| **Fast period (sessions)** and **Slow period (sessions)** | Moving-average lengths (default 20 / 50) under **Advanced parameters**. The RSI rule instead shows **RSI buy at or below** and **RSI sell at or above** (default 30 / 70). |
| **Also test a walk-forward split** | Under **Advanced parameters**, test the same fixed rule before and after **Out-of-sample starts** (default 2020-01-01). |

Click **Run backtest**. The results show *strategy return*, *buy & hold return*, *maximum drawdown*,
*Sharpe ratio*, *Probabilistic Sharpe (PSR)*, *CAGR*, *win rate* and *closed trades*. An amber
**Low sample** note appears with fewer than 30 closed trades. The **Equity & execution report**
contains the equity chart, **Trades**, **Execution and research assumptions** and, when selected,
**Walk-forward check**. Signals fill at the next session's open with fees and slippage, long or cash
only. **Download backtest JSON** saves the report and manifest.

**3. Monte Carlo**

Switch directly from **Backtest** to **Monte Carlo** to use the current backtest. If there is no
result, click **Run backtest with these settings** first. Click **Simulate return paths**. The
simulation reshuffles chunks of the strategy's own daily returns (*block bootstrap*). Use **Play**,
**Pause** or **Replay**, or enable **Reduced motion** to see complete static paths. The results
include *median* and *p05 / p95 terminal capital* and *resampled loss frequency*. Open
**Percentile bands as a table, and assumptions** or use **Download Monte Carlo JSON** for the report
and manifest.

> Good habit: decide your settings **before** looking at results. Then check that doubling costs and
> the walk-forward split don't destroy the result. On the synthetic random walk, *every* rule should
> show no edge. If one did, that would point to a bug.

### 6.7 Settings › Import data

Add your own articles or prices. Pick a type first:

- **Articles (JSONL)**: one JSON object per line.
- **Market prices (CSV)**: daily open, high, low, close and volume (OHLCV).

Choose a file or paste into **Records**, then click **Validate and import**. For one story, open
**Add one article by hand** and use **Save manual article**. The manual form opens automatically when
the inbox is empty. Formats are in
[section 8](#8-use-your-own-data).

The **Import report** shows how many records were saved and lists rejected rows with their reasons.
If more than ten rows were rejected, the **Show all** or **Show fewer errors** control changes the
length of the list. Successful imports offer **Analyse imported articles** or **See imported prices**.

### 6.8 Settings › Connections

Not needed for the demo. This page shows:

- **Connections** shows **Configured** or **Setup needed** based on settings present on the server.
- Under **Download historical prices for the Lab**, select companies and dates before clicking **Download
  history ending 2020**.
- Under **Refresh recent prices and news**, select companies and set **Recent-history lookback
  (calendar days)**. Company news is included by default. Click **Refresh selected recent
  evidence** to fetch the selected data from Upstox in the live universe.
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

The verdict badge can show **Positive**, **Negative**, **Mixed**, **No verdict** or **Not relevant**.
The Berger Paints example displays **Mixed** and keeps the research direction `neutral` in the
score formula and saved data.

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
- **Benchmark return** over the same days, and **Excess return** (gross stock return minus benchmark).

The case can show **completed**, **Waiting for five later trading days** or **No outcome to measure**.
For a pending outcome, import later prices and use **Results › Compare methods › Evaluate later
outcomes** to refresh it. A later outcome leaves the saved label as it was at the decision time.

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
2. Go to **Settings › Import data** and add articles and prices as below.
3. Go to **Analyse**, pick your article, set **Decision time**, and click **Analyse with configured models**.
   See [section 9](#9-real-market-data-and-real-ai-models-optional) for model setup.
4. Import prices for at least five trading days after the cutoff, then open the case in
   **Results › Saved runs** and click **Evaluate later outcomes**.

**Always include a timezone in times**, for example `2026-01-12T13:30:00+05:30` or
`2026-01-12T08:00:00Z`.

### Articles (JSONL, one per line)

```json
{"article_id": "LIVE:LOCAL:my-001", "source_url": "https://example.com/news/123", "text": "Full article text…", "published_at": "2026-01-12T13:30:00+05:30", "first_seen_at": "2026-01-12T13:35:00+05:30", "source_version": "1"}
```

Required fields: `article_id`, `source_url`, `text`, `published_at`, `first_seen_at`. The fields
`source_version` and `predecessor_id` (for a corrected version) are optional.

### Prices (CSV)

```csv
instrument_id,market_family,timestamp,available_at,open,high,low,close,volume,currency,unit,contract_id
LIVE:NSE:BERGEPAINT,equity,2026-01-12T10:00:00Z,2026-01-12T10:05:00Z,149.25,151.5,147.76,150.0,1000,INR,share,
```

- `timestamp` is the trading session; `available_at` is when the bar could first be known.
- Prices must be positive and volume zero or more.
- Commodities need an explicit `contract_id`; different contracts are never mixed.
- A **benchmark** series and, for commodity-linked stocks, the **commodity** series are needed to
  reach 100% coverage.
- The example identifiers are for **My data – real companies**. For **My data – demo companies**,
  use the demo universe's identifiers and leave off the `LIVE:` prefix.

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
5. Click **Connect real data** from Home, select companies, and click **Refresh selected recent evidence**.
   When a story is available, open **Analyse** and click **Analyse with configured models**.

Full instructions: [LIVE_SETUP.md](LIVE_SETUP.md).

---

## 10. Where your data lives, and how to reset it

| File | Workspace |
| --- | --- |
| `data/web_demo.sqlite` | **Demo data (offline)** |
| `data/market_events.sqlite` | **My data** workspaces |

Each file holds that workspace's whole state.

**Reset the demo** to a clean state (for example before presenting):

```powershell
# 1. Stop the website (Ctrl+C). 2. Keep the old demo as a dated backup:
Move-Item data\web_demo.sqlite ("data\web_demo.backup-" + (Get-Date -Format yyyyMMdd-HHmm) + ".sqlite")
# 3. Start again, then select Demo data (offline).
npm.cmd run dev
```

This never touches *My data*. To undo it, stop the website and move the backup back to
`data\web_demo.sqlite`.

Use **Settings › About › Restart the tour**, then **Home › Explore demo** if you are in a local workspace.
The browser stores the tour choices and theme preference.

---

## 11. Troubleshooting

| Problem | Cause | Fix |
| --- | --- | --- |
| `npm run dev` exits immediately, or says the port is in use | The website is already running elsewhere (another window or herdr tab) on ports 3000/8000. | Open http://127.0.0.1:3000 and use it, or stop the other copy (Ctrl+C there) and start again. |
| `npm : … running scripts is disabled on this system` | PowerShell blocks `npm.ps1`. | Use `npm.cmd run dev`. |
| **Can't reach the research engine.** banner | The Python API on port 8000 isn't running or crashed. | Click **Retry**. If that fails, stop and rerun `npm.cmd run dev` (about 20 s). Check that the `.venv` is installed. |
| Home shows **No stories yet** | The workspace has no articles. | Click **Explore demo**, **Connect real data**, or **Import news or prices**. |
| Analysis says **No verdict: evidence incomplete.** | A required price was missing or stale at the cutoff. | Use a later cutoff, or import the benchmark or commodity prices. |
| Analysis needs a model provider | Local articles use configured models. | Set up the model providers in section 9. |
| Outcome stays **Waiting for five later trading days** | The price history ends too soon. | Import later prices, then use **Results › Compare methods › Evaluate later outcomes**. |
| Indicators show **Warm-up missing** | Too few days of history. | Import longer history (SMA 200 needs 200 days). |
| Backtest says **No prices before 2021 for this company.** | The selected company has no eligible history. | Choose the synthetic lab series in the demo or import pre-2021 prices for your company. |
| **Upstox token not set.** | No token in `.env`. | Expected for the demo. See section 9 if you want real data. |
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
