# Live demo script: the guided demo tour (target 7:30, hard limit 8:00)

Project: *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal
Fusion in Indian Financial Markets*. The demo shows its implementation, **Market Events**.

This seven-step script starts with the **New here?** strip on **Home** and continues through
**Analyse**, **Results** and **Lab**. The instructions follow the dashboard controls in the current
checkout. The expected values come from the synthetic replay and historical fixtures. The demo runs
offline with recorded model answers.

---

## Before you present (checklist)

Do this 30 minutes before, in order.

1. **Start from a fresh demo database, so counts are predictable.** The web demo workspace always uses
   **`data/web_demo.sqlite`** under the project root (`src/market_events/api.py`, `configuration()`).
   The engine uses no SQLite side-files (no `-wal`/`-shm`), so this one file is the whole demo state.
   In PowerShell, from the repository root:
   ```powershell
   # 1. Stop the dev stack first (Ctrl+C in its window). The file must not be in use.
   # 2. Keep the old database as a dated backup instead of deleting it:
   Move-Item data\web_demo.sqlite ("data\web_demo.backup-" + (Get-Date -Format yyyyMMdd-HHmm) + ".sqlite")
   # 3. Restart the dev stack (Next.js on :3000, Python API on :8000):
   npm.cmd run dev
   ```
   Opening pages reads saved data. The demo file reappears when you click **Load synthetic demo
   (replay)** or **Start the tour →** in step 1.
   **Fresh-database counts:** after loading, 35 articles, 1,694 market observations (128 event bars plus
   the 1,566-bar lab series), 3 saved runs and 3 outcomes. Step 3 adds 2 runs (5 in total), and step 5
   takes completed outcomes to 5. Say "on a fresh database" when quoting counts.
2. Open http://127.0.0.1:3000 and choose **Demo data (offline)** in the header data selector. Open
   **Settings › About** and click **Restart the tour** to clear browser progress. Return to **Home**
   and check that the **New here?** strip shows **Start the tour →**.
3. **Check the synthetic banner** directly under the top bar. It says **Demo mode** and
   “All articles, prices and model answers are invented test data. Not advice; nothing here places orders.”
4. **Screen:** set the display to **1920×1080** (preferred) or **1366×768** at 100% browser zoom.
   Close other tabs and mute notifications.
5. In **Settings › Appearance**, try **Light** and **Dark**, then pick the one that reads best on the
   projector. **Light** is the default. **System** follows the device setting.
6. Check that `http://127.0.0.1:3000/api/research/health` returns `{"status":"ok",…}` and
   **Settings › Connections** shows **API connected**. Return to **Home**.
7. **Fallbacks ready:** the screenshot folder `web/tests/screenshots/<resolution>-<theme>/` is open in an
   image viewer (files `01-…` to `12-…`, mapped per step below). Those screenshots come from the automated
   walkthrough database, so their run counts differ from a fresh database; don't read counts off them.
   Optionally, have Streamlit and the CLI ready (see "Global fallbacks" at the end).

**Say once, at the start, and point at the banner:** "Everything you're about to see is synthetic and
replayed from recorded model outputs. It demonstrates the software's behaviour, not market performance."

---

## Step 1: Load the demo (0:00–0:40)

**Click** **Start the tour →** in the **New here?** strip on **Home**, or use **Load synthetic demo
(replay)** alongside the **Overview** heading.

**Expect** the notice “Synthetic replay demo loaded. Everything in it is invented test data.”
**Load the demo** gets a check mark and the **Overview** summary shows 35 demo stories. The demo
includes a saved run for the featured story, so the strip can already show the **Next:** links.

**Say:** "Opening the page wrote nothing. Loading is an explicit action: it imports 35 invented articles
and their prices, then analyses one article per event family with recorded model answers. No network,
no API keys."

**Fallback:** screenshots `01-home-start.png`, then `02-home-demo-loaded.png`.

## Step 2: Pick a news story (0:40–1:20)

**Click** **Analyse** and select **Crude-oil supply disruption for a paint maker** under
**Demo story**. If Home shows **Continue tour →**, that link opens the same story.

**Expect** **Berger Paints** to open with **Crude-oil supply disruption for a paint maker** (`syn-002`).
The source shows **Published** 12 Jan 2026, 13:30 IST, **first seen** 12 Jan 2026, 13:35 IST
and **Synthetic article · no web page**.

**Say:** "Each article carries two times: when it was published, and when *our dataset* first had it.
Prices also have two: the trading session, and when the bar became available. Evidence only counts if
both times are at or before the cutoff. That is how we rule out look-ahead." Optionally hover
**Decision time** to show its tooltip.

**Fallback:** `04-analyse-story.png`.

## Step 3: Freeze the moment (1:20–2:30)

**Check** **Decision time** for 12 Jan 2026, 17:30, **India (IST)**. To restore it, click
**Use demo cutoff (12 Jan, 17:30 IST)**. Open **More options** and click **Run all three methods and
compare**.

