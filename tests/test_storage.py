"""Synthetic SQLite integration tests exercise actual FK/transaction behaviour."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest

from market_events.schemas import (
    AnalysisRun,
    Article,
    Assessment,
    EventExtraction,
    EventOutcome,
    MarketObservation,
    ModelCall,
    TechnicalSnapshot,
)
from market_events.storage import Storage


NOW = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def source(identifier="a1", **changes):
    return Article.model_validate(
        {
            "article_id": identifier,
            "source_url": f"https://example.invalid/{identifier}",
            "text": "Synthetic earnings announcement.",
            "published_at": "2026-01-12T09:00:00Z",
            "first_seen_at": "2026-01-12T09:01:00Z",
            **changes,
        }
    )


def observation(**changes):
    return MarketObservation.model_validate(
        {
            "instrument_id": "NSE:ASIANPAINT",
            "market_family": "equity",
            "timestamp": NOW,
            "available_at": NOW,
            "open": 100,
            "high": 110,
            "low": 90,
            "close": 105,
            "volume": 1000,
            "currency": "INR",
            "unit": "share",
            **changes,
        }
    )


def run(identifier="r1", **changes):
    return AnalysisRun.model_validate(
        {
            "run_id": identifier,
            "article_id": "a1",
            "event_id": "e1",
            "policy": "llm_only",
            "decision_time": NOW,
            "created_at": NOW,
            "status": "completed",
            "config_snapshot": {"fusion": {"version": "v1"}},
            "mode": "replay",
            "extraction": EventExtraction(
                event_id="e1", event_type="earnings", source_spans=["earnings"]
            ),
            "calls": [
                ModelCall(
                    trace_id=f"trace-{identifier}",
                    run_id=identifier,
                    task="extract",
                    provider="recorded",
                    model="synthetic",
                    prompt_version="v1",
                    latency_ms=1,
                    status="completed",
                    mode="replay",
                )
            ],
            "assessment": Assessment(
                direction="positive",
                evidence_score=0.2,
                coverage=1,
                rules_version="v1",
                explanation="Synthetic evidence.",
            ),
            **changes,
        }
    )


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "data" / "ledger.sqlite") as store:
        yield store


def test_schema_tables_version_and_foreign_keys(storage):
    tables = {
        row[0]
        for row in storage.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "articles",
        "market_observations",
        "events",
        "event_sources",
        "analysis_runs",
        "model_calls",
        "assessments",
        "outcomes",
        "analysis_requests",
    } <= tables
    assert storage.connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert storage.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert storage.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_article_and_market_roundtrip_idempotency_and_reopen(tmp_path):
    path = tmp_path / "ledger.sqlite"
    article, bar = source(), observation()
    with Storage(path) as store:
        assert store.add_articles([article]) == 1
        assert store.add_articles([article]) == 0
        assert store.add_observations([bar]) == 1
        assert store.add_observations([bar]) == 0
    with Storage(path) as store:
        assert store.get_article("a1") == article
        assert store.list_articles() == [article]
        assert store.list_observations() == [bar]
        assert store.get_article("missing") is None


def test_legacy_run_optional_defaults_remain_idempotent_without_rewriting(storage):
    storage.add_articles([source()])
    legacy = run("legacy", event_id=None, extraction=None, calls=[], assessment=None)
    payload = legacy.model_dump(mode="json")
    payload.pop("technicals")
    original = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with storage.connection:
        storage.connection.execute(
            "INSERT INTO analysis_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                legacy.run_id,
                legacy.article_id,
                None,
                None,
                legacy.policy.value,
                legacy.decision_time.isoformat(),
                legacy.created_at.isoformat(),
                legacy.status,
                original,
            ),
        )
    loaded = storage.get_run(legacy.run_id)
    assert loaded.technicals is None
    storage.save_run(loaded)
    loaded.technicals = TechnicalSnapshot(decision_time=NOW, company_id="NSE:ASIANPAINT")
    with pytest.raises(ValueError, match="immutable run"):
        storage.save_run(loaded)
    assert (
        storage.connection.execute(
            "SELECT data FROM analysis_runs WHERE run_id = ?", (legacy.run_id,)
        ).fetchone()[0]
        == original
    )


def test_conflicting_sources_and_prices_are_not_replaced(storage):
    storage.add_articles([source()])
    storage.add_observations([observation()])
    with pytest.raises(ValueError, match="immutable article"):
        storage.add_articles([source(text="Correction.")])
    with pytest.raises(ValueError, match="immutable observation"):
        storage.add_observations([observation(close=106)])
    with pytest.raises(sqlite3.IntegrityError):
        storage.add_articles([source("other", source_url=source().source_url)])
    assert storage.get_article("a1").text == source().text
    assert storage.list_observations()[0].close == 105


def test_source_updates_and_unordered_predecessor_batch(storage):
    original = source()
    corrected = source(
        "a2",
        source_url=original.source_url,
        source_version="2",
        predecessor_id="a1",
        text="Corrected earnings.",
    )
    assert storage.add_articles([corrected, original]) == 2
    assert storage.get_article("a2").predecessor_id == "a1"
    assert storage.get_article("a1") == original


def test_missing_predecessor_rolls_back_entire_batch(storage):
    with pytest.raises(sqlite3.IntegrityError):
        storage.add_articles([source(), source("bad", predecessor_id="missing")])
    assert storage.list_articles() == []
    assert storage.add_articles([source()]) == 1


def test_observation_conflict_rolls_back_prior_insert_in_batch(storage):
    storage.add_observations([observation()])
    with pytest.raises(ValueError):
        storage.add_observations(
            [observation(instrument_id="NSE:BERGEPAINT"), observation(close=106)]
        )
    assert len(storage.list_observations()) == 1


def test_full_run_has_real_child_rows_and_immutable_snapshot(storage):
    storage.add_articles([source()])
    saved = run()
    storage.save_run(saved)
    storage.save_run(saved)
    assert storage.get_run("r1") == saved
    assert storage.list_runs() == [saved]
    assert storage.list_events() == [saved.extraction]
    for table in ("analysis_runs", "events", "event_sources", "model_calls", "assessments"):
        assert storage.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
    saved.config_snapshot["fusion"]["version"] = "changed"
    with pytest.raises(ValueError, match="immutable run"):
        storage.save_run(saved)
    assert storage.get_run("r1").config_snapshot["fusion"]["version"] == "v1"
    assert storage.get_run("missing") is None


def test_failed_run_is_saved_without_extraction(storage):
    storage.add_articles([source()])
    failed = run(
        status="failed", error="Model unavailable", event_id=None, extraction=None, assessment=None
    )
    storage.save_run(failed)
    assert storage.get_run("r1") == failed
    assert len(storage.list_events()) == 0


def test_run_references_must_be_consistent(storage):
    with pytest.raises(ValueError, match="article does not exist"):
        storage.save_run(run())
    storage.add_articles([source()])
    with pytest.raises(ValueError, match="must match"):
        storage.save_run(run(event_id="other"))
    bad = run()
    bad.calls[0].run_id = "other"
    with pytest.raises(ValueError, match="containing run"):
        storage.save_run(bad)
    assert storage.list_runs() == []
    assert storage.list_events() == []


def test_call_collision_rolls_back_new_event_source_and_run(storage):
    storage.add_articles([source(), source("a2")])
    storage.save_run(run())
    later = run(
        "r2",
        article_id="a2",
        event_id="e2",
        extraction=EventExtraction(event_id="e2", event_type="earnings"),
    )
    later.calls[0].trace_id = "trace-r1"
    with pytest.raises(sqlite3.IntegrityError):
        storage.save_run(later)
    assert [item.event_id for item in storage.list_events()] == ["e1"]
    assert storage.get_run("r2") is None
    assert storage.connection.execute("SELECT count(*) FROM event_sources").fetchone()[0] == 1


def test_event_versions_append_without_overwriting_prior_source_version(storage):
    storage.add_articles([source(), source("a2", source_version="2", predecessor_id="a1")])
    storage.save_run(run())
    extraction = EventExtraction(
        event_id="e1", source_version="2", event_type="earnings", direction="negative"
    )
    storage.save_run(run("r2", article_id="a2", extraction=extraction))
    assert [event.source_version for event in storage.list_events()] == ["1", "2"]
    assert storage.list_events()[0].direction == "uncertain"


def test_same_event_different_policy_extractions_preserve_baseline_and_each_run(storage):
    storage.add_articles([source()])
    original = run()
    storage.save_run(original)
    different = EventExtraction(
        event_id="e1",
        event_type="order_announcement",
        direction="negative",
        amounts=[{"value": 100, "unit": "INR", "source_span": "Synthetic INR 100"}],
        reason="Different model interpretation",
    )
    alternative = run("r2", policy="slm_delegate", extraction=different)
    storage.save_run(alternative)
    assert storage.list_events() == [original.extraction]
    assert storage.get_run("r1").extraction == original.extraction
    assert storage.get_run("r2").extraction == different
    assert len(storage.list_runs()) == 2


def test_per_run_trace_ids_do_not_rewrite_event(storage):
    storage.add_articles([source()])
    first, second = run(), run("r2")
    first.extraction.trace_id = "trace-r1"
    second.extraction.trace_id = "trace-r2"
    storage.save_run(first)
    storage.save_run(second)
    assert storage.list_events()[0].trace_id == "trace-r1"
    assert storage.get_run("r2").extraction.trace_id == "trace-r2"


def test_duplicate_source_can_link_existing_event_without_reextraction(storage):
    storage.add_articles([source(), source("copy")])
    storage.save_run(run())
    storage.save_run(run("r2", article_id="copy", extraction=None, assessment=None))
    assert len(storage.list_events()) == 1
    assert storage.connection.execute("SELECT count(*) FROM event_sources").fetchone()[0] == 2
    assert storage.get_run("r2").event_id == "e1"


def test_sql_enforces_immutable_runs_events_and_source_versions(storage):
    storage.add_articles([source()])
    storage.save_run(run())
    for table in (
        "articles",
        "events",
        "analysis_runs",
        "model_calls",
        "assessments",
        "event_sources",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            storage.connection.execute(f"DELETE FROM {table}")
        storage.connection.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        storage.connection.execute("UPDATE articles SET source_version = '2'")
    storage.connection.rollback()
    assert storage.get_run("r1") == run()


def test_outcome_evolves_separately_from_frozen_decision(storage):
    storage.add_articles([source()])
    saved = run()
    storage.save_run(saved)
    pending = EventOutcome(run_id="r1", status="pending", reason="Horizon incomplete")
    completed = EventOutcome(run_id="r1", status="completed", gross_return=0.1, net_return=0.099)
    storage.save_outcome(pending)
    assert storage.get_outcome("r1") == pending
    storage.save_outcome(completed)
    assert storage.get_outcome("r1") == completed
    assert storage.list_outcomes() == [completed]
    assert storage.get_run("r1") == saved
    assert storage.get_outcome("missing") is None
    with pytest.raises(sqlite3.IntegrityError):
        storage.save_outcome(EventOutcome(run_id="missing", status="pending"))


def test_every_storage_connection_enforces_foreign_keys(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with Storage(path), Storage(path) as second:
        assert second.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            second.connection.execute(
                "INSERT INTO outcomes VALUES ('missing', 'pending', 'v1', '{}')"
            )


def test_future_schema_version_is_not_silently_accepted(tmp_path):
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(ValueError, match="schema_version"):
        Storage(path)


def test_memory_database_lifecycle():
    with Storage(Path(":memory:")) as store:
        store.add_articles([source()])
        assert len(store.list_articles()) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        store.list_articles()


def test_v1_database_migrates_without_changing_saved_data(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with Storage(path) as store:
        store.add_articles([source()])
        store.save_run(run())
    # Remove the v2 table and v3 insert guards to reconstruct the v1 schema.
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE analysis_requests")
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%_insert'"
        ).fetchall():
            connection.execute(f"DROP TRIGGER {name}")
        connection.execute("PRAGMA user_version = 1")
    with Storage(path) as migrated:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert migrated.get_article("a1") == source()
        assert migrated.get_run("r1") == run()
        assert migrated.claim_request("old-data-request", "r1")
        migrated.finish_request("old-data-request", "completed")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            migrated.connection.execute("UPDATE analysis_runs SET status = 'changed'")
    with Storage(path) as reopened:
        assert reopened.get_run("r1") == run()
        assert reopened.lookup_request("old-data-request")["status"] == "completed"


def test_two_connections_observe_one_committed_claim_without_open_transaction(tmp_path):
    path = tmp_path / "claims.sqlite"
    with Storage(path) as first, Storage(path) as second:
        assert first.lookup_request("same") is None
        assert first.claim_request("same", "r1") is True
        assert first.connection.in_transaction is False
        assert second.lookup_request("same") == {"run_id": "r1", "status": "started"}
        assert second.claim_request("same", "r2") is False
        assert second.connection.in_transaction is False
        assert first.lookup_request("same")["run_id"] == "r1"
        # Reserving a run ID under another request key cannot create two owners.
        assert second.claim_request("different-key", "r1") is False
        assert second.lookup_request("different-key") is None
        assert first.get_run("r1") is None


def test_simultaneous_claims_have_exactly_one_winner(tmp_path):
    path = tmp_path / "racing-claims.sqlite"
    with Storage(path):
        pass
    ready = Barrier(2)

    def claim(identifier):
        with Storage(path) as store:
            ready.wait(timeout=5)
            won = store.claim_request("same", identifier)
            assert store.connection.in_transaction is False
            return identifier, won

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["r1", "r2"]))
    winners = [identifier for identifier, won in results if won]
    assert len(winners) == 1
    with Storage(path) as store:
        assert store.lookup_request("same")["run_id"] == winners[0]


def test_interrupted_claim_survives_reopen_and_is_not_reclaimed(tmp_path):
    path = tmp_path / "interrupted.sqlite"
    with Storage(path) as store:
        assert store.claim_request("interrupted", "r1")
    with Storage(path) as store:
        request = store.lookup_request("interrupted")
        assert request["status"] == "started"
        assert store.get_run(request["run_id"]) is None
        assert store.claim_request("interrupted", "r2") is False
        assert store.claim_request("explicit-repeat", "r2") is True


def test_completed_claim_reuses_saved_run_and_finishing_is_idempotent(tmp_path):
    path = tmp_path / "finished.sqlite"
    with Storage(path) as first, Storage(path) as second:
        first.add_articles([source()])
        assert first.claim_request("request", "r1")
        first.save_run(run())
        first.finish_request("request", "completed")
        first.finish_request("request", "completed")
        assert first.connection.in_transaction is False
        request = second.lookup_request("request")
        assert request["status"] == "completed"
        assert second.get_run(request["run_id"]) == run()
        assert second.claim_request("request", "r2") is False
        with pytest.raises(ValueError, match="immutable"):
            second.finish_request("request", "failed")
        assert first.lookup_request("request")["status"] == "completed"


def test_request_completion_requires_saved_run_but_failure_remains_visible(storage):
    assert storage.claim_request("request", "r1")
    with pytest.raises(ValueError, match="saved run"):
        storage.finish_request("request", "completed")
    assert storage.lookup_request("request")["status"] == "started"
    storage.finish_request("request", "failed")
    storage.finish_request("request", "failed")
    assert storage.lookup_request("request")["status"] == "failed"
    assert storage.claim_request("request", "r2") is False
    with pytest.raises(ValueError, match="immutable"):
        storage.finish_request("request", "completed")
    assert storage.lookup_request("request")["status"] == "failed"


def test_request_validation_does_not_create_or_change_claims(storage):
    with pytest.raises(ValueError, match="Unknown"):
        storage.finish_request("unknown", "failed")
    for key, identifier in [("", "r1"), ("key", "  ")]:
        with pytest.raises(ValueError, match="nonempty"):
            storage.claim_request(key, identifier)
    assert storage.claim_request("request", "r1")
    for status in ("started", "invalid", "completed; DROP TABLE analysis_requests"):
        with pytest.raises(ValueError, match="completed or failed"):
            storage.finish_request("request", status)
    assert storage.lookup_request("request")["status"] == "started"
    assert storage.connection.in_transaction is False


@pytest.mark.parametrize(
    "run_status, request_status",
    [
        ("abstained", "completed"),
        ("irrelevant", "completed"),
        ("duplicate", "completed"),
        ("ineligible", "completed"),
        ("explanation_completed", "completed"),
        ("partial", "failed"),
        ("explanation_failed", "failed"),
    ],
)
def test_finish_request_accepts_terminal_pipeline_statuses(storage, run_status, request_status):
    storage.add_articles([source()])
    assert storage.claim_request("request", "r1")
    storage.save_run(run(status=run_status))
    storage.finish_request("request", run_status)
    assert storage.lookup_request("request") == {"run_id": "r1", "status": request_status}
    assert storage.get_run("r1").status == run_status


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
@pytest.mark.parametrize(
    "table",
    [
        "articles",
        "market_observations",
        "events",
        "event_sources",
        "analysis_runs",
        "model_calls",
        "assessments",
    ],
)
def test_external_sql_replace_cannot_bypass_immutability(storage, verb, table):
    storage.add_articles([source()])
    storage.add_observations([observation()])
    storage.save_run(run())
    path = storage.connection.execute("PRAGMA database_list").fetchone()[2]
    # External SQLite clients default to disabled recursive/delete triggers.
    with sqlite3.connect(path) as external:
        external.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            external.execute(f"{verb} INTO {table} SELECT * FROM {table}")
    assert storage.get_article("a1") == source()
    assert storage.list_observations() == [observation()]
    assert storage.get_run("r1") == run()
    assert storage.list_events() == [run().extraction]
    assert storage.connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "table, key, replacement",
    [
        ("articles", "article_id", "replacement-article"),
        ("market_observations", "observation_id", "replacement-observation"),
        ("model_calls", "trace_id", "replacement-trace"),
    ],
)
def test_replace_cannot_delete_saved_rows_via_natural_key(storage, table, key, replacement):
    storage.add_articles([source()])
    storage.add_observations([observation()])
    storage.save_run(run())
    cursor = storage.connection.execute(f"SELECT * FROM {table}")
    names = [column[0] for column in cursor.description]
    values = list(cursor.fetchone())
    values[names.index(key)] = replacement
    placeholders = ", ".join("?" for _ in values)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"), storage.connection:
        storage.connection.execute(
            f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", values
        )
    assert storage.get_article("a1") == source()
    assert storage.list_observations() == [observation()]
    assert storage.get_run("r1") == run()


def test_v2_migration_preserves_decisions_and_adds_replace_guards(tmp_path):
    path = tmp_path / "v2.sqlite"
    with Storage(path) as store:
        store.add_articles([source()])
        store.save_run(run())
        store.claim_request("request", "r1")
        store.finish_request("request", "completed")
    with sqlite3.connect(path) as connection:
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%_insert'"
        ).fetchall():
            connection.execute(f"DROP TRIGGER {name}")
        connection.execute("PRAGMA user_version = 2")
    with Storage(path) as migrated:
        assert migrated.get_run("r1") == run()
        assert migrated.lookup_request("request") == {"run_id": "r1", "status": "completed"}
        assert migrated.claim_request("request", "r2") is False
        with pytest.raises(sqlite3.IntegrityError, match="immutable"), migrated.connection:
            migrated.connection.execute(
                "INSERT OR REPLACE INTO analysis_runs SELECT * FROM analysis_runs"
            )
    with Storage(path) as reopened:
        assert reopened.connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert reopened.get_run("r1") == run()
