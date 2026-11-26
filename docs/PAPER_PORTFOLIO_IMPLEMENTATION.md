# Implementation brief: Paper Portfolio layer (screener, sizing, risk, rebalance)

> Give this file to Claude Code from the repository root:
> `claude "Read docs/PAPER_PORTFOLIO_IMPLEMENTATION.md and implement it fully. Follow every rule in it."`

## 0. Goal in one paragraph

Add a **paper portfolio** research layer to Market Events. It turns saved evidence assessments
into a ranked shortlist (**screener**), sizes a hypothetical INR budget across that shortlist
(**sizing**), checks every proposed paper trade against user limits (**risk**), and proposes
trades to bring a paper portfolio back to target weights (**rebalance**). The logic is adapted
from four skills in https://github.com/Jakeschincariol/trader-skill (MIT licence):
`trader-screener`, `trader-budget`, `trader-risk`, `trader-rebalance`. They are rebuilt for
Indian markets (NSE equities, INR, whole shares) inside `src/market_events/`. **Nothing places
orders.** Outputs are always labelled "paper proposal — research only, not advice".

## 1. Hard rules (read before writing any code)

1. **No trading and no broker.** `docs/DECISIONS.md` says "No trading, brokerage integration…".
   That still holds. No broker SDK, no order APIs, no Alpaca/Upstox order endpoints. Outputs are
   called `PaperTradeProposal`, never "order".
2. **No network calls** in any new module or test. Prices come only from the local SQLite ledger
   (`Storage.list_observations()`) or test fixtures.
3. **Cutoff safety.** Every function takes an `as_of` aware datetime. Only use assessments whose
   run decision time is `<= as_of`, and prices whose `available_at <= as_of`. This mirrors
   `market_features.py`. Write a test that proves a later price or later run is ignored.
4. **Do not port the US-only parts.** No SEC EDGAR, 13F, House PTRs, NYSE calendar, Yahoo/Stooq,
   US tax or wash-sale rules, `place_stock_order` JSON shape, or USD.
5. **Reference repo is read-only data.** Clone it into a temporary folder **outside** this repo
   (for example `%TEMP%\trader-skill-ref`), read `trader-screener/screen.py`,
   `trader-budget/size.py`, `trader-risk/check.py`, `trader-rebalance/rebalance.py` for ideas,
   and **do not run** any of its scripts or tests. Write fresh code in this project's style.
   Delete the clone when done.
6. **Keep existing behaviour.** All current tests must still pass. Do not change `fusion.py`,
   `pipeline.py`, existing prompts, existing schemas' fields, or existing CLI/API spellings.
   Only add.
7. **Style.** Python 3.10, Pydantic v2 models in `schemas.py` style, pure functions, type hints,
   short docstrings, `ruff` clean (line length 100). Configs are JSON in `configs/` with a
   required non-empty `"version"` string, like `fusion_rules.json`.
8. **Git.** Create branch `feat/paper-portfolio` first. Do not commit or push unless the user asks.

## 2. Files to add or change

| Path | Action | Purpose |
|---|---|---|
| `src/market_events/screener.py` | new | rank companies from assessments + technicals |
| `src/market_events/sizing.py` | new | split an INR budget into whole-share paper buys |
| `src/market_events/risk_limits.py` | new | PASS/BLOCK each paper proposal with reasons |
| `src/market_events/rebalance.py` | new | drift check and paper trades back to target |
| `src/market_events/paper_portfolio.py` | new | thin orchestrator: screen → size → risk; rebalance → risk |
| `src/market_events/schemas.py` | add models only | see section 3 |
| `configs/screener_rules.json` | new | default screening rules |
| `configs/portfolio_rules.json` | new | budget, buffer, caps, limits, band |
| `src/market_events/__main__.py` | add subcommands | `paper-screen`, `paper-size`, `paper-risk`, `paper-rebalance` |
| `src/market_events/api.py` | add routes | `POST /api/paper/screen`, `/api/paper/size`, `/api/paper/rebalance` |
| `tests/test_screener.py`, `tests/test_sizing.py`, `tests/test_risk_limits.py`, `tests/test_rebalance.py`, `tests/test_paper_portfolio.py` | new | section 6 |
| `tests/fixtures/paper_portfolio.json` | new | synthetic fixture data (`SYNTHETIC:` ids) |
| `THIRD_PARTY_NOTICES.md` | new | MIT notice + link for trader-skill (copy its LICENSE text) |
| `docs/DECISIONS.md` | append entry | dated entry: paper portfolio added; still no trading |
| `docs/CODEBASE_GUIDE.md`, `README.md` | update | add the new modules to the structure list |

