"""Vercel entry point for the Python API (the `api` service in vercel.json).

Vercel's filesystem is read-only except /tmp, so the bundled synthetic demo database is copied to
/tmp on a cold start. Private workspace records live in Postgres across deployments.
The demo always replays recorded output. The live workspace uses the configured provider secrets
and model mode when the user requests a sync or analysis.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WRITABLE = Path("/tmp/market-events")

sys.path.insert(0, str(ROOT / "src"))
WRITABLE.mkdir(parents=True, exist_ok=True)
demo_copy = WRITABLE / "web_demo.sqlite"
if not demo_copy.exists():
    shutil.copyfile(ROOT / "data/web_demo.sqlite", demo_copy)

os.environ.setdefault("MARKET_EVENTS_ROOT", str(ROOT))
os.environ.setdefault("MARKET_EVENTS_MODE", "replay")
os.environ.setdefault("MARKET_EVENTS_DEMO_DATABASE", str(demo_copy))
os.environ.setdefault("MARKET_EVENTS_DATABASE", str(WRITABLE / "market_events.sqlite"))

database_url = os.getenv("MARKET_EVENTS_DATABASE_URL") or os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("Configure DATABASE_URL for persistent Vercel workspace storage")

from market_events.postgres import initialize_postgres  # noqa: E402

initialize_postgres(database_url)

from market_events.api import create_app  # noqa: E402  (needs the paths above)

app = create_app(ROOT)
