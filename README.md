# Generative AI Financial Market Analysis — Findings and Roadmap

## Synopsis extraction

Read all four pages of **Project Synopsis Generative AI Stock Investment Platform.pdf**. The PDF contains selectable text, so OCR was unnecessary. The page-3 architecture diagram was inspected visually and transcribed separately.

- [Complete extracted synopsis, including diagram labels](synopsis-complete.md)
- [Original synopsis PDF](<Project Synopsis Generative AI Stock Investment Platform.pdf>)

The complete extraction preserves the cover details, abstract, overview, challenges, motivation, objectives, literature-review table, methodology, technology/evaluation plan, nine references and signature labels. Original reference claims are preserved in the extraction; corrections and verification limits are discussed below.

## Findings

**The strongest contribution is catalyst-to-confirmation fusion:** identify a financial event from news, verify its relationship to observable market behavior, and show an explainable signal with evidence. The research should measure whether that fusion improves on news-only and technical-only baselines.

**The proposed scope is ambitious for six months.** It combines SLM triage, LLM extraction, VLM chart interpretation, equities, derivatives, commodities, orchestration and five evaluation methods. A feasible implementation starts with a small daily equity universe, then integrates bounded experiments for the other tiers.

**Data availability is the first dependency to resolve.** Timestamped historical news, expired options, OI/IV and MCX contracts require actual coverage checks. Start prospective collection in month 1 so forward evaluation does not depend on finding historical data later.

**Evaluation quality matters more than adding agents.** Prevent future information from reaching features or chart images, compare the same periods and entry rules across baselines, include costs, and distinguish heuristic confidence from calibrated probabilities. Historical LLM memorization is a separate limitation.

**The bibliography needs repair.** The synopsis gives conflicting years and incorrect authors for the identifiable StockAgent paper. Other entries remain unverified; verify publisher records and DOIs before using them in the report. Supporting primary-source links are included in the roadmap.

**Completion should mean a reproducible research prototype, not a promised profitable trading system.** A well-explained negative ablation result is still useful evidence.

## Six-month implementation plan

Based on the four-page synopsis: **A Heterogenous LLM-VLM-SLM Approach to Multi-Agent Event Detection and Cross-Market Signal Fusion for Indian Financial Markets**.

Planning assumption: four students, each contributing approximately 8–12 focused hours per week, with basic Python knowledge. Adjust scope if actual availability is lower. Six months from 7 October 2026 is approximately 7 April 2027; confirm the college submission date and reserve the last two weeks for submission.

## What you are building

A research prototype that turns a timestamped news item into a structured event, maps it to an Indian instrument, checks market confirmation, and displays an explainable ranked signal with source evidence. The central research question is: **Does catalyst-to-confirmation fusion improve signal quality over news-only and technical-only baselines, and at what inference cost?**

An example workflow: company announces capacity expansion → detect expansion event and company → inspect price/volume response using only information available at the decision time → combine evidence → show bullish, bearish, or insufficient-evidence output with the source and timestamp. A positive headline alone must not automatically become a bullish recommendation.

Success means a reproducible system and defensible experiments. Profitability is an experimental outcome, not a completion requirement.

## Scope to freeze in week 1

| Component | Six-month target | Boundary |
|---|---|---|
| Equities | Fixed universe of 10 liquid NSE stocks across 2–3 sectors | Expand only after end-to-end evaluation works |
| Timing | End-of-day signals; one predefined 1–5 trading-day evaluation horizon | Avoid intraday execution complexity initially |
| Events | Earnings, capacity expansion/capex, order wins, regulatory action, supply disruption | Use an explicit taxonomy and an other/uncertain label |
| Language | One small triage model, one LLM event extractor | Benchmark existing models; training a foundation model is outside scope |
| Vision | One VLM evaluated on charts generated from your own OHLCV | Experimental tier; report whether it adds value |
| Quantitative | Returns, RSI, volume anomaly, simple candle/price features | Compute numbers deterministically |
| Derivatives | One index options-chain workflow with OI, OI-based PCR, IV when available | Collect prospectively from month 1 if access permits |
| Commodities | One MCX contract family and one macro driver | Define expiry/roll handling; do not mix contracts blindly |
| Interface | Ranked signals, evidence view, event timeline, experiment summary | Simple dashboard is enough |
| Validation | Chronological backtest, ablations, walk-forward, block-bootstrap robustness, paper ledger | No real-money execution needed |

