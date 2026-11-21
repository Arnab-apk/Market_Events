# Herdr development workflow

This is the development-agent workflow for this repository. The application's relevance/extraction agents remain bounded pipeline stages; development tabs do not become autonomous trading agents.

## Current roles

| Herdr tab | Agent name | Owned work |
| --- | --- | --- |
| Coordinator | Primary session | Contract, integration, app navigation, final review and full validation |
| Data | `history-data` | Historical adapter, then the user-requested Next.js conversion and initial Python API |
| Quant | `strategy-quant` | Quant engine and numerical tests, followed by independent HTTP API tests |
| UI & Docs | `charts-ui` | Strategy lab UI, TradingView/Lightweight Charts, accessible animation and UI tests |

All three workers were started in the existing project tabs for this extension. Understanding and Pitch tabs are independent existing work; the coordinator does not stop or replace them. Tab IDs are session-local: discover them instead of reusing IDs from another Herdr session.

For the conversion, Data owns `web/` and `scripts/dev-web.mjs`; Quant owns `tests/test_web_api.py`. After the initial API handoff the coordinator owns `api.py` integration fixes, manifests, namespace isolation and verification. UI completed the Streamlit chart modules before handoff. The user's instruction to proceed without further permission questions applies across the project workers; they follow the current host permission policy and continue independent work if an inherited session restriction blocks a command.

## Repeatable execution cycle

1. Coordinator records scope, ownership, API signatures and acceptance criteria in [the extension contract](TRADING_EXTENSION_CONTRACT.md). Each worker reads it before editing. The user's clarified history boundary is frozen there.
2. Inspect Herdr only from a managed pane (`$env:HERDR_ENV -eq '1'`). Run `herdr agent list`, `herdr tab list --workspace $env:HERDR_WORKSPACE_ID` and `herdr pane list --workspace $env:HERDR_WORKSPACE_ID`. Never commandeer an occupied pane.
3. Give each available worker one task within its ownership using `herdr agent prompt <name> '<bounded task>'`. Existing workers share the working tree; they must not edit one another's files, commit, start nested agents or automatically download account data.
4. Each worker implements, runs focused checks, then reports file paths, test results, result contracts and concrete limitations. Contract changes require coordinator agreement before dependent callers change.
5. Coordinator reads the implementation and numerical assumptions, tests complete UI workflows and runs the full offline suite and lint. A worker saying 'done' is a handoff, not proof of integration.
6. Keep useful tabs available for follow-up. Do not close user-owned tabs, stop Herdr, upgrade its server or answer another agent's approval dialogs automatically.

Useful status commands:

```powershell
herdr agent list
herdr agent read history-data --source recent-unwrapped --lines 100
herdr agent read strategy-quant --source recent-unwrapped --lines 100
herdr agent read charts-ui --source recent-unwrapped --lines 100
```

To start a future worker, create a tab only when desired, read the returned root pane ID, then run `herdr agent start <unique-name> --kind codex --pane <returned-id>`. Use `--no-focus` on tab creation to preserve the user's focus. Herdr command syntax comes from the installed `herdr --skill` and command-group help.

## Acceptance gates for this extension

- All study bars end no later than 2020-12-31; provider fetch timestamps remain truthful.
- Indicator warmups stay missing; invalid/ambiguous price series fail visibly.
- Signals derived at a close execute at a later session open, with explicit costs and no invented fills.
- Monte Carlo is reproducible for a seed, bounded in workload and labelled as historical resampling.
- Opening pages and changing filters never calls a provider or model, nor launches a backtest.
- Failed downloads, missing credentials, no eligible history and external chart failures remain visible.
- Numerical tests, provider-mocked tests, Streamlit interaction tests and rendered browser checks have separately stated evidence.

For later product work, partition by stable API boundaries rather than asking every agent to edit the same page or pipeline. See [the product roadmap](PRODUCT_ROADMAP.md) for the next milestones.
