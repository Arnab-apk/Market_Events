"""The complete research workflow, in the same order as the implementation guide."""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .agents.event_agent import extract_event
from .agents.explanation_agent import explain_assessment
from .agents.filter_agent import filter_article
from .config import Settings, load_settings, read_companies, read_config, read_exposure_rules
from .event_memory import classify_article
from .exposure import find_exposure
from .fusion import assess_evidence
from .ingestion import import_articles, import_market_prices
from .market_features import compute_market_features
from .model_client import BudgetExceeded, ModelClient, ModelError
from .outcomes import evaluate_outcome
from .schemas import AnalysisRun, ExecutionPolicy, ExposureRule, utc
from .storage import Storage


@dataclass
class Dependencies:
    storage: Storage
    settings: Settings
    client: ModelClient | None = None


def _snapshot(settings):
    result = settings.snapshot()
    result["companies.json"] = read_companies(settings)
    result["exposure_rules.json"] = read_exposure_rules(settings)
    result["fusion_rules.json"] = read_config(settings.root, "fusion_rules.json")
    result["technicals_version"] = "technicals-v1"
    result["prompts"] = {
        p.name: {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "text": p.read_text(encoding="utf-8"),
        }
        for p in sorted((settings.root / "prompts").glob("*.md"))
    }
    result["application_version"] = "0.1.0"
    return result


