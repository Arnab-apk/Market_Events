# Presentation readiness plan (target: 1 December 2026)

Goal: on 1 December the project must demo reliably, end to end, and look polished on a projector.
Baseline on 2026-11-21: `pytest -q` → 521 passed. Backup snapshot:
`D:\projects\Final_Yr_Proj_backup_2026-11-21.tar.gz`.

## Demo story (what the audience must see working)

1. Open the Next.js dashboard → **Load synthetic demo (replay)** (offline, no keys).
2. Import / inspect evidence (articles + prices) in the source inbox.
3. Analyse a commodity-shock article (crude oil → paint makers) under an execution policy.
4. Open the saved result: evidence label, signed score, coverage, reasons, source spans, audit trail.
5. Later outcomes (next open → 5th-session close), kept separate from the decision.
6. Compare policies (`llm_only` vs `slm_filter` vs `slm_delegate`): cost/tokens/results.
7. Strategy lab: indicators, a backtest with fees/slippage, a Monte Carlo bootstrap.

Everything synthetic must stay labelled synthetic. Do not invent performance claims.

## Agents and file ownership (one Herdr tab per agent, named after it)

`research` (tab `research`) owns `docs/research/**` and may only append to Cross-agent requests.

| Agent | Owns (may edit) | Must not edit |
| --- | --- | --- |
| `demo-ui` | `web/**`, `scripts/dev-web.mjs` | `src/`, `tests/`, `docs/` |
| `demo-backend` | `src/market_events/**`, `tests/**`, `configs/**`, `data/**` fixtures, `app.py` | `web/`, `docs/` |
| `pitch-docs` | `docs/presentation/**` (new), `docs/DEMO_AND_VIVA.md`, README demo section | any code |
| Coordinator (primary session) | this file, integration, final verification | — |

Rules for every agent:
- Read this file and `docs/BUILD_CONTRACT.md` first. Work only inside your ownership.
- Do not commit, do not start nested agents, do not download account/provider data, no new heavy dependencies.
- Only `demo-ui` runs the dev servers (ports 3000 and 8000). Others use pytest / FastAPI TestClient.
- If you need a change in someone else's area, append a request under **Cross-agent requests** below and continue.
- Finish with a short report: files changed, checks run with results, known limitations.

## Acceptance gates

- `.venv\Scripts\python.exe -m pytest -q` passes; `ruff check .` passes.
- `npm.cmd run check` and `npm.cmd run build` pass.
- The 7-step demo story works in the browser with no console errors, in light and dark mode,
  readable at 1366×768 and 1920×1080.
- Every step has an offline fallback (replay mode); nothing needs a live key on stage.

## Cross-agent requests

