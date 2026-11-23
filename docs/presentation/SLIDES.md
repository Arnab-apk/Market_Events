# Slides: A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets

Final-year project presentation, 1 December 2026. The software implementation is called **Market Events**.

14 slides, about 14 minutes of talk before the live demo (`DEMO_SCRIPT.md`) and the viva (`VIVA_QA.md`).
Every number on these slides was checked against the code or a saved artifact on 2026-11-21. Sources are
given in each slide's notes. **All bundled articles, prices and replay outputs are synthetic.** Keep the
synthetic label visible whenever a number is on screen.

Facts checked on 2026-11-21:
- `pytest -q`: **561 passed** (re-run after the cleanup and feature commits, 2026-11-21).
- Replay demo (re-run in a scratch database): `syn-001` earnings gives positive evidence, score 0.40,
  coverage 100%. `syn-003` order gives positive evidence, 0.40, 100%. `syn-002` crude-oil disruption gives
  neutral/mixed evidence, 0.04, 100%, with a conflict flag.
- Archived live development records (`runs/policy_comparison.json`, `runs/local_model_pilot.json`) use
  authored synthetic inputs. These files are gitignored and may be missing on a fresh checkout.
- Literature comes from `docs/research/RESEARCH_BRIEF.md`. Slides cite **only entries marked [V]**
  (bibliographic record verified; summary from the abstract). Industry cost shares are **[S]** secondary
  press sources and are labelled as such.
- **Reference note:** several references in the original synopsis could not be verified. Replace every
  synopsis reference with entries marked **[V]** in `docs/research/RESEARCH_BRIEF.md` (slides, report
  and bibliography). Do not carry unverified synopsis citations forward.

---

## Slide 1: Title

**A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets**

*Implemented as **Market Events**, a local, auditable research workbench*

- Heterogeneous agents: an SLM filter agent, an LLM event agent and an optional explanation agent, plus deterministic quantitative agents (exposure, market features, fusion)
- Turns dated news plus NSE equity and MCX commodity prices into source-grounded, deterministic evidence assessments. Models interpret; Python decides.
- Look-ahead-safe by construction, with every decision saved and auditable
- Local stack: Python research engine, FastAPI service, Next.js dashboard

**Speaker notes:** Say the full title once, then "which I implemented as Market Events", and use the short name afterwards. Introduce the project in one breath: "Given a news article and a decision time, what
does the evidence that was actually available at that time say, and can I prove it later?" Say early
that this is a research tool, not a trading bot. It places no orders (`docs/DECISIONS.md`, Scope).

---

## Slide 2: Problem and research questions

- News is unstructured, repeated and revised. "Ask an LLM if it's bullish" is neither reproducible nor auditable, and it can leak hindsight.
- RQ1: Can the model's role be limited to *interpretation*, with every numeric decision deterministic?
- RQ2: Can the system make it structurally impossible to use information unavailable at the decision cutoff?
- RQ3: Does routing the filter stage to a small model (SLM) cut cost without breaking extraction?
- RQ4: Can later outcomes be measured without contaminating the original decision?

**Speaker notes:** These are engineering research questions. RQ1, RQ2 and RQ4 are answered by
construction and by tests. RQ3 is only explored, and on our synthetic development data the honest answer
is "not shown" (slide 14). Say so now, so the examiners know we are not overclaiming.

---

## Slide 3: Synopsis to implementation

| Delivered | Changed (and why) | Future work |
| --- | --- | --- |
| Catalyst-to-confirmation pipeline (news event → market confirmation → fused evidence) | "Confidence" → **evidence coverage + abstention**: a coverage figure doesn't pretend to be a calibrated probability | VLM chart-reading tier |
| SLM triage + LLM extraction, with three comparable policies | Ranked recommendations → **signed evidence score**: no investment advice | Derivatives signals (OI, PCR, IV) |
| Entity resolution from reviewed aliases | Sentiment → **structured event extraction**: grounded, verifiable fields instead of polarity | Rolling multi-split walk-forward (one split delivered) |
| Optional explanation agent (separate child run) | Kite → **Upstox** (free read-only analytics token); PostgreSQL → **SQLite** (single-user, portable, append-only triggers) | Live paper trading |
| Equity confirmation: benchmark excess return (scored); RSI and other technicals, plus volume ratio (recorded as context) | backtesting.py / vectorBT → **audited custom engine** (next-open fills, explicit costs, inspectable assumptions) | Real-market evaluation (dated corpus, gold labels) |
| MCX commodity confirmation via reviewed exposure rules (synthetic demo; live near-month MCX crude path offline-tested) | LangGraph → **deterministic pipeline orchestrator** (reproducible, replayable, no hidden agent state) | Redis / MongoDB / Prometheus for scale and monitoring |
| Weighted, explainable fusion | Ablation → **commodity sensitivity comparison** on frozen inputs | Proper event study (CAR, BMP), deflated Sharpe and PBO |
| Message-level provenance and immutable runs; backtesting with a **walk-forward split** (in-sample vs out-of-sample, fixed config), Monte Carlo, FastAPI | **Added, not in the synopsis:** point-in-time cutoffs on every input; outcomes kept separate from decisions | Parametric look-ahead tests; SLM-extract-then-escalate policy |

