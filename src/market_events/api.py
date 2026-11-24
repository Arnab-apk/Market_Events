"""Local HTTP API for the Next.js UI in web/, reusing the same research engine. GET routes read the
ledger through a read-only view; anything that writes, calls a provider or calls a model is an
explicit POST. Workspace paths come only from server configuration, never from the request.

Run via ``python -m uvicorn market_events.api:app --host 127.0.0.1 --port 8000``.
"""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .api_schemas import (
    AnalysisRequest,
    BacktestRequest,
    BatchRequest,
    HistoryRequest,
    ImportRequest,
    MonteCarloRequest,
    SyncRequest,
    TechnicalRequest,
)
from .config import load_settings, read_companies, read_config
from .experiments import run_experiments
from .exporting import case_payload
from .ingestion import import_articles, import_market_prices
from .live_data import sync_historical, sync_live
from .model_client import ModelError
from .plain_language import describe_run
from .pipeline import (
    Dependencies,
    analyse_article,
    analyse_synced_news,
    compute_outcomes,
    explain_run,
    readiness,
    run_demo,
)
from .storage import Storage
from .technicals import compute_technicals
from .web_workspace import view_workspace

Workspace = Literal["local", "demo"]
Universe = Literal["demo", "live"]
IST = ZoneInfo("Asia/Kolkata")