Web UI is **phase 2** (section 8). Do not touch `web/` in phase 1.

## 3. New schemas (add to `schemas.py`)

Read `AnalysisRun` and `Assessment` in `schemas.py` first and use their real field names for the
run's company and decision time. Add:

- `ScreenRow`: `company_id: str`, `instrument_id: str`, `passed: bool`,
  `checks: list[dict]` (each `{"rule": str, "value": float|None, "limit": float, "passed": bool,
  "margin": float|None}`), `score: float|None`, `rank: int|None`, `run_id: str|None`.
- `ScreenResult`: `as_of`, `rules_version: str`, `rows: list[ScreenRow]`, `shortlist: list[str]`.
- `PaperPosition`: `instrument_id`, `quantity: int (ge=0)`, `price: float (gt=0)`,
  `value: float`, `weight: float`.
- `PaperTradeProposal`: `proposal_id: str` (stable hash of contents), `instrument_id`,
  `side: Literal["buy","sell"]`, `quantity: int (gt=0)`, `price: float (gt=0)`,
  `amount_inr: float`, `reason: str`, `label: str = "paper proposal — research only, not advice"`.
- `RiskVerdict`: `proposal_id`, `verdict: Literal["PASS","BLOCK"]`, `reasons: list[str]`.
- `PaperPlan`: `as_of`, `rules_version`, `budget_inr`, `cash_inr`, `positions`,
  `proposals`, `verdicts`, `warnings: list[str]`.

## 4. Configs

`configs/screener_rules.json`
```json
{
  "version": "screener-v1",
  "use_latest_run_per_company": true,
  "rules": [
    {"field": "evidence_score", "op": ">=", "value": 0.15},
    {"field": "coverage", "op": ">=", "value": 0.6},
    {"field": "direction", "op": "==", "value": "positive"},
    {"field": "rsi14", "op": "<=", "value": 70}
  ],
  "rank_by": "evidence_score",
  "max_shortlist": 5
}
```
Supported ops: `>=`, `<=`, `>`, `<`, `==`, `!=`, `in`. Fields come from the latest
`Assessment` (`evidence_score`, `coverage`, `direction`) and from `compute_technicals` output
(`rsi14`, `sma20`, `sma50`, `adx14`, … use the real keys that function returns). Abstained
assessments always fail with reason `"abstained: <abstention_reasons>"`. A missing value fails
the rule (never pass on missing data). Reject unknown ops or fields with `ValueError`.

`configs/portfolio_rules.json`
```json
{
  "version": "portfolio-v1",
  "currency": "INR",
  "budget_inr": 100000,
  "cash_buffer_pct": 0.10,
  "max_position_pct": 0.25,
  "min_order_inr": 5000,
  "max_order_inr": 50000,
  "weighting": "score",
  "rebalance_band_pp": 5,
  "min_trade_inr": 1000,
  "max_price_age_days": 5,
  "allowed_market_families": ["equity"],
  "blocked_instruments": [],
  "max_proposals_per_plan": 20
}
```
Validate: version non-empty; percents in (0, 1); amounts > 0; `weighting` in
`{"score","equal"}`; reject NaN/inf (copy the `finite_number` idea from `fusion.py`).

## 5. Algorithms (exact)

### 5.1 Screener (`screen(assessment_rows, technicals, rules, as_of) -> ScreenResult`)
1. Pick the latest run per company with decision time `<= as_of`.
2. Evaluate every rule; record value, limit, pass/fail and margin (`value - limit`, sign so that
   positive = passed comfortably; `None` for non-numeric).