- Every change trades breadth for auditability. The scope is narrower than the synopsis, and every claim can be checked.

**Speaker notes:** The Delivered column is verified in code: `pipeline.py`, `agents/`, `exposure.py`,
`market_features.py`, `technicals.py`, `fusion.py`, `storage.py`, `strategy_lab.py` and `api.py`. Be precise
about equity confirmation. Only the benchmark excess return enters the score; RSI and the other
technicals, and the volume ratio, are computed and saved as context but never scored (`fusion.assess_evidence`).
"Message-level provenance" means every model call is traced with model, prompt hash, request hash,
status, latency and tokens where reported. The bottom two rows of Future work come from
`RESEARCH_BRIEF.md` §4b. If asked why the scope changed, use VIVA_QA question 27.

---

## Slide 4: Why cross-market evidence? Commodity exposure

- An oil supply shock reaches firms the article never names: input costs for paint makers, fuel costs for airlines
- Paints: crude-linked inputs (solvents, resins, emulsions) are roughly **30–50% of raw-material costs** *(secondary press sources)*
- Airlines: aviation turbine fuel is roughly **35–40% of Indian airline operating costs** *(secondary press sources)*
- The sign is not universal: **Reliance** (refining/upstream, in our live universe) can have opposite or state-dependent crude sensitivity
- So exposure is a **reviewed, versioned, cutoff-dated rule**, not a learned black box. *The demo rules are synthetic.*

**Speaker notes:** Sources are in `RESEARCH_BRIEF.md` §1.5, all marked **[S]**: Upstox News on paint
stocks, and Business Standard (Oct 2026) on IndiGo's fuel charges. Figures vary by source, so present them
as "roughly" and "per press commentary". They are not verified against annual reports. Do **not** quote
the 55–60% airline figure; its primary source is unverified [U]. Our rules in `configs/exposure_rules.json`
use direction −1 for all five demo companies and are labelled "Conceptual synthetic input-cost sensitivity
assumption; not empirically validated". The press figures show *why* −1 is plausible. They do not validate
the rules. Live rules now exist (`configs/live_exposure_rules.json`): Asian Paints, Berger and IndiGo at −1 on
`LIVE:MCX:CRUDEOIL`, sourced [S] and pending team review, with `known_at` 2026-11-21. Reliance (sign ambiguous) and
Pidilite (unsourced) are reviewed *without* a rule, so a Reliance crude case abstains, and so does any real
article analysed at a cutoff before 21 November 2026. That is correct behaviour.

---

## Slide 5: Related work and novelty

- **LLMs in finance:** FinBERT (Araci 2019), BloombergGPT (Wu et al. 2023), FinGPT (Yang et al. 2023), the FinBen benchmark (Xie et al. 2024). Most work asks the model for sentiment or direction (e.g. Lopez-Lira & Tang).
- **Event-driven lineage:** Ding et al. (IJCAI 2015), and Trade the Event / EDT (Zhou et al., Findings of ACL 2021). JSON span extraction: Choi & Park (2025).
- **Cascades and routing:** FrugalGPT (Chen et al. 2023), RouteLLM (Ong et al., ICLR 2025), unified routing and cascading (Dekoninck et al., ICML 2025). *Our gate is a deterministic span check, not a learned scorer.*
- **Look-ahead and methodology:** Glasserman & Lin (2023), chronologically consistent LLMs (He et al. 2025), event studies (MacKinlay 1997; Brown & Warner 1985), and backtest overfitting (Bailey & López de Prado 2014)
- **Novelty, to our knowledge and based on a limited literature search:** models confined to grounded extraction; deterministic, versioned fusion of the benchmark-relative reaction with a reviewed, cutoff-dated commodity channel; abstention on missing evidence; an append-only ledger that replays every decision exactly

