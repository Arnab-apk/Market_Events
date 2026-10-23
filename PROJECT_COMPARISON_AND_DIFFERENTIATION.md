# Project comparison and differentiation plan

## A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets

**Prepared for:** Arnab and project team  
**Date:** 24 October 2026  
**Purpose:** Compare your synopsis with your friend's supplied outline and identify practical, measurable differences to build.

**Architecture revision:** Your latest decision supersedes the original synopsis's separate VLM tier. The current plan uses an SLM for filtering and suitable low-level tasks, an LLM for complex event analysis and explanations, and deterministic quantitative modules. There is no separate VLM model, agent or required vision experiment. If image interpretation is useful later, it may use the selected LLM's verified multimodal capability.

## 1. Recommendation

Keep your revised title and the central idea in your synopsis. Build an event-driven research framework that identifies an event, maps its potential exposure across markets, selects relevant evidence, and produces a traceable equity signal or abstains.

Make two capabilities the main contributions:

1. **Event-specific cross-market fusion:** select and combine company, equity, commodity and, where justified, derivatives evidence according to the event being analysed.
2. **Measured heterogeneous execution:** use an SLM for filtering and suitable low-level tasks, an LLM for complex extraction/reasoning, and numerical modules for calculations; measure end-to-end latency, token usage, quality and cost.

An event-to-impact map and a structured explanation of conflicting evidence should make these capabilities visible in the demonstration. They support the contributions; they do not need to become separate large projects.

Your friend's outline is a broad stock research application with a substantial C++ engine, watchlists, liquidity research, strategy controls, monitoring, backtesting, Monte Carlo scenarios and a chatbot. Your project can be a narrower investigation of **which evidence should be consulted for a financial event, whether combining markets helps, and how much model computation is needed**.

Different scope does not establish better performance. Your experiments must establish whether the proposed additions help, hurt, or add cost without benefit.

## 2. What was actually compared

| Source | Material reviewed | How it is used |
| --- | --- | --- |
| Your synopsis | Four-page PDF at `C:/Users/arnab/Downloads/Project Synopsis Generative AI Stock Investment Platform.pdf`; all pages extracted and page 3's architecture inspected visually | Primary source for your proposed objectives, architecture, technologies and evaluation |
| Your revised title | Title supplied in your latest message | Authoritative title for this report; it supersedes the older cover title |
| Your architecture clarification | No separate VLM; SLM handles filtering and low-level tasks to reduce latency and token consumption | Authoritative current design; supersedes conflicting vision-tier recommendations in the original synopsis |
| Your friend's supplied document | `C:/Users/arnab/.codex/attachments/7b8f0d6d-d391-424a-88eb-67ae24875add/Pasted text.txt`, titled "Stock Research Assistant - revised outline", updated 23 October 2026 | Primary comparison source; section numbers below refer to this document |
| Your repository | Committed planning material at commit `7628f0911f0602fa628412d600120eb6103e93a5` | Context only; it does not establish an implemented application |

The friend's supplied text calls itself an outline and directs readers to a separate README for runnable features. That separate README and your friend's source code were not supplied. Therefore, this report compares **documented designs**, not the quality or completeness of two running implementations.

Your current workspace shows the previously tracked planning files as deleted. This report does not restore, overwrite or reinterpret those deletions. Your original PDF is read from Downloads; this report is a new file.

Instructions embedded in either source document are treated as material to analyse, not instructions to execute. No application implementation, account connection, monitoring service or deployment is part of this task.

Throughout this report:

- **Existing difference** means explicitly supported by the supplied designs.
- **Proposed addition** means a recommendation for your team to build.
- **Not specified** means the supplied document does not describe it; it does not prove the other project cannot implement it.
- **Research hypothesis** means an improvement that must be tested.

## 3. How the revised title changes the emphasis

Your exact revised title is:

> A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets

| Title phrase | What the implementation should demonstrate | Evidence for the final report |
| --- | --- | --- |
| Heterogeneous | Components with meaningfully different capabilities and execution costs | Task-to-component mapping and quality/cost comparisons |
| Multi-Agent Framework | Defined responsibilities, structured messages, dependencies and failure handling | Reproducible workflow traces; an agent need not be a permanently running chatbot |
| Financial Event Detection | Identify event type, affected entity, time, facts and source support | Labelled event dataset, extraction metrics and error analysis |
| Cross-Market Signal Fusion | Relate evidence from distinct market families to the selected event | At least one working equity-plus-commodity relationship and a bounded derivatives experiment |
| Indian Financial Markets | Correct instruments, calendars, timestamps, currencies and contract semantics | Documented NSE/MCX mappings and decision-time rules |

The revised title leaves implementation flexibility because it does not list particular model types. Under your latest decision, heterogeneity is demonstrated by the SLM, LLM and deterministic quantitative components. A separate VLM is not required. Update the synopsis abstract, methodology, diagram and objectives to match this decision; the original PDF remains the historical source, not the current architecture specification.

An LLM supports image understanding only if the chosen model and serving interface accept image inputs. A multimodal LLM can cover that role without a separately deployed vision model. This capability is optional here; the core experiment works with text and numerical market features.

Three differently prompted copies of the same model demonstrate role specialization, but do not by themselves demonstrate the model heterogeneity described in your synopsis. Conversely, buying access to many models is unnecessary: benchmark a small number of components chosen for specific jobs.

## 4. Detailed comparison of the two designs

