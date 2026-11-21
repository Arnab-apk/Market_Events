# Live demo script: Next.js dashboard (target 7:30, hard limit 8:00)

Project: *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets*. The demo shows its implementation, **Market Events**.

Everything in the main path is **offline**: synthetic fixtures, recorded replay, no keys, no network.
Each step has an offline fallback. Clicks use the exact on-screen labels from `web/app/_components/*.tsx`
as of 2026-11-21. Expected values were reproduced on 2026-11-21 by running the same engine functions
against a scratch database. Re-check them at the final rehearsal, because the UI agent may still change
labels.

**Say once, at the start, and leave on screen:** "Everything you're about to see is synthetic and
replayed from recorded outputs. It demonstrates the software's behaviour, not market performance."

---

## Before the session (T−30 min)

1. From the repository root, in PowerShell:
   ```powershell
   npm.cmd run dev            # starts Next.js on :3000 and FastAPI on :8000 (scripts/dev-web.mjs)
   ```
   Wait for `Market Events website: http://127.0.0.1:3000`. Open it in the browser and zoom to fit
   1366×768 or 1920×1080. Pick the light or dark theme with the sun/moon button.
2. **Strategy lab fallback (only if the Next.js lab fails; see step 7).** In a second PowerShell window:
   ```powershell
   $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scratch\build_strategy_qa.py
   .\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
   ```
   `build_strategy_qa.py` is idempotent. It creates or reuses `scratch/SYNTHETIC_strategy_browser_qa.sqlite`
   (500 synthetic bars for `SYNTHETIC:LAB_QA_ONLY`, 2019-01-01 to 2020-11-30). `scratch/` is gitignored, so
   check the script exists on the presentation laptop. In the Streamlit tab, open the sidebar
   **Advanced · workspace and execution settings**. Set **SQLite database path** to
   `scratch/SYNTHETIC_strategy_browser_qa.sqlite` and **Company universe** to
   **Synthetic demo / local imports**. Click **Open workspace**, choose **Charts, backtests and Monte Carlo**,
   and leave the tab open.
3. Click **Try synthetic demo** once, as a warm-up. It is idempotent: identical requests reuse the saved
   runs (`pipeline.py`, `lookup_request`). In rehearsal, also run the step-6 policy analyses once, so the
   comparison table is already populated if anything fails on stage.
4. **Capture the static fallback pack** in rehearsal and save it to `docs/presentation/fallback/`:
   a screenshot of each step's end state, plus the downloads named in each step (`case-<run>.json`,
   `research-comparisons.json`, `backtest.json`). Name the files by step number.
5. Close other tabs, mute notifications, and confirm that `http://127.0.0.1:3000/api/research/health` returns `{"status":"ok",…}`.

**Global fallback ladder (any step):**
1. Next.js error banner "Python API is unavailable…": stop and rerun `npm.cmd run dev` (about 20 s). Meanwhile, narrate from the slide.
2. The Next.js app is still broken: switch to the Streamlit tab on :8501, which runs the same engine. Open
   the main page, click **Load synthetic demo (replay)**, then follow the same story with the Streamlit task names given per step.
3. No browser at all: CLI in PowerShell (verified 2026-11-21 against a scratch database):
   ```powershell
   $db = "data/cli_demo.sqlite"
   .\.venv\Scripts\python.exe -m market_events --database $db demo
   .\.venv\Scripts\python.exe -m market_events --database $db analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_filter --mode replay
   .\.venv\Scripts\python.exe -m market_events --database $db list-runs
   .\.venv\Scripts\python.exe -m market_events --database $db experiments --output runs/experiments.json
   .\.venv\Scripts\python.exe -m market_events --database $db export --output runs/export.json
   ```
4. No laptop: show the static fallback pack from step 4 above.

---

## Step 1: Open and load the synthetic demo (0:00–0:45)

**Click:**
1. Browser at `http://127.0.0.1:3000` (Overview).
2. **Try synthetic demo** (top right of the "Research with evidence." heading).

**Expect:** the notice "Synthetic replay demo loaded. These fixtures do not validate real-market
performance." The header workspace selector shows **Synthetic demo**, and the URL contains
`workspace=demo&universe=demo`.

**Say:** "Opening the page wrote nothing. Loading the demo is an explicit action. It imports 35 synthetic
articles and 128 synthetic event-price bars (plus a separately labelled synthetic lab series, if this
build includes it), then analyses one article per event family under the
`slm_delegate` policy, using recorded model outputs. This all runs offline."

