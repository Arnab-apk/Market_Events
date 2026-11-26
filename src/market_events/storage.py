"""The SQLite ledger that stores every article version, observation, event, run, model call and
outcome. Records are append-only: an identical write is a no-op and a conflicting one raises, so
saved decisions can never be rewritten. Outcomes live in a separate table and may be recomputed
without touching runs.

An identical write is idempotent; conflicting identities raise ValueError (or a
SQLite integrity error for violated foreign keys/unique keys). Outcomes live
separately and may be recomputed without altering the original decision.
"""

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from market_events.schemas import (
    AnalysisRun,
    Article,
    EventExtraction,
    EventOutcome,
    MarketObservation,
)


# ---------------------------------------------------------------------------
# Serialisation and schema migrations
# ---------------------------------------------------------------------------


def _json(record: BaseModel) -> str:
    return json.dumps(
        record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


SCHEMA_V1 = """
        CREATE TABLE articles (
            article_id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            source_version TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            published_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            predecessor_id TEXT REFERENCES articles(article_id) DEFERRABLE INITIALLY DEFERRED,
            data TEXT NOT NULL,
            UNIQUE(source_url, source_version),
            CHECK(predecessor_id IS NULL OR predecessor_id != article_id)
        );
        CREATE INDEX articles_content ON articles(content_hash);
        CREATE INDEX articles_availability ON articles(first_seen_at, published_at);
        CREATE TABLE market_observations (
            observation_id TEXT PRIMARY KEY,
            instrument_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            available_at TEXT NOT NULL,
            contract_id TEXT NOT NULL,
            data TEXT NOT NULL,
            UNIQUE(instrument_id, timestamp, contract_id)
        );
        CREATE INDEX market_availability ON market_observations(instrument_id, available_at, timestamp);
        CREATE TABLE events (
            event_id TEXT NOT NULL,
            source_version TEXT NOT NULL,
            event_type TEXT NOT NULL,
            company_id TEXT,
            data TEXT NOT NULL,
            PRIMARY KEY(event_id, source_version)
        );
        CREATE TABLE event_sources (
            event_id TEXT NOT NULL,
            source_version TEXT NOT NULL,
            article_id TEXT NOT NULL REFERENCES articles(article_id),
            PRIMARY KEY(event_id, source_version, article_id),
            FOREIGN KEY(event_id, source_version) REFERENCES events(event_id, source_version)
        );
        CREATE TABLE analysis_runs (
            run_id TEXT PRIMARY KEY,
            article_id TEXT NOT NULL REFERENCES articles(article_id),
            event_id TEXT,
            event_source_version TEXT,
            policy TEXT NOT NULL,
            decision_time TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY(event_id, event_source_version, article_id)
                REFERENCES event_sources(event_id, source_version, article_id),
            CHECK((event_id IS NULL) = (event_source_version IS NULL))
        );
        CREATE INDEX runs_article_time ON analysis_runs(article_id, decision_time);
        CREATE TABLE model_calls (
            trace_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES analysis_runs(run_id),
            position INTEGER NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            UNIQUE(run_id, position)
        );
        CREATE TABLE assessments (
            run_id TEXT PRIMARY KEY REFERENCES analysis_runs(run_id),
            direction TEXT NOT NULL,
            rules_version TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE outcomes (
            run_id TEXT PRIMARY KEY REFERENCES analysis_runs(run_id),
            status TEXT NOT NULL,
            definition_version TEXT NOT NULL,
            data TEXT NOT NULL
        );
        """


def _migrate_v1(connection: sqlite3.Connection) -> None:
    script = "BEGIN;" + SCHEMA_V1
    # Guard the ledger even when another local SQLite client opens the database.
    for table in (
        "articles",
        "market_observations",
        "events",
        "event_sources",
        "analysis_runs",
        "model_calls",
        "assessments",
    ):
        for operation in ("UPDATE", "DELETE"):
            script += (
                f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'Saved records are immutable'); END;\n"
            )
    connection.executescript(script + "PRAGMA user_version = 1; COMMIT;")


