# Research brief: positioning Market Events as a final-year project

Prepared 2026-11-21 by the `research` agent for the 1 December 2026 presentation.
Inputs: `docs/PRESENTATION_PLAN.md`, `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/EXPERIMENTS.md`,
`docs/DECISIONS.md` and a read of `src/market_events/` (`fusion.py`, `pipeline.py`, `outcomes.py`,
`strategy_lab.py`, `experiments.py`, `agents/`). I changed no code.

## How references were verified

| Mark | Meaning |
| --- | --- |
| **[V]** | I found the bibliographic record (title, authors, venue/ID) on arXiv, the publisher, ACL Anthology, RePEc or an institutional repository during this session. Any claim summarised here comes from the abstract or listing. I did not read the full text. |
| **[P]** | Partly verified. The record exists, but some details (author list, figures) come only from search snippets. Check them before quoting. |
| **[U]** | Unverified. It appeared only in another paper's reference list or a secondary page. Do not cite it in slides until someone checks it. |
| **[S]** | Secondary or press source. Fine for motivation, not as evidence. |

No reference in this document was written from memory alone. Each one turned up in a web search on 2026-11-21. Quote numbers from the papers themselves, not from this brief.

---

## 1. Related work

### 1.1 Language models for financial text and events

- **Financial PhraseBank.** Malo, P. et al. (2014). *Good debt or bad debt: Detecting semantic orientations in economic texts.* JASIST 65(4), 782–796. arXiv:1307.5336. https://arxiv.org/abs/1307.5336 **[V]**. This is the standard human-annotated sentence-sentiment benchmark for finance.
- **FinBERT.** Araci, D. (2019). *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models.* arXiv:1908.10063. https://arxiv.org/abs/1908.10063 **[V]**. A BERT model further trained on financial text, evaluated on Financial PhraseBank and FiQA. It is the obvious low-cost baseline for a relevance or sentiment filter.
- **BloombergGPT.** Wu, S. et al. (2023). *BloombergGPT: A Large Language Model for Finance.* arXiv:2303.17564. https://arxiv.org/abs/2303.17564 **[V]**. A 50B-parameter model trained on a mix of 363B tokens of Bloomberg financial data and 345B general tokens. It shows the proprietary, data-privileged approach.
- **FinGPT.** Yang, H., Liu, X.-Y., Wang, C. D. (2023). *FinGPT: Open-Source Financial Large Language Models.* arXiv:2306.06031 (FinLLM Symposium @ IJCAI 2023). https://arxiv.org/abs/2306.06031 **[V]**. An open, data-centric pipeline that adapts models with LoRA. It is the open-source counterpoint to BloombergGPT.
- **FinBen.** Xie, Q., Huang, J. et al. (2024). *FinBen: A Holistic Financial Benchmark for Large Language Models.* arXiv:2402.12659. https://arxiv.org/abs/2402.12659 **[V]**. v2 has 36 datasets across 24 tasks, including extraction and stock trading. Code is in the PIXIU repository.
- **Survey.** Nie, Y. et al. (2024). *A Survey of Large Language Models for Financial Applications: Progress, Prospects and Challenges.* arXiv:2406.11903. https://arxiv.org/abs/2406.11903 **[P]** (author list not checked beyond the first author). It names look-ahead bias and data pollution as open challenges.
- **Event-driven prediction, pre-LLM.** Ding, X., Zhang, Y., Liu, T., Duan, J. (2015). *Deep Learning for Event-Driven Stock Prediction.* IJCAI 2015, 2327–2333. https://www.ijcai.org/proceedings/2015/329 **[V]**. Structured events extracted from news are fed to a predictor. This is the lineage this project belongs to.
- **Corporate event detection and trading.** Zhou, Z., Ma, L., Liu, H. (2021). *Trade the Event: Corporate Events Detection for News-Based Event-Driven Trading.* Findings of ACL-IJCNLP 2021, 2114–2124. https://aclanthology.org/2021.findings-acl.186 **[V]**. Introduces the EDT dataset: 9,721 articles with token-level event labels and 303,893 timestamped articles with price labels. It is the closest public benchmark to this project's event families.
- **LLM sentiment and returns.** Lopez-Lira, A., Tang, Y. *Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models.* arXiv:2304.07619 (v1 2023 to v6 October 2025). https://arxiv.org/abs/2304.07619 **[V]**. The abstract changes across versions. Early versions report predictability of next-day returns from headline scores. Later versions frame it theoretically and report that strategy returns decline as LLM adoption rises. Cite the specific version you use.
- **Generative structured extraction.** Choi, S., Park, J. (2025). *Harnessing Generative LLMs for Enhanced Financial Event Entity Extraction Performance.* arXiv:2504.14633. https://arxiv.org/abs/2504.14633 **[V]**. A LoRA-tuned LLM emits JSON entities with character spans, scored by F1 on CCKS 2019. It is directly comparable to this project's JSON-plus-verbatim-span extraction.
- **Multi-field news extraction.** Zhu, D. et al. (2026). *Beyond Sentiment: Structured Information Extraction from Financial News.* arXiv:2607.28496. https://arxiv.org/abs/2607.28496 **[P]** (figures are from a snippet). Llama-3.1-70B extracts event type, impact subject and horizon as JSON. The authors themselves flag that the model's training cutoff overlaps the evaluation period.