**Fallback:** if the button spins for more than 10 s, choose **Synthetic demo** in the header workspace
selector, which reads the demo database saved in rehearsal. Otherwise use Streamlit's **Load synthetic demo (replay)**.

## Step 2: Inspect the evidence base (0:45–1:30)

**Click:**
1. Top nav **Import** (sidebar: **Import evidence**).
2. Point at the summary band: **Article sources 35**, **Market observations 1,694** (128 synthetic event bars plus
   the 1,566-bar synthetic lab series). Click the tab **Market prices · CSV** to show the required headers, including `available_at`.
3. Top nav **Research** (sidebar: **Event research**). In **Search sources**, type `crude`.
4. Click the item that begins "EXPLICITLY SYNTHETIC FIXTURE. Berger Paints faces synthetic input cost pressure…" (`2026-01-12 · syn-002`).

**Expect:** the right panel shows **Published 2026-01-12T08:00:00Z**, **First seen 2026-01-12T08:05:00Z**, and the full source text.

**Say:** "Each article carries two times: when it was published, and when *this dataset* first had it.
Prices also carry two: the session time and when the bar became available. Evidence counts only if both
times are before the decision cutoff." Do not import anything on stage.

**Fallback:** Streamlit **Import local evidence**, then **Analyse an article**. Or the step-2 screenshot.

## Step 3: Analyse the crude-oil → paint-maker case (1:30–2:45)

**Click:** (still in **Inspect & analyse**)
1. Leave **Decision cutoff** at `2026-01-12T12:00:00Z` (prefilled for the demo; 17:30 IST).
2. Leave **Research method** at **Small model with delegated extraction**, and **Analysis mode** at **Demo replay (demo articles only)**.
3. Click **Analyse and save run**.

**Expect** (instant; the identical demo request is reused):
- Heading **commodity supply disruption**, status **completed**, "Recorded replay · slm delegate"
- **Evidence label: neutral**, **Signed evidence score: 0.04**, **Evidence coverage: 100.00%**
- Warning box: **"Equity and exposure-adjusted commodity evidence disagree"**
- If the build shows the plain-language fields (`score_formula`, `plain_summary` from `plain_language.py`): "0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral (threshold ±0.15)". You can read this aloud instead of doing the arithmetic yourself.
- **Supporting source passages**: verbatim sentences from the article

**Say:** "The model's only job was to say *what happened*: a crude-oil supply disruption affecting Berger
Paints, quoting the exact sentences. Everything after that is Python. The stock's excess return over its
sector benchmark gives E = 0.008 / 0.02 = 0.40. Crude rose 1.5%, and our reviewed (synthetic) rule says
higher crude hurts paint makers, so C = −0.5. That gives 0.6 × 0.4 + 0.4 × −0.5 = 0.04. Within ±0.15 it is
neutral, and the disagreement is flagged rather than averaged away. This is not a probability."

**Cutoff beat (+30 s), same article, earlier time:** change **Decision cutoff** to
`2026-01-12T10:30:00Z` (16:00 IST) and click **Analyse and save run**. Expect status **abstained** with
**"Missing or stale mandatory commodity return"** (partial score 0.4 at 60.00% coverage, withheld).
**Say:** "At 16:00 IST the equity close is in, but crude doesn't settle until 11:00 UTC, so the crude bar
isn't available yet. The system refuses to answer rather than guess." Then restore
`2026-01-12T12:00:00Z`. (A 07:00 UTC cutoff, before publication, gives **ineligible** instead.) Both
attempts are saved as separate runs, which is intended.

**Fallback:** Streamlit **Analyse an article**, then **Analyse and save run**, then **Open saved result**.
Or CLI: `analyse syn-002 --decision-time "2026-01-12T12:00:00Z" --policy slm_delegate --mode replay`.

## Step 4: Open the saved result and audit trail (2:45–3:45)

**Click:**
1. Top nav **Results** (sidebar: **Saved results**).
2. In **Saved run**, choose `syn-002 · completed · slm delegate · …`. It is usually first, because the list shows newest first.
3. Click **Open saved evidence**.
4. Scroll to **Model call audit**. Then expand **Original article** and **Inspect saved extraction, numerical evidence and call trace**.

**Expect:** the same label, score and coverage. The audit table has two rows: **filter** with `recorded-slm`
and **extraction** with `recorded-llm`, both mode `replay`, status `success`, tokens `— / —`.

**Say:** "Saved runs are immutable. The database itself rejects updates. Every model call is traced with
model, prompt hash, request hash, status and latency. Tokens show a dash because replay has no real token
usage, and we never fill in zeros." Optionally click **Download full case**.

