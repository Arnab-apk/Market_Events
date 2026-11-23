# Viva: 27 likely examiner questions with grounded answers

Project: *A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets*. Implementation: **Market Events**.

Each answer was checked against the source on 2026-11-21. Citations use file plus function or constant
names, because line numbers move while other agents edit the code. "Synthetic" means authored fixtures:
`tests/fixtures/README.md`.

## A. Design and boundary

**1. Where exactly does the LLM stop and Python start?**
The model does two bounded tasks: relevance filtering (`agents/filter_agent.filter_article`) and
structured extraction (`agents/event_agent.extract_event`). Both go through `ModelClient.ask`, which
validates JSON against a Pydantic schema (`model_client.py`). Python does the rest: company resolution
(`exposure.resolve_company`), the exposure rule (`exposure.find_exposure`), features
(`market_features.compute_market_features`), and the score, label and abstention (`fusion.assess_evidence`).
No model output ever becomes a number in the score.

**2. How do you stop the model hallucinating facts?**
Grounding checks in `event_agent.extract_event`: every `source_span` must appear verbatim in `article.text`.
Every amount's value must appear as an exact numeric token in its span, with its unit and scale. Otherwise
`validation_status = "unsupported"`. Fusion then abstains ("Event extraction is not validated",
`fusion.py`). The company must be matchable from reviewed aliases present in the text. A conflicting model
`company_id` is discarded and the result becomes `unresolved`.

**3. What if the small model wrongly rejects a relevant article?**
`filter_agent.filter_article` turns an "irrelevant" verdict with no verbatim supporting span into
"uncertain", which escalates to LLM extraction. Unsupported filter spans also become "uncertain". A
*grounded* wrong rejection is still unrecoverable. That is the key cascade risk, and per-policy filter
recall is the metric for it (`RESEARCH_BRIEF.md` §1.7). The pilot forwarded 24 of 24 expected items, but
on synthetic data only (`runs/local_model_pilot.json`).

**4. Why not just ask GPT whether the news is bullish?**
That is neither reproducible nor auditable, and it is exposed to parametric look-ahead (Glasserman & Lin
2023). Here the direction comes from observed market data under frozen, versioned rules
(`configs/fusion_rules.json`, version `fusion-v1`). The same saved inputs always give the same score, and
`experiments.compare_ablations` recomputes it exactly.

**5. Is this a trading system?**
No. It is a long/cash *research* tool with no order path or brokerage integration (`docs/DECISIONS.md`,
Scope). Outcomes are hypothetical, and negative evidence is never turned into a short (`outcomes.py` docstring).

## B. Time and look-ahead

**6. Why do you need both `published_at` and `first_seen_at`?**
Publication time says when the source existed in the world. First-seen time says when *this dataset* had
it. A backfilled article can have an old publication date but only have reached us later. Both must be ≤
the cutoff (`pipeline.analyse_article` eligibility filter and its `ineligible` check). The same logic
applies to observations (`timestamp` and `available_at`, in `market_features.series`) and to exposure rules
(`effective_at` and `known_at`, in `exposure.find_exposure`).

**7. What are the kinds of look-ahead, and which have you handled?**
(1) Data availability: handled by the two-timestamp rule everywhere, and provider downloads stamped with
their real fetch time (`live_data.py`). (2) Revisions: handled. The ledger is append-only (SQLite triggers
in `storage.py` raise "Saved records are immutable"), price revisions are reported as conflicts, and
requests are hashed over a frozen config snapshot (`pipeline._snapshot`, `request_key`). (3) Parametric
model knowledge: **not tested**. It is limited because the model only extracts, never scores, and the
bundled articles are synthetic, so they cannot have been memorised. On real news, pretrained knowledge
could still bias relevance or event type. The planned test is an entity-anonymisation ablation
(Glasserman & Lin 2023) plus pre/post knowledge-cutoff splits.

**8. Could I download today's prices and analyse a 2020 decision?**
Not as decision evidence. Downloaded bars get `available_at` set to the actual download time, so they fail
`available_at ≤ cutoff`. The strategy lab is explicitly retrospective and says so in its manifest
("recorded availability is never backdated", `api.research_manifest`).

**9. What happens with stale data?**
If the latest bar in a return pair is more than 4 calendar days before the cutoff, the feature is marked
stale (`market_features.returns`). `fusion.available()` treats stale as missing, so a mandatory stale input
forces abstention.

