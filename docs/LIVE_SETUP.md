# Connect real Indian market data and technical indicators

This guide covers the read-only real-data extension of Market Events. Technical indicators run locally on imported or synced daily OHLCV history. Article extraction uses the separately configured language models. Credentials belong in your local `.env`; do not paste them into the dashboard, chat, screenshots or research exports.

**Integration status:** local indicators, typed snapshots, universe-aware pipeline, readiness checks, CLI entry points and the Upstox adapter are implemented and verified offline. The final combined suite passed **270 tests in 18.53 seconds**; full Ruff checks passed and all **40 Python files** passed the format check. Actual-adapter integration exercises HTTP parsing, mappings, storage, technical calculations, explicit news analysis, refresh identity and CLI missing-token handling with mocked transport. No real account connectivity has been verified.

## 1. Free provider choice

For this NSE-focused prototype, the selected provider is **Upstox**. Its current [Analytics Token documentation](https://upstox.com/developer/api-documentation/analytics-token/) describes a free, read-only token with one-year validity, generated directly in Developer Apps. Historical-data and news GET APIs are covered without a static IP requirement. This token cannot place or modify orders. The provider documentation was checked on 24 October 2026.

This keeps the initial setup to one provider credential for both prices and news. The app does not require a separate paid technical-indicator API: RSI and the other indicators are calculated from the downloaded bars. Local Ollama models can supply the existing filter/extraction roles without a cloud model API key.

Provider account access, permissions, actual response coverage and token validity are checked by an explicit fetch. A configured token is not proof of connectivity. No real provider account success is implied by offline tests.

Other free news tiers have constraints: [GNews](https://gnews.io/faq) currently describes a free non-commercial tier with 100 requests/day, 10 articles/request and a 12-hour delay; [NewsAPI](https://newsapi.org/pricing) describes a development tier with 100 requests/day and a 24-hour delay. These are comparison information, not additional adapters implemented here.

## 2. Configure your local environment

1. Open [Upstox Developer Apps](https://account.upstox.com/developer/apps).
2. Follow the official [Analytics Token generation steps](https://upstox.com/developer/api-documentation/analytics-token/#generate-an-analytics-token).
3. Add the token to the project's existing `.env`. If no `.env` exists, copy `.env.example` first. Preserve any existing model configuration.

```dotenv
# Keep synthetic replay available; choose Live data explicitly in the dashboard.
MARKET_EVENTS_UNIVERSE=demo
MARKET_EVENTS_MODE=replay
MARKET_EVENTS_DATABASE=data/market_events.sqlite

# Paste your own read-only token locally, never into source control.
UPSTOX_ANALYTICS_TOKEN=replace_with_your_token

# Optional for article event analysis. Use model names installed on your machine.
SLM_PROVIDER=ollama
SLM_BASE_URL=http://localhost:11434
SLM_MODEL=your_installed_small_model
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=your_installed_extraction_model
```

The token loader prefers `UPSTOX_ANALYTICS_TOKEN`; `UPSTOX_ACCESS_TOKEN` is a lower-priority alias. Keep only the credential you intend to use. The existing model adapters also support an OpenAI-compatible endpoint through their own provider/base-URL/model/API-key settings.

**Restart Streamlit after editing `.env`.** The settings loader uses `load_dotenv(override=False)`, so already loaded process-environment values deliberately take precedence. Saving a replacement token to the file alone may not refresh the running process. Shell-provided environment values also take precedence over `.env`.

## 3. Start the app

Use the environment setup in the [README](../README.md), then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501` and open a workspace. Keep the server local while using a personal token.

The workflow separates three actions:

| Action | Network/model behaviour |
| --- | --- |
| Inspect connection readiness | Reads configuration and imported coverage; performs no connection test |
| Sync live prices/news | Makes explicit read-only provider requests and saves accepted inputs |
| Analyse selected synced news | Explicitly invokes configured live models and saves event analyses |

Opening a page, reading the universe metadata or changing filters does not trigger a provider fetch or model inference.

## 4. First real-data run

1. Select the **live** data universe. Model mode is separate; technical analysis does not require live model mode.
2. Open the connection/data-sync view. Check that the provider credential is configured. This is a presence check, not a successful login claim.
3. Choose a live company. Start with one company to keep the first fetch easy to inspect.
4. Explicitly sync daily history. The default request is 550 calendar days, normally enough for the current 50-bar maximum minimum warm-up if the provider supplies sufficient sessions. The adapter also requests the configured benchmark. News is optional.
5. Inspect added-record counts, requested instruments, provider-resolved keys, warnings and errors. Empty/partial/failed responses remain visible.
6. Open technical analysis, select the same live company and submit a current offset-aware cutoff. Review history coverage, missing/stale status, values and interpretations.
7. To analyse articles, configure both model roles, select live model mode, and use the separate synced-news analysis action. The backend batch defaults to ten unique requested articles, with explicit skipped results beyond its configured limit.
8. Inspect saved runs and export the source evidence, technical snapshot and model traces. Later outcome evaluation remains separate.

The user-facing labels may be more descriptive than the internal function names below. All fetching and model actions require explicit submission.

## 5. Indicators and required daily history

| Indicator | Snapshot keys | Minimum eligible bars | Convention |
| --- | --- | --- | --- |
| RSI 14 | `rsi14` | 15 | Wilder smoothing of 14 close changes; flat=50, gains-only=100, losses-only=0 |
| SMA 20 / 50 | `sma20`, `sma50` | 20 / 50 | Arithmetic mean of recent closes |
| EMA 20 | `ema20` | 20 | SMA seed, alpha 2/21 |
| MACD 12/26 | `macd_line` | 26 | Independently SMA-seeded EMA12 minus EMA26 |
| MACD signal / histogram | `macd_signal`, `macd_histogram` | 34 | Nine-value SMA-seeded signal EMA; histogram=line-signal |
| Bollinger 20 | `bollinger20_middle`, `bollinger20_upper`, `bollinger20_lower` | 20 | SMA20 plus/minus two population standard deviations |
| ATR 14 | `atr14` | 15 | True range using previous close, Wilder smoothing |
| ADX 14 | `adx14` | 28 | Wilder directional movement; seed mean of first 14 valid DX values |

Price-valued indicators use the price series' units. RSI/ADX are 0–100 measures. Minimum warm-ups establish that a value can be computed under the documented seeds; they do not guarantee convergence to another chart service's values with a different hidden history.

All calculations are pure local Python. They use only bars with both observation timestamp and availability at/before the cutoff. Missing values stay null. Exact duplicates collapse; conflicting sessions or inconsistent currency/unit/contract invalidate the eligible series. Values more than four calendar days old remain auditable but are marked stale and their interpretations are withheld.

Indicators are saved on `AnalysisRun.technicals`. Unresolved company extractions retain an inspectable abstention and no technical snapshot. Indicators add technical context; they do not alter the existing event-fusion weights or become trade instructions.

## 6. Keep real and synthetic evidence separate

Synthetic replay companies use the existing demonstration IDs, such as `NSE:ASIANPAINT`. Real-data series use a separate namespace, such as `LIVE:NSE:ASIANPAINT`; the live benchmark is `LIVE:NSE:NIFTY50`. Live news article IDs also start with `LIVE:`.

The selected universe controls company mappings and eligible input collections. The analysis pipeline rejects an article from the opposite universe. When manually importing live articles, use a unique `LIVE:` article ID; live market imports likewise require the live instrument IDs. The same database can hold both namespaces without substituting one for the other.

The adapter uses the local [live universe configuration](../configs/live_universe.json) to select the pilot instruments. Provider keys are discovered against the current instrument master during an explicit sync rather than guessed from names or copied from synthetic IDs. The company selector excludes benchmark records.

Synthetic commodity exposure assumptions are not copied into the live universe. Optional reviewed real exposure rules belong in `configs/live_exposure_rules.json`; the default live rule collection is empty. Missing commodity/exposure evidence therefore causes the existing honest abstention. The live benchmark supplies broad-market context rather than the synthetic demonstration's conceptual sector benchmarks.

## 7. Availability, refreshes and reproducibility

Upstox daily candle timestamps identify the start of the candle. The adapter converts completed NSE daily sessions to their 15:30 `Asia/Kolkata` close. It conservatively skips the current local day and any future/incomplete date.

Historical bars downloaded now become available to this collected dataset at their actual first fetch. News `first_seen_at` likewise reflects collection, not an invented historical observation time. Consequently, a cutoff before the first download cannot consume that newly downloaded history even if its session dates are older. Use a cutoff at/after the completed sync to inspect current history; do not backdate availability to make a historical experiment pass.

Identical refreshes preserve stored availability and source identity. Changed rows under an immutable observation identity are reported as revisions/conflicts rather than overwriting saved evidence. Provider news is analysed only from the supplied headline/summary; the adapter does not invent a full article or scrape linked pages.

The sync report contains counts, coverage/metadata, warnings, structured errors, request count, imported article IDs and a cutoff for the separate batch action. API credentials are omitted from saved settings, readiness responses and exports. Run snapshots retain the selected company/rule configuration, prompt versions and eligible input hashes.

## 8. CLI workflow

These commands perform the same explicit actions as the dashboard:

```powershell
# Offline setup status: token presence/coverage only, no remote health check.
.\.venv\Scripts\python.exe -m market_events --universe live readiness

# Explicit provider request; omit --no-news to request company news too.
.\.venv\Scripts\python.exe -m market_events --database data/live.sqlite sync-live --companies LIVE:NSE:ASIANPAINT --lookback-days 550 --no-news

# Local computation on that same database, with current UTC cutoff by default.
.\.venv\Scripts\python.exe -m market_events --database data/live.sqlite --universe live technicals LIVE:NSE:ASIANPAINT

# Explicit provider request including news. Review article_ids/decision_time in its output.
.\.venv\Scripts\python.exe -m market_events --database data/live.sqlite sync-live --companies LIVE:NSE:ASIANPAINT
```

To analyse synced news, substitute an actual returned article ID and the returned offset-aware decision time:

```powershell
.\.venv\Scripts\python.exe -m market_events --database data/live.sqlite analyse-news --article-ids LIVE:NEWS:ACTUAL_RETURNED_ID --decision-time "ACTUAL_RETURNED_ISO_CUTOFF" --policy slm_delegate --limit 10
```

`analyse-news` explicitly selects live universe and live model execution. It never falls back to replay. An individual manual/imported live article can also use the existing `analyse` command with global `--universe live` and subcommand `--mode live`.

Global `--root`, `--database` and `--universe` options precede the subcommand. `sync-live` explicitly selects the live universe but does not invoke a model. Demo loading forces the demo universe even when your local environment defaults to live.

## 9. Common setup problems

| Symptom | What to check |
| --- | --- |
| Token absent | Add it to the project's `.env`, check shell overrides, then restart Streamlit |
| HTTP 401 | Check token validity/expiry and refresh the credential locally |
| HTTP 403 | Check account/API permissions and access to the requested data |
| HTTP 429 | Respect provider rate limits; reduce the selected universe/news pages and retry later |
| No new observations | It may be an identical refresh, no completed sessions, or an empty provider result; inspect the report |
| Instrument unresolved | Inspect current provider master metadata; the adapter does not guess an ISIN/key |
| Indicators missing | Check selected universe, cutoff, eligible bar count and required warm-up |
| All history unavailable at old cutoff | Newly fetched history was not yet available then; choose an honest later cutoff |
| Stale technicals | Sync newer completed sessions or investigate provider coverage; no forward fill is applied |
| Revision conflict | Review the changed source data; saved immutable bars are not overwritten |
| News analysis fails | Inspect model IDs, model server, budgets and call traces; sync alone does not configure a model |
| Commodity case abstains | Supply reviewed real exposure and compatible commodity observations; synthetic assumptions are intentionally excluded |

## 10. Implementation and verification boundaries

- [Technical calculations](../src/market_events/technicals.py) define seeds, periods, warm-ups, stale handling and source references.
- [The live provider adapter](../src/market_events/live_data.py) exposes `get_live_universe(settings_or_root)` plus `sync_live(dependencies, company_ids, lookback_days=550, include_news=True, now=None)`.
- [Configuration](../src/market_events/config.py) excludes credentials and selects the universe.
- [Pipeline](../src/market_events/pipeline.py) saves technical context, enforces namespaces and exposes offline readiness/separate batch analysis.
- [Full workflow and feature guide](../PROTOTYPE_WORKFLOW_AND_FEATURES.md) explains the existing event pipeline and outcome interpretation.

Automated indicator tests use independently checkable numerical examples and boundary cases. Provider tests use mocked response payloads, including failures; passing them does not establish actual account connectivity. The final offline checkpoint on 24 October 2026 was **270 passed in 18.53 seconds**, with full Ruff and 40-file format checks passing. Replay demo, outcomes, exports, technicals and readiness CLI smoke checks passed. The actual-adapter metadata UI smoke exposed five equity choices with zero network requests or evidence writes; the local Streamlit service at `127.0.0.1:8501` returned healthy status. Rendered-browser, mobile and screen-reader behaviour remain unverified. Run the full suite with `.\.venv\Scripts\python.exe -m pytest -q`.

This is a local end-of-day research application. It is not an intraday streaming service, automatically calibrated prediction model, corporate-action adjustment service or brokerage execution system. Exchange-calendar completeness and held-out real-data research quality still require separate evaluation.