**Speaker notes:** All entries above are marked [V] in `RESEARCH_BRIEF.md` §1. They replace the synopsis references, several of which could not be verified. Summaries come from
abstracts, not full texts. Quote numbers from the papers themselves, not from these slides. If asked about
Lopez-Lira & Tang, say the abstract changed across versions, and cite the version you name. Defend these
design claims, not performance claims (brief §2):
1. The model never emits a score.
2. Commodity exposure propagates the event to firms the article doesn't name, with `effective_at` and `known_at` dating.
3. Point-in-time discipline at every layer, plus request idempotency.
4. An explainable cascade gate, with an honest negative result on call savings.
5. Indian market setting (NSE, IST sessions, MCX crude).

Never say "first" or "novel" without "to our knowledge".

---

## Slide 6: System architecture

- Next.js dashboard → allow-listed same-origin proxy → FastAPI on loopback → shared Python engine
- `pipeline.analyse_article`: freeze config → reuse check → filter → extract → features → fuse → save
- SQLite ledger: append-only runs, model calls and assessments (database triggers). Outcomes are stored separately.
- Two model modes: **replay** (recorded fixtures, offline) and **live** (Ollama or an OpenAI-compatible endpoint)
- Self-explaining UI: a 7-step guided demo tour, glossary and tooltips, a plain-English verdict and a "How the score was built" formula

Diagram: `docs/presentation/ARCHITECTURE_DIAGRAM.md` (mermaid, with a plain-text fallback).

**Speaker notes:** Walk the diagram left to right. The proxy forwards only listed endpoints and rejects
cross-origin writes (`web/app/api/research/[...path]/route.ts`; `api.py` `local_boundary`). Saved records
are immutable: SQLite triggers `RAISE(ABORT, 'Saved records are immutable')` (`storage.py`). Identical
requests are hashed and reused instead of re-running inference (`pipeline.py`, `request_key`,
`lookup_request`). The original Streamlit app (`app.py`) still runs on the same engine. The guided tour is
`web/app/_components/demo-tour.tsx`. The plain-English summary, reasons and score formula are display-only
fields built by `plain_language.py` from the saved components. They are never stored, so the immutable
decision record is unchanged.

---

## Slide 7: Models interpret, Python decides

- Models do two bounded tasks: **filter** (relevance) and **extract** (event type, company, amounts, verbatim spans)
- Every output is schema-validated (Pydantic). Spans must appear verbatim in the source, and amounts must match value, unit and scale.
- Company identity is resolved in Python from reviewed aliases. A disagreeing model guess is discarded.
- The score, coverage, label and abstention are computed in `fusion.py`. **No model ever outputs a score.**
- The optional explanation must equal the saved deterministic text and spans. It is a separate child run.

**Speaker notes:** Show `agents/event_agent.py` lines 34–56: any span not in `article.text`, or an
amount whose number, unit or scale isn't in its span, sets the result to `unsupported`. Fusion then
abstains ("Event extraction is not validated"). In `filter_agent.py`, an "irrelevant" verdict with no
supporting span becomes "uncertain" and is escalated rather than dropped. `pipeline.explain_run` saves the
explanation as a child run, so it cannot alter the parent.

---

## Slide 8: Look-ahead-safe cutoffs

- Four timestamps: article `published_at` and `first_seen_at`, observation `timestamp` and `available_at`
- Evidence is eligible only if **both** of its times are ≤ the decision cutoff
- Exposure rules also need `effective_at` ≤ cutoff **and** `known_at` ≤ cutoff
- Provider downloads record their real fetch time as availability, so history downloaded today cannot backfill a past cutoff
- Stale inputs (latest bar more than 4 calendar days before the cutoff) are flagged and gated out by fusion

**Speaker notes:** Code: `pipeline.py` lines 83–102 filter observations and articles on both times.
`market_features.py` `series()` repeats the check, and lines 66–67 mark staleness.
`exposure.find_exposure` picks the latest vintage known at the cutoff. Demo proof (re-run 2026-11-21):
`syn-002` at a 07:00 UTC cutoff, before its 08:00 publication, returns status `ineligible` with "Article
publication/first-seen time is later than the decision cutoff". At 10:30 UTC (16:00 IST), the equity close is
available but the crude bar (11:00 UTC) is not, so the same article **abstains** with "Missing or stale mandatory
commodity return". The partial score of 0.40 at 60% coverage is withheld.

---

## Slide 9: Three kinds of look-ahead