def analyse_article(
    article_id, decision_time, policy, dependencies, repeat_run=False
) -> AnalysisRun:
    """Save every reached decision, including filtering, failures and abstentions."""
    storage, settings = dependencies.storage, dependencies.settings
    article = storage.get_article(article_id)
    if article is None:
        raise ValueError(f"Unknown article: {article_id}")
    decision_time = utc(decision_time)
    snapshot = _snapshot(settings)
    eligible_observations = [
        o
        for o in storage.list_observations()
        if o.timestamp <= decision_time
        and o.available_at <= decision_time
        and o.instrument_id.startswith("LIVE:") == (settings.universe == "live")
    ]
    snapshot["eligible_observation_hash"] = hashlib.sha256(
        "".join(sorted(o.model_dump_json() for o in eligible_observations)).encode()
    ).hexdigest()
    eligible_articles = [
        a
        for a in storage.list_articles()
        if a.published_at <= decision_time
        and a.first_seen_at <= decision_time
        and a.article_id.startswith("LIVE:") == (settings.universe == "live")
    ]
    snapshot["eligible_source_hash"] = hashlib.sha256(
        "".join(sorted(a.model_dump_json() for a in eligible_articles)).encode()
    ).hexdigest()
    key_payload = {
        "article": article.model_dump(mode="json"),
        "cutoff": decision_time.isoformat(),
        "policy": ExecutionPolicy(policy).value,
        "snapshot": snapshot,
    }
    request_key = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
    parent_run_id = None
    existing = storage.lookup_request(request_key)
    if existing:
        parent_run_id = existing["run_id"]
        if not repeat_run:
            saved = storage.get_run(existing["run_id"])
            if saved:
                return saved
            raise ValueError(
                "This request is active or interrupted. Use an explicit repeat experiment to create a linked retry."
            )
    if repeat_run:
        request_key += ":" + str(uuid4())
    run = AnalysisRun(
        run_id=str(uuid4()),
        article_id=article_id,
        policy=ExecutionPolicy(policy),
        decision_time=decision_time,
        status="started",
        created_at=datetime.now(timezone.utc),
        config_snapshot=snapshot,
        mode=settings.mode,
        request_key=request_key,
        parent_run_id=parent_run_id,
    )
    client = dependencies.client or ModelClient(settings, run.run_id)
    # Reject an invalid dependency before reserving the durable request. Otherwise a
    # caller error would strand a request without a saved run to inspect or reuse.
    if dependencies.client is not None and client.calls:
        raise ValueError("Use a fresh model client for every analysis")
    if not storage.claim_request(request_key, run.run_id):
        raise ValueError(
            "An identical analysis request is already active; inspect its saved result"
        )
    started = time.perf_counter()
    try:
        client.run_id = run.run_id
        if article.article_id.startswith("LIVE:") != (settings.universe == "live"):
            run.status = "ineligible"
            run.error = "Article and workspace universes differ; choose demo or live explicitly"
            return run
        if article.published_at > decision_time or article.first_seen_at > decision_time:
            run.status = "ineligible"
            run.error = "Article publication/first-seen time is later than the decision cutoff"
            return run
        stage = time.perf_counter()
        run.memory = classify_article(article, eligible_articles, decision_time)
        run.stage_durations_ms["event_memory"] = (time.perf_counter() - stage) * 1000
        if run.memory["status"] == "duplicate":
            related = set(run.memory["related_article_ids"])
            existing_event_ids = {
                previous.event_id
                for previous in storage.list_runs()
                if previous.article_id in related and previous.event_id
            }
            # Reuse an unambiguous saved identity without re-extracting the copy.
            # If no baseline exists yet, retain the source relationship in memory.
            if len(existing_event_ids) == 1:
                event_id = next(iter(existing_event_ids))
                versions = {
                    event.source_version
                    for event in storage.list_events()
                    if event.event_id == event_id
                }
                if article.source_version in versions or len(versions) == 1:
                    run.event_id = event_id
            run.status = "duplicate"
            return run
        companies = run.config_snapshot["companies.json"]
        role = "llm" if run.policy == ExecutionPolicy.llm_only else "slm"
        stage = time.perf_counter()
        run.filter_decision = filter_article(article, client, role, {"companies": companies})
        run.stage_durations_ms["filter"] = (time.perf_counter() - stage) * 1000
        if run.filter_decision.relevance == "irrelevant":
            run.status = "irrelevant"
            return run
        delegated = run.filter_decision if run.policy == ExecutionPolicy.slm_delegate else None
        stage = time.perf_counter()
        run.extraction = extract_event(article, client, companies, delegated)
        run.stage_durations_ms["extraction"] = (time.perf_counter() - stage) * 1000
        # Updates share a source event identity; each analysis retains its own extraction.
        ancestor = article
        seen = {article.article_id}
        source_snapshot = {source.article_id: source for source in eligible_articles}
        while ancestor.predecessor_id and ancestor.predecessor_id not in seen:
            previous = source_snapshot.get(ancestor.predecessor_id)
            if (
                previous is None
                or previous.first_seen_at > decision_time
                or previous.published_at > decision_time
            ):
                break
            seen.add(previous.article_id)
            ancestor = previous
        run.extraction.event_id = (
            "evt-" + hashlib.sha256(ancestor.article_id.encode()).hexdigest()[:20]
        )
        run.event_id = run.extraction.event_id
        rules = [ExposureRule.model_validate(r) for r in run.config_snapshot["exposure_rules.json"]]
        stage = time.perf_counter()
        run.exposure = find_exposure(run.extraction, rules, decision_time)
        company = next(
            (c for c in companies if c["instrument_id"] == run.extraction.company_id), {}
        )
        commodity_id = (
            run.exposure.rule.commodity_id if run.exposure.rule else run.extraction.commodity_id
        )
        run.features = compute_market_features(
            eligible_observations,
            decision_time,
            company_id=run.extraction.company_id,
            commodity_id=commodity_id,
            benchmark_id=company.get("benchmark_id"),
        )
        from .technicals import compute_technicals

        if run.extraction.company_id:
            run.technicals = compute_technicals(
                eligible_observations, decision_time, run.extraction.company_id
            )
        run.assessment = assess_evidence(
            run.extraction,
            run.exposure,
            run.features,
            run.config_snapshot["fusion_rules.json"],
        )
        run.stage_durations_ms["numerical_evidence"] = (time.perf_counter() - stage) * 1000
        if run.memory["status"] == "unresolved":
            run.assessment.direction = "abstain"
            run.assessment.abstention_reasons.append("Unresolved source version history")
            run.assessment.explanation += " Source history is unresolved; assessment withheld."
        run.status = "abstained" if run.assessment.direction == "abstain" else "completed"
        return run
    except BudgetExceeded as exc:
        run.status, run.error = "partial", str(exc)
        return run
    except (ModelError, ValueError) as exc:
        run.status, run.error = "failed", str(exc)
        return run
    except KeyboardInterrupt:
        run.status, run.error = "interrupted", "Analysis interrupted; use an explicit linked repeat"
        raise
    finally:
        run.calls = list(client.calls)
        run.latency_ms = (time.perf_counter() - started) * 1000
        storage.save_run(run)
        storage.finish_request(
            request_key, "failed" if run.status in {"started", "interrupted"} else run.status
        )