### 1.2 Small-versus-large cascades and routing

- **FrugalGPT.** Chen, L., Zaharia, M., Zou, J. (2023). *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance.* arXiv:2305.05176. https://arxiv.org/abs/2305.05176 **[V]**. Models are called from cheapest to most expensive, and a learned scorer stops the cascade once an answer is judged acceptable. The authors report matching GPT-4 with up to 98% lower cost on their tasks.
- **RouteLLM.** Ong, I. et al. (2025). *RouteLLM: Learning to Route LLMs with Preference Data.* ICLR 2025. arXiv:2406.18665. https://arxiv.org/abs/2406.18665 **[V]**. A router trained on preference data picks a strong or weak model per query and reports more than 2× cost reduction without losing quality.
- **Cascade routing.** Dekoninck, J., Baader, M., Vechev, M. (2025). *A Unified Approach to Routing and Cascading for LLMs.* ICML 2025, PMLR 267:12987–13010. arXiv:2410.10347. https://arxiv.org/abs/2410.10347 **[V]**. Its key finding is that a good quality estimator matters most. That is the point to emphasise, because this project's estimator is deterministic span verification.

**How this maps to the three policies.** (`SYSTEM_ARCHITECTURE.md` §6; `pipeline.py` lines 179–188)

| Policy | Literature analogue | Difference |
| --- | --- | --- |
| `llm_only` | Single strong model (the baseline in all three papers) | The LLM still runs a separate filter call, so there are two LLM calls per relevant article. |
| `slm_filter` | A two-stage **gatekeeper** cascade: the cheap model decides only whether to escalate | The SLM never produces the final answer. Savings come only from the cheaper filter call and from articles the SLM drops as irrelevant. |
| `slm_delegate` | Closest to draft-and-verify or hint passing. No direct equivalent among the three papers. | Verified SLM spans and entities pass to the LLM as hints, and the LLM still reads the full article. |

The quality estimator here is a **deterministic verbatim-span check** (`filter_agent.py`). An unsupported SLM rejection becomes "uncertain" and escalates. That is a conservative, explainable gate, not a learned scorer as in FrugalGPT or RouteLLM. The current code has no policy where the SLM does the extraction and the LLM steps in only when validation fails, which would be the true FrugalGPT analogue (see future work).

### 1.3 Look-ahead bias and point-in-time evaluation