If options or MCX access cannot be secured by week 2, agree a fallback with the guide: preserve the adapter and demonstrate that tier on a documented licensed sample or prospective dataset. Report limited coverage and evaluate equity-only performance separately. Never substitute simulated market data for actual observations without labeling it.

## First 14 days: get an end-to-end head start

1. **Days 1–2:** agree universe, horizon, event labels, evaluation question, budget and dataset rights with the guide. Audit every bibliography entry against a publisher page or DOI. Make a one-page requirements document and divide ownership.
2. **Days 3–4:** create the Python environment, dependency lockfile, README and module skeleton. Set up local data storage. Acquire sample equity OHLCV and 30–50 timestamped news/filing items. Record source, publication time and ingestion time independently.
3. **Days 5–7:** implement one vertical slice: article → event JSON → company/ticker mapping → technical confirmation → fused signal → stored evidence. Start with manual event labels or a deterministic stub so model access cannot block integration.
4. **Days 8–10:** connect the actual LLM extractor, reject invalid JSON, add uncertainty/abstention, and show results in a simple dashboard. Every factual explanation must trace to stored evidence. Treat retrieved text as data, not executable instructions.
5. **Days 11–14:** produce a replayable demo on 20–30 cases, including irrelevant news, ambiguous company names, duplicates and missing market data. Establish a technical-only baseline. Start prospective news and derivatives snapshots immediately if access is available.

**Day-14 deliverable:** a news item produces a timestamped, inspectable signal from a single command or dashboard action; another student can reproduce it from the README. Do not spend these two weeks on a polished UI or a large agent framework.

## Month-by-month schedule

| Month | Work | Exit criterion |
|---|---|---|
| 1: Oct 7–Nov 6 | Scope, literature repair, source feasibility, ingestion, schemas, ticker aliases, vertical slice and technical baseline | Reproducible equity demo; ingestion logs; preliminary labeled dataset; documented options/MCX access decision |
| 2: Nov 7–Dec 6 | SLM triage, LLM event extraction, deduplication, entity resolution, provenance and annotation | End-to-end equity pipeline; held-out extraction metrics; errors classified; inference latency/cost measured |
| 3: Dec 7–Jan 6 | Structured agent orchestration, fusion, VLM chart experiment and limited derivatives/commodity adapters | All promised tiers integrated or explicitly scoped; missing-input behavior works; ablation runs reproducible |
| 4: Jan 7–Feb 6 | Chronological backtesting, walk-forward evaluation, cost/slippage assumptions and weight selection | Frozen strategy/prompt versions; validation-selected weights; paper ledger running by start of month |
| 5: Feb 7–Mar 6 | Forward paper observations, locked-test evaluation, ablations and block-bootstrap robustness | Comparison tables, uncertainty intervals, failure analysis and frozen feature set |
| 6: Mar 7–Apr 7 | Final paper ledger analysis, reliability fixes, report, poster/demo and viva practice | Reproducible release, complete report, recorded demo and submission buffer |

Write report sections as you finish modules. Keep paper observation running during months 4–6; do not start it in the final week. This observation window demonstrates forward behavior but is too short to establish long-term profitability.

## Architecture and stack

Start with modular Python functions sharing typed inputs/outputs. An agent is a component with a defined responsibility, not necessarily an autonomous chatbot. Introduce graph orchestration when dependencies, retries and shared state require it.

Recommended initial architecture:

```text
News/filings + OHLCV + optional options/MCX snapshots
                       ↓
             timestamped ingestion/store
                       ↓
         deduplication → SLM relevance triage
                       ↓
       LLM event extraction + ticker resolution
                       ↓
   quantitative features + optional VLM/derivatives/macro evidence
                       ↓
       fusion + missing-data rules + abstention
                       ↓
           evidence dashboard + paper ledger
```