**Optional contrasts (same cutoff, from the inbox):** `syn-001` gives **positive, 0.4**. `syn-005` (an unconfirmed
SpiceJet report) gives **abstained**, "Unsupported event family". `syn-004` (an arts sponsorship) gives
**irrelevant** after one filter call.

**Do not click** **Request model explanation** in replay. No explanation is recorded, so it would fail
visibly and save an `explanation_failed` child run. If asked, explain that it is a separate child trace that cannot change the parent.

**Fallback:** Streamlit **Review saved results**. Or the `case-<run>.json` from the fallback pack.

## Step 5: Later outcomes, kept separate (3:45–4:30)

**Click:**
1. Top nav **Compare** (sidebar: **Comparisons**). Click **Evaluate later outcomes**.
2. Top nav **Results**. Reopen the `syn-002` case (**Open saved evidence**) and expand **Original price evidence and later outcome**.

**Expect** (synthetic): `"status": "completed"`, entry at `2026-01-13T03:45:00Z` (09:15 IST, the next
session's open), exit on 2026-01-19 (the 5th observed session's close), `gross_return ≈ 0.0458`,
`net_return ≈ 0.0448` (10 bps round trip), `benchmark_return ≈ 0.0090`.

**Say:** "The outcome is a market-adjusted return, with beta implicitly 1, from the next open to the
fifth close after the cutoff. It measures *post-cutoff drift*. The score only used the reaction that was
already visible at the cutoff, so it is not circular. It sits in its own table and never rewrites the
decision. Honest note: all three demo cases show the same +4.58%, because the synthetic prices are
constant growth paths. This shows the mechanics, not the market."

**Fallback:** CLI `outcomes`, then `export`, and show the `outcome` block. Or Streamlit **Compare research runs**.

## Step 6: Compare execution policies (4:30–5:30)

**Click:**
1. Top nav **Research**. Search `crude`, then select `syn-002` again.
2. **Research method** → **Small-model filter + large-model extraction**. Click **Analyse and save run**.
3. **Research method** → **Large-model extraction only**. Click **Analyse and save run**.
4. Top nav **Compare**. Click **Load saved comparisons**.
5. Optional: expand **Inspect matched cohorts, run manifest, ablations and later outcomes** and find the `syn-002` ablation rows.

**Expect:** both new runs show **neutral, 0.04**, the same as `slm_delegate`. The **Policy usage**
table has rows for `replay / llm only`, `replay / slm delegate` and `replay / slm filter`. Each new run makes
2 calls, and tokens are `— / —`. The ablation rows show **equity only → positive, 0.4** versus
**equity + commodity → neutral, 0.04**. If the build shows the **extraction agreement** table, it is
labelled "Synthetic sanity check on authored articles, not a benchmark". In replay, filter recall is
1.0, and precision drops below 1 once `syn-005` has been analysed, because the gold labels mark the
unconfirmed SpiceJet items irrelevant. **Estimated cost** stays empty in replay.

**Say (frame it honestly):** "This table is *not* a policy comparison. Replay returns the same recorded
answer whichever model role is selected, and it has no token counts, so every policy looks identical by
construction. What it shows is the audit plumbing: runs, calls and failures are counted per policy and
per mode, and missing tokens stay missing instead of becoming zero. The only real comparison we have is
the archived live run on the same synthetic articles: 8 calls for LLM-only against 9 for each
small-model policy, so there was no saving. That is a negative result. The agreement table is a sanity
check against labels I wrote myself, with one annotator, not a benchmark. The useful row here is the
ablation: the commodity channel turns a positive equity signal neutral on identical frozen evidence."

**Fallback:** the policy rows saved in rehearsal (step 4 of "Before the session") already appear after
**Load saved comparisons**. Or use `research-comparisons.json` from the pack, or CLI `experiments`.

## Step 7: Strategy lab, a random-walk sanity check (5:30–7:15)

**Frame it before any number appears.** The lab series `SYNTHETIC:LAB_DEMO` is an **authored, seeded,
zero-drift random walk**: 1,566 sessions, 2015-01-01 to 2020-12-31 (`configs/synthetic_lab.json`,
`tests/fixtures/synthetic_lab_history.csv`). It has no edge by construction. The beat checks that the
engine reports *no edge*, that costs make things worse, and that a fixed configuration is not tuned.
It never enters event evidence. **Do not** import `scratch/SYNTHETIC_UI_QA_2020.csv`: it labels synthetic
prices as `NSE:ASIANPAINT`, which would show as "Asian Paints" with no synthetic banner.