3. `passed` = all rules pass. Rank passed rows by `rank_by` descending, tie-break by `company_id`.
4. `shortlist` = first `max_shortlist` instrument ids.

### 5.2 Sizing (`size(shortlist_scores, prices, rules, as_of) -> PaperPlan`)
1. Investable = `budget_inr × (1 − cash_buffer_pct)`. Cap = `budget_inr × max_position_pct`.
2. Raw weight = evidence score (`"score"`) or 1 (`"equal"`).
3. **Water-fill with cap:** allocate investable proportional to weight among uncapped names; any
   name above cap is set to cap and removed; repeat with what is left. If every name is capped,
   the rest stays cash (add a warning).
4. Drop names whose slice < `min_order_inr`, then redo step 3 with the remaining names. Repeat
   until stable. Add a warning for each dropped name.
5. **Whole shares** (NSE delivery has no fractional shares): `qty = floor(slice / price)`.
6. **Use leftover:** while some name has `price <= leftover` and `(qty+1) × price <= cap`, buy one
   more share of the name furthest below its slice (largest `slice − qty × price`; tie-break by id).
   It may end above its slice, never above cap, never into the buffer.
7. Everything left is cash. Emit one `buy` `PaperTradeProposal` per name with qty > 0.

**Worked example (must be a test):** budget ₹1,00,000, buffer 10 %, cap 25 %, min order ₹5,000.

| id | score | price ₹ |
|---|---|---|
| SYNTHETIC:NSE:AAA | 0.60 | 1450 |
| SYNTHETIC:NSE:BBB | 0.40 | 820 |
| SYNTHETIC:NSE:CCC | 0.30 | 2310 |
| SYNTHETIC:NSE:DDD | 0.20 | 415 |
| SYNTHETIC:NSE:EEE | 0.05 | 990 |

- EEE's first slice is ₹2,903.23, under ₹5,000, so it is dropped.
- Slices: AAA ₹25,000 (capped), BBB ₹25,000 (capped), CCC ₹24,000, DDD ₹16,000.
- Final quantities: AAA 17 (₹24,650), BBB 30 (₹24,600), CCC 10 (₹23,100), DDD 42 (₹17,430).
- Spent ₹89,780. Cash ₹10,220 (₹10,000 buffer + ₹220 idle).

### 5.3 Risk (`check(proposals, positions, cash_inr, prices, rules, as_of) -> list[RiskVerdict]`)
Apply proposals in order to a running paper state. BLOCK (collect **all** reasons) when:
- instrument is in `blocked_instruments`, or its `market_family` is not allowed (commodities and
  benchmarks such as `NIFTY50` are always blocked as buys);
- quantity not a positive integer, price ≤ 0, NaN/inf, or unknown side → "malformed";
- `amount_inr > max_order_inr` or `< min_order_inr` (sells below min are allowed if they close
  the whole position);
- sell quantity > held quantity → "would go short";
- after the fill, position weight > `max_position_pct` of total portfolio value;
- after a buy, cash < `cash_buffer_pct × total value` → "eats cash buffer";
- newest price with `available_at <= as_of` is older than `max_price_age_days` → "stale price";
- same `proposal_id` seen twice → "duplicate";
- more than `max_proposals_per_plan` proposals → block the extras.
Blocked proposals do not change the running state. Passed ones do.

### 5.4 Rebalance (`rebalance(positions, cash_inr, targets, prices, rules, as_of) -> PaperPlan`)
1. Value every position at its latest cutoff-safe price. Total = positions + cash.
2. Drift (pp) = `(weight − target) × 100`. Only names with `|drift| > rebalance_band_pp` trade.
3. **Sells first:** sell `floor((value − target_value) / price)` shares.
4. **Then buys,** using only cash above the buffer (`cash − buffer_pct × total`):
   `floor(min(target_value − value, available) / price)`; never above cap.
5. Skip any trade under `min_trade_inr`. Names not in targets are sold fully (reason
   "not in targets").

