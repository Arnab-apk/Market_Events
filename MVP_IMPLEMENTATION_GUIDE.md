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