Use Python, pandas/NumPy, Pydantic-style schemas, FastAPI, PostgreSQL and Parquet files for bulk data. A simple Streamlit dashboard is a reasonable implementation choice for this prototype. Use pretrained financial sentiment models as a baseline and benchmark candidate SLM/LLM/VLM models against your own data before choosing. Keep the model provider interchangeable.

Use one backtesting engine. The synopsis lists both backtesting.py and vectorbt; implementing two is unnecessary. Add Redis, MongoDB and Prometheus only if a demonstrated requirement justifies their maintenance. PostgreSQL plus local structured files is a manageable initial storage design. Hardware and API budget are unknown, so do not commit to a large local model until you run a latency/memory trial.

Suggested modules: `ingestion/`, `schemas/`, `agents/`, `features/`, `fusion/`, `evaluation/`, `api/`, `dashboard/`, `configs/`, `tests/`, `docs/`. Keep raw data immutable and secrets outside version control. Commit code, data manifests and small reproducible fixtures; avoid committing large datasets or credentials.

## Data and evidence contract

Store at least: article/event ID, source URL, original text or permitted extract, content hash, publication timestamp, ingestion timestamp, timezone, instrument ID, event type, direction, extracted evidence spans, model/version, prompt version, output validity and processing time. If publication time is unknown, mark it unknown rather than inventing it.

Market records need exchange, symbol, instrument/expiry where applicable, timestamp, OHLCV, optional OI/IV, adjustment policy and provider. Define whether PCR is volume-based or OI-based and which expiries/strikes enter the calculation. Define how IV is supplied or estimated. Avoid treating OI, PCR or IV as unconditionally bullish/bearish; evaluate the rule you choose.

News published after market close cannot affect an earlier close-time signal. Use the next eligible decision/entry time. Features must have `available_at <= decision_time`. Do not feed a chart containing future candles to the VLM. Log delays and fail to insufficient-evidence when mandatory inputs are stale or unavailable.

Start with 100 labeled items and aim for roughly 300–500 carefully annotated items if resources permit. Include irrelevant items and duplicate reports. Have two students independently label a subset, reconcile disagreements, and measure agreement. Split related stories as a group so duplicate coverage cannot leak across evaluation sets.

## Fusion and confidence

Begin with a transparent weighted score over normalized directional evidence, for example language, technical, derivatives and commodity components. Choose initial weights as a documented baseline and tune only on chronological validation windows. Related inputs are correlated; do not assume each is independent supporting evidence.

Separate the directional score, evidence coverage and confidence. An LLM's self-reported confidence is not a measured probability of a profitable outcome. Until calibration is validated, label outputs as evidence strength or heuristic confidence. Define explicit abstention for unresolved entities, conflicting evidence, stale inputs and poor coverage. If optional components are missing, either abstain or apply a predefined renormalization rule and display reduced coverage; never treat missing evidence as a positive signal.

## Experiments needed for a credible report

| Question | Experiment/metric |
|---|---|
| Does event extraction work? | Per-event precision/recall/F1; entity mapping accuracy; schema validity; evidence support |
| Does fusion help? | Same universe, dates, entry rules and costs for technical-only, news-only, news + technical, and full fusion |
| Does the small model save resources? | Compare triage on/off for relevant-event recall, model calls, latency and cost |
| Does the VLM add information? | Full system with/without VLM and quantitative-only chart features |
| Do cross-market tiers help? | Remove derivatives and commodities separately; disclose data coverage and use comparable subsets |
| How strong are simulated results? | Net returns, max drawdown, trade count, exposure, turnover, hit rate and Sharpe with stated sampling/annualization |
| How stable are the results? | Chronological walk-forward windows, cost sensitivity and block-bootstrap intervals |
| Can it work prospectively? | Frozen daily paper ledger with signal, decision time, hypothetical fill, costs and subsequent outcome |

