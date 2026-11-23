# Live demo script: the guided demo tour (target 7:30, hard limit 8:00)

Project: *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal
Fusion in Indian Financial Markets*. The demo shows its implementation, **Market Events**.

The live demo follows the dashboard's own **7-step demo tour** on the Overview page
(`web/app/_components/demo-tour.tsx`). Labels in **bold** are exact on-screen text from
`web/app/_components/*.tsx` as committed in `420065e`/`8b4fca7`. Expected values were reproduced on
2026-11-23 through the real API on a fresh demo database. Everything is **synthetic, offline, recorded replay**.

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
   This touches only the demo workspace. "My data" (`data/market_events.sqlite`) is not affected. Opening
   pages never recreates the file; it reappears when you click **Load synthetic demo** in tour step 1.
   **Fresh-database counts:** after loading, 35 articles, 1,694 market observations (128 event bars plus
   the 1,566-bar lab series), 3 saved runs and 3 outcomes. Step 3 adds 2 runs (5 in total), and step 5
   takes outcomes to 5. Every count except articles and observations grows with each click, so say "on a
   fresh database" whenever you quote one.
2. Open http://127.0.0.1:3000, choose **Synthetic demo (offline)** in the header workspace selector, and
   click **Restart tour** on the Overview tour card. This clears the saved tour progress kept in the
   browser's localStorage under `market-events-tour`. The card should read **0 of 7 done**.
3. **Check the synthetic banner** directly under the top bar: **"Synthetic demo · recorded replay —
   Invented articles and prices with pre-recorded model answers. Offline; nothing here is real-market
   evidence."** It is always shown in the demo workspace and cannot be dismissed.
4. **Screen:** set the display to **1920×1080** (preferred) or **1366×768** at 100% browser zoom.
   Close other tabs and mute notifications.
5. **Light/dark:** toggle the theme button in the top bar (**Dark mode** / **Light mode**) once in each
   direction. Then pick the one that reads best on the projector; light is usually safer. If the room is
   bright or the animation distracts, click **Effects on** to pause effects.
6. Check that `http://127.0.0.1:3000/api/research/health` returns `{"status":"ok",…}` and that the top bar shows **API connected**.
7. **Fallbacks ready:** the screenshot folder `web/tests/screenshots/<resolution>-<theme>/` is open in an
   image viewer (files `01-…` to `12-…`, mapped per step below). Those screenshots come from the automated
   walkthrough database, so their run counts differ from a fresh database; don't read counts off them.
   Optionally, have Streamlit and the CLI ready (see "Global fallbacks" at the end).

**Say once, at the start, and point at the banner:** "Everything you're about to see is synthetic and
replayed from recorded model outputs. It demonstrates the software's behaviour, not market performance."

---

## Step 1: Load the demo (0:00–0:40)

**Click:** on the Overview tour card (**Demo tour: from a headline to evidence you can check**), step 1
**Load the demo**, then **Load synthetic demo**. (The heading button **Load synthetic demo (replay)** does the same.)

**Expect:** the notice "Synthetic replay demo loaded. These fixtures do not validate real-market
performance." The tour shows **1 of 7 done** and moves to step 2. The summary cards show 35 articles and
1,694 records.

**Say:** "Opening the page wrote nothing. Loading is an explicit action: it imports 35 invented articles
and their prices, then analyses one article per event family with recorded model answers. No network,
no API keys."

**Fallback:** screenshots `01-overview-start.png`, then `02-overview-demo-loaded.png`.

## Step 2: Pick a news story (0:40–1:20)

**Click:** tour step 2 **Pick a news story**, then **Open the story**.

**Expect:** **Event research** opens with **Crude-oil supply disruption for a paint maker (mixed
evidence, conflict)** (`syn-002`) selected at the top of **Demo story articles**. The source shows
**Published 12 Jan 2026, 13:30 IST** and **First seen 12 Jan 2026, 13:35 IST**, and the badge reads
**SYNTHETIC SOURCE**.

**Say:** "Each article carries two times: when it was published, and when *our dataset* first had it.
Prices also have two: the trading session, and when the bar became available. Evidence only counts if
both times are before the cutoff. That is how we rule out look-ahead." Optionally hover a dotted term
(for example **Decision cutoff**) to show a tooltip, or open **Glossary**.

**Fallback:** `05-events-inbox.png`.

## Step 3: Freeze the moment (1:20–2:30)

**Click:** the cutoff is already filled with **12-01-2026**, **17:30** and **India (IST)**. If not, click
**Use demo cutoff (12 Jan, 17:30 IST)**. Then click **Analyse under all three methods**.

**Expect:** a **Result** panel with **Same article, three methods**. All three cards (**Large model does
both steps**, **Small model screens → large model extracts**, **Small model screens and hands over hints
→ large model extracts**) show **Neutral**, **+0.04**, **100%**, **completed**. Below that is the run
summary in plain English: "After this crude oil supply disruption, Berger Paints beat its benchmark by
0.8%, but crude oil rose 1.5%, which counts against it under its reviewed synthetic exposure
assumption, so the evidence is mixed (neutral)."

**Say:** "Three ways of routing work between a small and a large model. In replay they *must* agree,
because the answers are recorded, so this shows consistency, not model quality. The note under the
cards says exactly that."

