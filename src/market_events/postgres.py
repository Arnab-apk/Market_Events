"""Postgres transport for the ledger's parameterized SQL and transaction boundary.

The same table definitions and Storage methods serve local SQLite and hosted Postgres.
Schema setup is an explicit startup/deployment operation, never a page-view side effect.
"""

import sqlite3
import re
from contextlib import contextmanager

import psycopg
from psycopg import sql

SCHEMA_NAME = "market_events"
TABLES = r"\b(articles|market_observations|events|event_sources|analysis_runs|model_calls|assessments|outcomes|analysis_requests|portfolios)\b"


@contextmanager
def _database_errors():
    try:
        yield
    except psycopg.IntegrityError as error:
        raise sqlite3.IntegrityError("Workspace record violates a ledger constraint") from error
    except psycopg.Error as error:
        raise sqlite3.DatabaseError("Persistent workspace database is unavailable") from error


class PostgresConnection:
    """Small DB-API bridge; values always remain bound parameters."""

    def __init__(self, url: str, *, readonly=False):
        with _database_errors():
            self.raw = psycopg.connect(
                url, autocommit=True, connect_timeout=15, prepare_threshold=None
            )
        self.readonly = readonly
        self.schema = SCHEMA_NAME
        self.transactions = []

    def execute(self, query, parameters=None):
        # Transaction poolers do not retain session SET/search_path between queries.
        # Qualify constant table names; parameter values are never interpolated.
        query = re.sub(
            TABLES, lambda match: sql.Identifier(self.schema, match[0]).as_string(self.raw), query
        )
        with _database_errors():
            if self.readonly:
                with self.raw.transaction():
                    self.raw.execute("SET TRANSACTION READ ONLY")
                    return self.raw.execute(query.replace("?", "%s"), parameters)
            return self.raw.execute(query.replace("?", "%s"), parameters)

    def __enter__(self):
        transaction = self.raw.transaction()
        self.transactions.append(transaction)
        with _database_errors():
            transaction.__enter__()
        return self

    def __exit__(self, *args):
        with _database_errors():
            return self.transactions.pop().__exit__(*args)

    def close(self):
        self.raw.close()


def initialize_postgres(url: str):
    """Idempotently create schema under a transaction-scoped migration lock."""
    from .storage import PORTFOLIO_SCHEMA, SCHEMA_V1

    with _database_errors(), psycopg.connect(url, connect_timeout=15) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(481773024)")
        connection.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SCHEMA_NAME))
        )
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(SCHEMA_NAME))
        )
        connection.execute("CREATE TABLE IF NOT EXISTS ledger_schema (version INTEGER NOT NULL)")
        row = connection.execute("SELECT version FROM ledger_schema").fetchone()
        if row is not None and row[0] != 1:
            raise ValueError("Unsupported persistent ledger schema version")
        if row is None:
            connection.execute(SCHEMA_V1)
            connection.execute("""CREATE TABLE analysis_requests (
                request_key TEXT PRIMARY KEY CHECK(length(trim(request_key)) > 0),
                run_id TEXT NOT NULL UNIQUE CHECK(length(trim(run_id)) > 0),
                status TEXT NOT NULL DEFAULT 'started'
                    CHECK(status IN ('started', 'completed', 'failed'))
            )""")
            connection.execute("""CREATE FUNCTION reject_ledger_mutation() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                    RAISE EXCEPTION 'Saved records are immutable' USING ERRCODE = '23000';
                END $$""")
            for table in (
                "articles",
                "market_observations",
                "events",
                "event_sources",
                "analysis_runs",
                "model_calls",
                "assessments",
            ):
                connection.execute(
                    f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation()"
                )
            connection.execute("INSERT INTO ledger_schema VALUES (1)")
        connection.execute(PORTFOLIO_SCHEMA)