**Worked example (must be a test):** total ₹1,00,000. Targets AAA 45 %, BBB 45 % (cash 10 %).
Held: AAA 40 sh × ₹1,450 = ₹58,000 (58 %); BBB 40 sh × ₹820 = ₹32,800 (32.8 %); cash ₹9,200.
- Drift: AAA +13 pp, BBB −12.2 pp. Both are outside the 5 pp band.
- Sell AAA 8 sh (₹11,600). AAA becomes ₹46,400 and cash ₹20,800.
- Buy BBB: available = 20,800 − 10,000 = ₹10,800, so buy 13 sh (₹10,660), not 14.
- Result: BBB ₹43,460, cash ₹10,140. Check: 46,400 + 43,460 + 10,140 = 1,00,000.

### 5.5 Orchestrator (`paper_portfolio.py`)
- `build_plan(storage, rules_root, as_of, budget_inr=None) -> PaperPlan`: screen → size → risk.
- `build_rebalance(storage, rules_root, positions, cash_inr, as_of) -> PaperPlan`: targets come
  from a fresh `build_plan`'s weights; then rebalance → risk.
- Every plan carries both config versions and the label. Optionally write JSON to
  `runs/paper/<as_of>-<hash>.json` (folder is gitignored; create it if missing).

## 6. Tests (pytest, offline, synthetic only)

Write tests **before** each module (TDD). Minimum:
- `test_screener.py`: each op; missing value fails; abstained fails with reason; ranking and
  tie-break; later run after `as_of` ignored; unknown field/op raises.
- `test_sizing.py`: the worked example exactly; equal weighting; all-capped → warning + cash;
  every name under min order → empty plan + warning; price ≤ 0 or NaN rejected; total spent
  + cash == budget (to the paisa).
- `test_risk_limits.py`: one test per BLOCK reason; multiple reasons collected; blocked proposal
  does not change state; commodity and `NIFTY50` buys blocked; stale price; duplicate id.
- `test_rebalance.py`: the worked example exactly; inside band → no trades; sells before buys;
  buffer limits buys; name not in targets sold fully; min trade skip.
- `test_paper_portfolio.py`: end-to-end on the demo database (`python -m market_events demo`
  data) or a fixture; plan is deterministic (same inputs → same `proposal_id`s); no network
  (monkeypatch `socket.socket` to raise).
- CLI and API: one smoke test each (use `httpx`/FastAPI `TestClient` like `tests/test_web_api.py`).

## 7. CLI and API

```
python -m market_events --database data/demo.sqlite paper-screen --as-of 2020-12-31T15:30:00+05:30
python -m market_events --database data/demo.sqlite paper-size --as-of ... [--budget 100000]
python -m market_events --database data/demo.sqlite paper-risk --plan runs/paper/<file>.json
python -m market_events --database data/demo.sqlite paper-rebalance --positions positions.json --cash 9200 --as-of ...
```
Print a readable table plus the "research only, not advice" label. `--json` prints raw JSON.
API routes return the Pydantic models as JSON, follow the existing error style in `api.py`, and
accept the same parameters.

## 8. Phase 2 (only after phase 1 is green and the user asks)

- Web dashboard page "Paper portfolio": shortlist table with each rule's pass/fail, sizing table,
  PASS/BLOCK chips with reasons, rebalance drift bars. Reuse existing CSS tokens in
  `web/app/*.css`; no new UI framework.
- Optional NSE price alerts (rebuild of `trader-alerts`): NSE trading calendar from a reviewed
  config file, prices from the local ledger only.

## 9. Done checklist (run all on Windows from repo root)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m market_events --database data/demo.sqlite demo
.\.venv\Scripts\python.exe -m market_events --database data/demo.sqlite paper-size --as-of 2020-12-31T15:30:00+05:30
```
- [ ] All old and new tests pass; ruff clean.
- [ ] Both worked examples reproduce the exact numbers above.
- [ ] `grep -ri "place_stock_order\|alpaca\|sec.gov\|NYSE" src` finds nothing new.
- [ ] No network imports (`urllib`, `requests`, `httpx`) in the four new modules.
- [ ] `THIRD_PARTY_NOTICES.md` added; `DECISIONS.md`, `CODEBASE_GUIDE.md`, `README.md` updated.
- [ ] Reference clone deleted; nothing committed unless the user asked.
- [ ] Final message lists files changed, test count, and any limitation.
