"""Portable exports retain original decisions and only their referenced market rows."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_events.exporting import case_payload, export_bundle
from market_events.schemas import (
    AnalysisRun,
    Article,
    EventOutcome,
    MarketFeatures,
    MarketObservation,
    TechnicalSnapshot,
)
from market_events.storage import Storage

NOW = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def populate(storage):
    article = Article(
        article_id="article",
        source_url="example.invalid/synthetic",
        text="Synthetic evidence.",
        published_at=NOW,
        first_seen_at=NOW,
    )
    selected = MarketObservation(
        instrument_id="stock",
        market_family="equity",
        timestamp=NOW,
        available_at=NOW,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=100,
        currency="INR",
        unit="share",
    )
    later = selected.model_copy(
        update={
            "observation_id": "",
            "timestamp": NOW.replace(day=13),
            "available_at": NOW.replace(day=13),
        }
    )
    later = MarketObservation.model_validate(later.model_dump())
    storage.add_articles([article])
    storage.add_observations([selected, later])
    run = AnalysisRun(
        run_id="run/with/path",
        article_id=article.article_id,
        policy="llm_only",
        decision_time=NOW,
        created_at=NOW,
        status="completed",
        mode="replay",
        config_snapshot={},
        features=MarketFeatures(
            decision_time=NOW, observation_ids=[selected.observation_id, "unavailable-id"]
        ),
    )
    storage.save_run(run)
    storage.save_outcome(EventOutcome(run_id=run.run_id, status="pending"))
    return run, selected


def test_case_and_bundle_resolve_saved_references_without_writes(tmp_path):
    with Storage(tmp_path / "evidence.sqlite") as storage:
        run, selected = populate(storage)
        before = storage.get_run(run.run_id).model_dump_json()
        payload = case_payload(storage, run)
        assert [row["observation_id"] for row in payload["observations"]] == [
            selected.observation_id
        ]
        assert payload["missing_observation_ids"] == ["unavailable-id"]
        assert payload["outcome"]["status"] == "pending"
        paths = export_bundle(storage, tmp_path / "export.json", run.run_id)
        exported = json.loads((tmp_path / "export.json").read_text(encoding="utf-8"))
        assert exported["observations"] == payload["observations"]
        assert exported["missing_observation_ids_by_run"] == {run.run_id: ["unavailable-id"]}
        reports = list((tmp_path / "export-cases").glob("*.md"))
        assert len(reports) == 1
        assert selected.observation_id in reports[0].read_text(encoding="utf-8")
        assert json.loads(Path(paths["usage"]).read_text())["outcomes"] == exported["outcomes"]
        assert storage.get_run(run.run_id).model_dump_json() == before
        assert len(storage.list_runs()) == 1
        with pytest.raises(ValueError, match="Unknown run"):
            export_bundle(storage, tmp_path / "unknown.json", "unknown")
        assert not (tmp_path / "unknown.json").exists()


def test_saved_explanation_text_is_exported_with_unchanged_parent(tmp_path):
    with Storage(tmp_path / "evidence.sqlite") as storage:
        run, _ = populate(storage)
        child = run.model_copy(deep=True)
        child.run_id = "explanation"
        child.status = "explanation_completed"
        child.parent_run_id = run.run_id
        child.config_snapshot = {
            "explanation_parent_run_id": run.run_id,
            "explanation_result": {
                "text": "Saved grounded explanation.",
                "source_spans": ["evidence"],
            },
        }
        storage.save_run(child)
        export_bundle(storage, tmp_path / "child.json", child.run_id)
        exported = json.loads((tmp_path / "child.json").read_text(encoding="utf-8"))
        assert (
            exported["runs"][0]["config_snapshot"]["explanation_result"]["text"]
            == "Saved grounded explanation."
        )
        report = next((tmp_path / "child-cases").glob("*.md")).read_text(encoding="utf-8")
        assert "Saved grounded explanation." in report
        assert storage.get_run(run.run_id).config_snapshot == {}


def test_technical_history_references_export_without_features_or_future_rows(tmp_path):
    with Storage(tmp_path / "evidence.sqlite") as storage:
        original, selected = populate(storage)
        previous = MarketObservation.model_validate(
            {
                **selected.model_dump(),
                "observation_id": "",
                "timestamp": NOW.replace(day=11),
                "available_at": NOW.replace(day=11),
            }
        )
        storage.add_observations([previous])
        run = original.model_copy(deep=True)
        run.run_id = "technical-context"
        run.features = None
        run.technicals = TechnicalSnapshot(
            decision_time=NOW,
            company_id="stock",
            values={"rsi14": None},
            missing=["rsi14"],
            history_bars=2,
            required_history={"rsi14": 15},
            observation_ids=[previous.observation_id, selected.observation_id, "lost-history"],
        )
        storage.save_run(run)
        before = storage.get_run(run.run_id).model_dump_json()
        payload = case_payload(storage, run)
        assert {row["observation_id"] for row in payload["observations"]} == {
            previous.observation_id,
            selected.observation_id,
        }
        assert payload["missing_observation_ids"] == ["lost-history"]
        export_bundle(storage, tmp_path / "technicals.json", run.run_id)
        exported = json.loads((tmp_path / "technicals.json").read_text(encoding="utf-8"))
        assert len(exported["observations"]) == 2
        assert exported["runs"][0]["technicals"]["required_history"]["rsi14"] == 15
        report = next((tmp_path / "technicals-cases").glob("*.md")).read_text(encoding="utf-8")
        assert "Technical indicators at the decision cutoff" in report
        assert "lost-history" in report
        assert previous.observation_id in report
        assert storage.get_run(run.run_id).model_dump_json() == before
