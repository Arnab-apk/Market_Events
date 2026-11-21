# MVP implementation guide

## A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets

**Prepared for:** Arnab and project team  
**Date:** 24 October 2026  
**Status:** Implementation specification. The application described here has not been built or tested by writing this guide.  
**Primary constraint:** Keep the implementation small, readable, reproducible and explainable in a college viva.

This guide turns the [project comparison and differentiation report](PROJECT_COMPARISON_AND_DIFFERENTIATION.md) into an MVP build plan. Where the broader report describes additional features, the MVP boundaries in this guide take precedence for the first release. Your confirmed architecture uses an SLM for filtering and suitable low-level tasks, an LLM for complex analysis, and deterministic code for calculations. There is no separate VLM tier.

## Contents

1. [MVP outcome and scope](#1-mvp-outcome-and-scope)
2. [User workflow and architecture](#2-user-workflow-and-architecture)
3. [Small technology stack](#3-small-technology-stack)
4. [Repository structure and reading order](#4-repository-structure-and-reading-order)
5. [Module responsibilities and interfaces](#5-module-responsibilities-and-interfaces)
6. [Data contracts and storage](#6-data-contracts-and-storage)
7. [SLM and LLM responsibilities](#7-slm-and-llm-responsibilities)
8. [Cross-market evidence and fusion](#8-cross-market-evidence-and-fusion)
9. [Outcome tracking and evaluation](#9-outcome-tracking-and-evaluation)
10. [Dashboard behaviour](#10-dashboard-behaviour)
11. [Readability and maintenance rules](#11-readability-and-maintenance-rules)
12. [Documentation required during implementation](#12-documentation-required-during-implementation)
13. [Build milestones](#13-build-milestones)
14. [Tests and verification](#14-tests-and-verification)
15. [Setup and planned commands](#15-setup-and-planned-commands)
16. [Failure handling and reproducibility](#16-failure-handling-and-reproducibility)
17. [Completion checklist and final handover](#17-completion-checklist-and-final-handover)
18. [After the MVP and reference documentation](#18-after-the-mvp-and-reference-documentation)

## 1. MVP outcome and scope

### 1.1 What the first version must do

A user imports a dated news item or filing and market observations, then receives a stored event assessment containing:

- The event type, affected company and exact supporting source passages.
- Whether the item is new, a duplicate, an update or unresolved within the collected dataset.
- A reviewed relationship to a commodity when relevant.
- Equity and cross-market observations available at the chosen decision time.
- A deterministic evidence score, coverage and explicit missing/conflicting evidence.
- A concise explanation and a later, separately computed outcome.
- A trace of SLM/LLM calls, versions, token usage and latency.

The MVP is an event research application. It does not need an autonomous trader or a general-purpose financial assistant to demonstrate the project.

### 1.2 Frozen first-release boundaries

| Area | MVP boundary |
| --- | --- |
| User | One local researcher; no accounts, roles or multi-tenant deployment |
| Equity universe | Five NSE stocks across two sectors, selected and documented before evaluation |
| Events | Earnings, order announcements and commodity supply disruptions; include other/uncertain labels |
| Timing | Daily observations and a clearly defined end-of-day decision cutoff |
| Cross-market path | One commodity family with reviewed exposure mappings for a subset of the five stocks |
| AI | One SLM configuration and one LLM configuration, with separate task prompts |
| Data entry | Article JSONL import, market CSV import and optional manual article entry |
| Interface | A local Streamlit dashboard and a small command-line entry point |
| Storage | SQLite metadata/observations and local permitted source files |
| Outcome | One five-trading-session event outcome, measured from a defined next-session entry |
| Research comparison | Equity-only versus equity-plus-commodity; LLM-only versus SLM-filtered versus SLM-delegated |
| Demo | Actual model inference path plus clearly labelled recorded replay |

Five stocks and 30-50 reviewed pilot articles are suitable integration targets, not evidence of statistically reliable predictive performance. Expand the evaluation dataset only after the pipeline works.

### 1.3 Deferred features

Defer derivatives/OI/PCR/IV, portfolio import and exposure totals, external notifications, a 24/7 worker, a generic chatbot, vector search, chart-image analysis, order-book research, full historical strategy optimization, Monte Carlo dashboards and real-money execution. These remain possible later phases of the broader project.

The MVP must still contain a genuine cross-market path: equity observations plus an actual commodity series. If only synthetic observations are available, label the build a functional prototype and leave real-data validation incomplete. Removing derivatives from the MVP does not remove them from the full synopsis; record the staging decision in project documentation.

## 2. User workflow and architecture

### 2.1 One complete user journey

1. Import a small article dataset and equity/commodity observations.
2. Validate source fields, identifiers and timezones; reject malformed rows with clear reasons.
3. Select an item, a decision cutoff and an execution policy.
4. Check exact duplicates and earlier eligible event versions.
5. Ask the SLM to filter relevance and perform approved low-level tasks.
6. Escalate relevant complex or uncertain cases to the LLM for structured extraction.
7. Resolve the affected instrument against canonical identifiers; hold ambiguous mappings for review.
8. Select a reviewed exposure mapping and eligible market observations.
9. Compute numerical features and the evidence assessment in ordinary code.
10. Save the result and show a deterministic explanation template; optionally request an LLM explanation.
11. When future observations exist, calculate and display the event outcome separately.

An irrelevant item stops after filtering, but its routing decision and usage remain stored. A failed or unsupported analysis stays visible with a reason rather than disappearing from the dataset.

### 2.2 Architecture

```text
Imported articles + price observations + reviewed company/exposure configuration
                                     |
                           validation and event memory
                                     |
                       SLM filtering / low-level task handling
                                     |
                       LLM structured extraction when needed
                                     |
                     entity resolution and exposure selection
                                     |
                     deterministic market feature calculations
                                     |
                       fusion / coverage / abstention rules
                                     |
                          SQLite result and run trace
                              /                  \
                  dashboard and export       later outcome evaluation
```

`pipeline.py` coordinates these steps in order. It should read like the workflow above. Use ordinary function calls, typed data and a few small client/storage classes; graph orchestration is unnecessary for this first version.

### 2.3 Dependency rule

The dashboard and CLI call the pipeline. The pipeline calls domain functions, agents and storage. Numerical functions do not call models or the dashboard. Agent functions do not write arbitrary database records. Provider clients do not decide event relevance or trading direction.

This separation lets you explain a result by following one path rather than searching through unrelated UI callbacks.

## 3. Small technology stack

| Tool | MVP purpose | Rule for keeping it understandable |
| --- | --- | --- |
| Python | Application, models integration and numerical logic | Choose one supported Python version and record the exact tested version |
| Streamlit | Local dashboard | Keep UI code separate from processing logic |
| pandas and NumPy | Date-indexed market calculations | Use clear column names and explicit missing-data behaviour |
| Pydantic | Typed input/output validation | Use named schemas instead of passing unstructured dictionaries everywhere |
| SQLite through `sqlite3` | Durable events, observations, runs and outcomes | Keep parameterized SQL inside one storage module initially |
| One HTTP client, such as Requests | SLM/LLM requests and later source adapters | Centralize timeouts, authentication and error translation |
| `python-dotenv` plus environment variables | Local configuration | Commit only placeholder configuration, never credentials |
| pytest | Meaningful unit and integration checks | Focus on time correctness, data integrity, routing and accounting |
| Ruff | Formatting and linting | Use one shared configuration in `pyproject.toml` |
| Python logging and `time.perf_counter` | Trace and latency measurement | Record task IDs and timings consistently |

Use Streamlit's built-in charts initially; add a chart library only if a required display cannot be expressed clearly. Use SQLite text/entity/date queries for the pilot; FTS5 is a later addition if document search warrants it.

Do not add FastAPI, React, Docker, Redis, MongoDB, a graph database or a vector database merely because they appear in a proposed stack. Each additional component needs a demonstrated MVP requirement.

Keep provider configuration interchangeable. One chosen protocol may serve both models; if the SLM and LLM require different protocols, implement two small adapters inside the model-client boundary. Do not design a general provider framework in advance.

## 4. Repository structure and reading order

The following is a proposed final MVP structure. Create files when their milestone needs them, rather than generating empty modules for every future idea.

```text
Final_Yr_Proj/
  README.md
  MVP_IMPLEMENTATION_GUIDE.md
  PROJECT_COMPARISON_AND_DIFFERENTIATION.md
  pyproject.toml
  requirements.lock
  .env.example
  .gitignore
  app.py
  configs/
    settings.example.json
    companies.json
    exposure_rules.json
    fusion_rules.json
  prompts/
    filter_event.md
    extract_event.md
    explain_assessment.md
  src/
    market_events/
      __init__.py
      __main__.py
      config.py
      schemas.py
      pipeline.py
      ingestion.py
      event_memory.py
      exposure.py
      market_features.py
      fusion.py
      outcomes.py
      storage.py
      model_client.py
      agents/
        __init__.py
        filter_agent.py
        event_agent.py
        explanation_agent.py
  tests/
    fixtures/
      articles.jsonl
      market_prices.csv
      recorded_model_outputs.json
      README.md
    test_ingestion.py
    test_event_memory.py
    test_routing.py
    test_market_features.py
    test_fusion.py
    test_outcomes.py
    test_pipeline.py
  docs/
    CODEBASE_GUIDE.md
    DATA_DICTIONARY.md
    MODEL_AND_PROMPT_NOTES.md
    EXPERIMENTS.md
    DECISIONS.md
    IMPLEMENTATION_LOG.md
    DEMO_AND_VIVA.md
  data/                         # Ignored local input files and SQLite database
  runs/                         # Ignored generated exports and diagnostic records
```

The lockfile is an exact dependency snapshot generated from a clean, tested environment, with its generation method documented. `pyproject.toml` declares the package, dependencies and development tools. Do not maintain a second competing handwritten dependency list.

### Reading order for you and an examiner

1. `README.md`: purpose, implemented features and exact setup/demo commands.
2. `docs/CODEBASE_GUIDE.md`: architecture and module map.
3. `schemas.py`: the objects moving between components.
4. `pipeline.py`: one complete analysis journey.
5. `agents/`: which tasks use the SLM and LLM.
6. `market_features.py`, `exposure.py`, `fusion.py`: the actual decision logic.
7. `outcomes.py`: how subsequent results are measured.
8. `storage.py`, `model_client.py`: persistence and external integration.
9. `app.py`: how results are presented.
10. `tests/` and `docs/EXPERIMENTS.md`: evidence that the system behaves as described.

## 5. Module responsibilities and interfaces

| Module | Owns | Must not own |
| --- | --- | --- |
| `config.py` | Read settings, validate paths/model settings and expose typed configuration | Event scoring or hidden runtime decisions |
| `schemas.py` | Named records, enums and input/output constraints | SQL, HTTP requests or UI state |
| `ingestion.py` | Validate imported files, normalize timestamps and return records/errors | LLM interpretation or silent correction of invalid facts |
| `event_memory.py` | Exact duplicates, candidate related events and eligible version history | Claims that an item is new to the entire market |
| `exposure.py` | Resolve reviewed company aliases and select versioned exposure rules | Invented economic relationships |
| `agents/filter_agent.py` | SLM relevance, coarse labels, candidate aliases and escalation | Market arithmetic or final directional decisions |
| `agents/event_agent.py` | LLM structured event extraction and source support checks | Filling missing market observations |
| `agents/explanation_agent.py` | Optional explanation using an already computed assessment | Overriding scores, numbers or eligibility rules |
| `model_client.py` | Provider request/response translation, timeouts and usage records | Prompt-specific financial decisions |
| `market_features.py` | Eligible observations, returns, volume and benchmark features | Calls to model providers or database mutation |
| `fusion.py` | Directional score, coverage, conflict and abstention | Loading files or inventing probabilities |
| `outcomes.py` | Future-label calculation for completed horizons | Modifying saved decisions using later observations |
| `storage.py` | Parameterized queries, transactions and schema initialization | Model prompting and UI rendering |
| `pipeline.py` | The explicit workflow and saving stage results | Large inline SQL blocks or duplicated numerical formulas |
| `app.py` | Forms, tables, charts and invoking public workflows | Business rules embedded in widget callbacks |

### Small public interfaces

The following are proposed signatures, not implemented functions:

```python
def import_articles(path: Path) -> ImportResult: ...
def filter_article(article: Article, client: ModelClient) -> FilterDecision: ...
def extract_event(article: Article, client: ModelClient) -> EventExtraction: ...
def find_exposure(event: EventExtraction, rules: ExposureRules) -> ExposureMatch: ...
def compute_market_features(observations: list[MarketObservation],
                            decision_time: datetime) -> MarketFeatures: ...
def assess_evidence(event: EventExtraction, exposure: ExposureMatch,
                    features: MarketFeatures, rules: FusionRules) -> Assessment: ...
def analyse_article(article_id: str, decision_time: datetime,
                    policy: ExecutionPolicy, dependencies: Dependencies) -> AnalysisRun: ...
def evaluate_outcome(run: AnalysisRun,
                     later_observations: list[MarketObservation]) -> EventOutcome: ...
```

Use lightweight dependency objects only to pass the actual clients, storage and settings. Avoid a service locator, runtime class registration or dependency-injection framework. An explicit constructor or function argument is easier to trace.

## 6. Data contracts and storage

### 6.1 Minimum schemas

| Schema | Important fields |
| --- | --- |
| `Article` | ID, source URL/ID, permitted text, published/first-seen times, content hash and source version |
| `MarketObservation` | Instrument ID, market family, observation time, available-at time, OHLCV, currency/unit and contract ID if applicable |
| `FilterDecision` | Relevant/irrelevant/uncertain, coarse event type, candidate entities, selected source spans, reason and model trace ID |
| `EventExtraction` | Event ID, source version, type, canonical company or unresolved state, amounts/units, supporting spans and validation status |
| `ExposureRule` | Company/sector, commodity, relationship hypothesis, source, direction convention, effective/known-at times and version |
| `MarketFeatures` | Named values, supporting observation IDs, cutoff, missing/stale status and numerical-definition version |
| `Assessment` | Direction label, evidence score, coverage, conflicts, abstention reasons and exact inputs/rules used |
| `ModelCall` | Run/task IDs, provider/model, prompt version, usage, timing, retries and status |
| `AnalysisRun` | Run ID, article/event IDs, policy, decision cutoff, immutable configuration snapshot and stage results |
| `EventOutcome` | Run ID, hypothetical entry/exit times and prices, gross/net label, benchmark comparison and pending/completed/invalid status |

Use timezone-aware datetimes. Store timestamps normalized to UTC and display them in `Asia/Kolkata`. Preserve the source timezone where relevant. Distinguish publication time, first seen, market observation time and availability; they are not interchangeable.

Pydantic validates structure and declared constraints; it does not establish that an extracted financial statement is true. Check source spans, identifiers, numerical units and eligible timestamps separately.

### 6.2 Import formats

Article JSONL: one record per source item with `article_id`, `source_url`, `published_at`, `first_seen_at` where known, `text` and `source_version`.

Market CSV: `instrument_id`, `market_family`, `timestamp`, `available_at`, `open`, `high`, `low`, `close`, `volume`, `currency`, `unit`, and `contract_id` when applicable. Keep the timestamp convention documented: session close time is different from a vendor's midnight date label.

Reject duplicate observation keys, impossible OHLC relationships and invalid timestamps. Missing required prices should produce an import error or explicit invalid record, not an invented value. Report unknown availability times and the conservative eligibility assumption used for historical imports.

### 6.3 SQLite tables

Start with `articles`, `market_observations`, `events`, `event_sources`, `analysis_runs`, `model_calls`, `assessments` and `outcomes`. `event_sources` links multiple articles or updates to an event without pretending each is an independent catalyst. Store immutable configuration snapshots with runs even if editable defaults live in JSON files.

Use foreign keys, unique IDs and unique constraints for exact source/observation versions. Keep transactions short; never hold one open during model inference. Enable foreign-key enforcement on each connection. Prefer one active analysis writer in the local MVP and show a clear busy state if another run is active.

Start with a `schema_version` value and versioned migration functions inside `storage.py`. Changing a model or fusion policy creates new runs, not silent updates to old results. A corrected source gets a new version linked to its predecessor.

## 7. SLM and LLM responsibilities

### 7.1 Task policy

| Task | Owner | Required control |
| --- | --- | --- |
| Exact hash duplicate, date parsing, arithmetic and canonical lookup | Ordinary code | Test known cases; no model needed |
| Relevance filter and coarse event tag | SLM | Evaluate relevant-event recall and forward uncertain cases |
| Candidate alias selection and relevant passage selection | SLM after pilot validation | Check against canonical candidates and original source spans |
| Ambiguous entity resolution and detailed event extraction | LLM | Validate structured output and evidence support |
| Market features and fusion | Ordinary code | Model outputs cannot overwrite numerical results |
| Final explanation | Deterministic template first; LLM on demand | Use saved assessment only, cite inputs and preserve the decision |

Keep one filter-agent role, one event-analysis role and one optional explanation role. The two LLM roles may use the same model with different prompts. There is no need for an open-ended agent debate.

### 7.2 Three execution policies

- `llm_only`: shared deterministic preprocessing, then LLM handling for model tasks.
- `slm_filter`: the same workflow with SLM relevance filtering before LLM extraction.
- `slm_delegate`: filtering plus validated SLM low-level results reused during LLM extraction.

Keep final extraction validation and numerical scoring identical between policies. Save model usage for irrelevant and failed items too. Self-reported confidence is not a reliable probability; choose rejection/escalation rules from reviewed examples and measure their errors.

### 7.3 Token and latency controls

Use compact schemas and selected source passages, retain original permitted text, and fall back to wider context when passage validation fails. Preserve dates, amounts, units, conditions and negation. Do not repeatedly pass full article histories or agent transcripts.

Allow at most one extraction call for a normal accepted item, plus a bounded retry for a transient failure or malformed result. Optional explanation is a distinct, logged on-demand call. Define explicit per-run request/token limits in settings; reaching a limit creates a visible partial result, not an unbounded retry loop.

Record input/output tokens separately for each model where provided, using each provider's reported units. Unknown usage stays unknown, not zero. Record wall-clock stage durations and full item latency, including model loading, queueing, validation and retries. Compare cold/warm and cached/uncached runs separately.

Fewer large-model tokens do not automatically mean lower total cost or latency. Your MVP should demonstrate the measured tradeoff, including missed events or additional sequential SLM overhead.

### 7.4 Model selection gate

Before full integration, benchmark a small SLM candidate on 20-30 reviewed pilot items on the actual available machine or endpoint. Verify JSON reliability, relevant-event recall, latency and resource use. Select the LLM with the same evidence-grounding check. Record exact model/provider identities and limitations in `MODEL_AND_PROMPT_NOTES.md`.

No particular GPU, paid API or model size is assumed. If the selected SLM cannot run acceptably, revise its hosting/model choice and record the decision. Recorded replay can unblock UI development, but the complete MVP requires a demonstrated real SLM and LLM path.

## 8. Cross-market evidence and fusion

### 8.1 Small reviewed exposure configuration

For one commodity family, list the selected companies, the proposed exposure, source evidence and limitations. A relationship might describe input-cost pressure for a consumer of that commodity. It is a hypothesis, not a universal price-direction rule.

Record the source and `known_at` time of company-specific information. A current exposure description must not silently appear in a historical replay before it was known. Start with manually reviewed mappings; the LLM may suggest a candidate for review, but must not add it automatically to active scoring rules.

Use actual instrument and contract identities. Commodity futures need an explicit contract/expiry and roll policy. For the first demonstration, a single documented contract over a bounded interval avoids needing to build a continuous series immediately. An international benchmark is not automatically equivalent to an MCX instrument.

### 8.2 Minimum numerical features

Implement only these initial features, with full definitions in `DATA_DICTIONARY.md`:

- Equity return over one predefined prior-session lookback.
- Equity return relative to a comparable sector/index observation over that same interval.
- Relative volume against earlier completed sessions, excluding the current session from its own baseline.
- Commodity return over an explicitly aligned interval available before the decision cutoff.
- Freshness and missing-input flags, separate from directional measurements.

Avoid forward-filling across missing sessions unless a specific feature definition justifies it. If the required earlier window is unavailable, mark the feature missing. Corporate-action handling must be consistent within each return calculation.

### 8.3 Start with a fixed, transparent policy

`fusion_rules.json` defines which features are required for each event family, their direction conventions, documented weights and abstention conditions. For commodity events, compare an equity-only policy with an equity-plus-commodity policy. Earnings and order events need not request commodity data when it has no reviewed relevance.

Keep the evidence score, coverage and direction label separate. Predefined normalization and thresholds belong in configuration with a version, not scattered constants in Python. Zero-denominator or mandatory-input failures produce `insufficient_evidence`. Missing commodity evidence is never a neutral commodity return.

Initial outputs are `positive_evidence`, `negative_evidence`, `mixed_evidence` or `insufficient_evidence`. These labels describe the assessment policy; they are not calibrated probabilities or instructions to trade.

The LLM explanation receives the computed assessment, source spans and observation references. It may explain uncertainty but cannot change the numerical score. Provide a readable deterministic template whenever the optional explanation call fails.

## 9. Outcome tracking and evaluation

### 9.1 A practical outcome definition

For an eligible end-of-day decision, use the next valid exchange-session open as the hypothetical entry. Define the five-session outcome as the close of the fifth eligible equity session **counting the entry session as session one**. This is a fixed definition for the MVP, not a claim that it is the optimal investment horizon.

Report stock return and a consistently timed benchmark comparison. When a split or other corporate action crosses the interval, use a fully consistent adjustment/accounting policy or mark that outcome invalid until support exists. Do not mix adjusted closing prices with raw opening prices.

If fees/slippage are not configured, label the result gross and do not display it as net profit. If costs are supported, document the exact hypothetical transaction and cost assumptions. Independent event outcomes are not funded portfolio returns and must not be summed into a portfolio equity curve.

Use exchange-session data rather than adding calendar days. Missing future observations leave the outcome `pending`; they must not be replaced with an invented return. Save the outcome separately from the immutable original assessment.

### 9.2 Minimum comparisons

| Comparison | Hold constant | Measure |
| --- | --- | --- |
| Equity-only versus equity-plus-commodity | Same eligible events, dates, exposure mappings and numerical definitions | Subsequent outcome association, coverage, disagreement and failures |
| LLM-only versus SLM filtering | Same incoming article set, final task and LLM configuration | Recall, extraction quality, calls, tokens and latency |
| Filtering versus filtering plus delegation | Same source evidence, validation and model versions | Incremental token/latency savings and lost/changed facts |

Use a reviewed pilot for prompt/routing development and a separate later chronological evaluation set. Keep related story versions together. If future-return labels overlap a split boundary, exclude or purge the conflicting samples. Report sample counts and do not claim reliable superiority from a small pilot.

Historical models may already know historical outcomes. Do not supply future labels to agents; document model timing limitations and start a prospective frozen-run ledger once the pipeline is stable. The MVP's first evaluation demonstrates reproducibility and preliminary behaviour, not established profitability.

### 9.3 Useful counters

Show relevant-event recall, entity/extraction correctness on reviewed examples, invalid-output rate, accepted/abstained counts, per-model token usage, escalation rate, median/p95 latency where sample size supports it, and missing-data failures. Unknown provider usage is reported as unavailable.

For cross-model token reporting, retain separate counts and tokenizer/provider identities. Raw tokens from different tokenizers are not interchangeable units of computation. Monetary cost and measured latency should be recorded separately.

## 10. Dashboard behaviour

Use four ordinary views or tabs. This is a functional layout specification, not a requirement for a separate frontend framework.

| View | Required interactions | Information shown |
| --- | --- | --- |
| Import and watchlist | Import article/price files; inspect validation errors; select configured companies | Source, coverage interval, accepted/rejected rows and latest observation |
| Event inbox | Filter by company/type/status; select an article; explicitly start analysis | New/duplicate/update candidates, source time and analysis status |
| Event evidence | Inspect extraction, exposure, market evidence, conflicts; request optional explanation | Source passages, timestamps, score/coverage, missing inputs and run ID |
| Outcomes and runs | Inspect completed/pending outcomes; compare policies; export a run | Saved results, model usage, timings, errors and evaluation sample counts |

Analysis must run only after an explicit submit action. Store a request/run identifier and reuse completed results when the UI reruns. Disabling a button is not the only duplication defence: storage needs an idempotency key derived from source version, cutoff, policy and configuration/model versions. Explicit repeat experiments create separate linked run IDs.

Streamlit reruns scripts after interactions; its documented [forms](https://docs.streamlit.io/develop/concepts/architecture/forms) batch user input. Use these for analysis submission. Its [caching](https://docs.streamlit.io/develop/concepts/architecture/caching) can help with reusable reads/resources, but SQLite remains the source of truth for completed runs. Do not cache writes or rely on session state as the only durable history. Keep cache keys tied to data/configuration versions and freshness.

The interface must distinguish `live_model`, `recorded_replay`, `synthetic_fixture` and `imported_historical_data`. A recorded response is not fresh model inference, and a current model analysing an old article is not a historically available forecast.

## 11. Readability and maintenance rules

### 11.1 Naming and organization

- Use financial names that explain meaning: `relative_volume`, `decision_time`, `source_version` and `missing_required_inputs`.
- Use `snake_case` for functions/files, `PascalCase` for schemas/classes and clear enum values.
- Prefer one function for one understandable operation. A processing function should not also draw widgets, execute SQL and perform HTTP calls.
- Use plain branching and named intermediate values rather than nested comprehensions or clever one-liners.
- Use classes for useful state/lifecycles such as a client or database connection; pure calculations should remain functions.
- Avoid catch-all files named `utils.py`, `helpers.py` or `manager.py`. Put a helper beside the feature it supports.
- Avoid duplicated event schemas or parallel implementations of the same score in the UI and backend.
- Split a module when it contains multiple responsibilities or becomes difficult to explain; do not split every tiny function into a separate file.

### 11.2 Types, comments and docstrings

Type public function inputs and outputs. Public financial functions should describe units, time assumptions, missing-data behaviour and their return type. Comments should explain a financial or engineering reason, not translate obvious Python into English.

Good explanatory comment:

```python
# Use only earlier sessions so today's volume cannot inflate its own baseline.
historical_volume = completed_sessions.iloc[:-1]["volume"]
```

For every numerical formula, document one worked example and its edge cases. Keep notebooks for exploration only; move accepted logic into the package so a demo does not depend on cells executed in an unknown order.

### 11.3 Error handling and configuration

Use a small set of named errors/statuses such as `InvalidImport`, `AmbiguousEntity`, `MissingMarketData`, `ModelUnavailable` and `InvalidModelOutput`. Catch errors at the layer that can act on them. Avoid `except Exception: pass` or replacing a failed feature with zero.

Keep timeouts, data paths, allowed model identifiers, output limits, feature windows and scoring settings in validated configuration. Prompts live in `prompts/`, not inside UI code. Store prompt/configuration hashes in runs so a Git revision alone is not the only way to reconstruct them.

### 11.4 Change discipline

Implement one milestone at a time and keep a working end-to-end path. Use small commits with clear messages. Do not leave abandoned alternative implementations, unused frameworks, copied demo projects or unexplained scripts in the repository.

Format and lint with a shared [Ruff configuration](https://docs.astral.sh/ruff/). Choose a small initial rule set for basic errors, imports and readable code; introduce stricter checks only when the team understands them. Passing a formatter does not replace reviewing financial assumptions.

## 12. Documentation required during implementation

Documentation is part of each milestone's completion, not a task left for the submission week.

| File | Required content | When to update |
| --- | --- | --- |
| `README.md` | What works now, setup, commands, sample workflow, limitations and links | Every delivered feature |
| `CODEBASE_GUIDE.md` | Module map, dependency direction, reading order and one traced example | When module responsibilities change |
| `DATA_DICTIONARY.md` | Fields, units, IDs, timestamps, formulas and missing values | Every schema/feature change |
| `MODEL_AND_PROMPT_NOTES.md` | Task ownership, actual models, prompt versions, routing and failure examples | Every model/prompt-policy change |
| `EXPERIMENTS.md` | Dataset versions, splits, configurations, metrics and negative results | Every comparison run |
| `DECISIONS.md` | Date, decision, reason, alternatives and consequence | Each important scope/design decision |
| `IMPLEMENTATION_LOG.md` | Completed work, touched modules, verification evidence and limitations | At the end of every implementation milestone |
| `DEMO_AND_VIVA.md` | Demo commands, cases, architecture explanation and questions | As the end-to-end path grows |
| `tests/fixtures/README.md` | Whether each fixture is synthetic/real/recorded, source rights and expected behaviour | Whenever fixtures change |

### A useful implementation-log entry

```markdown
### M3 - SLM filtering and extraction

- Status: completed / partial / blocked
- Implemented: describe the actual user-visible behaviour.
- Modules: list the files and each file's responsibility.
- Verified: record the command, result, date and model/data configuration.
- Known limitations: state failures or missing coverage.
- Documentation updated: list the corresponding guide sections.
- Next dependency: identify the next concrete deliverable.
```

Do not mark a milestone complete because code was generated or a UI tab exists. Record a working example and relevant verification. When AI assists implementation, the team still needs a plain-language explanation of the accepted change.

## 13. Build milestones

This is a sequence with exit criteria, not a promised calendar. Work availability, model access and real data determine duration. Do not build later-stage infrastructure while an earlier end-to-end path is broken.

| Milestone | Work to implement | Exit criterion |
| --- | --- | --- |
| M0: scaffold | Package, configuration, schemas, test tools, README and documentation index | Fresh environment imports the package; documented checks run |
| M1: valid data | Article/market imports, canonical companies, SQLite and fixture manifests | Valid files load; malformed/duplicate rows receive explicit handling |
| M2: numerical path | Eligible equity/commodity features, reviewed mappings and deterministic assessment | One stored cross-market assessment works without relying on model-generated numbers |
| M3: model integration | Real SLM filtering, low-level tasks, LLM extraction, source validation and usage traces | Reviewed pilot includes accepted, irrelevant, ambiguous and failed-model cases |
| M4: event workflow | Event memory, full pipeline, idempotency, explicit reanalysis and template explanations | Replaying an article does not create a duplicate catalyst or accidental paid call |
| M5: dashboard | Four views, submit actions, evidence display, stored run reads and export | User completes import-to-assessment from the local interface |
| M6: outcomes and comparisons | Five-session outcome tracker and the three execution policies | Common-input comparison exports quality/resource data with pending outcomes handled |
| M7: handover | Relevant tests, locked environment, recorded replay, code map and viva demo | Another teammate reproduces a representative run using only the README |

Implement M2 with clearly labelled validated example extraction objects before M3. This keeps integration moving without pretending a stub is a real model. M7 must include a documented actual-model run; replay is the resilient demo path, not a substitute for implementation.

For each milestone, update `IMPLEMENTATION_LOG.md` and demonstrate the current path to another team member. Everyone should be able to locate the schema, main pipeline and score calculation without assistance.

## 14. Tests and verification

Use tests that protect important behaviour rather than assertions that mirror every implementation line.

| Area | Important examples |
| --- | --- |
| Imports | Invalid OHLC, unknown identifiers, duplicate keys, missing timezones and contradictory source versions |
| Temporal eligibility | After-cutoff article excluded; future market row excluded; historical mapping not yet known excluded |
| Event memory | Exact duplicate linked correctly; genuine source update preserved; similar but distinct events not silently merged |
| Routing | Irrelevant item retained in logs; uncertain item escalates; invalid low-level extraction falls back without losing evidence |
| Features | Known return example; zero/missing volume denominator; current session excluded from historical volume baseline |
| Fusion | Required commodity missing produces abstention; conflicting inputs stay visible; score is not labelled a probability |
| Model integration | Timeout, unavailable usage, invalid JSON, unsupported source span and bounded retries |
| Outcomes | Entry follows decision; fifth-session convention; pending horizon; corporate-action invalidation and gross/net labelling |
| Persistence | Repeated request idempotency; failed run visible; completed assessment not overwritten by later outcomes |
| End-to-end | A synthetic fixture exercises the full numerical flow and matches a reviewed expected result |

Keep automated tests offline by default, using small synthetic observations and recorded provider responses. Mark optional real-provider smoke checks explicitly and invoke them deliberately; do not spend tokens on every routine test run.

Manual verification should cover at least five cases: a clear event, an irrelevant article, a duplicate/update, conflicting cross-market evidence and missing/stale market data. Confirm that changing an unrelated dashboard filter does not create a new model call.

## 15. Setup and planned commands

These are **target commands for the implementation**, not commands that currently work in this documentation-only repository. Implement each command with `argparse` in `__main__.py` and verify the final README against a clean environment.

### 15.1 Planned Windows setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

The implementation must first declare package/build metadata in `pyproject.toml`, generate the lockfile from the chosen clean environment and document its Python/platform compatibility. Document how development tooling is installed or included in that tested lock. Do not publish invented version pins before trying the environment.

Configure SLM/LLM endpoints, model identifiers and credentials through `.env` or the process environment, with non-secret defaults in an example configuration. Validate them at startup and show which required component is missing. Keep environment files and local datasets out of Git.

### 15.2 Planned workflow commands

```powershell
.\.venv\Scripts\python.exe -m market_events init-db
.\.venv\Scripts\python.exe -m market_events import-articles --file data\articles.jsonl
.\.venv\Scripts\python.exe -m market_events import-prices --file data\market_prices.csv
.\.venv\Scripts\python.exe -m market_events analyse --article-id ARTICLE_ID --as-of "2026-10-23T16:00:00+05:30" --policy slm_delegate
.\.venv\Scripts\python.exe -m market_events evaluate --run-id RUN_ID
.\.venv\Scripts\python.exe -m market_events export --run-id RUN_ID
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`ARTICLE_ID` and `RUN_ID` are placeholders replaced with actual imported/generated IDs. The example cutoff is illustrative and must correspond to the selected dataset and documented exchange-session policy. CLI validation must refuse a cutoff earlier than mandatory source availability.

### 15.3 Planned demonstration and quality commands

```powershell
.\.venv\Scripts\python.exe -m market_events demo --mode replay
.\.venv\Scripts\python.exe -m market_events demo --mode live-model
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

`replay` uses recorded model outputs and states this visibly. `live-model` runs actual configured models against the declared fixture inputs; it does not mean the underlying market observations are live. Both modes compute numerical features and fusion through the same production code.

The export should include assessment JSON, a human-readable Markdown case report and a machine-readable usage/outcome record, linked by run ID. Export generated files under `runs/` rather than scattering them through source folders.

## 16. Failure handling and reproducibility

| Situation | Required MVP response |
| --- | --- |
| SLM unavailable | Show the failure; offer explicitly labelled LLM-only execution if configured and requested |
| LLM unavailable | Preserve import/filter results; show incomplete analysis and allow later retry |
| Optional explanation fails | Show deterministic template based on the saved assessment |
| Missing source time or market history | Show the limitation and abstain where required; no manufactured feature values |
| Interrupted run | Record incomplete/failed state; allow a linked retry with an explicit stage and usage history |
| Schema/configuration changes | Preserve old run snapshots; migration creates a documented version |
| Provider returns different model | Log actual identity; flag the run for experimental compatibility review |
| Replay selected | Display recorded-model provenance and original source/model dates |

Treat imported article content as evidence, not executable instructions. Restrict model access to the supplied schemas/read-only tools; there is no reason for a news article to authorize shell commands, file changes or trading operations. Keep credentials out of prompts and logs.

For each reproducible run, retain code revision where available, data/source hashes, exact model identity, prompt/configuration snapshots, decision time, selected observations, provider outputs or permitted diagnostic extracts and final assessment. Model responses may still vary; recorded replay is the exact demonstration path, while live-model experiments disclose this variability.

Include dataset provenance and redistribution permission in fixture manifests. The live connector is optional for the MVP: valid imported real observations can demonstrate the research path. A source adapter should be added only after checking actual coverage and access; lack of an API account should not block all numerical development.

## 17. Completion checklist and final handover

### 17.1 Functional acceptance

- [ ] Import validated articles and equity/commodity observations.
- [ ] Demonstrate actual SLM filtering and low-level task handling.
- [ ] Demonstrate actual LLM extraction with supported source passages.
- [ ] Preserve duplicate/update relationships and ambiguous items.
- [ ] Run one real equity-commodity evidence assessment at a valid cutoff.
- [ ] Show score, coverage, conflicts and explicit abstention reasons.
- [ ] Display a deterministic explanation and optional grounded LLM explanation.
- [ ] Store original decisions and evaluate completed five-session outcomes separately.
- [ ] Compare the three execution policies with quality and usage measurements.
- [ ] Support a clearly labelled recorded replay without model/network access.

### 17.2 Readability acceptance

- [ ] A teammate can explain `pipeline.py` by following its function calls.
- [ ] UI, storage, model integration and financial calculations have clear boundaries.
- [ ] No duplicate scoring formulas or undocumented financial constants exist.
- [ ] Public financial functions document units, timing and missing-data behaviour.
- [ ] Schema fields and formulas have worked examples.
- [ ] Prompts and configuration are named, versioned and linked to runs.
- [ ] Unused scaffolding, abandoned experiments and temporary scripts are removed from the final source tree.
- [ ] Meaningful tests, formatting and lint checks pass in the documented environment.

### 17.3 Handover package

Provide a README, codebase guide, data dictionary, implementation log, model/prompt notes, experiment report and a five-case demo script. Include a manifest explaining which data and outputs are synthetic, imported historical, recorded or newly inferred.

The final `IMPLEMENTATION_LOG.md` should answer:

1. What was implemented and where?
2. What is the exact route from an article to an assessment?
3. What does the SLM do, and when does the LLM run?
4. Which numerical rules determine the displayed result?
5. What failed or remains outside scope?
6. How can someone reproduce the demonstration and comparison?

For viva preparation, be able to explain why a duplicate is not a new event, why missing evidence is not zero, why a future candle is ineligible, why a score is not a probability, and why fewer LLM calls may still fail to improve total latency.

The MVP is complete when this package and the working path are reproducible, not when every planned full-project feature has been added.

## 18. After the MVP and reference documentation

### 18.1 Next features in order

1. Add one permitted live data adapter and prospective collection with recorded health/freshness.
2. Add meaningful-change alerts inside the application, then an independently running worker if needed.
3. Add manual/CSV portfolio relevance without requiring brokerage credentials.
4. Add the bounded derivatives workflow promised in the full project, using actual covered data.
5. Expand event history search, reviewed exposure mappings and the evaluation sample.

Each extension must update the schemas, module guide, tests and implementation log. Keep the first complete MVP as a reproducible tagged milestone before adding broader scope.

### 18.2 Official documentation checked for this guide

- [Streamlit forms](https://docs.streamlit.io/develop/concepts/architecture/forms): supports explicit batched submission rather than launching analysis on every widget change.
- [Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching): explains reruns and data/resource caching; cache use does not replace durable run records.
- [Pydantic validation](https://docs.pydantic.dev/latest/): supports typed records and schema validation; factual evidence checks remain application responsibilities.
- [Ollama chat API](https://docs.ollama.com/api/chat): one possible model endpoint supports schema-formatted output and usage/timing fields. Model compatibility and latency must be tested; Ollama is not mandatory for both model roles.
- [Ruff](https://docs.astral.sh/ruff/): shared Python linting/formatting configured through the project tooling.

These sources support tool capabilities, not a claim that this repository already has a working application or that the proposed models will improve market prediction. Implementation, model selection, data verification and measured results remain future work.
