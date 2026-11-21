"""Production replay path: time correctness, idempotency, immutable decisions and errors."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from market_events.config import load_settings
from market_events.ingestion import import_articles, import_market_prices
from market_events.model_client import ModelClient
from market_events.pipeline import Dependencies, analyse_article, compute_outcomes, run_demo
from market_events.schemas import Article, ExecutionPolicy
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


@pytest.fixture
def deps(tmp_path):
    settings = load_settings(ROOT)
    settings.mode = "replay"
    settings.database_path = tmp_path / "research.sqlite"
    with Storage(settings.database_path) as storage:
        storage.add_articles(import_articles(ROOT / "tests/fixtures/articles.jsonl").records)
        storage.add_observations(
            import_market_prices(ROOT / "tests/fixtures/market_prices.csv").records
        )
        yield Dependencies(storage, settings)


def test_demo_has_all_three_families_and_exact_reviewed_market_result(tmp_path):
    runs = run_demo(ROOT, tmp_path / "demo.sqlite")
    assert len(runs) == 3
    assert all(r.status == "completed" for r in runs)
    assert {r.extraction.event_type for r in runs} == {
        "earnings",
        "order_announcement",
        "commodity_supply_disruption",
    }
    cross = next(r for r in runs if r.extraction.event_type == "commodity_supply_disruption")
    assert cross.features.values["commodity_return"] is not None
    assert cross.assessment.coverage == 1
    expected = json.loads((ROOT / "tests/fixtures/expected_demo_outputs.json").read_text())
    assert cross.features.values["equity_return"] == pytest.approx(
        expected["syn-002"]["features"]["values"]["equity_return"]
    )
    assert cross.assessment.evidence_score == pytest.approx(
        expected["syn-002"]["assessment"]["evidence_score"]
    )


def test_same_request_reuses_stored_run_and_explicit_repeat_links(deps):
    original = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    cached = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    assert cached.run_id == original.run_id
    assert len(deps.storage.list_runs()) == 1
    repeated = analyse_article("syn-002", CUTOFF, "slm_delegate", deps, repeat_run=True)
    assert repeated.run_id != original.run_id
    assert repeated.parent_run_id == original.run_id
    assert len(deps.storage.list_runs()) == 2
    assert len(deps.storage.list_events()) == 1


def test_outcomes_do_not_rewrite_assessment(deps):
    run = analyse_article("syn-003", CUTOFF, ExecutionPolicy.llm_only, deps)
    original = deps.storage.get_run(run.run_id).model_dump_json()
    result = compute_outcomes(deps)
    assert result[0].status == "completed"
    assert result[0].entry_time > run.decision_time
    assert deps.storage.get_run(run.run_id).model_dump_json() == original


def test_after_cutoff_and_unknown_replay_fail_without_fabricated_inference(deps):
    early = analyse_article("syn-001", datetime(2026, 1, 1, tzinfo=timezone.utc), "llm_only", deps)
    assert early.status == "ineligible"
    assert not early.calls
    source = Article(
        article_id="uploaded",
        source_url="https://example.invalid/new",
        text="A new source",
        published_at=CUTOFF,
        first_seen_at=CUTOFF,
    )
    deps.storage.add_articles([source])
    failed = analyse_article(source.article_id, CUTOFF, "slm_filter", deps)
    assert failed.status == "failed"
    assert failed.calls[0].status == "failed"
    assert failed.calls[0].input_tokens is None
    assert deps.storage.get_run(failed.run_id).error


def test_three_policies_share_deterministic_numerical_result(deps):
    runs = [analyse_article("syn-002", CUTOFF, p, deps) for p in ExecutionPolicy]
    assert all(r.status == "completed" for r in runs)
    assert len({r.assessment.evidence_score for r in runs}) == 1
    assert runs[0].calls[0].model == "recorded-llm"
    assert runs[1].calls[0].model == "recorded-slm"
    assert len(deps.storage.list_events()) == 1


def test_reused_client_is_rejected_without_stranding_request(deps):
    client = ModelClient(deps.settings, "initial")
    deps.client = client
    first = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    assert first.status == "completed"
    assert all(call.run_id == first.run_id for call in first.calls)

    with pytest.raises(ValueError, match="fresh model client"):
        analyse_article("syn-003", CUTOFF, "slm_delegate", deps)
    assert len(deps.storage.list_runs()) == 1

    # Correcting the dependency must allow the same request without an explicit repeat.
    deps.client = None
    second = analyse_article("syn-003", CUTOFF, "slm_delegate", deps)
    assert second.status == "completed"
    assert second.parent_run_id is None


def test_client_setup_failure_does_not_reserve_request(deps, monkeypatch):
    import market_events.pipeline as pipeline

    with monkeypatch.context() as patch:

        def fail_setup(*args, **kwargs):
            raise ValueError("Client setup failed")

        patch.setattr(pipeline, "ModelClient", fail_setup)
        with pytest.raises(ValueError, match="Client setup failed"):
            analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    assert not deps.storage.list_runs()
    assert analyse_article("syn-002", CUTOFF, "slm_delegate", deps).status == "completed"


def test_evidence_uses_captured_observations_despite_concurrent_import(deps, monkeypatch):
    observations = deps.storage.list_observations()
    reads = iter([observations, []])
    monkeypatch.setattr(deps.storage, "list_observations", lambda: next(reads))
    run = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    assert run.status == "completed"
    assert run.features.observation_ids
    assert run.assessment.coverage == 1


def test_memory_uses_captured_sources_despite_concurrent_import(deps, monkeypatch):
    sources = deps.storage.list_articles()
    article = deps.storage.get_article("syn-002")
    duplicate = Article(
        article_id="concurrent-duplicate",
        source_url="https://example.invalid/concurrent-duplicate",
        text=article.text,
        published_at=article.published_at - timedelta(minutes=1),
        first_seen_at=article.first_seen_at - timedelta(minutes=1),
    )
    reads = iter([sources, [*sources, duplicate]])
    monkeypatch.setattr(deps.storage, "list_articles", lambda: next(reads))
    run = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    assert run.status == "completed"
    assert run.memory["status"] == "new"


def test_optional_explanation_is_persisted_separately_from_parent(deps, monkeypatch):
    import market_events.pipeline as pipeline

    original = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    saved = deps.storage.get_run(original.run_id).model_dump_json()
    text = original.assessment.explanation
    monkeypatch.setattr(pipeline, "explain_assessment", lambda *args: text)
    assert pipeline.explain_run(original.run_id, deps) == text
    child = next(run for run in deps.storage.list_runs() if run.run_id != original.run_id)
    assert child.status == "explanation_completed"
    assert child.parent_run_id == original.run_id
    assert child.config_snapshot["explanation_result"] == {
        "text": text,
        "source_spans": original.extraction.source_spans,
    }
    assert not child.stage_durations_ms
    assert deps.storage.get_run(original.run_id).model_dump_json() == saved


def test_duplicate_links_existing_event_without_new_extraction(deps):
    original = analyse_article("syn-002", CUTOFF, "slm_delegate", deps)
    source = deps.storage.get_article(original.article_id)
    duplicate = Article(
        article_id="later-copy",
        source_url="https://example.invalid/later-copy",
        text=source.text,
        published_at=source.published_at + timedelta(minutes=1),
        first_seen_at=source.first_seen_at + timedelta(minutes=1),
    )
    deps.storage.add_articles([duplicate])
    run = analyse_article(duplicate.article_id, CUTOFF, "slm_delegate", deps)
    assert run.status == "duplicate"
    assert run.event_id == original.event_id
    assert run.extraction is None
    assert not run.calls
    assert len(deps.storage.list_events()) == 1
    linked = deps.storage.connection.execute(
        "SELECT article_id FROM event_sources WHERE event_id = ?", (original.event_id,)
    ).fetchall()
    assert {row[0] for row in linked} == {original.article_id, duplicate.article_id}