(append here: `- [from → to] request`)
- [research → demo-backend] Add a gold-label fixture (relevance, event_type, company_id, commodity_id) for the 35 synthetic articles in `tests/fixtures/articles.jsonl`, plus a read-only `extraction_agreement(runs, gold)` in `experiments.py`. It should report per-policy filter recall/precision, field accuracy, validation-status rates and abstention rate, labelled "synthetic sanity check, not a benchmark" (see `docs/research/RESEARCH_BRIEF.md` §4a-1). — DONE (demo-backend)
- [research → demo-backend] Add an optional `configs/model_prices.json` (per-1k input/output token rates) and an `estimated_cost` field in `summarize_policies`, computed only for live groups with complete token usage and null otherwise, never filling in missing counts (§4a-2). — DONE (demo-backend)
- [research → demo-backend] Add a probabilistic Sharpe ratio (Bailey & López de Prado; vs SR*=0, using skewness, kurtosis and n) to `run_backtest` results, with the assumption note "single configuration; not deflated for the number of configurations tried", plus a unit test (§4a-3). — DONE (demo-backend)
- [research → demo-ui] In the strategy lab, show the new PSR and its "not deflated for trials" note beside Sharpe. In the policy comparison view, show the extraction-agreement table and `estimated_cost` with their labels, and hide them when the API returns null or unavailable (§4a-4). — DONE (demo-ui): PSR card beside Sharpe with the not-deflated note, extraction-agreement table (label + notes) and an estimated-cost column, each hidden when null.
- [research → pitch-docs] Add a "Related work & novelty" slide under `docs/presentation/` built from RESEARCH_BRIEF §1–2, citing only entries marked [V] and using the novelty statement's "to our knowledge" wording (§4a-5). — DONE (pitch-docs)
- [research → pitch-docs] Add a "Three kinds of look-ahead" slide and viva answer: data availability (handled), revisions (handled), parametric model knowledge (not tested; limited because the model only extracts and the articles are synthetic) (§4a-6). — DONE (pitch-docs)
- [research → pitch-docs] In `docs/DEMO_AND_VIVA.md`, define the outcome as a market-adjusted (beta = 1) next-open → 5th-close return that measures post-cutoff drift, separate from the reaction-day evidence in the score. List market-model CAR with BMP tests as future work (§4a-7). — DONE (pitch-docs)
- [research → pitch-docs] Add a commodity-exposure motivation slide: crude-linked inputs are roughly 30–50% of paint raw-material costs, and ATF is roughly 35–40% of Indian airline operating costs. Label these "secondary press sources; demo rules are synthetic" and add the Reliance sign-ambiguity example (§4a-8). — DONE (pitch-docs)
- [research → pitch-docs] Add a demo-script beat for step 7: rerun the same pre-chosen backtest at 2× fees/slippage, and state that the configuration was fixed in advance, not tuned on stage (§4a-9). — DONE (pitch-docs)
- [demo-ui → demo-backend] Step 7 can't run offline right now. `HistoryRequest` caps dates at 2020-12-31, but the replay demo only has 2026 bars (16 per company), and the local/live workspace has 0 bars. So *Load local history* / *Run backtest* return 422 in every workspace without a live Upstox token. Please add a clearly labelled synthetic pre-2021 daily OHLCV fixture to the demo workspace (for example `SYNTHETIC:LAB_QA_ONLY`, about 300+ sessions in 2019–2020, loaded by `/api/demo` and listed by `read_companies` for the demo universe). The UI already shows a "SYNTHETIC QA HISTORY · not performance evidence" banner for `SYNTHETIC:` ids. Until then the lab shows an explanatory empty state. — DONE (demo-backend): `SYNTHETIC:LAB_DEMO`, 523 sessions 2019–2020, loaded by `/api/demo` and the CLI `demo`. It is listed in `/api/workspace` companies for the demo universe via `configs/synthetic_lab.json` rather than `read_companies`, so it never enters event-analysis snapshots.
- [demo-ui → demo-backend] Optional: replay `ModelCall`s carry `input_tokens`/`output_tokens = null`, so the policy comparison can only show call counts per model tier, not tokens. If the recorded fixtures have token counts, persisting them (still labelled replay) would make step 6 more concrete. Don't invent counts. — SKIPPED: the recorded replay fixtures contain no token counts, so none can be persisted without inventing them. Replay rows keep tokens null and `estimated_cost` null.
- [demo-backend → demo-ui] The synthetic demo now has a labelled offline strategy-lab series, `SYNTHETIC:LAB_DEMO` (523 bars, 2019–2020). It appears in `/api/workspace` `companies` (demo universe only) with `synthetic: true`, `research_bars: 523` and a `source` note, so the lab auto-selects it. Please reword the demo-only banner "the bundled 2026 demo is excluded by the 2020 cutoff…" so it no longer implies the demo has no lab history. Keep the existing "SYNTHETIC QA HISTORY · Interface verification only; not performance evidence" warning. — DONE (demo-ui): banner now shows only when no company has pre-2021 bars; the SYNTHETIC QA HISTORY warning is kept.
- [demo-backend → demo-ui] New API fields: backtest `metrics.probabilistic_sharpe` (may be null) plus an assumptions note containing "not deflated for the number of configurations tried"; `/api/comparisons` `extraction_agreement` (null when no gold-labelled runs) with `label`, `groups[]` and `notes[]`; `policy_summary[].estimated_cost` and `cost_currency` (null in replay, and null until rates are added to `configs/model_prices.json`, which ships empty). `/api/explain` in replay now returns 422 with a readable `detail` instead of 500. — DONE (demo-ui): the UI reads these fields, and the explanation button is disabled for replay runs with a note.
- [demo-backend → pitch-docs] Demo beat for steps 3–4, from the existing data: `syn-002` at 2026-01-12 12:00 UTC gives equity +0.40, crude leg −0.50, score 0.04, neutral with a conflict. The same article at 10:30 UTC (16:00 IST; after the equity close, before crude settles at 11:00 UTC) abstains with "Missing or stale mandatory commodity return". Contrasts: `syn-001` positive 0.40, `syn-005` abstain, `syn-004` irrelevant. The extraction-agreement table shows filter recall 1.0 and precision below 1 in replay, because gold labels mark the unconfirmed SpiceJet items irrelevant. Label it "synthetic sanity check, not a benchmark". Step 7 numbers come from `SYNTHETIC:LAB_DEMO`, an authored random walk: never present them as performance. — DONE (pitch-docs)
- [demo-backend → coordinator] The Starlette TestClient deprecation is silenced narrowly in `tests/conftest.py`. The durable fix is to replace the dev dependency `httpx` with `httpx2` in `pyproject.toml` and reinstall. That file and the network install are outside demo-backend ownership.
- [demo-ui → demo-backend] `assessment.explanation` prints raw floats and runs sentences together. Example: "neutral: evidence score 0.03999999035395829; coverage 1.00. Equity and exposure-adjusted commodity evidence disagree Score is deterministic…". It's shown verbatim under "Why this label" on stage. Please round the score (3 dp) and add the missing full stop. The UI does not rewrite backend text.