- Glasserman, P., Lin, C. (2023). *Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis.* arXiv:2309.17322. https://arxiv.org/abs/2309.17322 **[V]**. Removing company names from headlines improved in-sample performance, which the authors attribute to a "distraction effect" from what the model already knows. This is a cheap test the project could reuse.
- Sarkar, S. K., Vafa, K. (2024). *Lookahead Bias in Pretrained Language Models.* SSRN 4754678. ICML 2025 listing: https://icml.cc/virtual/2025/48685. NBER conference PDF: https://conference.nber.org/conf_papers/f205530/f205530.pdf **[P]** (the SSRN ID comes from a citing paper). The paper offers direct tests for leakage from pretraining data.
- He, S., Lv, L., Manela, A., Wu, J. (2025). *Chronologically Consistent Large Language Models.* arXiv:2502.21206. https://arxiv.org/abs/2502.21206 **[V]**. ChronoBERT and ChronoGPT come in one vintage per year from 1999, trained without future data. One secondary source says the weights were later withdrawn from Hugging Face. **[U]** Check before relying on them.
- Benhenda, M. (2026). *Look-Ahead-Bench: a Standardized Benchmark of Look-ahead Bias in Point-in-Time LLMs for Finance.* arXiv:2601.13770. https://arxiv.org/abs/2601.13770 **[P]**. Reported figures come from the abstract snippet.
- *Evaluating LLMs in Finance Requires Explicit Bias Consideration.* arXiv:2602.14233. https://arxiv.org/abs/2602.14233 **[P]** (authors not checked).
- Gao, Jiang, Yan. *Detecting Lookahead Bias in LLM Forecasts.* arXiv:2512.23847 **[U]**. Seen only in reference lists.

**Three kinds of look-ahead, and where this project stands:**

1. **Data availability** (using information before it existed in the dataset). This is handled well. Articles need both `published_at` and `first_seen_at` at or before the cutoff. Observations need both `timestamp` and `available_at`. Exposure rules need both `effective_at` and `known_at`. Provider history is stamped with its real fetch time (`SYSTEM_ARCHITECTURE.md` §9).
2. **Revisions** (silently replacing what was known). This is handled: the ledger is append-only, price revisions are reported as conflicts, and each request is hashed over a frozen configuration snapshot.
3. **Parametric knowledge** (the model already "knows" what happened). This is not handled, but it is limited by design. The model only extracts. It never outputs a direction, score or forecast; deterministic fusion does that. The bundled articles are synthetic, so the model cannot have memorised them. On real news, a model could still bias its relevance or event-type decisions using knowledge of what happened later.

### 1.4 Event-study methodology

- MacKinlay, A. C. (1997). *Event Studies in Economics and Finance.* Journal of Economic Literature 35(1), 13–39. https://ideas.repec.org/a/aea/jeclit/v35y1997i1p13-39.html **[V]**. The canonical tutorial: estimation window, event window, normal-return models (constant mean, market model), and aggregation into CAR and CAAR.
- Brown, S. J., Warner, J. B. (1985). *Using Daily Stock Returns: The Case of Event Studies.* Journal of Financial Economics 14, 3–31. doi:10.1016/0304-405X(85)90042-X **[V]**. Covers the properties of daily excess-return models: non-normality and non-synchronous trading.
- Boehmer, E., Musumeci, J., Poulsen, A. B. (1991). *Event-study methodology under conditions of event-induced variance.* Journal of Financial Economics 30(2), 253–272. doi:10.1016/0304-405X(91)90032-F **[V]**. The standardised cross-sectional (BMP) test, robust to the variance spike around events.
- Agarwalla, S. K., Jacob, J., Varma, J. R. (2013, revised 2014). *Four Factor Model in Indian Equities Market.* IIM Ahmedabad WP 2013-09-05. https://www.iima.ac.in/publication/four-factor-model-indian-equities-market **[V]**. Fama-French and momentum factors for India, with a public data library. This is the Indian-market benchmark if factor-adjusted abnormal returns are ever used.

**Current implementation versus standard practice** (`outcomes.py`):

- The outcome is a **market-adjusted return** (stock return minus a benchmark, implicitly beta = 1) from the next 09:15 IST open to the fifth observed session close, with a 10 bp round trip. MacKinlay treats this as a legitimate but restricted model. It has no estimation window, no beta, no aggregation across events and no test statistic.
- The decision score itself uses the **reaction-day** excess return that is already observable at the cutoff (`market_features.py`). The score therefore describes the market's initial reaction plus the commodity channel, and the outcome measures **post-cutoff drift**. That framing is defensible, but it must be said explicitly in the viva. Otherwise "the score predicted the outcome" sounds circular.
- Benchmark choice: the demo uses synthetic sector benchmarks and the live universe uses Nifty 50. For paint makers and airlines, a broad index absorbs part of the sector-wide oil effect differently from a sector index. Future work should report both.

### 1.5 Commodity exposure of Indian listed firms