def create_app(root=None, settings=None):
    """App factory supports isolated offline tests without loading local secrets."""
    api = FastAPI(title="Market Events Research API", version="0.1.0")
    api.state.root = Path(root or os.getenv("MARKET_EVENTS_ROOT", ".")).resolve()
    api.state.settings = settings

    # ---------------------------------------------------------------------------
    # Request boundary, error mapping and health
    # ---------------------------------------------------------------------------

    @api.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Browser mutations go through Next's same-origin route. This loopback
        # service also refuses cross-origin browser POSTs sent directly to it.
        origin = request.headers.get("origin")
        if request.method != "GET" and origin:
            allowed = os.getenv("MARKET_EVENTS_WEB_ORIGIN", "http://127.0.0.1:3000")
            if origin not in {allowed, "http://localhost:3000"}:
                return JSONResponse({"detail": "Cross-origin mutation refused"}, status_code=403)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 10_000_000:
            return JSONResponse({"detail": "Request exceeds 10 MB limit"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.exception_handler(ValidationError)
    async def invalid_record(request, exc):
        # Pydantic diagnostics can contain user input; do not echo arbitrary records.
        return JSONResponse(
            {"detail": "Invalid record or configuration; check required fields and timestamps"},
            status_code=422,
        )

    @api.exception_handler(ValueError)
    async def invalid_operation(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @api.exception_handler(ModelError)
    async def model_unavailable(request, exc):
        # Replay has no recorded output for this task, or a live model failed. The
        # saved parent run is unchanged; report it rather than a server error.
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @api.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse(
            {"detail": "Workspace database could not be read or updated"}, status_code=409
        )

    @api.get("/api/health")
    def health():
        return {"status": "ok", "history_end": "2020-12-31"}

    # ---------------------------------------------------------------------------
    # Shared helpers: workspace selection, scoping and chart rows
    # ---------------------------------------------------------------------------

    def configuration(workspace, universe):
        base = api.state.settings or load_settings(api.state.root)
        result = base.model_copy(deep=True)
        result.root = api.state.root
        result.universe = "demo" if workspace == "demo" else universe
        if workspace == "demo":
            # A hosted deployment points this at a writable copy (see vercel_app.py).
            demo = os.getenv("MARKET_EVENTS_DEMO_DATABASE")
            result.database_path = Path(demo) if demo else api.state.root / "data/web_demo.sqlite"
            result.mode = "replay"
        elif not result.database_path.is_absolute():
            result.database_path = api.state.root / result.database_path
        return result

    @contextmanager
    def dependencies(workspace, universe, *, write=False):
        config = configuration(workspace, universe)
        if write:
            with Storage(config.database_path) as store:
                yield Dependencies(store, config)
        else:
            with view_workspace(config.database_path) as store:
                yield Dependencies(store, config)

    def namespace(identifier, config):
        return identifier.startswith("LIVE:") == (config.universe == "live")

    def run_json(run):
        """Saved run plus API-only plain-language fields (never persisted)."""
        return {**run.model_dump(mode="json"), **describe_run(run)}

    def demo_story(config):
        """Featured demo-story entries by article ID; empty outside the demo universe."""
        filename = config.root / "configs/demo_story.json"
        if config.universe != "demo" or not filename.exists():
            return {}
        entries = read_config(config.root, "demo_story.json").get("articles", [])
        return {entry["article_id"]: entry for entry in entries}

    def article_json(article, story):
        entry = story.get(article.article_id)
        return {
            **article.model_dump(mode="json"),
            "featured": entry is not None,
            "story_role": entry.get("story_role") if entry else None,
            "story_order": entry.get("story_order") if entry else None,
            "story_title": entry.get("story_title") if entry else None,
        }

    def research_companies(config):
        """Active universe, plus explicit SYNTHETIC: lab series in the demo universe only.

        The lab series is labelled QA history for interface verification; it is never
        an event-evidence company and never appears in the live universe.
        """
        rows = read_companies(config)
        if config.universe != "demo" or not (config.root / "configs/synthetic_lab.json").exists():
            return rows
        lab = [
            row
            for row in read_config(config.root, "synthetic_lab.json")
            if str(row.get("instrument_id", "")).startswith("SYNTHETIC:")
        ]
        return rows + lab

    def require_company(identifier, config):
        if identifier not in {row["instrument_id"] for row in research_companies(config)}:
            raise HTTPException(422, "Select a company from the active universe")

    def selected_bars(payload, deps):
        from .strategy_lab import prepare_history

        require_company(payload.company_id, deps.settings)
        return prepare_history(
            deps.storage.list_observations(),
            payload.company_id,
            payload.start_date,
            payload.end_date,
            as_of=payload.as_of,
        )

    def chart_rows(rows):
        return [
            {
                "time": row.timestamp.astimezone(IST).date().isoformat(),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "available_at": row.available_at.isoformat(),
            }
            for row in rows
        ]

    def research_manifest(payload, bars):
        records = [row.model_dump(mode="json") for row in bars]
        return {
            "schema_version": "strategy-lab-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params": payload.model_dump(mode="json"),
            "instrument_id": bars[0].instrument_id,
            "currency": bars[0].currency,
            "unit": bars[0].unit,
            "supporting_observation_ids": [row.observation_id for row in bars],
            "history_fingerprint": hashlib.sha256(
                json.dumps(records, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            "evidence": "Retrospective OHLC research; recorded availability is never backdated.",
            "actual_start": bars[0].timestamp.astimezone(IST).date().isoformat(),
            "actual_end": bars[-1].timestamp.astimezone(IST).date().isoformat(),
        }

    # ---------------------------------------------------------------------------
    # Workspace, synthetic demo and imports
    # ---------------------------------------------------------------------------

    @api.get("/api/workspace")
    def workspace_data(workspace: Workspace = "local", universe: Universe = "live"):
        with dependencies(workspace, universe) as deps:
            config = deps.settings
            articles = [
                row for row in deps.storage.list_articles() if namespace(row.article_id, config)
            ]
            runs = [row for row in deps.storage.list_runs() if namespace(row.article_id, config)]
            observations = [
                row
                for row in deps.storage.list_observations()
                if namespace(row.instrument_id, config)
            ]
            ids = {run.run_id for run in runs}
            story = demo_story(config)
            coverage = []
            for company in research_companies(config):
                rows = [
                    row for row in observations if row.instrument_id == company["instrument_id"]
                ]
                coverage.append(
                    {
                        **company,
                        "bars": len(rows),
                        "start": min((r.timestamp for r in rows), default=None),
                        "end": max((r.timestamp for r in rows), default=None),
                        "latest_close": max(rows, key=lambda r: r.timestamp).close
                        if rows
                        else None,
                        "research_bars": sum(
                            r.timestamp.astimezone(IST).date().year <= 2020 for r in rows
                        ),
                    }
                )
            return {
                "workspace": workspace,
                "universe": config.universe,
                "provenance": "synthetic_fixture / recorded_replay"
                if workspace == "demo"
                else "imported evidence",
                "exists": config.database_path.exists(),
                "mode": config.mode,
                "companies": coverage,
                "articles": [article_json(a, story) for a in articles],
                "demo_story": sorted(story.values(), key=lambda entry: entry["story_order"]),
                "runs": [run_json(r) for r in runs],
                "outcomes": [
                    r.model_dump(mode="json")
                    for r in deps.storage.list_outcomes()
                    if r.run_id in ids
                ],
                "observations_count": len(observations),
                "readiness": readiness(deps),
                "history_end": "2020-12-31",
            }

    @api.post("/api/demo")
    def demo():
        config = configuration("demo", "demo")
        runs = run_demo(api.state.root, config.database_path, mode="replay", settings=config)
        return {
            "provenance": "synthetic_fixture / recorded_replay",
            "run_ids": [r.run_id for r in runs],
        }

    @api.post("/api/import")
    def import_data(
        payload: ImportRequest, workspace: Workspace = "local", universe: Universe = "live"
    ):
        with TemporaryDirectory() as directory:
            filename = Path(directory) / (
                "articles.jsonl" if payload.kind == "articles" else "prices.csv"
            )
            filename.write_text(payload.content, encoding="utf-8")
            result = (import_articles if payload.kind == "articles" else import_market_prices)(
                filename
            )
        added, errors = 0, list(result.errors)
        with dependencies(workspace, universe, write=True) as deps:
            for position, row in enumerate(result.records, 1):
                identifier = row.article_id if payload.kind == "articles" else row.instrument_id
                if not namespace(identifier, deps.settings):
                    errors.append(
                        {
                            "record": position,
                            "error": "Record namespace differs from selected universe",
                        }
                    )
                    continue
                try:
                    add = (
                        deps.storage.add_articles
                        if payload.kind == "articles"
                        else deps.storage.add_observations
                    )
                    added += add([row])
                except (ValueError, sqlite3.IntegrityError):
                    errors.append(
                        {
                            "record": position,
                            "error": "Immutable record conflict; saved version retained",
                        }
                    )
        return {"added": added, "errors": errors, "warnings": result.warnings}

    # ---------------------------------------------------------------------------
    # Analysis, saved cases and explanations
    # ---------------------------------------------------------------------------

    @api.post("/api/analyse")
    def analyse(
        payload: AnalysisRequest, workspace: Workspace = "local", universe: Universe = "live"
    ):
        if workspace == "demo" and payload.mode != "replay":
            raise HTTPException(422, "The synthetic demo uses recorded replay only")
        config = configuration(workspace, universe)
        if not namespace(payload.article_id, config):
            raise HTTPException(422, "Article and selected universe differ")
        with dependencies(workspace, universe, write=True) as deps:
            deps.settings.mode = payload.mode
            run = analyse_article(
                payload.article_id,
                payload.decision_time,
                payload.policy,
                deps,
                repeat_run=payload.repeat_run,
            )
            return run_json(run)

    @api.get("/api/case/{run_id}")
    def case(run_id: str, workspace: Workspace = "local", universe: Universe = "live"):
        with dependencies(workspace, universe) as deps:
            run = deps.storage.get_run(run_id)
            if not run or not namespace(run.article_id, deps.settings):
                raise HTTPException(404, "Saved run not found in this universe")
            payload = case_payload(deps.storage, run)
            payload["run"].update(describe_run(run))
            return payload

    @api.post("/api/explain/{run_id}")
    def explanation(run_id: str, workspace: Workspace = "local", universe: Universe = "live"):
        with dependencies(workspace, universe, write=True) as deps:
            run = deps.storage.get_run(run_id)
            if not run or not namespace(run.article_id, deps.settings):
                raise HTTPException(404, "Saved run not found in this universe")
            return {"text": explain_run(run_id, deps)}

    # ---------------------------------------------------------------------------
    # Technicals and strategy lab (read-only research)
    # ---------------------------------------------------------------------------

    @api.post("/api/technicals")
    def technicals(
        payload: TechnicalRequest, workspace: Workspace = "local", universe: Universe = "live"
    ):
        with dependencies(workspace, universe) as deps:
            require_company(payload.company_id, deps.settings)
            observations = deps.storage.list_observations()
            snapshot = compute_technicals(observations, payload.decision_time, payload.company_id)
            ids = set(snapshot.observation_ids)
            rows = sorted(
                (r for r in observations if r.observation_id in ids), key=lambda r: r.timestamp
            )
            return {"snapshot": snapshot.model_dump(mode="json"), "bars": chart_rows(rows)}

    @api.post("/api/history")
    def history(
        payload: HistoryRequest, workspace: Workspace = "local", universe: Universe = "live"
    ):
        from .strategy_lab import indicator_series

        with dependencies(workspace, universe) as deps:
            bars = selected_bars(payload, deps)
            return {
                "bars": chart_rows(bars),
                "indicators": indicator_series(bars),
                "requested_start": payload.start_date,
                "requested_end": payload.end_date,
                "actual_start": bars[0].timestamp.astimezone(IST).date(),
                "actual_end": bars[-1].timestamp.astimezone(IST).date(),
                "manifest": research_manifest(payload, bars),
            }

    @api.post("/api/backtest")
    def backtest(
        payload: BacktestRequest, workspace: Workspace = "local", universe: Universe = "live"
    ):
        from .strategy_lab import run_backtest, walk_forward

        with dependencies(workspace, universe) as deps:
            bars = selected_bars(payload, deps)
            arguments = payload.model_dump(
                exclude={"company_id", "start_date", "end_date", "as_of", "walk_forward_split"}
            )
            result = {
                **run_backtest(bars, **arguments),
                "manifest": research_manifest(payload, bars),
            }
            if payload.walk_forward_split is not None:
                result["walk_forward"] = walk_forward(bars, payload.walk_forward_split, **arguments)
            return result

    @api.post("/api/monte-carlo")
    def simulation(payload: MonteCarloRequest):
        from .strategy_lab import monte_carlo

        arguments = payload.model_dump()
        result = monte_carlo(**arguments)
        result["manifest"] = {
            "schema_version": "strategy-lab-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params": payload.model_dump(exclude={"daily_returns"}),
            "input_returns_count": len(payload.daily_returns),
            "input_returns_fingerprint": hashlib.sha256(
                json.dumps(payload.daily_returns, allow_nan=False).encode()
            ).hexdigest(),
            "evidence": "Client-supplied historical returns; no claim of future-market probabilities.",
        }
        return result

    # ---------------------------------------------------------------------------
    # Explicit provider sync and live news batches
    # ---------------------------------------------------------------------------

    @api.post("/api/sync/{kind}")
    def sync(
        kind: Literal["historical", "live"],
        payload: SyncRequest,
        workspace: Workspace = "local",
        universe: Universe = "live",
    ):
        if workspace != "local" or universe != "live":
            raise HTTPException(
                422, "Provider downloads require your local workspace and live universe"
            )
        # Validate the frozen dates before even opening a writable database.
        if kind == "historical":
            HistoryRequest(
                company_id=payload.company_ids[0],
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
        with dependencies(workspace, universe, write=True) as deps:
            for identifier in payload.company_ids:
                require_company(identifier, deps.settings)
            if kind == "historical":
                return sync_historical(
                    deps, payload.company_ids, payload.start_date, payload.end_date
                )
            return sync_live(
                deps,
                payload.company_ids,
                payload.lookback_days,
                payload.include_news,
                include_commodities=payload.include_commodities,
            )

    @api.post("/api/analyse-news")
    def batch(payload: BatchRequest, workspace: Workspace = "local", universe: Universe = "live"):
        if workspace != "local" or universe != "live":
            raise HTTPException(422, "News batches require the live local workspace")
        with dependencies(workspace, universe, write=True) as deps:
            deps.settings.mode = "live"
            return analyse_synced_news(
                deps, payload.article_ids, payload.decision_time, payload.policy, payload.limit
            )

    # ---------------------------------------------------------------------------
    # Policy comparisons and outcomes
    # ---------------------------------------------------------------------------

    @api.get("/api/comparisons")
    def comparisons(workspace: Workspace = "local", universe: Universe = "live"):
        with dependencies(workspace, universe) as deps:
            # Existing descriptive comparison functions consume the read-only view.
            # Scope the view's runs so synthetic and live results never mix.
            original = deps.storage.list_runs
            deps.storage.list_runs = lambda: [
                r for r in original() if namespace(r.article_id, deps.settings)
            ]
            run_ids = {run.run_id for run in deps.storage.list_runs()}
            original_outcomes = deps.storage.list_outcomes
            deps.storage.list_outcomes = lambda: [
                outcome for outcome in original_outcomes() if outcome.run_id in run_ids
            ]
            return run_experiments(deps)

    @api.post("/api/outcomes")
    def outcomes(workspace: Workspace = "local", universe: Universe = "live"):
        with dependencies(workspace, universe, write=True) as deps:
            runs = [r for r in deps.storage.list_runs() if namespace(r.article_id, deps.settings)]
            result = []
            for run in runs:
                result.extend(compute_outcomes(deps, run.run_id))
            return [row.model_dump(mode="json") for row in result]

    return api


app = create_app()
