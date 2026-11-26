# Working on Market Events

- Start with [the codebase guide](docs/CODEBASE_GUIDE.md) and the relevant paths below. Use scoped `rg` searches and read surrounding lines before editing. Use sections of the [generated repo map](.cache/codex-context/map/CODESIGHT.md) for discovery and refresh it with `./scripts/codex-context.ps1 -Map`.
- For verbose, finite commands, use `./scripts/codex-context.ps1 -Compress 'git diff -- web/app'`. Keep the command in one argument. Use the ordinary shell for exact diffs and source reads, native PowerShell syntax, live servers, and interactive work. Initialize optional tooling with `./scripts/codex-context.ps1 -Setup`.
- Use project memory on demand when resuming prior work. Search project key `market-events`. Save short operational decisions or handoffs that help future sessions. Keep credentials, private holdings, and raw transcript dumps out of memory.
- Give each Herdr worker explicit file ownership, an acceptance check, and the relevant handoff link. At a milestone, record changed files, verification, and the next open item. Use `/compact` to continue the same task and `/new` for unrelated work. Use `/model` for a lighter reasoning effort on straightforward edits. Use `$paleo` when a concise reply helps.

| Area | Start here |
| --- | --- |
| Python research engine and API | `src/market_events/`, `tests/`, `pyproject.toml` |
| Website and local launch | `web/app/`, `web/AGENTS.md`, `web/tests/`, `package.json` |
| Research and presentation | `docs/DECISIONS.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/presentation/` |
| Workstream handoffs | `docs/UI_REDESIGN_PLAN.md`, `docs/PORTFOLIO_SPRINT_HANDOFF.md` |
