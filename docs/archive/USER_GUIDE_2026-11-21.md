# User guide

Detailed operating notes for **Market Events**, the implementation of *A Heterogeneous Multi-Agent
Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets*.
This is the full former README, moved here on 2026-11-21 so the [project README](../../README.md) can stay
short. Nothing was removed. Relative commands assume the repository root as the working directory.

## Next.js / React website

Use the sun/moon button in the header to switch between light and dark mode. The first visit follows the system preference; an explicit choice is saved on the device. Both modes cover the overview, research forms, evidence tables, and charts. The overview includes a three-step research guide with locally bundled React Bits SpotlightCard interactions and a static Aurora accent: add evidence, investigate an event, and inspect saved results. Empty inboxes link directly to importing an article, and successful imports link to the next research step. The manual article form opens automatically for an empty source inbox.

The web frontend lives in `web/` and uses the Python engine through a local FastAPI service. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[web,dev]"
npm.cmd --prefix web install
npm.cmd run dev
```

Open [the Next.js website](http://127.0.0.1:3000). The development command starts Next.js on port 3000 and the Python API on port 8000, both on loopback. Provider/model credentials stay in the Python environment. The frontend proxies only supported research endpoints through its own origin. Page reads do not initialize a workspace database; imports, demo loading, model analysis and provider refreshes remain explicit actions.

The website uses a premium charcoal dashboard with horizontal navigation, compact workspace summaries, a saved-price area chart, an evidence-coverage ring and a searchable watchlist. The design combines the supplied Zajno crypto dashboard reference with the health dashboard's restrained hierarchy. **Load local chart** computes only from saved observations; it never contacts a provider or model. React Bits components remain bundled locally for supporting views, with their upstream license and motion controls. See the [website verification record](../WEBSITE_VERIFICATION.md) for the latest checks.

`npm.cmd run check` runs TypeScript and ESLint; `npm.cmd run build` produces the frontend production build. The original Streamlit app remains available using the command in **Start locally** below. This local conversion does not add hosted authentication, multi-user authorization or brokerage execution; those are separate [product milestones](../PRODUCT_ROADMAP.md).

## Trading research extension

Open a workspace, then choose **Charts, backtests and Monte Carlo** in the sidebar. This strategy lab adds TradingView's hosted chart (opt-in), Lightweight Charts for imported OHLC, common indicator choices, price-rule backtests and animated historical-return bootstrap scenarios. The study window ends on **31 December 2020**, as requested; its default start is 1 January 2015. The bundled 2026 demo is not suitable history for this window and is never silently substituted.

Import your own validated historical market CSV through **Import local evidence**, or select the live universe and explicitly download historical daily candles in the lab. Upstox downloads require a local provider token; none was configured when this extension was implemented. Historical availability stays at the real fetch time, so these are retrospective experiments rather than claims of point-in-time knowledge in 2020. TradingView's hosted widget has its own data and does not enforce the local historical cutoff or supply backtest data.

Backtests use long/cash rules, next-observed-session-open fills, per-fill fees and adverse slippage. Final positions remain marked to market. Monte Carlo resamples strategy returns with a seed and moving blocks; its scenario frequencies are not calibrated future-market probabilities. Read each result's assumptions before interpreting it.

The work is coordinated in separate Herdr Data, Quant and UI & Docs tabs. See the [agent workflow](../AGENT_WORKFLOW.md), [extension contract](../TRADING_EXTENSION_CONTRACT.md), and [product roadmap and Next.js architecture](../PRODUCT_ROADMAP.md). A normal Next.js/React website can provide these interfaces while keeping the Python research engine behind an API.

A local Streamlit research prototype for dated financial articles, reviewed commodity exposure assumptions, deterministic evidence fusion and separate later outcomes. The five-stock demonstration universe and all bundled article/market/model fixtures are **synthetic**. Replay demonstrates software behaviour; it does not establish model quality, investability or predictive performance.

## Start locally

Tested on **Python 3.10.21 on Windows**. Python 3.10+ is declared in `pyproject.toml`; the checked-in `requirements.lock` captures the tested Windows environment, including development tools. Other Python/platform combinations have not been verified.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Use Python 3.10.21 for the `python` command above to reproduce the tested environment. Open [the local dashboard](http://127.0.0.1:8501) after starting Streamlit.

The lock was generated from the installed environment using:

```powershell
uv --cache-dir .cache/uv pip freeze --python .venv/Scripts/python.exe --exclude-editable | Set-Content -Encoding utf8 requirements.lock
```

Regenerate it after deliberate dependency changes and verification; ordinary setup installs the existing lock first, then installs this project editable with `--no-deps`. `pyproject.toml` remains the dependency declaration; the lock is its tested environment snapshot.

Opening the page performs no database or demo writes. Use **Load synthetic demo (replay)** in the main-area quick start to explore without keys; it opens a saved result summary and explicitly selects the demo universe. The demo always runs offline recorded replay. To inspect your own workspace, choose **Open workspace**; local paths and model/universe settings are under **Advanced · workspace and execution settings**. Changing the root or database requires opening that workspace explicitly.

1. Choose **Import local evidence** for article JSONL, market CSV or manual entry. Inspect row errors and warnings. Provider/live article IDs start with `LIVE:`; demo/local identifiers remain separate.
2. Choose **Analyse an article**, filter the inbox and select a readable source excerpt. Set an offset-aware cutoff; `2026-01-12T17:30:00+05:30` is the labelled synthetic fixture cutoff. Model policy and default-off **Explicit repeat experiment** are in an advanced expander.
3. Submit **Analyse and save run**, then choose **Open saved result**. Identical completed requests reuse the durable pipeline result. Explicit repeats create separate linked runs. Replay supports fixture articles only; unsupported articles remain visible failures.
4. **Review saved results** starts with the evidence label, signed score and percentage coverage, followed by reasons/conflicts. Source, price evidence, audit and later outcomes remain available in tabs; raw JSON, mappings and configuration are in labelled expanders. Saved technical snapshots are shown when available. Optional model explanations require a separate explicit action and create linked child traces; older records may lack retained text. Case downloads retain original evidence and missing references.
5. **Explore price indicators** works from imported equity history without articles, provider keys or model credentials. Select a company and submit a current offset-aware cutoff to compute a supporting price chart and RSI, SMA, EMA, MACD, Bollinger bands, ATR and ADX. Warm-ups need 15–50 eligible daily bars; conflicting/inconsistent history and stale data remain explicit. The demo's seven bars at its decision cutoff cannot supply these histories. Indicators do not change event fusion scores.
6. **Connect and refresh data** separates offline configuration checks from explicit provider refreshes and a separate optional bounded news-model batch. Token presence never means a verified connection. See the [real-data setup guide](../LIVE_SETUP.md) for the read-only token, local environment configuration, restart requirements, permissions and integration status. The adapter and pipeline are integrated and verified with mocked HTTP responses; an actual account connection still needs your configured token and an explicit refresh.
7. **Compare research runs** evaluates later outcomes only on its explicit action and shows policy summaries/common-input cohorts plus commodity sensitivity. Explanation usage remains separate. Comparison exports include run provenance. Viewing or exporting does not mutate saved decisions.

`live` means actual configured model inference on imported evidence. It does not fetch live quotes or establish real-data validation. Model configuration is owned by `config.py`; use local `.env`/environment settings such as `SLM_MODEL`, `LLM_MODEL`, `SLM_BASE_URL`, `LLM_BASE_URL` and provider API keys. Keep credentials out of exports and source control. Failures remain visible; live inference does not silently fall back to replay.

## Command line

Global options precede the command. Replace `ARTICLE_ID` with an imported article's ID and choose a cutoff consistent with its source/market availability.

```powershell
.\.venv\Scripts\python.exe -m market_events --database data/demo.sqlite demo
.\.venv\Scripts\python.exe -m market_events import-articles data/articles.jsonl
.\.venv\Scripts\python.exe -m market_events import-market data/market_prices.csv
.\.venv\Scripts\python.exe -m market_events analyse ARTICLE_ID --decision-time "2026-01-12T17:30:00+05:30" --policy slm_delegate --mode replay
.\.venv\Scripts\python.exe -m market_events outcomes
.\.venv\Scripts\python.exe -m market_events export --output runs/export.json
.\.venv\Scripts\python.exe -m market_events experiments --output runs/experiments.json
.\.venv\Scripts\python.exe -m pytest -q
```

CLI export also writes a separate `.usage.json` and a directory of Markdown case reports. Add `--run-id RUN_ID` to export one case. Selected market observations are included; unavailable references stay explicit. The comparison export is descriptive and includes a run manifest; use the full case/bundle export to retain original source, frozen configuration and numerical evidence.

## Interpretation and limits

The evidence score is a deterministic signed score, not a probability or recommendation. Missing mandatory evidence causes abstention even when a partial score exists. Returns are fractions, volume context is a ratio, and article narrative direction never replaces numerical evidence. Outcomes use next-session open to fifth-session close, with separate gross/net/benchmark returns; pending is not failure or zero.

Policy aggregates are descriptive and may contain unmatched articles, different configurations or repeated runs. Replay token/timing records cannot demonstrate live savings. Existing `runs/local_model_pilot.json` records local `qwen3.5:2b` filtering and `gemma4:e4b` extraction: 30 filter requests had zero failures, all 24 expected items were forwarded, and three of three tested Gemma extractions were grounded after the typed-amount schema fix. The older `local_smoke.json` retains only one validated extraction of three; the later pilot does not erase those failures. These are synthetic development records, not held-out quality, predictive performance or real-market validation. This continuation made no provider calls. Real data permissions, corporate actions, mapping review and prospective evaluation remain necessary research work.

UI behaviour was checked with Streamlit AppTest, included in `pytest -q`. Browser screenshots, rendered browser appearance, mobile layout and screen-reader behaviour were **not checked** because no browser was available to the browser tool.

Final **offline integration checkpoint** on 2026-10-24: **270 tests passed in 18.53s**, repository Ruff check passed and format-check found 40 files formatted. The UI worker separately ran **12 AppTest workflow tests**. Actual adapter parsing/storage/pipeline integration was exercised with HTTP transports mocked; a separate UI smoke used the real adapter metadata with zero network or analysis writes. Real-account connectivity and rendered browser/mobile/screen-reader behaviour remain unverified. The 197-test and 242-test checkpoints are historical. See [verification details](../IMPLEMENTATION_LOG.md).

See [code map](../CODEBASE_GUIDE.md), [data definitions](../DATA_DICTIONARY.md), [model notes](../MODEL_AND_PROMPT_NOTES.md), [experiments](../EXPERIMENTS.md), [decisions](../DECISIONS.md), [implementation record](../IMPLEMENTATION_LOG.md) and [demo script](../DEMO_AND_VIVA.md). The shared [build contract](../BUILD_CONTRACT.md) controls interfaces when guide examples differ.
