# A Heterogeneous Multi-Agent Framework for Financial Event Detection and Cross-Market Signal Fusion in Indian Financial Markets

**Market Events** is the software that implements this framework. It is a research website and workbench
for dated financial news about Indian (NSE) companies. Small and large language models only *read*
an article: they decide whether it matters and extract what happened, quoting the source word for word.
Ordinary Python then checks that evidence against market prices that were actually available at the
decision time, including a reviewed commodity link such as crude oil → paint makers. It produces a signed,
explainable evidence score, or abstains when evidence is missing, and saves every step so it can be
audited and replayed.

> **Research tool, not advice.** The bundled demo articles, prices and model outputs are **synthetic**.
> They demonstrate how the software behaves, not market performance. Nothing here places orders.

## Quick start

Tested on Windows with Python 3.10.21 and Node.js. Run from the repository root.

```powershell
# one-time setup
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e ".[web,dev]"
npm.cmd --prefix web install

# web dashboard (Next.js on :3000 plus the Python API on :8000)
npm.cmd run dev
```

Open http://127.0.0.1:3000 and click **Explore demo**. It works offline with bundled evidence and recorded model responses.

For a final-year demonstration, open a demo story, run the recorded replay, and inspect the verdict and its source evidence in **Results**. Use the same decision cutoff when comparing methods.

Offline demo from the command line instead:

```powershell
.\.venv\Scripts\python.exe -m market_events --database data/demo.sqlite demo
.\.venv\Scripts\python.exe -m pytest -q        # run the test suite
```

To use real market data, choose **Connect real data** from Home. The Upstox integration imports completed daily candles and recent company news on demand. Configure the read-only token before refreshing. Article analysis with configured models has its own setup. See [the real-data setup guide](docs/LIVE_SETUP.md).