**Say first:** "This series is a random walk I generated. A sound engine should find no edge here. If it
found one, that would be a bug. The configuration was fixed before this presentation, and I won't tune it
on stage."

**Click (Next.js; labels as of 2026-11-21, re-check at rehearsal because demo-ui is still polishing):**
1. Top nav **Strategies**. **Instrument** → **Synthetic lab series (QA only) · 1566 pre-2021 bars**. Point
   at **"SYNTHETIC QA HISTORY · Interface verification only; not performance evidence."**
2. Keep **Study start** 2015-01-01 and **Study end** 2020-12-31. Click **Load local history**.
3. **Pre-committed configuration:** **SMA crossover**, fast 20, slow 50, capital 100000, **Fee per fill (bps)** 10,
   **Slippage per fill (bps)** 5. Click **Run backtest**.
4. **Cost stress:** change only fee to **20** and slippage to **10**. Click **Run backtest**. Then restore 10 / 5.
5. **Walk-forward:** with the same configuration, set the walk-forward split to **2020-01-01** and run it.
   In-sample is 2015–2019 and out-of-sample is 2020; each is an independent backtest.
6. Optional, if time allows: **Simulate return paths** (300 paths, horizon 252, seed 42, block size 5).

**Expect** (computed 2026-11-21 through `POST /api/backtest` and `/api/monte-carlo` on a fresh demo
workspace; they match demo-backend's figures. Synthetic random walk, so this is not a strategy result):

| Run | Strategy return | Buy & hold | Max drawdown | Sharpe | PSR | Closed trades | Win rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full 2015–2020, 10 / 5 bps | −52.5% | +33.8% | −55.7% | −0.79 | 0.025 | 20 | 15% |
| Full 2015–2020, 20 / 10 bps | −55.3% | +33.6% | −58.1% | −0.85 | 0.016 | 20 | 15% |
| Walk-forward in-sample 2015–2019 (10 / 5) | −41.4% | +24.7% | −49.3% | −0.69 | 0.058 | 15 | 7% |
| Walk-forward out-of-sample 2020 (10 / 5) | −17.5% | +9.0% | −19.2% | −1.23 | 0.098 | 4 | 25% |

Fees plus slippage over the full window: about 4,388 at 10 / 5 bps and 8,549 at 20 / 10 bps (initial
capital 100,000). Monte Carlo (10 / 5, seed 42): median terminal ≈ 89,000, p05 ≈ 72,000, p95 ≈ 110,000,
resampled loss frequency 0.8.

**Say:** "No edge, as expected: the rule loses to buy-and-hold, and the probabilistic Sharpe ratio is about
2%, meaning roughly a 2% chance the true Sharpe is above zero. That figure is for one configuration and is not
deflated for trials. Doubling costs makes it worse, from −52% to −55%. The walk-forward split shows the same
story in both halves, so there is no hidden period where it 'works'. With only 20 trades, below the 30-trade
low-sample threshold, none of these numbers would be trustworthy even on real data. Fills happen at the next
open after a close signal. The Monte Carlo loss frequency is a resampling statistic, not a probability of
future loss."

**Fallback A (Streamlit):** the tab prepared before the session (`SYNTHETIC:LAB_QA_ONLY`, a different synthetic
series) shows the same mechanics with **Run backtest**, the 1× → 2× cost change, and **Simulate return paths**.
Don't quote the table above for it.
**Fallback B:** `backtest.json` and the screenshots in the pack. If time is short, do only the framing,
the 10 / 5 run and the 2× rerun.

## Step 8: Close (7:15–7:30)

**Say:** "To recap: the model said what happened, Python decided what the evidence shows using only
what was available at 17:30 IST, the outcome was measured separately afterwards, and every step is saved
and replayable. Happy to take questions."

---

## Timing summary

| Step | Window | Can cut? |
| --- | --- | --- |
| 1 Load demo | 0:00–0:45 | no |
| 2 Evidence base | 0:45–1:30 | shorten to the inbox only |
| 3 Analyse `syn-002` | 1:30–2:45 | skip the optional cutoff proof |
| 4 Saved result and audit | 2:45–3:45 | no |
| 5 Outcomes | 3:45–4:30 | yes, narrate from slide 12 |
| 6 Policies | 4:30–5:30 | use only the pre-saved comparison |
| 7 Strategy lab: random-walk sanity check, cost stress, walk-forward | 5:30–7:15 | drop walk-forward and Monte Carlo |
| 8 Close | 7:15–7:30 | no |
