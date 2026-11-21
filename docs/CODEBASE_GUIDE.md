# Codebase guide

Read `schemas.py` first, then `pipeline.py`. `app.py` presents forms and saved results and calls public workflows. It contains no SQL, return formula or fusion arithmetic. `experiments.py` groups saved resource traces and calls the same `fusion.assess_evidence` function twice on frozen inputs for sensitivity comparisons; it never calls a model or changes a saved run.

The separate historical strategy lab is reached through `app.py` → `lab_ui.render_strategy_lab`. `strategy_lab.py` owns retrospective history selection, causal indicator series, price-rule backtest accounting and seeded bootstrap scenarios. `chart_widgets.py` supplies sandboxed HTML chart/animation builders; `live_data.sync_historical` owns explicit historical downloads through 2020. These workflows do not change saved event-fusion decisions. See [the extension contract](TRADING_EXTENSION_CONTRACT.md) for APIs and [the product roadmap](PRODUCT_ROADMAP.md) for the proposed Next.js boundary.

| Boundary | Responsibility |
| --- | --- |
| `ingestion`, `storage`, `event_memory` | Row validation, durable records, cutoff-eligible history |
| `agents`, `model_client` | Structured relevance/extraction and bounded provider requests |
| `config`, `schemas` | Local configuration and explicit record contracts |
| `exposure`, `market_features`, `fusion` | Reviewed mappings, eligible observations, deterministic assessment |
| `outcomes` | Later five-trading-session measurements |
| `pipeline`, CLI | Explicit orchestration, persistence and public workflows |
| `app`, `experiments` | Local workbench, saved evidence display and descriptive comparisons |
| `exporting` | Read-only case payloads, referenced observation resolution, JSON/usage/Markdown exports |

Trace one synthetic commodity case: import article and bars → select noon UTC cutoff → classify prior dataset evidence → policy-controlled filter/extraction → resolve company and historically known exposure → compute eligible market features → deterministic fusion → immutable run and trace → separately evaluate future sessions → export. An irrelevant filter result, unresolved company or missing commodity evidence remains inspectable rather than becoming an invented successful assessment.

Read `docs/BUILD_CONTRACT.md` for exact function signatures. Do not copy financial rules into UI callbacks. Analysis runs only on form submission; the optional explanation has its own explicit button. Workspace opening is explicit because `Storage` initializes schema; simply displaying the page must not initialize it. Durable identical-request reuse belongs to pipeline/storage. A default-off repeat checkbox passes `repeat_run=True` only with analysis submission, creating linked repeated experiments through that same boundary.

The event inbox filters the latest saved company/type/status without inferring entities for unanalysed text. Watchlist rows select each configured company's latest imported session and show coverage/availability, currency and units; later outcome observations may be present, so the table is explicitly not cutoff-filtered evidence. Optional `explain_run` failure keeps the saved deterministic explanation and assessment visible.

The inbox uses the latest analysis, excluding optional explanation children, and filters article IDs to the active demo/local or `LIVE:` namespace. Saved-case observation tables resolve feature and technical snapshot references from immutable storage, report absent IDs and share their payload builder with the JSON download. CLI bundles include the union of referenced observations, missing IDs per run, separate usage and Markdown cases. None of these reads recompute market features or substitute newly imported sessions.

Explanation children remain visible in Saved runs with parent IDs, inherited-evidence labels and persisted generated text when present. Experiments separate their usage from analysis resources and export a run manifest plus mode/policy context for outcomes. Project root and database together identify the active workspace; changing either requires an explicit open action before storage is used.

The UI uses task labels: Start here, Analyse an article, Review saved results, Explore price indicators, Connect and refresh data, Compare research runs, and Import local evidence. Source snippets and display labels supplement stable IDs; backend enums/contracts are unchanged. Saved results present the assessment summary before source/audit tabs. Raw JSON, local paths, model policy and explicit repeats remain available through labelled expanders.

The independent Technicals view calls `technicals.compute_technicals` only after form submission, from local imported observations. It has no article or model dependency and charts only returned observation references. The Connections view calls the read-only `pipeline.readiness` and offline universe reader while rendering; provider sync and the bounded `pipeline.analyse_synced_news` batch each require separate explicit submits. Temporary technical/sync/batch state is scoped to root, database and selected universe. No credential is entered or echoed by the UI. The final 270-test checkpoint includes actual adapter parsing, storage and pipeline integration with HTTP transports mocked; the metadata/UI smoke makes no network requests. Real-account access remains unverified.