| Kind | What leaks | Status here |
| --- | --- | --- |
| 1. Data availability | Information used before it existed in the dataset | **Handled:** two timestamps on every article, observation and exposure rule; real fetch time on provider data |
| 2. Revisions | What was known gets silently replaced | **Handled:** append-only ledger, price revisions reported as conflicts, requests hashed over a frozen config |
| 3. Parametric knowledge | The model already "knows" what happened next | **Not tested.** Limited by design: the model only extracts, and our articles are synthetic. |

- Residual risk on real news: pretrained knowledge could still bias relevance or event-type decisions
- Planned test: entity-anonymisation ablation (Glasserman & Lin 2023) and pre/post knowledge-cutoff splits

**Speaker notes:** Source: `RESEARCH_BRIEF.md` §1.3. For kind 2, revisions show up as conflicting
observations in `live_data.sync_live` reports, and storage rejects conflicting inserts (`storage.py`
triggers). For kind 3 the honest framing is "mitigated, not measured". The model never emits a
direction or score, and synthetic articles cannot have been memorised. Do not claim it is solved.

---

## Slide 10: Fusion scoring (deterministic, versioned)

- E = clip(excess_return / 0.02, −1, 1). C = clip(commodity_return × exposure_direction / 0.03, −1, 1).
- Commodity disruption: score = 0.6·E + 0.4·C. Earnings and orders use equity only (weight 1.0).
- Label: ≥ +0.15 positive, ≤ −0.15 negative, otherwise neutral/mixed. Coverage = available weight / configured weight (minimum 0.6).
- Missing mandatory evidence → **abstain**, even when a partial score exists. Opposite signs → explicit conflict.
- Synthetic worked example (`syn-002`, Berger Paints): E = 0.008/0.02 = 0.40, C = −0.015/0.03 = −0.50, score = 0.24 − 0.20 = **0.04, neutral, with a conflict flag**

**Speaker notes:** Rules are frozen in `configs/fusion_rules.json` (`fusion-v1`). Its provenance field
says "Frozen conceptual demonstration policy, not calibrated probabilities". The implementation is
`fusion.assess_evidence`. The equity rose while the input-cost signal was negative, so the evidence
disagrees. The equity-only ablation of the same saved run gives 0.40, positive (`experiments.compare_ablations`).
The score is evidence strength, **not a probability**. Volume is shown as context but never scored. The
score uses the *reaction-day* excess return already visible at the cutoff. Keep this in mind for slide 12.

---

## Slide 11: SLM vs LLM execution policies

| Policy | Filter | Extraction | Delegated hints | Literature analogue |
| --- | --- | --- | --- | --- |
| `llm_only` | LLM | LLM | no | single strong model |
| `slm_filter` | SLM | LLM | no | gatekeeper cascade |
| `slm_delegate` | SLM | LLM | verified filter output | closest to hint passing |

- Every policy filters first. Irrelevant items stop after one call. Extraction always gets the **full** article.
- Per-run budgets: 4 requests, conservative 24,000-unit admission estimate, 2 attempts per task
- Every attempt is traced: model, prompt hash, request hash, status, latency, and tokens when reported

**Speaker notes:** Routing is `pipeline.py` lines 179–188, and budgets are `config.Settings` and
`model_client.ask`. The admission estimate is serialized bytes plus the output allowance, not real tokens.
The dashboard names the policies by what they do: "Large model does both steps", "Small model screens → large
model extracts" and "Small model screens and hands over hints → large model extracts" (`web/app/_components/types.ts`).
Replay returns the same recorded output for any role, so **replay cannot show a policy difference**; only
live runs can. Live development models: `qwen3.5:2b` in the SLM role and `gemma4:e4b` in the LLM role
(`runs/handover.usage.json`). There is no "SLM extracts, LLM on validation failure" policy yet. That
would be the true FrugalGPT analogue (brief §1.2) and is future work.

---

## Slide 12: Outcomes kept separate from decisions

- **Definition:** a market-adjusted (beta = 1) return from the **next** session's 09:15 IST open to the 5th observed session's close, net of a 10 bps round trip
- It measures **post-cutoff drift**. The score uses the reaction already visible at the cutoff, so the two are not circular.
- `pending` until five finished, available sessions exist. Abstained decisions → `invalid`. Never a zero.
- Evaluated only on an explicit action and stored in a separate table. Negative evidence is never turned into a short trade.
- Future work: market-model CAR with an estimation window, plus BMP and sign tests (MacKinlay 1997; Boehmer et al. 1991)

