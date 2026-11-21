# Step-7 demo backtest: review against the backtest-expert checklist

Reviewed 2026-11-21 against the practitioner checklist in the community skill
`tradermonty/claude-trading-skills@backtest-expert`. Only the skill's written guidance was applied;
its scripts were not run. The numbers come from this project's own `strategy_lab.run_backtest`, using
`sma_cross` (20/50) on `tests/fixtures/synthetic_lab_history.csv`. That file is `SYNTHETIC:LAB_DEMO`,
a seeded zero-drift random walk covering 2019-01-01 to 2020-12-31 (523 bars).

| Metric | Base (10 bps fee, 5 bps slippage) | Stress (2× costs) |
|---|---|---|
| Total return | −36.9% | −38.4% |
| Buy-and-hold benchmark | +26.1% | +25.9% |
| Sharpe | −1.37 | −1.44 |
| Probabilistic Sharpe (vs 0) | 0.024 | 0.018 |
| Max drawdown | −39.5% | −40.7% |
| Closed trades / win rate | 8 / 25% | 8 / 25% |

## Checklist verdict

| Checklist item | Status |
|---|---|
| Clear, rule-based hypothesis | ✅ fixed SMA 20/50 cross, long/cash, next-open fills |
| ≤ 4 tunable parameters | ✅ 2 |
| Realistic costs, 1.5–2× slippage stress | ✅ 2× stress shown; it is never better |
| Sample size ≥ 30 trades (preferably 100+) | ❌ **8 closed trades**: results carry no statistical weight |
| ≥ 5 years, multiple regimes | ❌ 2 years (the lab window allows 2015–2020) |
| Parameter plateau, not spike | ❌ no sensitivity grid |
| Walk-forward / out-of-sample | ❌ missing (also a synopsis objective) |

## How to present it

This is a **sanity check, not a strategy result**. On a random walk, an honest backtester must not
find an edge. Costs make it worse, and a probabilistic Sharpe ratio of about 2% says there is no evidence of skill.
Say this before the audience reads the −37% figure.

## Requests (priority order)

1. UI: show a "low sample size" warning when closed trades < 30, next to Sharpe and PSR.
2. Backend: walk-forward split (in-sample / out-of-sample metrics side by side) for a fixed configuration.
3. Backend: extend the synthetic series to 2015–2020 (still labelled random walk) for more trades.
4. Optional: a small fast/slow parameter grid that shows a plateau versus a spike.