Open **Portfolio** to create a ₹1,00,000 Indian-stock paper account, import a holdings CSV or optionally connect Upstox, then review saved company evidence. The deployed private workspace saves portfolios and analysis in Neon Postgres. Live paper prices refresh from Upstox every 15 seconds; TradingView is an independent chart view. Sarvam supplies hosted analysis, with no local model installation required. See the [Portfolio setup](docs/PORTFOLIO_SPRINT_HANDOFF.md#portfolio-assistant-and-broker-setup) for the broker connection and Chrome shortcut.

Use the [mentor showcase](docs/MENTOR_SHOWCASE.md) for a complete presentation workflow and observed live proof. Use [diagnostics/](diagnostics/README.md) for the troubleshooting runbook, safe health checks, release evidence and archived verification history.

## How it works (catalyst to confirmation)

1. **Collect:** import a dated article and daily prices. Each record keeps *when it was published* and *when it became available*.
2. **Triage:** a filter agent (small or large model, depending on the chosen policy) decides whether the article is relevant, citing exact sentences.
3. **Extract:** a large-model event agent returns a structured event (type, company, amounts, verbatim quotes). Python rejects anything not found word for word in the source.
4. **Confirm:** deterministic agents resolve the company, apply a reviewed commodity-exposure rule, and compute the stock's excess return over its benchmark (plus the commodity move), using only data available before the cutoff.
5. **Fuse:** a fixed, versioned rule combines the evidence into a score in [−1, 1] with a coverage figure, or abstains. The score is evidence strength, not a probability.
6. **Record and review:** the run, every model call and the assessment are saved immutably. Later outcomes, policy comparisons and a strategy lab (backtests, Monte Carlo) work from the saved records.

## Project structure

```text
.
├── src/market_events/        Python research engine (all calculations live here)
│   ├── pipeline.py           orchestrator: runs the agents in order and saves each run
│   ├── agents/               model agents: filter_agent, event_agent, explanation_agent
│   ├── model_client.py       model calls: replay fixtures or live endpoint, schema checks, traces
│   ├── exposure.py           company resolution and reviewed commodity-exposure rules
│   ├── market_features.py    cutoff-safe returns, benchmark excess return, volume ratio
│   ├── technicals.py         RSI, SMA/EMA, MACD, Bollinger, ATR, ADX (context only)
│   ├── fusion.py             deterministic evidence score, coverage and abstention
│   ├── outcomes.py           later next-open → fifth-close outcomes, stored separately
│   ├── strategy_lab.py       historical backtests and Monte Carlo (studies end 2020-12-31)
│   ├── experiments.py        policy usage, matched cohorts, ablations, agreement checks
│   ├── screener.py           paper portfolio: rank companies from saved assessments + technicals
│   ├── sizing.py             paper portfolio: split an INR budget into whole-share paper buys
│   ├── risk_limits.py        paper portfolio: PASS/BLOCK each paper proposal, with reasons
│   ├── rebalance.py          paper portfolio: drift check and paper trades back to target
│   ├── paper_portfolio.py    paper portfolio: runs screen → size → risk, and rebalance → risk
│   ├── storage.py            SQLite ledger with append-only saved records
│   ├── api.py                FastAPI service used by the web dashboard
│   └── __main__.py           command-line interface (python -m market_events)
├── web/                      Next.js dashboard (UI only; proxies to the Python API)
├── app.py                    original Streamlit interface (same engine, fallback UI)
├── configs/                  companies, exposure rules, fusion rules, live universe, prices,
│                             screener_rules.json and portfolio_rules.json (paper portfolio)
├── prompts/                  versioned model instructions (filter, extract, explain)
├── tests/                    pytest suite and synthetic fixtures (tests/fixtures/)
├── scripts/                  dev launcher and model/policy comparison helpers
└── docs/                     documentation (start at docs/README.md)
```

`data/`, `runs/` and `scratch/` are local, gitignored working folders, so they may be missing on a fresh checkout.

## Paper portfolio (research only)

Four commands turn saved assessments into **paper proposals**. They never place orders, use only
local data available at `--as-of`, and print "research only, not advice". Add `--json` for raw output.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m market_events --database data/demo.sqlite paper-screen --as-of 2020-12-31T15:30:00+05:30
& $py -m market_events --database data/demo.sqlite paper-size --as-of 2020-12-31T15:30:00+05:30 --budget 100000
& $py -m market_events --database data/demo.sqlite paper-risk --plan runs/paper/<file>.json
& $py -m market_events --database data/demo.sqlite paper-rebalance --positions positions.json --cash 9200 --as-of 2020-12-31T15:30:00+05:30
```

- `paper-screen` checks each company's latest assessment against the screener rules and lists a ranked shortlist.
- `paper-size` splits a hypothetical INR budget across that shortlist in whole shares, keeping a cash buffer and a per-name cap.
- `paper-risk` marks each proposal in a saved plan PASS or BLOCK, with every reason it was blocked.
- `paper-rebalance` compares paper holdings with target weights and proposes paper trades for names that drifted outside the band.
  `positions.json` is a JSON list of `{"instrument_id": ..., "quantity": whole_shares}`.

Add `--json` for raw output. `paper-size` and `paper-rebalance` save the plan to `runs/paper/` (gitignored) unless you pass `--no-save`.

The demo database's runs are dated 2026, so the 2020 cutoff above returns an empty plan with a warning. The tests use synthetic fixtures only.

## Honest limits

- All bundled data is synthetic. There is no held-out real-market evaluation, and no accuracy, calibration or profitability claim.
- The real-data provider adapter is tested only with mocked HTTP. A real-account connection is unverified.
- Fusion weights and exposure rules are conceptual assumptions, not fitted or empirically validated.
- This is a single-user local tool, with no authentication or trading integration.
- The paper portfolio layer is tested only on synthetic data. Its rules are untuned defaults, and its proposals are not advice.
- The paper portfolio ideas are adapted from MIT-licensed trader-skill. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Further reading

- [Documentation index](docs/README.md): every document, grouped
- [User guide](docs/USER_GUIDE.md): how to use the website step by step, reading results, troubleshooting
- [System architecture](docs/SYSTEM_ARCHITECTURE.md) and [code map](docs/CODEBASE_GUIDE.md)
- [Experiments and their limits](docs/EXPERIMENTS.md)
- [Presentation pack](docs/presentation/SLIDES.md) and [demo and viva notes](docs/DEMO_AND_VIVA.md)