def compute_outcomes(dependencies, run_id=None) -> list:
    storage = dependencies.storage
    observations = storage.list_observations()
    results = []
    for run in storage.list_runs():
        if run_id is not None and run.run_id != run_id:
            continue
        if run.status not in {"completed", "abstained"}:
            continue
        companies = run.config_snapshot["companies.json"]
        company = next(
            (c for c in companies if c["instrument_id"] == run.extraction.company_id), {}
        )
        result = evaluate_outcome(run, observations, benchmark_id=company.get("benchmark_id"))
        storage.save_outcome(result)
        results.append(result)
    return results


def run_demo(root=Path("."), database_path=None, mode="replay", settings=None) -> list[AnalysisRun]:
    # A caller-supplied Settings (e.g. the web app's) is copied, never mutated, and
    # avoids re-reading local .env secrets for an offline replay.
    settings = settings.model_copy(deep=True) if settings else load_settings(Path(root))
    settings.universe = "demo"
    settings.mode = "live" if mode in {"live", "live-model"} else "replay"
    if database_path:
        settings.database_path = Path(database_path)
    articles = import_articles(settings.root / "tests/fixtures/articles.jsonl")
    market = import_market_prices(settings.root / "tests/fixtures/market_prices.csv")
    # Explicit SYNTHETIC: QA history so the strategy lab has an offline, labelled
    # fallback. It is a separate instrument, so it never enters event evidence.
    lab_path = settings.root / "tests/fixtures/synthetic_lab_history.csv"
    lab = import_market_prices(lab_path) if lab_path.exists() else None
    if articles.errors or market.errors or (lab and lab.errors):
        raise ValueError(
            f"Invalid demo fixtures: {articles.errors + market.errors + (lab.errors if lab else [])}"
        )
    if lab and any(not r.instrument_id.startswith("SYNTHETIC:") for r in lab.records):
        raise ValueError("Synthetic lab history must use SYNTHETIC: instrument identifiers")
    storage = Storage(settings.database_path)
    try:
        storage.add_articles(articles.records)
        storage.add_observations(market.records)
        if lab:
            storage.add_observations(lab.records)
        dependencies = Dependencies(storage, settings)
        cutoff = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)
        # Select one eligible example per event family using fixture labels, never model guesses.
        recorded = json.loads(
            (settings.root / "tests/fixtures/recorded_model_outputs.json").read_text(
                encoding="utf-8"
            )
        )
        selected = []
        for family in ("earnings", "order_announcement", "commodity_supply_disruption"):
            item = next(
                (
                    a
                    for a in articles.records
                    if a.published_at <= cutoff
                    and a.first_seen_at <= cutoff
                    and recorded.get(a.article_id, {}).get("extraction", {}).get("event_type")
                    == family
                ),
                None,
            )
            if item:
                selected.append(item)
        runs = [
            analyse_article(a.article_id, cutoff, ExecutionPolicy.slm_delegate, dependencies)
            for a in selected
        ]
        compute_outcomes(dependencies)
        return runs
    finally:
        storage.close()