Academic studies of oil shocks in Indian sector indices (all **[P]**; abstracts only):
- Zubair (2024). *Impact of crude oil price volatility on Indian stock market returns: a quantile regression approach.* Economic Annals 69(242), 93–128. https://ea.ekof.bg.ac.rs/index.php/economicannals/article/view/519. Sector returns fall with oil volatility, more strongly in bearish markets.
- Mishra & Mishra, *Resources Policy* vol. 70. Uses Ready's (2018) decomposition of oil shocks across ten NSE sector indices (2010–2019). Demand and supply shocks affect sectors differently. Full citation not checked.
- Gopal, Kumara & Naveenan (2025), *Cogent Economics & Finance*. *Crude complexities: sectoral asymmetries in the Indian stock market response to oil price changes.* https://archives.christuniversity.in/items/show/22788

Industry sensitivity, for motivation only (**[S]**; figures vary by source and I did not check each figure's attribution):
- **Paints.** Press and broker commentary puts crude-linked inputs (solvents, resins, emulsions) at roughly 30–50% of paint raw-material costs. One cited heuristic is that a 10% rise in crude has historically meant a gross-margin decline of about 130 bp. Examples: Upstox News, https://upstox.com/news/market-news/stocks/asian-paints-berger-indigo-paints-can-paint-stocks-weather-crude-price-fluctuations/article-194560/ . Confirm against the cost-of-materials notes in the Asian Paints and Berger annual reports before stating a number.
- **Airlines.** Aviation turbine fuel is usually quoted at about 35–40% of an Indian airline's operating costs. Business Standard (Oct 2026): https://www.business-standard.com/amp/industry/aviation/indigo-hikes-fuel-charges-from-oct-6-as-atf-costs-rise-over-14-126100500387_1.html . A higher figure of 55–60% during the 2026 fuel shock is attributed to the Federation of Indian Airlines. **[U]**: I did not identify the primary source.
- **Sign ambiguity.** Reliance is in the live universe. A refiner or upstream producer can have the *opposite* or a state-dependent crude sensitivity compared with a paint maker. That is a strong argument for the project's reviewed, versioned, cutoff-dated exposure rules over a learned mapping that cannot be audited.

The bundled exposure rules (`configs/exposure_rules.json`) are explicitly *"Conceptual synthetic input-cost sensitivity assumption; not empirically validated"*. Keep that label. The sources above explain why the direction `-1` is plausible for paints and airlines. They do not validate the rules.

### 1.6 Backtest overfitting

- Bailey, D. H., López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.* Journal of Portfolio Management. SSRN 2460551, https://papers.ssrn.com/abstract=2460551 **[V]**.
- Bailey, D. H., Borwein, J., López de Prado, M., Zhu, Q. J. (2017). *The Probability of Backtest Overfitting.* Journal of Computational Finance 20(4). doi:10.21314/JCF.2016.322. SSRN 2326253, https://papers.ssrn.com/abstract=2326253 **[V]**. Introduces combinatorially symmetric cross-validation (CSCV).
- Harvey, C. R., Liu, Y., Zhu, H. (2016). *…and the Cross-Section of Expected Returns.* Review of Financial Studies 29(1), 5–68. NBER w20592, https://www.nber.org/papers/w20592 **[V]**. Argues that new factors should clear t > 3 under multiple testing.
- White, H. (2000). *A Reality Check for Data Snooping.* Econometrica 68(5), 1097–1126. doi:10.1111/1468-0262.00152 **[V]**.
- Künsch, H. R. (1989). *The Jackknife and the Bootstrap for General Stationary Observations.* Annals of Statistics 17(3), 1217–1241. doi:10.1214/aos/1176347265 **[V]**. The theoretical basis for the moving-block bootstrap that `strategy_lab.monte_carlo` uses.

**Current implementation** (`strategy_lab.py`; updated 2026-11-21 after the delivered changes). The lab offers buy-and-hold plus SMA/EMA crossover, RSI reversion, MACD crossover and Bollinger reversion rules, next-open fills, per-fill fees, adverse slippage, and a seeded moving-block bootstrap. It reports an annualised Sharpe from sample deviation with a zero risk-free rate.

Delivered since the first version of this brief:

- **Probabilistic Sharpe ratio: delivered.** `probabilistic_sharpe()` (Bailey & López de Prado) is returned as `metrics.probabilistic_sharpe` and shown beside Sharpe in the web lab. It is P(true per-session Sharpe > 0) given n, skewness and kurtosis. **Limit:** it covers a single configuration. It is *not* deflated for the number of configurations tried, so it is not a DSR. Both the result's assumption notes and the UI card say so.
- **Walk-forward split: delivered, but only as a single split.** `walk_forward()` runs one fixed, pre-chosen configuration independently on an in-sample segment (before `split_date`) and an out-of-sample segment (from `split_date`). Each segment starts in cash with its own warm-up. **Limits:** it is one split, not a rolling or anchored walk-forward. No parameters are optimised in-sample, so it tests stability, not a tuning procedure. It is reachable through the backtest API (`walk_forward_split`); at the time of this update nothing in `web/` calls it. Its own notes say "a single split is a robustness check, not proof of a persistent edge".
- **Longer synthetic lab series: delivered.** `SYNTHETIC:LAB_DEMO` now covers 2015-01-01 to 2020-12-31 (1,566 sessions). **Limit:** it is an authored, seeded, zero-drift random walk. Any backtest, PSR or walk-forward result on it is a mechanics check that should show *no* edge, and it is not evidence for or against any strategy.

**Still missing:**
- Nothing records **how many configurations** a user tried, so an on-stage parameter tweak remains an uncorrected multiple test.
- There is no DSR, PBO/CSCV, rolling walk-forward, or White/Hansen test.
- The demo therefore relies on the configuration being fixed in advance (stated in `docs/presentation/DEMO_SCRIPT.md`).

### 1.7 Evaluation metrics for extraction quality

Standard practice in event and entity extraction is precision, recall and F1 at the field or argument level, with exact or partial span matching (as in EDT and CCKS-style work above). Selective prediction gives the right lens for a system that abstains:

- Geifman, Y., El-Yaniv, R. (2017). *Selective Classification for Deep Neural Networks.* NeurIPS 2017. arXiv:1705.08500. https://arxiv.org/abs/1705.08500 **[V]**. Defines risk-coverage curves: error among the items answered, plotted against the fraction answered.

Suggested metric suite for this project. Each metric can be computed from saved runs plus a gold file:

| Layer | Metric | Notes |
| --- | --- | --- |
| Filter | Recall on relevant items (the key cascade risk), precision, escalation rate (`uncertain` share) | An SLM false negative is unrecoverable. Report it per policy. |
| Extraction | Schema-valid rate; grounding rate (all spans verbatim); amount/unit/scale fidelity; field accuracy for `event_type`, `company_id`, `commodity_id`; span-level P/R/F1 | Grounding is already enforced. Report the *rate* of validated, unsupported and unresolved results. |
| Decision | Abstention rate by reason; risk-coverage of evidence label against later outcome direction | The score is not a probability, so calibration metrics (Brier, ECE) do **not** apply. |
| Efficiency | Calls, input/output tokens, latency, and estimated cost per *validated* extraction, per policy | Live mode only. Replay timings are not model latency. |
| Agreement | Cohen's κ between two human annotators on the gold set | Needed before any real-data claim. |

### 1.8 `tradermonty/claude-trading-skills` (skills.sh): relevance assessment

Pages read (nothing installed): https://www.skills.sh/tradermonty/claude-trading-skills , https://tradermonty.github.io/claude-trading-skills/en , and the `backtest-expert` and `market-news-analyst` skill pages on that site.

- **What it is.** A community collection of about 74 Claude skills: `SKILL.md` instruction files, some with helper Python scripts. It calls itself a "workflow toolkit" and "not a signal service". The GitHub sidebar says MIT licence; I did not read the LICENSE file.
- **Fit.** The collection is US-centric (FMP, FINVIZ, Alpaca, CFTC COT, yfinance). I found no NSE or BSE skill. `market-news-analyst` is a prompt-only skill that has Claude web-search the last 10 days of news and rank an "Impact Score". It is an *LLM-as-analyst* design with no point-in-time discipline, which is the opposite of this project's *LLM-as-extractor, deterministic-evidence* design. It works as a contrast on the related-work slide, not as a component.
- **Useful content.** `backtest-expert` encodes a practitioner checklist: at least 100 trades, 4 or fewer parameters, slippage stress at 1.5–2× typical, look for parameter "plateaus" rather than "spikes", walk-forward testing, and treat out-of-sample below 50% of in-sample as likely overfit. These are reasonable heuristics to mention next to DSR and PBO, attributed as practitioner guidance rather than literature.
- **Verdict:** **low direct relevance.** Do not install or integrate it before 1 December. Its data sources, market and architecture do not match, and the project rules forbid new heavy dependencies and provider downloads.

---

## 2. Novelty statement

> *Market Events is a point-in-time, auditable workbench in which language models are confined to grounded extraction from dated news, while a deterministic, versioned evidence-fusion layer combines the stock's benchmark-relative reaction with a reviewed, cutoff-dated commodity-exposure channel (e.g., crude oil → Indian paint makers and airlines) and abstains whenever mandatory evidence is missing. It provides three cost-aware small/large model execution policies, gated by verbatim-span verification rather than a learned scorer, and records every call, prompt hash, configuration snapshot and later outcome in an append-only ledger so that each decision can be replayed exactly.*

Points to defend in the viva. These are claims about the design, not about performance:

1. **Separating interpretation from decision.** Most of the LLM-finance work cited above (Lopez-Lira & Tang; Glasserman & Lin; "Beyond Sentiment") asks a model for a sentiment or direction. Here the model never emits a score, which limits both hallucinated numbers and the effect of parametric look-ahead.
2. **Second-order (cross-market) event propagation.** Exposure rules carry `effective_at` and `known_at`, so a supply shock to one commodity reaches firms not named in the article, without hidden look-ahead in the mapping itself.
3. **Point-in-time discipline at every layer** (article, observation, exposure rule, configuration) plus request-level idempotency. This is more than most academic prototypes document.
4. **A cascade with an explainable gate**, and an honest negative finding so far: the archived comparison shows 8, 9 and 9 live calls, so there is no call saving on these inputs (`docs/EXPERIMENTS.md`).
5. **Indian market setting** (NSE equities, IST sessions, MCX crude), which is under-represented in the LLM-finance benchmarks above.

Phrase it as "to our knowledge, based on a limited literature search". Do **not** claim predictive accuracy, profitability or cost savings. None has been measured on real held-out data.

---

## 3. Gap analysis versus the current implementation

Status as of 2026-11-21, after the delivered and committed changes. "Partly addressed" means a mechanism now exists, but the research gap behind it remains.

| # | Area | Current state (verified in code/docs) | Remaining gap | Status | Severity for viva |
| --- | --- | --- | --- | --- | --- |
| G1 | Extraction quality | Grounding and schema validation enforced. **Delivered:** `tests/fixtures/gold_labels.json` (35 synthetic articles, single annotator) and `extraction_agreement()`, which reports per-policy filter recall/precision, field accuracy, validation rates and abstention rate in `/api/comparisons` and the Comparisons view, labelled "synthetic sanity check, not a benchmark". | The labels cover authored synthetic text from one annotator with no inter-annotator agreement. In replay the scores measure the recorded fixtures (the pipeline), not model quality. There is still no real-data gold set, span-level F1 or Cohen's κ. | Partly addressed | Medium: now answerable ("we measure it; here is the mechanism"), but no quality claim is possible |
| G2 | Cascade evaluation | Calls, tokens, latency and model tier per policy; replay/live split. **Delivered:** an `estimated_cost` field from optional `configs/model_prices.json`, plus filter recall via G1. | `model_prices.json` ships with **no rates**, and replay records no tokens, so `estimated_cost` is null everywhere until real rates and live runs exist. The archived live comparison still shows no call saving (8/9/9). Cost savings remain unmeasured. | Partly addressed (mechanism only) | High if asked "does the cascade save money?": the honest answer is "not measured yet" |
| G3 | Cascade design | SLM only filters; LLM always extracts; `llm_only` makes 2 LLM calls | No SLM-first-extract-then-escalate policy (the FrugalGPT analogue); the gate is not learned | Open | Medium (future work) |
| G4 | Outcome methodology | Market-adjusted 5-session return; long-only measurement; single horizon; no tests. Framing delivered in the presentation docs. | No estimation-window CAR, CAAR, BMP or sign test; no horizon sensitivity | Open (explained, not fixed) | Medium: explain, don't fix |
| G5 | Score versus outcome framing | Score includes the reaction-day excess return already seen at the cutoff. **Delivered:** "reaction + channel → later drift" framing in `DEMO_AND_VIVA.md` and the slides. | None in the docs. Any new slide must keep the framing. | Addressed (docs) | Low |
| G6 | Parametric look-ahead | Data and revision look-ahead handled; model knowledge not tested. **Delivered:** "three kinds of look-ahead" slide and viva answer. | No anonymisation or pre/post-knowledge-cutoff test | Open (explained) | Medium (explain) |
| G7 | Backtest overfitting | **Delivered:** PSR (single configuration, not deflated), one fixed-configuration in-sample/out-of-sample split (API only), a 2015–2020 synthetic random-walk series, and a 2× cost-stress beat in the demo script. | No record of the number of configurations tried; no DSR, PBO/CSCV, rolling walk-forward or Reality Check/SPA. Walk-forward is not yet in the web UI. The demo series is a random walk, so it carries no evidence. | Partly addressed | Medium |
| G8 | Exposure evidence | Synthetic demo rules labelled as such. **Delivered:** `LIVE:MCX:CRUDEOIL` near-month readiness in `configs/live_universe.json`, and `configs/live_exposure_rules.json` with **direction-only** rules (−1) for Asian Paints, Berger Paints and IndiGo. Reliance (sign ambiguous) and Pidilite (unsourced) are recorded as reviewed *without* a rule, so they abstain. A contract roll fails closed instead of splicing contracts. | The rules are **pending team review**, are sourced from secondary press only, and claim no magnitude or empirical validation. `known_at` = 2026-11-21, so they cannot support any decision dated before that (correctly), and no retrospective evaluation of the crude channel is possible. The MCX path is **offline-tested only** (mocked HTTP), with no real account sync. There is no annual-report or estimated-beta basis, and no automatic contract rolling. | Partly addressed | Low for demo; high for any real-data claim |
| G9 | Data | All bundled articles and prices synthetic; real adapter mocked | No real dated corpus with permissions | Open | Known and disclosed; future work |

---

## 4. Prioritised improvements

### (a) Small, safe items before 1 December

These are additive, labelled honestly, and change no existing saved decision. Each had a one-line request under **Cross-agent requests** in `docs/PRESENTATION_PLAN.md`.

**Status (2026-11-21):** all nine are delivered. For items 1–4 I checked the code. For items 5–9 I checked that the content is present in `docs/presentation/` and `docs/DEMO_AND_VIVA.md`, but did not review its wording line by line. The limits that remain are stated against each item.

1. **Synthetic gold labels plus an agreement report** (G1, G2) → `demo-backend`. **Delivered.** `tests/fixtures/gold_labels.json` covers the 35 synthetic articles, and `extraction_agreement()` reports per-policy filter recall/precision, field accuracy, validation rates and abstention rate, labelled "synthetic sanity check, not a benchmark". *Limits:* single annotator with no κ; authored synthetic text; in replay it measures the recorded fixtures, not model quality.
2. **Estimated cost per policy** (G2) → `demo-backend`. **Delivered as a mechanism.** `configs/model_prices.json` plus `estimated_cost`, computed only for live groups whose every call reports tokens and has a price entry. *Limits:* the file ships with no rates, and replay has no tokens, so the field is null in every current view. No cost saving has been measured.
3. **Probabilistic Sharpe ratio plus trial disclosure** (G7) → `demo-backend`. **Delivered.** It is P(true per-session Sharpe > 0), with the note "single configuration; not deflated for the number of configurations tried". *Limit:* it is not a DSR, and the number of trials is not recorded.
4. **Show the new fields** (G1, G2, G7) → `demo-ui`. **Delivered.** A PSR card with the not-deflated note; the agreement table; an estimated-cost column that is hidden while null.
5. **Related-work and novelty slide** → `pitch-docs`. **Delivered** (`docs/presentation/SLIDES.md`, "to our knowledge" wording).
6. **"Three kinds of look-ahead" slide and viva answer** (G6) → `pitch-docs`. **Delivered** (`SLIDES.md`, `DEMO_AND_VIVA.md`). The parametric look-ahead test itself remains future work.
7. **Outcome definition and framing** (G4, G5) → `pitch-docs`. **Delivered** (market-adjusted framing in `DEMO_AND_VIVA.md`, `SLIDES.md`, `DEMO_SCRIPT.md` and `VIVA_QA.md`). The event-study upgrade remains future work.
8. **Commodity-exposure motivation slide** (G8) → `pitch-docs`. **Delivered** (`SLIDES.md`, labelled "secondary press").
9. **Cost-stress demo beat** (G7) → `pitch-docs`. **Delivered** (`DEMO_SCRIPT.md` step 7: 10/5 → 20/10 bps, configuration fixed in advance).

Delivered beyond the original list, at the coordinator's and team's request:

- **Walk-forward (G7).** One fixed-configuration in-sample/out-of-sample split through the backtest API. *Limits:* a single split, not rolling or anchored; no in-sample optimisation; not yet exposed in the web UI at this update.
- **`SYNTHETIC:LAB_DEMO` extended to 2015–2020** (1,566 sessions). *Limit:* a seeded zero-drift random walk, useful only for mechanics.
- **Live crude readiness (G8).** `LIVE:MCX:CRUDEOIL` (near-month, chosen explicitly at sync, fails closed on a roll) and direction-only `configs/live_exposure_rules.json` for Asian Paints, Berger Paints and IndiGo, with Reliance and Pidilite deliberately left without a rule. *Limits:* the rules are pending team review, rest on secondary sources, claim no magnitude, and have `known_at` = 2026-11-21. The path is offline-tested only (mocked HTTP), not run against a real account.

**Still open before 1 December** (no request filed; only if time allows):
- Have a team member actually review and sign off `live_exposure_rules.json` (or keep it labelled "pending review" on any slide that mentions it).
- If walk-forward is mentioned on stage, show it from the API output or a prepared JSON, since the UI does not display it.

### (b) Future work, after the presentation

Items that are partly delivered now say what remains.

1. **Real corpus.** A permitted, dated Indian news corpus (provider news, NSE corporate announcements) with a manifest, a 200–500 article gold set annotated by two people (report Cohen's κ), and a temporal pilot/test split. The synthetic gold-label mechanism (§4a-1) can be reused for this set unchanged.
2. **Proper event study.** Market-model abnormal returns with a pre-event estimation window. CAR and CAAR at 1, 3, 5 and 10 sessions. BMP and sign tests. Sector versus Nifty 50 benchmarks. Optionally the IIMA four-factor model.
3. **Cascade research.** Add `slm_extract_escalate`, where the SLM extracts and the deterministic validator acts as FrugalGPT's scorer, escalating to the LLM on failure. Compare against a learned router (RouteLLM / cascade routing) on cost per validated extraction and filter recall. Compare against a FinBERT-style encoder filter. The cost and recall reporting now exists (§4a-1, §4a-2). What is missing is real provider rates in `model_prices.json`, live runs with complete token counts, and a real gold set.
4. **Parametric look-ahead tests.** Entity anonymisation ablation (Glasserman & Lin), pre- versus post-knowledge-cutoff splits, and chronologically consistent models if they are available.
5. **Exposure estimation.** `configs/live_exposure_rules.json` now exists, but it is direction-only, pending review and press-sourced. Next steps:
   - Replace each rule's source with annual-report raw-material disclosures, with `known_at` set to the filing date. That would also permit earlier, point-in-time-valid decisions than the current 2026-11-21 date.
   - Add rolling point-in-time betas of stock returns to crude and ATF as a cross-check and to justify magnitudes.
   - Revisit Reliance (sign ambiguous) and Pidilite (unsourced), which currently abstain by design.
   - Run the MCX sync against a real account.
6. **Overfitting control.** PSR and one fixed-configuration split are done. Still to do:
   - log every backtest configuration tried in a session;
   - compute the DSR over that set;
   - PBO via CSCV on parameter sweeps;
   - **rolling or anchored** walk-forward (several splits) instead of a single split, with the split shown in the UI;
   - White's Reality Check or Hansen's SPA.
7. **Event-driven strategy evaluation.** Backtest the evidence labels themselves: direction-aligned holding, abstention as cash, plus risk-coverage curves for the abstention policy.
8. **Engineering.** Exchange calendar and corporate-action adjustment; automatic MCX contract rolling (a roll currently fails closed rather than splicing contracts); external sanity checks on FinBen or EDT tasks.