**Speaker notes:** Code: `outcomes.evaluate_outcome`. The excess return is gross equity minus the
same-dates benchmark return, so beta is implicitly 1. Outcomes are the only mutable table (an upsert),
which lets `pending` become `completed` (`storage.py`). Synthetic demo numbers (re-run 2026-11-21): all
three demo runs show gross +4.58%, net +4.48%, benchmark +0.90%. **They are identical because the fixture
prices are constant geometric paths** (equity +1%/session, benchmark +0.2%, crude +1.5%;
`tests/fixtures/market_prices.csv`). That shows the mechanics only. Outcomes are not ground-truth labels
(`docs/EXPERIMENTS.md`).

---

## Slide 13: Strategy lab (retrospective price research)

- Six long/cash rules. Signal at the close → fill at the **next** observed open, with fees and adverse slippage on every fill (defaults 10 and 5 bps).
- Metrics: total return, buy and hold, max drawdown, Sharpe (√252, zero risk-free), **probabilistic Sharpe** (single configuration, not deflated), CAGR, win rate
- **Walk-forward split:** one configuration fixed in advance, run independently on in-sample (2015–2019) and out-of-sample (2020) segments
- Monte Carlo: seeded PCG64 moving-block bootstrap (Künsch 1989) of strategy returns, with p05/p50/p95 bands
- Studies end 31 Dec 2020. The demo uses `SYNTHETIC:LAB_DEMO`, a **zero-drift random walk**, as a sanity check: the correct result is "no edge".

**Speaker notes:** Code: `strategy_lab.run_backtest`, `strategy_lab.walk_forward`, `strategy_lab.probabilistic_sharpe`
and `strategy_lab.monte_carlo`. Assumptions are returned with every result. Synthetic figures, computed 2026-11-21
through the API (SMA 20/50, 2015–2020, 10/5 bps): −52.5% against buy and hold +33.8%, Sharpe −0.79, PSR 0.025,
20 trades. At 2× costs, −55.3%. Walk-forward gives −41.4% in-sample and −17.5% out-of-sample. Say it as "no edge
found, costs make it worse, PSR ≈ 2%". With 20 trades, it is below a 30-trade low-sample threshold. The Sharpe and
PSR are not deflated for the number of configurations tried (Bailey & López de Prado 2014), which is why the
configuration is fixed in advance and only costs are stressed on stage. A single split is a robustness check, not
proof of a persistent edge. Real history needs an explicit Upstox download, and no token is configured. The
1,566-session series is labelled QA history; never present it as performance.

---

## Slide 14: Results and limitations, stated honestly

- **Software:** 561 automated tests pass, and the replay demo is offline and reproducible. Synthetic replay: earnings and order give positive (0.40), crude disruption gives neutral (0.04) with a conflict, duplicates stop with 0 calls, and updates are recognised.
- **Live dev pilot (synthetic inputs):** `qwen3.5:2b` ran 30 filter calls with 0 failures and forwarded 24 of 24 expected items. `gemma4:e4b` produced 3 of 3 grounded extractions after a schema fix.
- **Policies:** the live run (7 synthetic articles each) gave `llm_only` 8 calls against 9 and 9 for the SLM policies, so **no saving**. The replay table is identical across policies by construction.
- **Not claimed:** accuracy, F1, calibration or profitability. There is no held-out real corpus.
- **Limits:** all bundled data is synthetic (constant-growth bars, conceptual exposure rules); the provider adapter is tested only with mocked HTTP; there is no exchange calendar or corporate-action adjustment; fusion weights are uncalibrated.

**Closing line:** "The project's claim is not that it predicts markets. Its claim is that every
conclusion it produces can be traced, re-run, and shown to have used only what was known at the time."

**Speaker notes:** Sources: `runs/local_model_pilot.json`, `runs/policy_comparison.json`,
`docs/EXPERIMENTS.md`, `tests/fixtures/README.md`. The live latencies (3.8 s against 21.9 s and 20.0 s
per run) mix cold and warm local calls, so they are not a benchmark. The earlier smoke run validated only
1 of 3 extractions before the typed-amount fix, and we keep that on record. The policies disagreed on
`syn-005` (LLM-only marked it irrelevant, the SLM policies abstained). If the agreement table is shown,
call it "synthetic sanity check on authored articles, not a benchmark": one annotator, and in replay
filter recall 1.0 with precision below 1, because the gold labels mark the unconfirmed SpiceJet items
irrelevant. Future work is on slide 3. Then hand over to the live demo.