def _migrate_v2(connection: sqlite3.Connection) -> None:
    """Add durable claims without requiring a run to exist before inference."""
    connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS analysis_requests (
            request_key TEXT PRIMARY KEY NOT NULL CHECK(length(trim(request_key)) > 0),
            run_id TEXT NOT NULL UNIQUE CHECK(length(trim(run_id)) > 0),
            status TEXT NOT NULL DEFAULT 'started'
                CHECK(status IN ('started', 'completed', 'failed'))
        );
        PRAGMA user_version = 2;
        COMMIT;
        """
    )


def _migrate_v3(connection: sqlite3.Connection) -> None:
    """Prevent REPLACE from deleting immutable rows when delete triggers are off.

    SQLite only fires delete triggers for REPLACE with recursive_triggers=ON.
    Guard conflicting inserts instead, including collisions on natural keys.
    """
    keys = {
        "articles": (
            "article_id = NEW.article_id OR "
            "(source_url = NEW.source_url AND source_version = NEW.source_version)"
        ),
        "market_observations": (
            "observation_id = NEW.observation_id OR (instrument_id = NEW.instrument_id "
            "AND timestamp = NEW.timestamp AND contract_id = NEW.contract_id)"
        ),
        "events": "event_id = NEW.event_id AND source_version = NEW.source_version",
        "event_sources": (
            "event_id = NEW.event_id AND source_version = NEW.source_version "
            "AND article_id = NEW.article_id"
        ),
        "analysis_runs": "run_id = NEW.run_id",
        "model_calls": (
            "trace_id = NEW.trace_id OR (run_id = NEW.run_id AND position = NEW.position)"
        ),
        "assessments": "run_id = NEW.run_id",
    }
    script = "BEGIN IMMEDIATE;\n"
    for table, condition in keys.items():
        script += (
            f"CREATE TRIGGER immutable_{table}_insert BEFORE INSERT ON {table} "
            f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {condition}) "
            "BEGIN SELECT RAISE(ABORT, 'Saved records are immutable'); END;\n"
        )
    connection.executescript(script + "PRAGMA user_version = 3; COMMIT;")


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


PORTFOLIO_SCHEMA = """CREATE TABLE IF NOT EXISTS portfolios (
    scope TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision > 0), data TEXT
)"""


class PortfolioConflict(ValueError):
    """A stale portfolio write must not overwrite another confirmed save."""


class Storage:
    """One local SQLite connection, with FK enforcement and schema initialization."""

    # ---------------------------------------------------------------------------
    # Connection lifecycle
    # ---------------------------------------------------------------------------

    def __init__(self, path: Path, database_url: str = ""):
        if database_url:
            from .postgres import PostgresConnection

            self.connection = PostgresConnection(database_url)
            return
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=5)
        try:
            self.connection.execute("PRAGMA foreign_keys = ON")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise ValueError(f"Unsupported database schema_version: {version}")
            if version == 0:
                _migrate_v1(self.connection)
                version = 1
            if version == 1:
                _migrate_v2(self.connection)
                version = 2
            if version == 2:
                _migrate_v3(self.connection)
            self.connection.execute(PORTFOLIO_SCHEMA)
            self.connection.commit()
        except Exception:
            self.connection.close()
            raise

    def portfolio(self, scope: str) -> dict:
        row = self.connection.execute(
            "SELECT revision, data FROM portfolios WHERE scope = ?", (scope,)
        ).fetchone()
        return (
            {"revision": row[0], "snapshot": json.loads(row[1]) if row[1] else None}
            if row
            else {"revision": 0, "snapshot": None}
        )

    def save_portfolio(self, scope: str, snapshot: dict | None, revision: int) -> dict:
        # A tombstone retains the revision after clearing, so stale tabs cannot resurrect it.
        data = json.dumps(snapshot, allow_nan=False) if snapshot is not None else None
        with self.connection:
            if revision == 0:
                cursor = self.connection.execute(
                    "INSERT INTO portfolios(scope, revision, data) VALUES (?, 1, ?) "
                    "ON CONFLICT(scope) DO NOTHING",
                    (scope, data),
                )
            else:
                cursor = self.connection.execute(
                    "UPDATE portfolios SET revision = revision + 1, data = ? "
                    "WHERE scope = ? AND revision = ?",
                    (data, scope, revision),
                )
            if cursor.rowcount != 1:
                raise PortfolioConflict(
                    "The portfolio changed in another tab. Reload before saving again."
                )
        return {"revision": revision + 1, "snapshot": snapshot}

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    # ---------------------------------------------------------------------------
    # Request reservations (identical analyses are reused)
    # ---------------------------------------------------------------------------

    def claim_request(self, request_key: str, run_id: str) -> bool:
        """Commit a started claim; return False if either key or run is claimed.

        No transaction remains open during model inference. Claims deliberately
        have no run foreign key because the run is saved only after inference;
        interrupted claims remain visible and are never silently reclaimed.
        """
        if not request_key.strip() or not run_id.strip():
            raise ValueError("Request key and run_id must be nonempty")
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO analysis_requests(request_key, run_id) VALUES (?, ?) "
                "ON CONFLICT DO NOTHING",
                (request_key, run_id),
            )
            return cursor.rowcount == 1

    def lookup_request(self, request_key: str) -> dict | None:
        """Return run_id/status, including durable unfinished claims."""
        row = self.connection.execute(
            "SELECT run_id, status FROM analysis_requests WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        if row is None:
            return None
        return {"run_id": row[0], "status": row[1]}

    def finish_request(self, request_key: str, status: str) -> None:
        """Commit completed/failed state; identical completion is idempotent.

        Terminal pipeline statuses map to completed/failed request states. A
        completed claim requires its saved run. A failed claim may lack a run
        if persistence itself failed. Terminal claims cannot be repurposed;
        an explicit repeat must use a new request key and run ID.
        """
        if status in {"failed", "partial", "explanation_failed"}:
            status = "failed"
        elif status in {
            "completed",
            "abstained",
            "irrelevant",
            "duplicate",
            "ineligible",
            "explanation_completed",
        }:
            status = "completed"
        else:
            raise ValueError(
                "Finished request status must be completed or failed, or a terminal run status"
            )
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE analysis_requests SET status = ? WHERE request_key = ? "
                "AND status IN ('started', ?) "
                "AND (? = 'failed' OR EXISTS (SELECT 1 FROM analysis_runs "
                "WHERE analysis_runs.run_id = analysis_requests.run_id))",
                (status, request_key, status, status),
            )
            if cursor.rowcount == 0:
                request = self.lookup_request(request_key)
                if request is None:
                    raise ValueError(f"Unknown analysis request: {request_key}")
                if request["status"] not in {"started", status}:
                    raise ValueError("Finished analysis request status is immutable")
                raise ValueError("Completed analysis request must reference a saved run")

    # ---------------------------------------------------------------------------
    # Articles and market observations
    # ---------------------------------------------------------------------------

    def add_articles(self, records: Iterable[Article]) -> int:
        """Insert unchanged source versions atomically; never overwrite a correction."""
        count = 0
        with self.connection:
            for article in records:
                data = _json(article)
                old = self.connection.execute(
                    "SELECT data FROM articles WHERE article_id = ?", (article.article_id,)
                ).fetchone()
                if old:
                    if old[0] != data:
                        raise ValueError(f"Conflicting immutable article: {article.article_id}")
                    continue
                self.connection.execute(
                    "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        article.article_id,
                        article.source_url,
                        article.source_version,
                        article.content_hash,
                        article.published_at.isoformat(),
                        article.first_seen_at.isoformat(),
                        article.predecessor_id,
                        data,
                    ),
                )
                count += 1
        return count

    def add_observations(self, records: Iterable[MarketObservation]) -> int:
        """Save new market observations; returns how many were new."""
        count = 0
        with self.connection:
            for observation in records:
                data = _json(observation)
                old = self.connection.execute(
                    "SELECT data FROM market_observations WHERE observation_id = ?",
                    (observation.observation_id,),
                ).fetchone()
                if old:
                    if old[0] != data:
                        raise ValueError(
                            f"Conflicting immutable observation: {observation.observation_id}"
                        )
                    continue
                self.connection.execute(
                    "INSERT INTO market_observations VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        observation.observation_id,
                        observation.instrument_id,
                        observation.timestamp.isoformat(),
                        observation.available_at.isoformat(),
                        observation.contract_id or "",
                        data,
                    ),
                )
                count += 1
        return count

    def get_article(self, id: str) -> Article | None:
        """Return the saved article with this ID, if any."""
        row = self.connection.execute(
            "SELECT data FROM articles WHERE article_id = ?", (id,)
        ).fetchone()
        return Article.model_validate_json(row[0]) if row else None

    def list_articles(self) -> list[Article]:
        """All saved articles, by publication time."""
        return [
            Article.model_validate_json(row[0])
            for row in self.connection.execute(
                "SELECT data FROM articles ORDER BY published_at, article_id"
            )
        ]

    def list_observations(self) -> list[MarketObservation]:
        """All saved market observations, by timestamp."""
        return [
            MarketObservation.model_validate_json(row[0])
            for row in self.connection.execute(
                "SELECT data FROM market_observations ORDER BY timestamp, instrument_id, contract_id"
            )
        ]

    # ---------------------------------------------------------------------------
    # Events and analysis runs
    # ---------------------------------------------------------------------------

    def list_events(self) -> list[EventExtraction]:
        """All saved event extractions."""
        return [
            EventExtraction.model_validate_json(row[0])
            for row in self.connection.execute(
                "SELECT data FROM events ORDER BY event_id, source_version"
            )
        ]

    def _save_event(self, run: AnalysisRun, article: Article) -> str | None:
        event = run.extraction
        if event:
            if event.event_id != run.event_id:
                raise ValueError("Run event_id must match its extraction")
            old = self.connection.execute(
                "SELECT data FROM events WHERE event_id = ? AND source_version = ?",
                (event.event_id, event.source_version),
            ).fetchone()
            # The first extraction is an immutable source/event baseline. Model
            # interpretations may differ across runs; each full extraction lives
            # in its immutable analysis_runs JSON, not in an overwritten event.
            if not old:
                self.connection.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                    (
                        event.event_id,
                        event.source_version,
                        event.event_type,
                        event.company_id,
                        _json(event),
                    ),
                )
            version = event.source_version
        elif run.event_id:
            versions = self.connection.execute(
                "SELECT source_version FROM events WHERE event_id = ?", (run.event_id,)
            ).fetchall()
            if (article.source_version,) in versions:
                version = article.source_version
            elif len(versions) == 1:
                version = versions[0][0]
            else:
                raise ValueError("Run references a missing or ambiguous event version")
        else:
            return None
        self.connection.execute(
            "INSERT INTO event_sources SELECT ?, ?, ? WHERE NOT EXISTS "
            "(SELECT 1 FROM event_sources WHERE event_id = ? AND source_version = ? "
            "AND article_id = ?)",
            (run.event_id, version, article.article_id) * 2,
        )
        return version

    def save_run(self, run: AnalysisRun) -> None:
        """Atomically append event/source links, a run, its calls and assessment."""
        data = _json(run)
        with self.connection:
            old = self.connection.execute(
                "SELECT data FROM analysis_runs WHERE run_id = ?", (run.run_id,)
            ).fetchone()
            if old:
                # Older snapshots may omit optional fields added by a later schema.
                # Compare their interpreted defaults without rewriting ledger bytes.
                if old[0] != data and _json(AnalysisRun.model_validate_json(old[0])) != data:
                    raise ValueError(f"Conflicting immutable run: {run.run_id}")
                return
            article = self.get_article(run.article_id)
            if article is None:
                raise ValueError(f"Run article does not exist: {run.article_id}")
            if any(call.run_id != run.run_id for call in run.calls):
                raise ValueError("Every model call must reference its containing run")
            version = self._save_event(run, article)
            self.connection.execute(
                "INSERT INTO analysis_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    run.article_id,
                    run.event_id,
                    version,
                    run.policy.value,
                    run.decision_time.isoformat(),
                    run.created_at.isoformat(),
                    run.status,
                    data,
                ),
            )
            for position, call in enumerate(run.calls):
                self.connection.execute(
                    "INSERT INTO model_calls VALUES (?, ?, ?, ?, ?, ?)",
                    (call.trace_id, run.run_id, position, call.task, call.status, _json(call)),
                )
            if run.assessment:
                self.connection.execute(
                    "INSERT INTO assessments VALUES (?, ?, ?, ?)",
                    (
                        run.run_id,
                        run.assessment.direction,
                        run.assessment.rules_version,
                        _json(run.assessment),
                    ),
                )

    def get_run(self, id: str) -> AnalysisRun | None:
        """Return one saved analysis run, if any."""
        row = self.connection.execute(
            "SELECT data FROM analysis_runs WHERE run_id = ?", (id,)
        ).fetchone()
        return AnalysisRun.model_validate_json(row[0]) if row else None

    def list_runs(self) -> list[AnalysisRun]:
        """All saved analysis runs, oldest first."""
        return [
            AnalysisRun.model_validate_json(row[0])
            for row in self.connection.execute(
                "SELECT data FROM analysis_runs ORDER BY created_at, run_id"
            )
        ]

    # ---------------------------------------------------------------------------
    # Outcomes
    # ---------------------------------------------------------------------------

    def save_outcome(self, outcome: EventOutcome) -> None:
        """Save or replace the later outcome for a run."""
        with self.connection:
            self.connection.execute(
                "INSERT INTO outcomes VALUES (?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET "
                "status=excluded.status, definition_version=excluded.definition_version, data=excluded.data",
                (outcome.run_id, outcome.status, outcome.definition_version, _json(outcome)),
            )

    def get_outcome(self, run_id: str) -> EventOutcome | None:
        """Return the saved outcome for a run, if any."""
        row = self.connection.execute(
            "SELECT data FROM outcomes WHERE run_id = ?", (run_id,)
        ).fetchone()
        return EventOutcome.model_validate_json(row[0]) if row else None

    def list_outcomes(self) -> list[EventOutcome]:
        """All saved outcomes."""
        return [
            EventOutcome.model_validate_json(row[0])
            for row in self.connection.execute("SELECT data FROM outcomes ORDER BY run_id")
        ]