| Dimension | Friend's supplied outline | Your synopsis | Consequence for your build |
| --- | --- | --- | --- |
| Primary workflow | Select a stock, inspect evidence, request reports, test strategies and explore risk; sections 2 and 4 | Detect a catalyst, verify market behaviour and fuse signals; page 2 | Make events the main entry point and stocks the affected entities |
| Market coverage | Indian cash equities first; derivatives explicitly excluded; US equities later; section 1 | Equities, derivatives and commodities; pages 2-3 | Cross-market support is the clearest existing scope difference |
| Event understanding | Dated news/company events, sentiment and relevance; sections 5-6 | Entity resolution, event detection, sentiment and summarisation; pages 2-3 | Formal event schemas and exposure mapping can deepen your event work |
| Market evidence | Price structure, relative volume/strength, permitted liquidity/depth; sections 5 and 9A | Equity technicals, derivatives OI/PCR/IV, MCX and macro evidence; pages 2-3 | Prioritize relationships between market families over competing on depth features |
| Generative roles | News analyst, market/liquidity analyst and reviewer; section 6 | Original PDF has language, vision, quantitative and decision tiers; page 3 | Current design replaces the separate vision tier with SLM task handling, LLM analysis and numerical modules |
| Heterogeneous models | OpenRouter/Ollama providers plus a FinBERT classifier; sections 3, 6-7 | Original PDF has SLM triage, LLM extraction and VLM charts; pages 2-3 | Current SLM-LLM cascade must demonstrate token/latency savings with quality preserved |
| Image input | No explicit VLM chart-analysis tier described | Original PDF specifies a separate VLM tier; removed by your latest decision | Optional images can use a verified multimodal LLM; no separate vision component or required experiment |
| Fusion | Reviewer compares analyst reports; predefined numerical strategy comparisons; sections 6 and 10 | Weighted fusion across signal families; pages 2-3 | Add event-dependent evidence selection and transparent missing-data rules |
| Numerical language | C++17 core with Python interface; section 3 | Python-oriented stack; page 3 | Python is practical for your scope, but language choice is an engineering distinction |
| Liquidity/order flow | Extensive capability-dependent research; section 9A | No comparable detailed order-book module specified | Leave full depth/order-flow work outside your initial scope |
| Monitoring | Separate durable worker, health checks, checkpoints and alerts; section 8 | Orchestration and monitoring tools listed; detailed worker behaviour not specified | Implement dependable collection and scheduled research runs before 24/7 monitoring |
| User tools | Strategy builder, indicator workspace, chatbot and simulation labs; section 4 | Ranked explainable signals and evidence; pages 2-3 | An event casebook and experiment viewer fit your research better |
| Backtesting | Explicit execution/accounting rules and multiple baselines; section 10 | Backtesting, ablation, walk-forward and paper trading listed | Your evaluation needs equally precise operational definitions |
| Monte Carlo | Dedicated bootstrap/GBM risk-scenario lab; section 11 | Monte Carlo/robustness evaluation named | Use focused robustness analysis; a separate simulation product is optional |
| Uncertainty | Missing evidence, disagreement and insufficient-evidence actions; sections 2, 6 and 12 | Confidence and provenance; pages 2-3 | Abstention is shared; measure its effect on coverage and error |
| Data realism | Detailed source capabilities, timestamp, licensing and historical limitations; sections 9-10 | Candidate tools named, with less detailed access specification | Adopt this discipline; your additional markets increase the data burden |
| Research emphasis | Evidence-grounded assistant plus comparative experiments; section 14 | Catalyst-to-confirmation, heterogeneous models and cross-market fusion | Freeze a focused hypothesis instead of accumulating application features |

### Shared features you should not present as exclusive

Both designs already include news, market observations, multiple agents/components, explainable outputs, provenance, historical evaluation, uncertainty and simulations or robustness analysis. Your friend's outline also explicitly addresses events, price/volume confirmation, model budgets, disagreement and temporal leakage.

Accordingly, do not describe their work as merely "sentiment plus lagging indicators". That would misrepresent the supplied outline. Do not claim source links, abstention, paper evaluation or a reviewer agent are unique to yours.