Use chronological training/validation/test periods, not shuffled market rows. Purge samples whose future-return labels overlap a later evaluation window. Select thresholds, model versions and weights on validation; reserve the final test until decisions are frozen. State corporate-action handling, universe selection/survivorship limitations, benchmark, next-eligible-bar fills, fees and slippage.

Historical LLM evaluation has an additional risk: a model may have learned events or outcomes during pretraining. Prevent pipeline look-ahead, document model cutoffs where known, and treat prospective frozen-model observation as complementary evidence. Historical backtests alone do not eliminate model memorization.

For Monte Carlo-style robustness, block-bootstrap returns or trades to preserve some temporal dependence and examine drawdown/return sensitivity. Do not shuffle individual daily observations and claim you have simulated realistic future markets. Small samples require visibly qualified conclusions.

## Four-person ownership

| Owner | Primary work | Shared obligation |
|---|---|---|
| Student A | Data ingestion, market datasets, timestamps and backend | Review evidence/time correctness |
| Student B | Annotation, SLM/LLM pipeline, entity mapping and literature | Review extraction errors |
| Student C | Quantitative features, derivatives/commodities, backtests and fusion | Review evaluation validity |
| Student D | VLM experiment, dashboard, integration and reproducibility | Review usability and system failures |

Assign names by strengths rather than assuming a particular student fits a role. Agree contracts before implementing in parallel. Each student documents their module, reviews another module, and participates in labeling and experiments. Hold one short integration meeting and one working end-to-end demo each week. Track tasks with a definition of done and keep a decision log.

## Risks to resolve early

1. **Data access:** historical timestamped news, expired options and MCX data can control feasibility. Confirm actual coverage, licensing, budget and instrument mapping before committing the evaluation design.
2. **Scope creep:** keep one universe/horizon and freeze additions after month 3. Preserve required heterogeneous tiers as bounded experiments rather than expanding every asset class.
3. **Evaluation leakage:** make availability-time checks and future-candle exclusion testable. Prioritize tests here, in fusion missing-input rules and paper-ledger fills.
4. **Bibliography errors:** verify exact titles/authors/years/DOIs and reread each paper before claiming a limitation. The synopsis table calls StockAgent 2025 while its reference calls it 2026 with Xiao/Zhang; the identifiable StockAgent paper has different authors and was first submitted in 2024.
5. **Model cost/reliability:** cache by content/model/prompt version, deduplicate, bound retries, record failed calls and cap daily inference expenditure.

## Source checks performed on 7 October 2026

- [Kite Connect historical candle documentation](https://www.kite.trade/docs/connect/v3/historical/) describes OHLCV/OI and continuous historical support for futures; check its contract/token constraints before planning a derivatives dataset.
- [Kite Connect forum: expired options data](https://kite.trade/forum/discussion/12880/how-to-download-historical-option-data-which-has-expired) states expired options candle data is not offered. Do not assume the synopsis's Kite choice supplies every needed historical options dataset.
- [StockAgent primary paper](https://arxiv.org/abs/2407.18957) identifies Chong Zhang and coauthors, initial submission in July 2024, and a revised version in June 2026. Correct the synopsis reference using the exact version/publisher record you actually read.
- [Glasserman and Lin: Assessing Look-Ahead Bias](https://arxiv.org/abs/2309.17322) discusses overlap between LLM training history and financial backtests. This motivates the separate prospective ledger.

These checks do not validate the remaining eight bibliography entries. The exact Chen/Madisetti title was not located in the initial search; that is a reason for further verification, not proof that it does not exist.

## Definition of finished

- All promised tiers run on documented real or explicitly labeled sample data, with scope limitations visible.
- Another student can set up and reproduce a representative signal and an experiment from written instructions.
- Outputs show timestamp, source, event, market confirmation, evidence coverage and an explanation grounded in stored records.
- Results compare baselines and ablations with chronological separation, declared costs and uncertainty.
- Report includes architecture, data provenance, labeling, experiment settings, failure cases, limitations and corrected references.
- Demo works on cached fixtures if external services fail; report, slides and submission package are ready before the deadline.
