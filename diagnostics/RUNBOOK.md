# Troubleshooting Market Events

## Capture safe context first

From the repository root:

```powershell
.venv/Scripts/python.exe diagnostics/doctor.py --output diagnostics/local/health.json
git status --short
npm.cmd run check
```

The doctor makes no provider/model requests and does not initialize a database. It prints package versions, configured/not-configured flags and local record counts. It never exports credential values, article text or holdings. `diagnostics/local/` is ignored; review all artifacts before sharing them.

## Portfolio or analysis missing after a deployment

Production requires a connected persistent Postgres database. Confirm Neon is connected to the correct Vercel project and **Production** environment, then redeploy after changing environment variables. `MARKET_EVENTS_DATABASE_URL` overrides `DATABASE_URL`. Keep these variables server-only. Hosted startup fails if no persistent database is configured.

The private workspace uses Neon. The synthetic demo intentionally uses a disposable bundled SQLite copy. Confirm the website's Data selector before assuming records were lost. Authorized Vercel project visitors share the current private workspace; separate personal accounts are not implemented.

For an explicit read-only database check after preparing an ignored environment file:

```powershell
.venv/Scripts/python.exe diagnostics/doctor.py --env-file .cache/market-events-storage.env --check-database --output diagnostics/local/database-health.json
```

Use the Neon console's backup/restore facilities before any destructive database maintenance. Do not drop or recreate the production ledger to repair a deployment. The additive schema initializer runs under a migration lock. Immutable source/run tables reject updates and deletes. A portfolio conflict means another tab saved a newer revision; use **Reload saved portfolio** before retrying.

## Live quotes, news or models fail

1. Check Settings → Connections. A configured badge proves only that a setting exists.
2. Use an explicit bounded refresh, inspect its report, and distinguish missing data from provider errors.
3. Paper quotes use the Analytics Token and show actual last-trade timestamps. A closed exchange or unchanged trade can leave prices steady. Refresh pauses in hidden tabs.
4. Sarvam uses `SARVAM_API_KEY`; neither analysis role requires a local model server. Inspect the saved Model call audit for provider failures and token/latency data.
5. A saved abstention can be correct even when all services work. Check event family, evidence coverage, source quotes and decision cutoff.

TradingView is independent of valuation and analysis. An unavailable symbol or exchange entitlement affects its external chart. Use **Open this chart on TradingView**; do not scrape chart prices or replace missing quotes with invented values.

## Website or protected deployment cannot be opened

Use the signed-in browser to open https://final-yr-proj.vercel.app. Vercel Authentication is required. Do not disable protection or generate temporary bypass credentials merely to test a page. Verify the linked project before running Vercel mutations; a checkout subdirectory can resolve a different project.

For local development use `npm.cmd run dev`. `MARKET_EVENTS_API_URL` selects the upstream Python service. Read-only requests and explicit writes use the Next proxy's allow-list and origin checks. Extension permissions do not bypass those checks.

## Run the relevant verification

```powershell
.venv/Scripts/python.exe -m pytest -q
node.exe --test web/tests/*.test.mjs
npm.cmd run check
npm.cmd run build
npm.cmd --prefix web run test:e2e
```

Browser tests expect the frontend/API stack and must use disposable databases: imports, analysis and portfolio scenarios deliberately write records. Set `PLAYWRIGHT_BASE_URL` when testing an isolated server. `tests/test_persistent_storage.py` supports `MARKET_EVENTS_TEST_DATABASE_URL`; it creates and removes a unique test schema, preserving production records. Never pass real secrets as command-line literals or paste raw environment output into reports.

Store new reports under `diagnostics/local/YYYY-MM-DD/`. Promote only sanitized summaries/screenshots into `diagnostics/evidence/` and link them from the handoff.