def readiness(dependencies) -> list[dict]:
    """Offline configuration/coverage checks, never a provider connection test."""
    settings = dependencies.settings
    token_present = bool(settings.live_data.access_token.get_secret_value())
    live_universe = settings.universe == "live"
    models_present = bool(settings.slm.model.strip() and settings.llm.model.strip())
    now = datetime.now(timezone.utc)
    rows = [
        observation
        for observation in dependencies.storage.list_observations()
        if observation.market_family == "equity"
        and observation.instrument_id.startswith("LIVE:") == live_universe
        and observation.timestamp <= now
        and observation.available_at <= now
    ]
    return [
        {
            "capability": "market_history",
            "name": "Upstox daily price history",
            "configured": token_present,
            "ready": token_present and live_universe,
            "reason": (
                "Configured; connection and entitlements checked only on explicit sync"
                if token_present and live_universe
                else "Select live universe and set UPSTOX_ANALYTICS_TOKEN in local .env"
            ),
        },
        {
            "capability": "news",
            "name": "Upstox instrument news",
            "configured": token_present,
            "ready": token_present and live_universe,
            "reason": (
                "Uses the same read-only token; sync is explicit"
                if token_present and live_universe
                else "Select live universe and configure the read-only token"
            ),
        },
        {
            "capability": "technicals",
            "name": "Local technical analysis",
            "configured": True,
            "ready": bool(rows),
            "reason": (
                f"{len(rows)} eligible imported equity bars; each company's full set needs 50 bars"
                if rows
                else "Import prices or sync history; no news or model key is required"
            ),
        },
        {
            "capability": "event_models",
            "name": "Live article filtering and extraction",
            "configured": models_present,
            "ready": models_present and settings.mode == "live" and live_universe,
            "reason": (
                "Configured; actual connectivity is checked only when analysis is submitted"
                if models_present and settings.mode == "live" and live_universe
                else "Select live universe/mode and configure SLM_MODEL and LLM_MODEL"
            ),
        },
    ]


def analyse_synced_news(
    dependencies, article_ids, decision_time, policy="slm_delegate", limit=10
) -> list[dict]:
    """Explicit bounded live batch; every requested item has a visible result."""
    if dependencies.settings.universe != "live" or dependencies.settings.mode != "live":
        raise ValueError("News analysis requires the live universe and live model mode")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Batch limit must be an integer between 1 and 100")
    cutoff = utc(decision_time)
    policy = ExecutionPolicy(policy)
    results = []
    identifiers = list(dict.fromkeys(article_ids))
    for position, article_id in enumerate(identifiers):
        row = {"article_id": article_id, "run_id": None, "status": "failed", "error": None}
        if position >= limit:
            row.update(status="skipped", error="Explicit batch limit reached")
        elif not isinstance(article_id, str) or not article_id.startswith("LIVE:"):
            row["error"] = "Select an article from the live namespace"
        else:
            try:
                run = analyse_article(article_id, cutoff, policy, dependencies)
                row.update(run_id=run.run_id, status=run.status, error=run.error)
            except (ValueError, OSError) as exc:
                row["error"] = str(exc)
        results.append(row)
    return results


def explain_run(run_id, dependencies) -> str:
    original = dependencies.storage.get_run(run_id)
    if not original or not original.assessment:
        raise ValueError("Select a saved assessed run")
    # Optional inference creates an immutable child run carrying its own trace and budget.
    child = original.model_copy(deep=True)
    child.run_id = str(uuid4())
    child.created_at = datetime.now(timezone.utc)
    child.calls = []
    child.stage_durations_ms = {}
    child.error = None
    child.request_key = None
    child.parent_run_id = original.run_id
    child.mode = dependencies.settings.mode
    child.config_snapshot["explanation_parent_run_id"] = original.run_id
    child.config_snapshot["explanation_runtime_settings"] = dependencies.settings.snapshot()
    client = ModelClient(dependencies.settings, child.run_id)
    started = time.perf_counter()
    try:
        article = dependencies.storage.get_article(child.article_id)
        explanation = explain_assessment(article, child, client)
        child.config_snapshot["explanation_result"] = {
            "text": explanation,
            "source_spans": list(child.extraction.source_spans),
        }
        child.status = "explanation_completed"
        return explanation
    except (ModelError, ValueError) as exc:
        child.status, child.error = "explanation_failed", str(exc)
        raise
    finally:
        child.calls = list(client.calls)
        child.latency_ms = (time.perf_counter() - started) * 1000
        dependencies.storage.save_run(child)
