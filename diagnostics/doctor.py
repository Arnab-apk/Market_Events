"""Read-only project diagnostics. Output contains presence flags and counts, never keys/holdings.

Run: .venv/Scripts/python.exe diagnostics/doctor.py --output diagnostics/local/health.json
Add --check-database to explicitly check configured Postgres connectivity without migrations.
"""

import argparse
import importlib.metadata
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Optional ignored environment file")
    parser.add_argument("--check-database", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from dotenv import load_dotenv
    from market_events.config import load_settings

    if args.env_file:
        load_dotenv(args.env_file, override=False)
    settings = load_settings(ROOT)
    url = settings.database_url.get_secret_value()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "storage": "postgres" if url else "sqlite",
        "mode": settings.mode,
        "models": {"filter": settings.slm.model, "extraction": settings.llm.model},
        "configured": {
            key: bool(os.getenv(key)) and os.getenv(key) != "[SENSITIVE]"
            for key in (
                "SARVAM_API_KEY",
                "UPSTOX_ANALYTICS_TOKEN",
                "UPSTOX_CLIENT_ID",
                "UPSTOX_CLIENT_SECRET",
            )
        },
        "packages": {},
        "database_check": "not requested" if url else "local read-only",
        "notes": [
            "Configured flags do not prove provider connectivity. No provider/model requests were made."
        ],
    }
    for name in ("market-events", "fastapi", "pydantic", "psycopg", "streamlit", "pytest"):
        try:
            report["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][name] = "not installed"
    connection = None
    try:
        if url and args.check_database:
            from market_events.postgres import PostgresConnection

            connection = PostgresConnection(url, readonly=True)
        elif not url and settings.database_path.exists():
            connection = sqlite3.connect(
                settings.database_path.resolve().as_uri() + "?mode=ro", uri=True
            )
        if connection:
            report["record_counts"] = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("articles", "market_observations", "analysis_runs", "model_calls")
            }
            report["database_check"] = "passed"
        elif not url:
            report["database_check"] = "no local database; nothing created"
    except Exception:
        # Driver diagnostics can include connection details; keep exported failures generic.
        report["database_check"] = "failed; check credentials, network and schema initialization"
    finally:
        if connection:
            connection.close()
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return int(report["database_check"].startswith("failed"))


if __name__ == "__main__":
    raise SystemExit(main())