## C. Scoring

**10. Walk me through the score.**
E = clip(excess_return / 0.02, −1, 1). For commodity disruptions, C = clip(commodity_return ×
rule.direction / 0.03, −1, 1), and score = Σ wᵢ·componentᵢ / Σ (weights of available components), with
weights 0.6 and 0.4. Coverage = available weight / configured weight. Labels: ≥ 0.15 positive, ≤ −0.15
negative, otherwise neutral. Demo `syn-002`: E = 0.40, C = −0.50, score 0.04, neutral, with a conflict
(`fusion.assess_evidence`; verified in a scratch replay on 2026-11-21).

**11. Where do 0.6 / 0.4, 0.02 / 0.03 and 0.15 come from? Are they calibrated?**
They are not calibrated. They are a frozen, conceptual demonstration policy. The config's own provenance
field says "Frozen conceptual demonstration policy, not calibrated probabilities"
(`configs/fusion_rules.json`). Fitting them needs labelled real data with a temporal split (future work).

**12. Is the score a probability or confidence?**
No. It is a signed evidence strength in [−1, 1]. Coverage measures how much of the configured evidence
was available, not how confident we are. Calibration metrics (Brier, ECE) therefore don't apply. The UI
says "Evidence completeness, not predictive confidence" (`web/app/_components/premium-overview.tsx`). The
result view prints the arithmetic under "How the score was built", for example `0.6 × (+0.40 equity vs
benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted) = +0.04 → neutral (threshold ±0.15)`, beside
"Threshold ±0.15" and "Minimum 60%" (`workspace-panels.tsx` `RunSummary`; text from `plain_language.py`).

**13. Why abstain instead of returning a partial score?**
A partial score can look confident while hiding a missing mandatory input. If a required feature, a valid
reviewed exposure, validated extraction, a resolved company, or resolved source history is missing, the
direction is `abstain` and the reasons are listed. The partial score is still kept for audit
(`fusion.assess_evidence`, `reasons`; and the unresolved-memory override in `pipeline.analyse_article`).

**14. Why does a missing commodity price force abstention for a supply-disruption event?**
For that event family, the commodity channel *is* the hypothesis. `required_features` lists
`commodity_return` and `exposure` (`configs/fusion_rules.json`). Without them, an equity-only number would
answer a different question. The equity-only variant is still available as an explicit ablation.

**15. Where does the −1 crude sensitivity for paint makers come from?**
It is a synthetic, reviewed assumption, labelled "Conceptual synthetic input-cost sensitivity assumption;
not empirically validated" (`configs/exposure_rules.json`). It is motivated, not validated, by secondary
press figures: crude-linked inputs are roughly 30–50% of paint raw-material costs, and ATF is roughly
35–40% of Indian airline operating costs (`RESEARCH_BRIEF.md` §1.5, marked [S]). The sign is
firm-specific. A refiner such as Reliance can have the opposite or a state-dependent sensitivity, which is
why rules are reviewed, versioned and cutoff-dated rather than learned. For real data,
`configs/live_exposure_rules.json` holds direction-only rules for Asian Paints, Berger and IndiGo on
`LIVE:MCX:CRUDEOIL`. They are [S]-sourced, pending team review, with `known_at` 2026-11-21, so they cannot support an
earlier cutoff. Reliance and Pidilite are reviewed without a rule, so they abstain.

## D. Models and policies

**16. What is the difference between the three policies?**
`llm_only` uses the LLM to filter and extract. `slm_filter` uses the SLM to filter and the LLM to extract.
`slm_delegate` does the same, plus it passes the verified filter output to the LLM as hints
(`pipeline.analyse_article`, `role` and `delegated`). Extraction always receives the full article. The UI
labels say what each does: "Large model does both steps", "Small model screens → large model extracts" and
"Small model screens and hands over hints → large model extracts" (`web/app/_components/types.ts`).

