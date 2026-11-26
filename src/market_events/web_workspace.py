"""Read-only view of a ledger for the HTTP API's GET routes. It opens SQLite in read-only mode and
never runs migrations, so viewing a page can never create or change a database. It mirrors the
read methods of Storage.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .schemas import AnalysisRun, Article, EventOutcome, MarketObservation


class WorkspaceView:
    """Read existing schema records without running Storage's schema migrations."""

    def __init__(self, path: Path, database_url: str = ""):
        self.connection = None
        if database_url:
            from .postgres import PostgresConnection

            self.connection = PostgresConnection(database_url, readonly=True)
        elif path.exists():
            self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            self.connection.execute("PRAGMA query_only = ON")

    def records(self, table, model):
        # Table names below are source constants, never request parameters.
        """Decode every JSON row of one ledger table into a model."""
        if self.connection is None:
            return []
        return [
            model.model_validate_json(row[0])
            for row in self.connection.execute(f"SELECT data FROM {table}")
        ]

    def list_articles(self):
        """Saved article versions, by publication time."""
        return sorted(self.records("articles", Article), key=lambda row: row.published_at)

    def list_observations(self):
        """Saved observations, by timestamp."""
        return sorted(
            self.records("market_observations", MarketObservation), key=lambda row: row.timestamp
        )

    def list_runs(self):
        """Saved runs, oldest first."""
        return sorted(self.records("analysis_runs", AnalysisRun), key=lambda row: row.created_at)

    def list_outcomes(self):
        """Saved outcomes."""
        return self.records("outcomes", EventOutcome)

    def get_run(self, identifier):
        """One saved run, if present."""
        return next((row for row in self.list_runs() if row.run_id == identifier), None)

    def get_article(self, identifier):
        """One saved article, if present."""
        return next((row for row in self.list_articles() if row.article_id == identifier), None)

    def get_outcome(self, identifier):
        """The outcome for one run, if present."""
        return next((row for row in self.list_outcomes() if row.run_id == identifier), None)

    def close(self):
        """Close the read-only connection."""
        if self.connection:
            self.connection.close()

    def portfolio(self, scope):
        if self.connection is None:
            return {"revision": 0, "snapshot": None}
        if (
            isinstance(self.connection, sqlite3.Connection)
            and not self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='portfolios'"
            ).fetchone()
        ):
            return {"revision": 0, "snapshot": None}
        row = self.connection.execute(
            "SELECT revision, data FROM portfolios WHERE scope = ?", (scope,)
        ).fetchone()
        return (
            {"revision": row[0], "snapshot": json.loads(row[1]) if row[1] else None}
            if row
            else {"revision": 0, "snapshot": None}
        )


@contextmanager
def view_workspace(path: Path, database_url: str = ""):
    """Context manager yielding a read-only view of a ledger."""
    view = WorkspaceView(path, database_url)
    try:
        yield view
    finally:
        view.close()