Multi-agent financial analysis is also established prior work. [TradingAgents](https://arxiv.org/abs/2412.20138) describes specialized financial agents and collaborative decision making. Your contribution should be a tested design choice within this area, not a claim to have invented financial agents.

## 5. Differences worth building, ranked

| Priority | Capability | Status relative to your synopsis | Distinction from supplied friend outline | Effort and dependency |
| --- | --- | --- | --- | --- |
| P0 | Structured events plus company/sector exposure mapping | Event extraction exists; explicit exposure map is a proposed addition | Makes cross-market relationships actionable and inspectable | Medium; requires reviewed mappings and event labels |
| P0 | Event-specific cross-market routing and fusion | Extends your proposed weighted fusion | Explicit event-conditioned selection is not described there | Medium; depends on correctly timestamped market data |
| P0 | One real equity-commodity workflow | Already within your scope | Friend's stated scope is cash equities | Medium to high; data access and contract handling matter |
| P0 | Reproducible comparison on common observations | Evaluation is already promised | Establishes effectiveness; this is shared research discipline | Medium; must be designed before tuning |
| P0 | SLM filtering and low-level task handling with escalation | Extends synopsis triage under your latest decision | Explicit task delegation and token/latency evaluation differentiate the proposed execution design | Medium; needs task-level labels and routing checks |
| P1 | One bounded derivatives-context workflow | Already in your synopsis | Derivatives are excluded by friend | High data dependency; start prospective recording early |
| P1 | Structured conflict explanations and feature-removal replay | Extends confidence/provenance | More specific explanation mechanism; general disagreement is shared | Medium; store complete input snapshots |
| P2 | Validated probability calibration or regime-dependent weighting | Proposed extension | Potentially useful but not necessary for initial distinction | High sample-size/overfitting risk |
| Defer | Full knowledge graph, autonomous trading, broad asset coverage | Beyond the minimum needed | Adds scope without ensuring useful evidence | High; unnecessary for the first release |

P0 means build first. P1 means integrate in bounded form after the end-to-end path works. These are connected capabilities within one pipeline, not independent products to build at full scale.

## 6. Capability 1: structured event detection and an impact map

### What to build

Turn a news item or filing into a validated event record. Separate what the source states from the team's hypothesis about market exposure.

Minimum extraction fields:

- Event ID, story cluster ID, source ID and URL.
- Publication time, first-seen time and event-effective time when known.
- Event type and subtype; allow `other` and `uncertain`.
- Mentioned organization and resolved instrument IDs.
- Extracted amounts, units, dates and supporting text spans.
- Whether the item is new information, a correction, or a duplicate, where determinable.
- Model/prompt versions, validation state and processing time.

Start with three event families: earnings, order announcements and commodity supply disruptions. Earnings can be labelled as a business outcome without claiming an earnings surprise: a surprise requires a defensible expectations reference that may be unavailable.

Add a small reviewed exposure table:

```text
event family -> economic mechanism hypothesis -> potentially exposed sector/company
             -> relevant market evidence -> supporting reference -> mapping version
```

A table or JSON configuration is enough initially. A graph database is unnecessary.

### Example

For a reported oil-supply disruption, the event record states the reported facts. A separate mapping proposes potential input-cost exposure for selected oil-consuming businesses. Another mapping may propose different exposure for an upstream producer. These are hypotheses, not universal directional rules.

Company hedging, pricing power, inventory, exchange rates and existing expectations can change the relationship. The model must not invent a company's exposure. Unknown exposure should remain unknown.

### Why it helps and how to assess it

This connects event detection to the cross-market part of your title. Evaluate event-type precision/recall/F1, entity resolution, numerical extraction and support for each exposure link. Include ambiguous subsidiaries, repeated stories and irrelevant articles in the evaluation.

Compare sector-level mapping with company-specific mapping only where reviewed company-level information exists. Do not assume that more detailed model-generated relationships are more accurate.

## 7. Capability 2: event-specific cross-market fusion

### Select evidence according to the question

| Event | Required initial checks | Optional contextual checks | Interpretation limit |
| --- | --- | --- | --- |
| Earnings | Correct company, dated results, stock/sector movement and relative volume | Company fundamentals available at decision time | Growth is not automatically a positive surprise |
| Order announcement | Contract facts, company mapping, price/volume response | Order size relative to previously available company scale | Missing contract economics prevent confident profit claims |
| Commodity supply disruption | Commodity observations, exposed-company mapping, stock/sector response | Currency or market-wide context if actually available | A plausible mechanism is not a proven causal effect |
| Broad market/policy event, later extension | Correct event time, index response and an eligible market-context dataset | Defined derivatives snapshot | Index derivatives do not directly verify one company's economics |

Use a versioned deterministic routing table first. It is easier to debug and compare than allowing an LLM to choose arbitrary tools. The LLM can explain the selected evidence; the routing policy should remain reproducible.

### A transparent initial fusion rule

Keep three outputs separate:

1. **Directional evidence score:** how the directional inputs lean under the chosen policy.
2. **Coverage:** how much required/expected evidence was available and valid.
3. **Conflict state:** whether important observations disagree with the proposed interpretation.

For directional features only, an illustrative baseline is:

```text
direction_score = sum(valid_i * event_weight_i * feature_i)
                  / sum(valid_i * event_weight_i)

coverage = sum(valid_i * event_weight_i)
           / sum(expected_i * event_weight_i)
```

Here, `feature_i` is a predefined normalized directional feature, `valid_i` requires a fresh observation available by the decision time, and weights are nonnegative and versioned. The denominator being zero produces insufficient evidence, not a zero-direction observation. Coverage applies to the predefined event policy, rather than to whichever data happened to arrive.

These are baseline formulas, not proven optimal fusion. Required-input failures must still gate the output even if optional evidence gives a high score. Do not let renormalizing over two remaining inputs imply full evidence coverage.

Volatility, IV, freshness and evidence quality need not be directional. Use them as context, filters or separately defined features. Do not force every input into a bullish/bearish vote. Correlated inputs are not independent confirmations.

Define abstention reasons such as unresolved entity, missing required market, stale input, source conflict or insufficient coverage. Select thresholds and weights using past development/validation data only. A directional score is not a probability of profit.

### The main comparison

Compare a fixed news-plus-equity pipeline with the event-specific cross-market pipeline on the same eligible events. Then compare fixed versus event-specific routing with the same available feature families. This distinguishes the value of extra data from the value of routing.

## 8. Capability 3: bounded commodity and derivatives workflows

### Commodity workflow

Start with one MCX commodity family and a small set of reviewed equity exposures. A commodity observation and an equity observation must have distinct instrument identifiers, source timestamps, currencies, units and calendars.

For futures, retain contract and expiry identifiers and define a roll policy. Joining two contracts without adjustment can create an apparent return caused by the roll. MCX crude and an international USD oil benchmark are not interchangeable series; currency, contract specifications and trading hours matter.

Start with equity outcomes as the prediction target. Using commodity and derivatives inputs does not require simulating trades in all three markets. This preserves genuine cross-market analysis while keeping execution/accounting manageable.

### Derivatives workflow

Use one index and a defined expiry/strike selection. Record the actual snapshot time. Define whether PCR uses open interest or volume, and state the exact included contracts. If IV is available, record whether it is provider-supplied or estimated and under which assumptions.

Rising OI alone does not imply bullishness: contracts have both buyers and sellers. IV describes implied volatility, not direction. Index options are broad market context and should not be presented as stock-specific confirmation without a separately tested relationship.

[Kite's historical-data documentation](https://kite.trade/docs/connect/v3/historical/) describes OHLCV/OI candles and continuous daily history for NFO and MCX futures, with contract-token constraints. This documentation does not establish access to a complete historical options-chain/IV dataset. Verify actual coverage before committing to historical derivatives experiments.

If access is unavailable, keep the adapter and demonstrate a clearly labelled replay from an appropriate sample; report the main scored experiment as equity-plus-commodity. Revisit promised derivatives scope with the guide rather than silently fabricating inputs or calling an equity-only experiment cross-market.

## 9. Capability 4: heterogeneous components with measurable jobs

| Component | Defined job | Output | Comparison needed |
| --- | --- | --- | --- |
| SLM | Filter irrelevant items and handle validated low-level tasks such as coarse event labels and candidate entity matching | Structured labels, candidate IDs, evidence references and escalation status | Against direct LLM handling, filtering-only and a simple classifier/rule baseline |
| LLM | Resolve ambiguous entities, extract complex events, assess supplied cross-market evidence and explain conflicts | Validated event object and evidence-grounded analysis | Against labelled examples; compare with/without SLM delegation |
| Quantitative modules | Compute features, timestamps, eligibility and accounting | Reproducible numbers and status codes | Known examples and time/accounting invariants |
| Fusion module | Apply event policy and missing-data/conflict rules | Score, coverage, reasons and evidence references | Fixed versus event-specific policies |
| Explanation component | Summarize stored findings | Source-supported explanation | Support, consistency and completeness review |

The SLM should route uncertain or complex items onward instead of silently discarding them. Keep exact duplicate hashes, timestamp parsing, canonical identifier lookup and arithmetic in ordinary code where possible; low-level work does not always need model inference. Measure relevant-event recall across the whole pipeline, not just the accuracy of the items it accepted. Missed rare events can outweigh saved model calls.

Choose actual models after a small benchmark on the hardware and budget your team has. Your friend's GPU situation, seven-month estimate and zero-spend constraint are not automatically your constraints. Keep providers interchangeable, record the actual returned model/version, cap retries and cache by content plus configuration.

Report quality, calls per event, input/output tokens separately for the SLM and LLM, end-to-end wall-clock latency, hardware and measured cost. Include retries, validation, queueing and model-loading overhead. If a free provider is used, report calls/tokens and availability failures; zero monetary spend does not mean zero computation. Fewer LLM tokens alone do not prove fewer total tokens or lower latency.

For a fair architectural comparison, report both a same-task quality comparison and a resource-matched comparison. A longer multi-agent run should not receive an undisclosed larger evidence window or unlimited retries.

## 10. Capability 5: SLM task delegation and token-efficient escalation

Use a cascade of deterministic preprocessing, SLM handling and selective LLM escalation. The intended benefit is to reserve the larger model's context and computation for cases that need it. Savings remain a hypothesis until measured on the complete pipeline.

### Task boundaries

| Task | Initial owner | Escalation or validation rule |
| --- | --- | --- |
| Exact duplicate detection, timestamp parsing and canonical lookup | Deterministic code | Flag malformed or ambiguous records; do not spend tokens on exact matches |
| Relevance filtering | SLM | Reject only under a held-out validated policy; forward uncertain items to the LLM |
| Coarse event category and topic tags | SLM | Escalate unsupported, multi-event or uncertain categories |
| Alias/entity candidate selection | Lookup rules plus SLM for ambiguous text | LLM resolves ambiguity against supplied canonical candidates; do not invent tickers |
| Relevant passage selection for a long document | SLM, after validation | Preserve exact source spans, dates, numbers, units, qualifications and negation; fall back to broader context if checks fail |
| Complex event facts, relationships and conflicting evidence | LLM | Validate factual outputs against retained source evidence |
| Cross-market interpretation and final explanation | LLM over stored structured observations | Deterministic eligibility, fusion and numerical checks remain authoritative |

The SLM can complete accepted low-level tasks without sending those same tasks to the LLM again. Relevant events still reach the LLM when complex extraction or reasoning is needed. Log which tasks were accepted, rejected or escalated and why. Treat model self-reported confidence as an uncalibrated routing feature until evaluated; it is not evidence that an item is safe to discard.

### Preserve evidence while reducing context

Pass compact typed records and relevant source passages to the LLM instead of repeatedly sending every article, raw time series and full agent transcript. Retain the original permitted source text and span references for audit and fallback. Check critical dates, amounts, currencies and negation before relying on a reduced context. Token savings that remove decisive evidence are not an improvement.

Cache by content hash, model/prompt version and decision cutoff; a cache hit must not substitute stale observations or an ineligible later source version. Avoid repeated explanations of unchanged events. Use bounded output schemas rather than long intermediate prose.

### Compare three execution policies

1. Deterministic preprocessing followed by LLM-only handling of all model tasks.
2. The same pipeline with SLM relevance filtering only.
3. Filtering plus SLM low-level task delegation and selective LLM escalation.

Keep the event set, model versions, final task and evaluation rules fixed. Measure missed relevant events, extraction errors, source-support failures, LLM tokens, SLM tokens, calls, escalation rate, median/p95 latency and monetary cost where available. Report outcomes over all incoming items and over relevant events so filtering gains cannot conceal lost events.

Use each provider/model's tokenizer or reported usage and identify it. Raw token counts across tokenizers are not directly equivalent units of cost or computation; report per-model counts and measured latency/cost rather than presenting their sum as a universal efficiency measure. Disclose cold and warm runs, cache status and shared-hardware contention. A sequential SLM stage can increase accepted-item latency even while reducing the full workload's cost.

## 11. Capability 6: explain conflicts and replay decisions

Your friend's reviewer already handles disagreement. Your more specific addition should be a structured explanation tied to cross-market evidence.

For each signal, show:

- What the event source actually says.
- Which exposure mapping was applied and why.
- Which observations support or contradict the proposed direction.
- Which expected inputs were missing or stale.
- Which rule produced the score, rank or abstention.
- Which model, prompt, mapping and fusion versions were used.

Add a **feature-removal replay**: recompute the frozen fusion result after excluding one input family. For example, display how the score changes when commodity evidence is removed. This explains sensitivity to supplied inputs; it is not a causal estimate of what would happen if oil prices had never changed.

Use observed price/volume changes only to describe the response already visible by the decision time. Evaluate later returns separately. A price movement following news does not prove that the news caused it or establish how much information remains unpriced.

## 12. Recommended end-to-end architecture

```text
Timestamped news/filings + equity data + eligible commodity/derivatives observations
                                  |
                      immutable records and source metadata
                                  |
                deterministic preprocessing and SLM filtering
                                  |
                 SLM low-level tasks and validated escalation
                                  |
                 LLM event extraction and entity resolution
                                  |
                    reviewed event-to-exposure mapping
                                  |
                       versioned event-specific routing
                                  |
           equity features | commodity context | derivatives context
                                  |
                  fusion + validity gates + conflict checks
                                  |
             ranked event cases / abstentions / source explanations
                                  |
                  frozen paper ledger and experiment results
```

Start as a modular Python application. A practical first stack is Python, pandas/NumPy, typed schemas, one relational store or SQLite pilot, Parquet for bulk observations, one backtesting implementation and a simple dashboard. Add FastAPI when a separate client or service interface is needed.

Your synopsis lists PostgreSQL, Redis, MongoDB, Prometheus, backtesting.py and vectorbt. It does not follow that all are needed on day one. Use one backtesting engine and one primary metadata store. A workflow graph can be introduced when retries, branching and resumability justify it; ordinary typed functions are enough for the first path.

Suggested modules:

```text
src/
  ingestion/          # Adapters, timestamps, deduplication, capability checks
  events/             # Schemas, extraction, entity resolution, annotation
  exposure/           # Reviewed relationship tables and versions
  routing/            # Event-to-evidence policies
  features/           # Equity, commodity and derivatives computations
  models/             # SLM task handlers, escalation and LLM interfaces
  fusion/             # Scores, coverage, conflict rules and abstention
  explanation/        # Evidence rendering and feature-removal replay
  evaluation/         # Splits, backtests, ablations and paper ledger
  dashboard/          # Event casebook and experiment viewer
configs/
tests/
docs/
```

This is a proposed structure, not a claim that these modules currently exist.

## 13. Data contract and output example

### Minimum auditable record

| Group | Required information |
| --- | --- |
| Identity | Event/story IDs, canonical company/instrument ID, market family |
| Source | Source URL/ID, permitted text or extract, content/version hash |
| Time | Publication, first-seen, update, observation-availability and decision times |
| Event facts | Type, entity, extracted amounts/units and evidence spans |
| Exposure | Relationship hypothesis, supporting reference and mapping version |
| Observations | Values, timestamps, provider, currency/unit, expiry where applicable |
| Model trace | Actual SLM/LLM, task owner, prompt version, escalation reason, validity, per-model tokens and latency |
| Fusion trace | Policy version, inputs, score, coverage, conflict and abstention reasons |
| Outcome | Entry rule, hypothetical fill, horizon, fees/slippage and subsequent result |

Store publication and first-seen times independently. If historical first-seen time is unknown, record that limitation and use a documented conservative eligibility policy; do not fabricate precise historical ingestion times. Unknown or absent evidence is not neutral evidence.

### Illustrative output

The following is a fictional schema example, not a real event, observation or recommendation. Null values deliberately avoid invented market measurements.

```json
{
  "event_id": "demo-event-001",
  "event_type": "commodity_supply_disruption",
  "affected_entity": "FICTIONAL_COMPANY_A",
  "event_source_ids": ["demo-source-001"],
  "exposure_hypothesis": "Potential input-cost pressure",
  "exposure_mapping_version": "mapping-v1",
  "decision_time": null,
  "evidence": {
    "equity": {"status": "not_supplied", "observation_id": null},
    "commodity": {"status": "not_supplied", "observation_id": null},
    "derivatives": {"status": "optional_not_supplied", "observation_id": null}
  },
  "direction_score": null,
  "evidence_coverage": 0.0,
  "decision": "insufficient_evidence",
  "reason_codes": ["missing_decision_time", "missing_required_observations"],
  "fusion_policy_version": "fusion-v1"
}
```

An operational bullish/bearish label describes the model's directional output, not permission to short or evidence of profitability. If the paper strategy is long-only, map bearish output to avoiding or exiting a holding under explicit rules.

## 14. Evaluation that establishes effectiveness

### Research questions

- **RQ1:** Does structured event extraction improve over sentiment alone?
- **RQ2:** Does relevant cross-market evidence improve the news-plus-equity baseline?
- **RQ3:** Does event-specific routing improve the quality/resource tradeoff over fixed routing?
- **RQ4:** Does SLM filtering reduce LLM workload while preserving relevant-event recall?
- **RQ5:** Does delegating low-level tasks to the SLM reduce token usage, end-to-end latency or cost beyond filtering alone, while preserving extraction and reasoning quality?
- **RQ6:** Does abstention reduce errors at an acceptable loss of coverage?

### Minimum experiment matrix

| ID | Configuration | Main purpose |
| --- | --- | --- |
| B0 | Buy-and-hold or another explicitly defined benchmark | Financial reference; account for comparable costs and exposure |
| B1 | Deterministic equity price/volume rules | Market-only baseline |
| B2 | News sentiment only | Basic text baseline |
| B3 | Structured events plus equity features | Strong baseline for the central contribution |
| E1 | B3 plus eligible cross-market features with fixed routing/fusion | Value of additional market inputs |
| E2 | Same feature families as E1, event-specific routing/fusion | Value of your routing design |
| A1 | E2 with LLM-only model tasks versus SLM filtering before the LLM | Filtering savings versus missed events |
| A2 | E2 with filtering-only versus filtering plus SLM low-level task delegation | Incremental token, latency and cost effects at comparable quality |
| A3 | Frozen E2 at different predefined abstention settings | Error-versus-coverage tradeoff |

Do not begin with a full factorial search over every possible feature combination. Start with B1-B3 and E1-E2; add the bounded component studies. Report all prespecified runs, including negative results.

### Metrics

| Layer | Useful measurements |
| --- | --- |
| Detection | Per-class precision/recall/F1, entity accuracy, amount/unit correctness, schema validity |
| Exposure mapping | Reviewed-link correctness, unsupported-link rate, unresolved entities |
| Prediction | Predefined five-day outcome metric, class balance and performance by event family |
| Ranking | Precision among the top K eligible events and number of opportunities, if ranking is used |
| Simulation | Net return, drawdown, turnover, exposure, trade count and a clearly defined benchmark |
| Abstention | Coverage and error/accuracy among accepted cases, plus performance of rejected cases where measurable |
| Explanation | Fraction of factual claims supported by stored evidence; numerical consistency and missing-input disclosure |
| Resources | Per-model input/output tokens and calls, median/p95 end-to-end latency, escalation rate, model failures and cost per incoming item/relevant event |

Define the target before tuning. One possible primary target is five-trading-day stock return relative to a sector benchmark from a feasible next-session entry. Define any up/neutral/down thresholds in advance using development data. This benchmark-relative prediction target is separate from the funded paper strategy's realized net return.

### Temporal and statistical controls

1. Use chronological development, validation and final test windows. Keep related story versions together and prevent future-return labels from overlapping later split boundaries.
2. Require `available_at <= decision_time` for every feature, text version and chart. An end-of-day feature cannot justify an earlier same-day trade.
3. Use the next permitted tradable observation for hypothetical fills. Define corporate actions, calendars, costs, slippage and missing-session handling consistently.
4. Compare configurations on the same eligible events/dates. Also report full-input coverage separately so restricting to a convenient subset does not hide missing-data failures.
5. Freeze prompts, models, mappings, thresholds and weights before the final test. Record model/provider changes; do not quietly pool incompatible versions.
6. Account for dependence: many stocks responding to the same macro story are not independent events. Use event/date blocks for appropriate uncertainty estimates and state sample limitations.
7. Limit claims when event counts are small. Ten stocks or a few months of observations may not support many event-specific parameters or probability calibration.
8. Historical LLM tests can be contaminated by pretrained knowledge of later outcomes. [Glasserman and Lin](https://arxiv.org/abs/2309.17322) discuss this issue. Complement historical experiments with a timestamped prospective paper ledger under frozen configurations.

Use block bootstrap or another justified dependence-aware method for robustness, with explicit assumptions. A Monte Carlo result is not proof of future performance. A short forward run establishes observed operation and preliminary outcomes, not durable profitability.

## 15. Scope to freeze for the first release

| Item | Recommended initial boundary |
| --- | --- |
| Target instruments | Fixed 10-stock NSE research universe across 2-3 sectors, with selection rule documented |
| Event families | Earnings, order announcements and one commodity supply-disruption family |
| Decision frequency | End of day at a defined India-market decision cutoff |
| Prediction horizon | One primary five-trading-day horizon |
| Cross-market path | One real equity-commodity relationship; timestamps aligned to the decision cutoff |
| Derivatives | One index/expiry-selection workflow, evaluated on its actual available overlap |
| SLM | One filtering/low-level-task candidate, explicit escalation policy and simple rule/classifier comparisons |
| LLM | One selected configuration for complex extraction, evidence reasoning and explanations |
| Image analysis | Optional use of the selected LLM only if it supports images; no separate VLM tier or required image experiment |
| Simulation | Explicit long-only equity paper policy; no requirement to trade futures/options |
| Dataset | Begin with 30-50 reviewed pilot items; expand toward a few hundred if feasible, without treating this as a statistical sufficiency guarantee |
| Interface | Event list, evidence detail, pipeline trace and experiment results |

Prototype labels should include irrelevant items, uncertain entities, duplicate stories, contradictions and missing observations. Have two team members independently label a subset and resolve disagreements using written guidelines.

Your friend's microstructure and 24/7 monitoring scope is already substantial. Adding those capabilities to your first release would reduce time available for your distinctive experiments.

## 16. What to keep, change and defer

| Action | Recommendation | Reason |
| --- | --- | --- |
| Keep | Your exact revised title | Describes the intended framework without committing the title to model names |
| Keep | Catalyst-to-confirmation and provenance | Central to your synopsis, though not exclusive to your project |
| Strengthen | Structured event/exposure records | Connects source facts to cross-market inputs |
| Strengthen | Weighted fusion into an event-specific, versioned policy | Creates a clear design comparison |
| Adopt | SLM for filtering/low-level tasks and LLM for complex analysis | Implements your current architecture and makes token/latency savings testable |
| Remove | Separate VLM tier and mandatory chart-vision ablation | Superseded by your explicit architecture decision; update the synopsis accordingly |
| Simplify | Storage, orchestration and backtesting tools | Reduces integration burden without weakening the hypothesis |
| Defer | Generic finance chatbot and broad strategy builder | Useful product features, but weak differentiation from the supplied outline |
| Defer | Full depth/order-flow engine and 24/7 alert infrastructure | Separate data/runtime problems outside your first research question |
| Defer | Foundation-model training, deep RL and unrestricted autonomous agents | Not needed to demonstrate this framework |
| Defer | Full portfolios across stocks/options/commodities | Requires substantially different risk, margin, expiry and accounting models |

## 17. Practical build sequence and team ownership

The following is a provisional 12-week engineering sequence, not a confirmed submission schedule. Actual data access, working hours and hardware determine timing. Reserve additional time for prospective observation, analysis and the college report; start data collection early.

| Stage | Deliverable | Exit criterion |
| --- | --- | --- |
| Weeks 1-2 | Scope, source feasibility, event schema and annotated pilot | Reproduce one event-to-equity case; record a go/no-go decision for commodity/derivatives sources |
| Weeks 3-4 | Timestamped ingestion, SLM filtering, entity resolution, extraction and market baseline | Replay 20-30 cases including ambiguity, duplicates and missing data |
| Weeks 5-6 | Reviewed exposure map and one real cross-market path | Show exactly which observations were eligible at each decision time |
| Weeks 7-8 | Fixed and event-specific fusion plus experiment runner | Produce B3/E1/E2 results on a common interval; freeze development decisions |
| Weeks 9-10 | Bounded derivatives integration and SLM filtering/delegation comparisons | Report coverage, quality, per-model token usage and end-to-end latency/cost |
| Weeks 11-12 | Reliability, frozen evaluation, demo and documentation | Another teammate reproduces a representative result from setup instructions |

Start prospective recording as soon as a permitted working adapter exists. Freeze a usable baseline early enough to observe it while later engineering proceeds. Record each version separately; do not retroactively replace earlier paper decisions with improved outputs.

For the four-person team listed in the synopsis, assign responsibilities by strengths:

| Role | Primary ownership | Required collaboration |
| --- | --- | --- |
| Data/backend owner | Ingestion, timestamps, identifiers, storage and source feasibility | Review market eligibility and failure handling with evaluation owner |
| Event/model owner | Annotation, SLM filtering/low-level tasks, escalation, LLM extraction and entity resolution | Review exposure mappings with quantitative owner |
| Quantitative/evaluation owner | Features, contract handling, fusion, backtests and statistics | Review temporal leakage and dataset assumptions with data owner |
| Integration/efficiency owner | Token/latency instrumentation, routing traces, event casebook and reproducibility | Help maintain shared fixtures and compare LLM-only, filtering-only and delegated execution |

Everyone should understand the complete pipeline, review another person's module and contribute to annotation. These are suggested roles, not messages or assignments sent to named teammates.

## 18. What the final demo should prove

Use a prepared casebook drawn from actual eligible data; label any synthetic fixtures clearly.

1. **Clear company event:** correct extraction and mapping, with price/volume context.
2. **Cross-market event:** show why the routing table selects commodity evidence and how it affects the result.
3. **Conflicting case:** plausible event impact but contradictory market observations; show the frozen rule's response.
4. **Missing-data case:** required observations unavailable; produce a reasoned abstention.
5. **Duplicate story:** a second article updates or links to an existing event without becoming an independent signal.
6. **Component comparison:** show fixed/event-specific fusion, then compare LLM-only, SLM-filtered and SLM-delegated execution using recorded quality and resource measurements.

The reviewer should be able to trace a displayed conclusion back to a source, mapping, observation and policy version. The experiment viewer should show where the added complexity helps, fails or costs too much.

An offline replay should work if live providers fail. Label it as replay with original observation times; do not present cached results as fresh inference.

## 19. Synopsis revisions and defensible claims

### Proposed project description

> This project develops a heterogeneous multi-agent framework for extracting structured financial events and combining event-relevant evidence from Indian equity, commodity and derivatives markets. An SLM filters incoming material and handles validated low-level tasks, escalating ambiguous or complex cases to an LLM for event extraction, evidence reasoning and explanations. Deterministic quantitative components compute market observations and enforce eligibility rules. A versioned event-specific fusion policy produces ranked signals or abstentions with source provenance, evidence coverage and conflict explanations. The architecture uses no separate VLM tier; optional image inputs can be handled by the selected LLM if it supports them. Chronological comparisons, task-delegation ablations, token and end-to-end latency measurements, and prospective paper observations evaluate the framework's quality and efficiency.

### Suggested objectives

1. Extract and validate financial events, entities and evidence spans from timestamped sources.
2. Represent reviewed relationships between event families, company exposure and relevant market inputs.
3. Implement and compare fixed versus event-specific cross-market fusion policies.
4. Measure whether SLM filtering and low-level task delegation reduce LLM token usage, end-to-end latency or cost while preserving event recall, extraction quality and source support.
5. Produce auditable signals and abstentions with reproducible input/version traces.
6. Evaluate extraction, prediction, explanations and paper performance without temporal leakage.

### Claims you can make before results

- The framework is designed to test event-specific cross-market fusion.
- It uses heterogeneous components for explicitly different tasks.
- It supports evidence tracing and missing-input handling.
- It is evaluated against specified baselines.

### Claims that require evidence

- Cross-market fusion improves predictive or paper performance.
- SLM filtering saves resources without unacceptable event loss.
- Low-level task delegation improves token/latency/cost measurements beyond filtering alone without unacceptable quality loss.
- The system is better calibrated, more robust or more efficient than a comparison system.

Do not claim the project is globally novel, predicts causal effects, guarantees profits or outperforms your friend's system. Distinction from the supplied outline is a scope comparison; a literature novelty claim requires a broader, verified review. A direct performance comparison with your friend would require both running systems, common data and disclosed resource/execution assumptions.

### Bibliography repair

Your synopsis's StockAgent table and reference disagree on year and attribute the identifiable paper to the wrong authors. The primary record is [When AI Meets Finance (StockAgent), Chong Zhang and coauthors](https://arxiv.org/abs/2407.18957), first submitted in July 2024 and subsequently revised. Cite the exact version or publisher record you read.

The remaining synopsis references have not all been verified in this comparison. Resolve exact titles, authors, venues and identifiers before using their claimed limitations to establish a research gap. A plausible-looking reference is not sufficient evidence.

## 20. Build acceptance checklist

- [ ] Use the revised title consistently in your README, report and presentation.
- [ ] Distinguish documented proposals from implemented features.
- [ ] Freeze a stock universe, event taxonomy, decision cutoff and outcome horizon.
- [ ] Confirm source access and actual historical/prospective coverage.
- [ ] Run one complete event-to-equity path with stored evidence.
- [ ] Run one genuine cross-market path with reviewed exposure mapping.
- [ ] Implement fixed and event-specific policies with explicit missing-data gates.
- [ ] Preserve a bounded derivatives workflow or document an agreed scope limitation.
- [ ] Implement the SLM filtering, low-level-task and LLM escalation boundaries.
- [ ] Compare LLM-only, filtering-only and filtering-plus-delegation policies on the same inputs.
- [ ] Measure per-model tokens, event recall, extraction quality and end-to-end latency/cost.
- [ ] Replace the separate vision tier in synopsis text/diagram with the current SLM-LLM architecture.
- [ ] Produce common-period baseline comparisons and uncertainty analysis.
- [ ] Run and preserve a frozen prospective paper ledger.
- [ ] Demonstrate contradiction, duplicate and missing-input cases.
- [ ] Repair the bibliography and record negative experiments.
- [ ] Make a representative run reproducible from setup instructions.

## 21. Sources and verification limits

### Supplied primary materials

- [Your synopsis PDF](<C:/Users/arnab/Downloads/Project Synopsis Generative AI Stock Investment Platform.pdf>): pages 1-4, including the page 3 architecture. Your revised title and latest removal of a separate VLM tier override the original title and vision-tier requirements for this report. The PDF itself has not been edited.
- [Friend's supplied outline](<C:/Users/arnab/.codex/attachments/7b8f0d6d-d391-424a-88eb-67ae24875add/Pasted text.txt>): updated 23 October 2026. Sections 1-16 provide the comparison evidence. Its provider/pricing assertions are not independently adopted as current requirements here.
- [Your committed planning README](https://github.com/Arnab-apk/Final_Yr_Proj/blob/7628f0911f0602fa628412d600120eb6103e93a5/README.md): read through local Git history for context; not evidence of runnable code.

### External primary sources checked for this report

- [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138): supports the statement that specialized multi-agent financial workflows are established prior work. It does not validate this report's proposed cross-market design.
- [When AI Meets Finance (StockAgent)](https://arxiv.org/abs/2407.18957): supports the author/title/submission-history correction.
- [Kite Connect historical-data documentation](https://kite.trade/docs/connect/v3/historical/): supports the stated candle, futures-continuity and token limitations. Account entitlement, data rights and actual access still require project-specific checking.
- [Glasserman and Lin, Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis](https://arxiv.org/abs/2309.17322): supports the historical-LLM evaluation caveat; this report does not reproduce their experiments.

All proposed performance benefits, economic exposure relationships, architecture choices and schedules in this document are recommendations or hypotheses. No profitability, model benchmark or head-to-head application result was measured during this comparison.