**17. Did the small model save cost?**
Not on our data. The archived live comparison on 7 synthetic articles per policy shows `llm_only` with
8 calls (6,978 input / 1,075 output tokens, mean 3.8 s/run), `slm_filter` with 9 calls (8,173 / 1,292,
21.9 s) and `slm_delegate` with 9 calls (8,507 / 1,314, 20.0 s) (`runs/policy_comparison.json`). Latencies
mix cold and warm local calls, so they are not a benchmark. Replay cannot show differences at all, because
it returns the same recorded output for every role (`ModelClient._replay`). A cost model now exists in
code (`experiments.estimated_cost`). It is computed only for live groups with complete token counts, and
is null otherwise.

**18. Which models did you use?**
For live development: `qwen3.5:2b` in the SLM role and `gemma4:e4b` in the LLM role, both via Ollama
(`runs/handover.usage.json` call records). They are configured through `SLM_MODEL` and `LLM_MODEL` in the
environment (`config.load_settings`). Requests use temperature 0 and JSON mode (`ModelClient._live`).

**19. How good is the extraction? Precision and recall?**
There is no real-data P/R/F1. That is a stated gap. On synthetic inputs, 3 of 3 `gemma4:e4b` extractions
were grounded after the typed-amount schema fix, and the earlier smoke run had only 1 of 3
(`runs/local_smoke.json`, kept on record). The backend has added `experiments.extraction_agreement(runs,
gold)`, which reports filter recall and precision, field accuracy, validation rates and abstention per
policy against authored gold labels. It is explicitly a "synthetic sanity check, not a benchmark". A real
evaluation needs a 200–500 article gold set with two annotators and Cohen's κ.

**20. What stops runaway cost or infinite retries?**
Per-run budgets in `config.Settings`: `max_requests = 4`, `max_tokens = 24000` (a conservative byte-based
admission estimate, not provider tokens), at most 2 attempts per task, and a 120 s timeout. Exceeding a
budget raises `BudgetExceeded`, and the run is saved as `partial` (`model_client.ask`, `pipeline.analyse_article`).

## E. Outcomes, strategy lab, evidence

**21. Isn't comparing the score with the outcome circular?**
No. The score uses the *reaction-day* excess return already observable at the cutoff. The outcome is a
market-adjusted (beta = 1) return from the **next** session's 09:15 IST open to the 5th observed session's
close, minus 10 bps round trip. It measures post-cutoff drift (`outcomes.evaluate_outcome`). It has no
estimation window, beta, aggregation or test statistic. A market-model CAR with BMP tests (MacKinlay 1997;
Boehmer et al. 1991) is future work.

**22. Why are all three demo outcomes +4.58%?**
The synthetic fixture prices are constant geometric paths: every equity rises 1% per session, the
benchmark 0.2% and crude 1.5% (`tests/fixtures/market_prices.csv`). The identical numbers prove the
mechanics (entry and exit dates, costs, benchmark alignment), not anything about markets.

**23. How do you avoid overfitting in the strategy lab?**
Fills happen at the next observed open after a close signal, with fees and adverse slippage on every fill
(`strategy_lab.run_backtest` assumptions). The study is capped at 2020-12-31. The Sharpe is for a single
configuration. We do not log trials, so there is no deflated Sharpe or PBO yet (Bailey & López de Prado
2014). The engine now also reports `probabilistic_sharpe` with the note "single configuration; not
deflated for the number of configurations tried" (`strategy_lab.probabilistic_sharpe`). On stage, the
configuration is fixed in advance and only costs are stressed (×2). A walk-forward split
(`strategy_lab.walk_forward`; `walk_forward_split` on `POST /api/backtest`) runs the same fixed configuration
independently on in-sample and out-of-sample segments. On the demo's zero-drift random walk, both halves
lose (−41.4% for 2015–2019, −17.5% for 2020), which is the correct "no edge" answer. A single split is a
robustness check, not proof of an edge. With 20 trades, it is below a 30-trade low-sample threshold.

**24. What does the Monte Carlo tell me?**
It is a seeded PCG64 overlapping moving-block bootstrap of the strategy's own daily returns, without
wrap-around (Künsch 1989; `strategy_lab.monte_carlo`). It shows dispersion under resampled history. The
"loss frequency" is not a probability of future loss. Regime changes and survivorship are not captured.

**25. What is actually verified, and what isn't?**
Verified: 561 automated tests pass (`pytest -q`, 2026-11-21) across ingestion, immutable storage, routing,
fusion, features, technicals, outcomes, strategy lab, API and UI workflows (`tests/`). The offline replay
demo is reproducible. Not verified: a real provider-account connection (the adapter is tested only with
mocked HTTP, per `docs/LIVE_SETUP.md`), predictive quality, profitability, exchange-calendar completeness,
corporate-action adjustment, and screen-reader behaviour. All bundled data is synthetic.