**Optional look-ahead beat (+25 s):** set the time to **16:00** (that is 10:30 UTC) and click **Analyse
and save run**. Expect **"No label: evidence incomplete."** with the reason "The commodity's price move for
the same session was not yet available, or was too old, at the cutoff." **Say:** "At 4 pm IST the stock
had closed but crude hadn't settled, so the system refuses to guess." Restore with **Use demo cutoff**.
This adds one saved run, which is intended.

**Fallback:** `06-events-analysed.png`, or CLI
`analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_filter --mode replay`.

## Step 4: Read the verdict (2:30–3:40)

**Click:** in the tour bar at the top of the page, **Open saved result**. Alternatively: **Results**, then
pick a `Berger Paints · … · Neutral · …` entry in **Saved run (newest first)**. The case opens
automatically.

**Expect:** **Evidence label: Neutral**, **Signed evidence score: +0.04 (Threshold ±0.15)** and
**Evidence coverage: 100% (Minimum 60%)**. Then **How the score was built**:
`0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral (threshold ±0.15)`.
Then **Why this label: Conflict: The stock's own move and the commodity's implied effect point in
opposite directions.** Finally, **Numbers available at the cutoff** (equity excess +0.80%, commodity
+1.50%, relative volume 1.23× context only) and **Supporting source passages**.

**Say:** "The language model only said *what happened*, quoting the sentence word for word. Everything
on this screen after that is Python: a fixed, versioned rule. The stock beat its sector, but crude rose,
and for a paint maker that's a cost, so the signals conflict and the label is neutral. It's flagged, not
averaged away. This score is evidence strength, not a probability." Scroll to **Model call audit**:
"Every model call is recorded. Tokens say **Not recorded (replay)**; we never fill in zeros."

**Do not** click **Request model explanation**: it is disabled for replay runs, and the note says why.

**Fallback:** `07-saved-case.png`, or Streamlit **Review saved results**.

## Step 5: See what happened next (3:40–4:20)

**Click:** on the same case, **Evaluate later outcomes** (shown when this run has no outcome yet; the
tour's **Evaluate later outcomes** link opens the same page).

**Expect:** the **Later outcome · evaluated separately from the decision** card shows **completed**, Net
return **+4.48%** (gross +4.58%), Benchmark return **+0.90%**, entry 13 Jan 2026 09:15 IST and exit
19 Jan 2026. The footnote reads **"Synthetic fixture prices. This is not real-market performance."**

**Say:** "This is measured *after* the decision and stored separately, so it can't change the verdict.
It's a market-adjusted return from the next morning's open to the fifth session's close, net of
10 basis points. Honest note: every demo company shows the same +4.58%, because the invented prices
rise by a fixed amount each day. This shows the mechanics, not the market."

**Fallback:** `09-saved-outcome.png`, or CLI `outcomes`.

## Step 6: Compare the methods (4:20–5:10)

**Click:** tour **Load comparisons**, or top nav **Compare**. The page loads automatically.

**Expect:** call cards per method, then **Method usage**. On a fresh database, after step 3, that is
**Large model does both steps** with 1 run and 2 calls, **Small model screens → large model extracts**
with 1 run and 2 calls, and the hints method with 3 runs and 6 calls (the demo's three articles; 4 runs and 8 calls if you did
the 16:00 beat). Tokens
show **Not recorded in replay**. Below are **Same article, different methods** and **Extraction agreement
with hand labels**, tagged **SYNTHETIC SANITY CHECK**; on a fresh database, filter recall and precision
are 100%.

**Say:** "This is *not* a quality comparison. Replay gives every method the same recorded answer and has
no token data. What it shows is the audit: runs, calls and failures counted per method, with missing data
left missing. Our only real comparison was a live development run on the same synthetic articles: 8 calls
for the large-model-only method against 9 for each small-model method, so there was *no* saving. We report
that negative result. The agreement table checks against labels I wrote myself; it's a sanity check, not
a benchmark."

**Fallback:** `08-comparisons.png`, or CLI `experiments`.

## Step 7: Test a price rule, as a random-walk sanity check (5:10–7:10)

**Frame it before any number appears.** **Say:** "The lab series is a random walk I generated, so a sound
engine should find *no* edge. If it found one, that would be a bug. The configuration was fixed before
this talk, and I won't tune it on stage."

**Click:** tour **Open Strategy lab** (top nav **Strategy lab**).
1. **Instrument** already shows **Synthetic lab series (QA only) · 1566 pre-2021 bars** (otherwise click
   **Pick demo series**). Point at **SYNTHETIC QA HISTORY · Interface verification only; not performance
   evidence.** Keep **Study start** 01-01-2015 and **Study end** 31-12-2020, then click **Load local history**.
2. Keep the defaults: **SMA crossover**, **Initial capital (INR)** 100000, **Fee per fill (bps)** 10,
   **Slippage per fill (bps)** 5, fast 20, slow 50. Click **Run backtest**.
3. **Cost stress:** change only the fee to **20** and the slippage to **10**, then click **Run backtest**. Restore 10 and 5.
4. **Walk-forward:** tick **Also test a walk-forward split** (**Out-of-sample starts** 2020-01-01) and
   click **Run backtest**. The **Walk-forward check** table appears.
5. Optional, if under 6:30: **Simulate return paths**, then **Play**.

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

**Click:** back to **Overview**. The tour card shows **7 of 7 done** or **Tour complete**.
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