**Expect** a **Verdict** with **Compare 3 methods**. All three cards (**Large model does
both steps**, **Small model screens → large model extracts**, **Small model screens and hands over hints
→ large model extracts**) show **Mixed**, **+0.04**, **100%** and **completed**. The verdict
summary says “After this crude oil supply disruption, Berger Paints beat its benchmark by
0.8%, but crude oil rose 1.5%, which counts against it under its reviewed synthetic exposure
assumption, so the evidence is mixed (neutral).”

**Say:** "Three ways of routing work between a small and a large model. In replay they *must* agree,
because the answers are recorded, so this shows consistency, not model quality. The note under the
cards says exactly that."

**Optional look-ahead beat (+25 s)** · Set **Decision time** to 16:00 IST (10:30 UTC), keep
**Small model screens and hands over hints → large model extracts** selected and click **Analyse**.
Expect **No verdict: evidence incomplete.** The verdict explains that the commodity price move
was unavailable at the cutoff. **Say** “At 4 pm IST the stock had closed but crude hadn't settled,
so the system refuses to guess.” Click **Use demo cutoff (12 Jan, 17:30 IST)** to restore the form.
This adds one saved run. Select the 17:30 run explicitly in step 4.

**Fallback:** `05-analyse-verdict.png`, or CLI
`analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_filter --mode replay`.

## Step 4: Read the verdict (2:30–3:40)

**Click** **Open in Results** in the **Verdict**, or use **Results › Saved runs**. In the saved-runs
table, click the **Crude-oil supply disruption for a paint maker** story in the row with the
17:30 IST cutoff and **Large model does both steps**. On a fresh demo this is one of the new runs
from step 3, so you can evaluate its later outcome in step 5.

**Expect** **Evidence** to show **Mixed**, **Signed evidence score** to show +0.04 (**Threshold ±0.15**)
and **Data coverage** to show 100% (**Minimum 60%**). **What pushed the score** shows
`0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral (threshold ±0.15)`.
Point to **Conflict**, then open **Numbers at the decision time** (equity excess +0.80%, commodity
+1.50%, relative volume 1.23× for context). **Full audit trail (sources, model calls, rules)**
contains **Supporting source passages** and **Model call audit**.

**Say:** "The language model only said *what happened*, quoting the sentence word for word. Everything
on this screen after that is Python: a fixed, versioned rule. The stock beat its sector, but crude rose,
and for a paint maker that's a cost, so the signals conflict and the label is neutral. It's flagged, not
averaged away. This score is evidence strength, not a probability." Scroll to **Model call audit**:
"Every model call is recorded. Tokens say **Not recorded (replay)**; we never fill in zeros."

**Request model explanation** is disabled for replay runs.

**Fallback:** `06-results-saved.png`, or Streamlit **Review saved results**.

## Step 5: See what happened next (3:40–4:20)

**Click** **Evaluate later outcomes** on the saved case. If it already has an outcome, read the card.

**Expect** **Later outcome · checked separately from the verdict** to show **completed**, Net
return **+4.48%** (gross +4.58%), Benchmark return **+0.90%**, entry 13 Jan 2026 09:15 IST and exit
19 Jan 2026. The footnote reads “Synthetic test prices, not real-market performance.”

**Say:** "This is measured *after* the decision and stored separately, so it can't change the verdict.
The net stock return comes from the next morning's open to the fifth session's close, after
10 basis points of costs. The screen also shows the benchmark return and the gross stock return
minus that benchmark. The demo stocks share the same gross return because their prices follow the
same synthetic pattern."

**Fallback:** `08-results-outcome.png`, or CLI `outcomes`.

## Step 6: Compare the methods (4:20–5:10)

**Click** **Results › Compare methods**. The page loads automatically.

**Expect:** call cards per method, then **Method usage**. On a fresh database, after step 3, that is
**Large model does both steps** with 1 run and 2 calls, **Small model screens → large model extracts**
with 1 run and 2 calls, and the hints method with 3 runs and 6 calls (the demo's three articles; 4 runs and 8 calls if you did
the 16:00 beat). Tokens
show **Not recorded in replay**. Expand **Same article, different methods** and **Agreement with hand
labels · synthetic sanity check**. On a fresh database, filter recall and precision are 100%.

**Say:** "This is *not* a quality comparison. Replay gives every method the same recorded answer and has
no token data. What it shows is the audit: runs, calls and failures counted per method, with missing data
left missing. Our only real comparison was a live development run on the same synthetic articles: 8 calls
for the large-model-only method against 9 for each small-model method, so there was *no* saving. We report
that negative result. The agreement table checks against labels I wrote myself; it's a sanity check, not
a benchmark."

**Fallback:** `07-results-compare.png`, or CLI `experiments`.

## Step 7: Test a price rule, as a random-walk sanity check (5:10–7:10)

**Frame it before any number appears.** **Say:** "The lab series is a random walk I generated, so a sound
engine should find *no* edge. If it found one, that would be a bug. The configuration was fixed before
this talk, and I won't tune it on stage."

**Open** **Lab › Backtest**.

