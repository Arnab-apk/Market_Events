"""Exercise identical ledger behavior on SQLite and an opt-in isolated Postgres schema."""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import SecretStr

from market_events.config import Settings
from market_events.storage import PortfolioConflict, Storage
from market_events.web_workspace import view_workspace
from test_storage import observation, run, source


@pytest.fixture(params=["sqlite", "postgres"])
def ledger(request, tmp_path, monkeypatch):
    url = ""
    schema = None
    if request.param == "postgres":
        url = os.getenv("MARKET_EVENTS_TEST_DATABASE_URL", "")
        if not url:
            pytest.skip("Set MARKET_EVENTS_TEST_DATABASE_URL to exercise a temporary schema")
        import psycopg
        from psycopg import sql
        from market_events import postgres

        schema = "test_market_events_" + uuid4().hex
        monkeypatch.setattr(postgres, "SCHEMA_NAME", schema)
        postgres.initialize_postgres(url)
        postgres.initialize_postgres(url)  # Simulate a second cold start.
    path = tmp_path / "ledger.sqlite"
    yield lambda: Storage(path, url), path, SecretStr(url)
    if schema:
        with psycopg.connect(url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_saved_analysis_quotes_and_calls_survive_new_connections(ledger):
    open_store, path, url = ledger
    with open_store() as store:
        store.add_articles([source()])
        store.add_observations([observation()])
        store.save_run(run())
    with open_store() as store:
        assert store.get_run("r1") == run()
        assert store.list_events()
        assert len(store.list_observations()) == 1
        assert store.add_articles([source()]) == 0
        store.save_run(run())
        with pytest.raises(ValueError, match="Conflicting"):
            store.save_run(run(status="partial"))
        with pytest.raises(sqlite3.IntegrityError):
            with store.connection:
                store.connection.execute(
                    "UPDATE analysis_runs SET status='partial' WHERE run_id='r1'"
                )
    with view_workspace(path, url.get_secret_value()) as view:
        assert view.get_run("r1").calls[0].trace_id == "trace-r1"
        assert view.get_article("a1") == source()


def test_portfolio_revision_cash_and_clear_tombstone(ledger):
    open_store, path, url = ledger
    snapshot = {
        "source": "Paper test",
        "holdings": [{"symbol": "TEST", "quantity": 3}],
        "paper": {"startingCash": 100, "cash": 25},
    }
    with open_store() as store:
        assert store.portfolio("local:live") == {"revision": 0, "snapshot": None}
        store.save_portfolio("local:live", snapshot, 0)
    with open_store() as store:
        assert store.portfolio("local:live")["snapshot"]["paper"]["cash"] == 25
        assert store.portfolio("local:demo")["snapshot"] is None
        with pytest.raises(PortfolioConflict):
            store.save_portfolio("local:live", None, 0)
        store.save_portfolio("local:live", None, 1)
    with view_workspace(path, url.get_secret_value()) as view:
        assert view.portfolio("local:live") == {"revision": 2, "snapshot": None}
    with open_store() as store:
        with pytest.raises(PortfolioConflict):
            store.save_portfolio("local:live", snapshot, 0)


def test_atomic_rollback_and_concurrent_claims(ledger):
    open_store, _, _ = ledger
    with open_store() as store:
        with pytest.raises(sqlite3.IntegrityError):
            with store.connection:
                store.connection.execute(
                    "INSERT INTO analysis_requests VALUES ('claim', 'run', 'started')"
                )
                store.connection.execute(
                    "INSERT INTO analysis_requests VALUES ('claim', 'other', 'started')"
                )
        assert store.lookup_request("claim") is None

    def claim(index):
        with open_store() as store:
            return store.claim_request("same-request", f"run-{index}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(claim, range(4))) == 1


def test_database_credentials_excluded_from_saved_config():
    settings = Settings(database_url=SecretStr("postgresql://private:secret@db.invalid/private"))
    assert "database_url" not in settings.snapshot()
    assert "secret" not in str(settings)