## F. Framing and scope

**26. Where is the multi-agent part?**
The framework uses specialised, heterogeneous agents. Three are language-model agents: the SLM filter agent
(`agents/filter_agent.py`), the LLM event agent (`agents/event_agent.py`) and the optional explanation
agent (`agents/explanation_agent.py`). Three are deterministic quantitative agents: exposure
(`exposure.py`), market features (`market_features.py`, plus `technicals.py` for context) and fusion
(`fusion.py`). A pipeline orchestrator (`pipeline.analyse_article`) coordinates them. It routes the filter
to the SLM or the LLM by policy, passes verified hints only under `slm_delegate`, and records message-level
provenance: every model call is traced with model, prompt hash, request hash, status, latency and tokens
where reported (`model_client.ask`, `ModelCall`), and saved atomically with the run (`storage.py`). These
are **not** autonomous, negotiating agents. They don't choose their own goals, talk to each other freely
or loop. That is deliberate, because a fixed, replayable orchestration is what makes every decision
auditable. "Heterogeneous" refers to mixing model sizes (SLM and LLM) with deterministic agents.

**27. Why did the scope change from the synopsis?**
Each change chose auditability and honesty over breadth (slide 3):
- **Confidence → evidence coverage plus abstention.** We have no labels to calibrate a probability, so we report how much evidence was available and abstain when mandatory inputs are missing.
- **Ranked recommendations → signed evidence score.** This avoids giving investment advice.
- **Sentiment → structured event extraction.** Grounded spans can be verified; a polarity score can't.
- **Tooling.** Kite → Upstox, for a free read-only analytics token. PostgreSQL → SQLite, for a single-user, portable, append-only ledger. backtesting.py/vectorBT → a small audited engine whose fill, cost and assumption rules are explicit and tested. LangGraph → a deterministic orchestrator that replays exactly.
- **Ablation → commodity sensitivity comparison** on frozen inputs (`experiments.compare_ablations`).
- **Additions not in the synopsis:** point-in-time cutoffs on every input, and outcomes kept separate from decisions.
- **Delivered after the synopsis review:** a single walk-forward split for a fixed backtest configuration (rolling multi-split walk-forward remains future work).
- **Deferred to future work:** a VLM chart tier, derivatives (OI, PCR, IV), live paper trading, real-market evaluation, and Redis/MongoDB/Prometheus, because none could be verified honestly with synthetic data and no live account in the time available.

Several synopsis references could not be verified, so citations now come only from [V] entries in
`docs/research/RESEARCH_BRIEF.md`.

---

## Quick-reference numbers (all synthetic; source in brackets)

| Item | Value |
| --- | --- |
| Fixture size | 35 articles, 128 bars (8 instruments × 16 sessions) [`tests/fixtures/README.md`] |
| Demo cutoff | 2026-01-12 12:00 UTC = 17:30 IST [`pipeline.run_demo`] |
| `syn-001` / `syn-003` | positive, 0.40, coverage 100% [scratch replay 2026-11-21] |
| `syn-002` | neutral, 0.04, coverage 100%, conflict. Equity-only ablation positive 0.40. |
| `syn-031` / `syn-032` | duplicate (0 calls) / update of `syn-001` |
| Demo outcomes | gross 4.58%, net 4.48%, benchmark 0.90% (constant-growth fixtures) |
| Pilot | 30 filters, 0 failures, 24/24 forwarded; 3/3 grounded extractions [`runs/local_model_pilot.json`] |
| Live policy calls | 8 / 9 / 9 (llm_only / slm_filter / slm_delegate) [`runs/policy_comparison.json`] |
| Tests | 561 passed [`pytest -q`, 2026-11-21, after the cleanup and feature commits] |
| Step-7 lab (random walk, SMA 20/50, 2015–2020) | −52.5% vs buy and hold +33.8%; Sharpe −0.79; PSR 0.025; 20 trades. 2× costs: −55.3%. Walk-forward: −41.4% in-sample, −17.5% out-of-sample [`POST /api/backtest`, 2026-11-21] |