1. In **Company**, verify **Synthetic lab series (QA only) · 1566 days before 2021**. Select it if
   needed. Point at “Synthetic test series: for trying the tool only, not evidence of performance.”
   Keep **Start** at 1 Jan 2015 and **End (latest 31 Dec 2020)** at 31 Dec 2020, then click
   **Load local history**.
2. Keep the defaults: **SMA crossover**, **Initial capital (INR)** 100000, **Fee per fill (bps)** 10,
   **Slippage per fill (bps)** 5, fast 20, slow 50. Click **Run backtest**.
3. **Cost stress:** change only the fee to **20** and the slippage to **10**, then click **Run backtest**. Restore 10 and 5.
4. **Walk-forward** · Open **Advanced parameters**, tick **Also test a walk-forward split**, keep
   **Out-of-sample starts** at 1 Jan 2020 and click **Run backtest**. The **Walk-forward check** table
   appears in **Equity & execution report**.
5. Optional if under 6:30: switch directly to **Monte Carlo**, click **Simulate return paths**, then
   **Play**. With reduced motion enabled, the complete paths are already visible.

**Expect** (`POST /api/backtest` on 2026-11-21/23; synthetic random walk):

| Run | Strategy return | Buy & hold | Max drawdown | Sharpe | PSR | Closed trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2015–2020, 10 / 5 bps | −52.55% | +33.78% | −55.73% | −0.79 | 2.49% | 20 |
| 2015–2020, 20 / 10 bps | −55.3% | +33.6% | −58.1% | −0.85 | 1.6% | 20 |
| In-sample 2015–2019 | −41.4% | +24.7% | −49.3% | −0.69 | 5.8% | 15 |
| Out-of-sample 2020 | −17.5% | +9.0% | −19.2% | −1.23 | 9.8% | 4 |

The amber note **"Low sample size — fewer than 30 closed trades."** appears. Monte Carlo (seed 42):
median ≈ 89,000, p05 ≈ 72,000, p95 ≈ 110,000.

**Say:** "No edge, as it should be. The rule loses to buy-and-hold, and the probabilistic Sharpe ratio is
about 2.5%, roughly the chance the true Sharpe is above zero. That figure is for this one configuration and
not deflated for trials. Doubling costs makes it worse. The walk-forward split shows the same story in
both halves, so there is no hidden 'good period'. With 20 trades the screen warns the sample is too small
to trust anyway. Fills happen at the next morning's open, never the same bar. The Monte Carlo reshuffles
chunks of this strategy's own returns; it shows luck, not a forecast."

**Fallback:** `10-lab-history.png`, `11-lab-backtest.png` (this shows exactly the 10 / 5 row above) and
`12-lab-monte-carlo.png`. If short of time, do only steps 1–2 plus the cost-stress rerun.

## Close (7:10–7:30)

**Click** **Home**. The strip shows **Tour complete** when the three main steps and follow-up
actions are checked.
**Say:** "The model said what happened. Python decided what the evidence showed, using only what was
known at 17:30 IST. The outcome was measured separately afterwards, and every step is saved and can be
replayed. Happy to take questions."

---

## Timing summary

| Step | Window | If running late |
| --- | --- | --- |
| 1 Load the demo | 0:00–0:40 | — |
| 2 Pick a news story | 0:40–1:20 | skip the tooltip |
| 3 Freeze the moment | 1:20–2:30 | skip the 16:00 cutoff beat |
| 4 Read the verdict | 2:30–3:40 | skip the call audit |
| 5 See what happened next | 3:40–4:20 | narrate from the slide on outcomes |
| 6 Compare the methods | 4:20–5:10 | show the method-usage table only |
| 7 Test a price rule | 5:10–7:10 | drop walk-forward and Monte Carlo |
| Close | 7:10–7:30 | — |

## Global fallbacks (any step)

1. **"Can't reach the research engine."** banner: stop and rerun `npm.cmd run dev` (about 20 s). Narrate
   from the matching screenshot meanwhile.
2. **Dashboard broken:** use the screenshots for the rest of the tour. They are a complete visual record
   of steps 1–7 at both resolutions and in both themes.
3. **Streamlit (same engine):** `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501`,
   then **Load synthetic demo (replay)**, **Analyse an article**, **Review saved results** and **Compare
   research runs**. Its lab (**Charts, backtests and Monte Carlo**) can use the synthetic QA database
   `scratch/SYNTHETIC_strategy_browser_qa.sqlite`. That is a different series, so don't quote the step-7 table for it.
4. **CLI** (verified against a scratch database):
   ```powershell
   $db = "data/cli_demo.sqlite"
   .\.venv\Scripts\python.exe -m market_events --database $db demo
   .\.venv\Scripts\python.exe -m market_events --database $db analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_filter --mode replay
   .\.venv\Scripts\python.exe -m market_events --database $db outcomes
   .\.venv\Scripts\python.exe -m market_events --database $db experiments --output runs/experiments.json
   ```

**After the presentation:** to return to your previous demo state, stop the stack and move the dated backup back to `data/web_demo.sqlite`.
