"""Read-only web views of the existing ledger; opening a page never creates it."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .schemas import AnalysisRun, Article, EventOutcome, MarketObservation


class WorkspaceView:
    """Read existing schema records without running Storage's schema migrations."""

    def __init__(self, path: Path):
        self.connection = None
        if path.exists():
            self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            self.connection.execute("PRAGMA query_only = ON")

    def records(self, table, model):
        # Table names below are source constants, never request parameters.
        if self.connection is None:
            return []
        return [
            model.model_validate_json(row[0])
            for row in self.connection.execute(f"SELECT data FROM {table}")
        ]

    def list_articles(self):
        return sorted(self.records("articles", Article), key=lambda row: row.published_at)

    def list_observations(self):
        return sorted(
            self.records("market_observations", MarketObservation), key=lambda row: row.timestamp
        )

    def list_runs(self):
        return sorted(self.records("analysis_runs", AnalysisRun), key=lambda row: row.created_at)

    def list_outcomes(self):
        return self.records("outcomes", EventOutcome)

    def get_run(self, identifier):
        return next((row for row in self.list_runs() if row.run_id == identifier), None)

    def get_article(self, identifier):
        return next((row for row in self.list_articles() if row.article_id == identifier), None)

    def get_outcome(self, identifier):
        return next((row for row in self.list_outcomes() if row.run_id == identifier), None)

    def close(self):
        if self.connection:
            self.connection.close()


@contextmanager
def view_workspace(path: Path):
    view = WorkspaceView(path)
    try:
        yield view
    finally:
        view.close()
