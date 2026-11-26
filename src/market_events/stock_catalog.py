"""Explicit discovery/preview for selectable NSE/BSE cash instruments.

Only provider-verified metadata is saved. Prices and reviewed exposure rules remain separate.
"""

import math
import re
from datetime import datetime, timezone
from functools import lru_cache

from .config import LiveDataSettings
from .live_data import BSE_MASTER_URL, MASTER_URL, _Reader, get_live_universe, sync_live


@lru_cache(maxsize=4)
def catalog(exchange: str, day: str) -> tuple[dict, ...]:
    url = MASTER_URL if exchange == "NSE" else BSE_MASTER_URL
    rows = _Reader(LiveDataSettings(), {"network_requests": 0}).get(url, authenticated=False)
    if not isinstance(rows, list):
        raise ValueError("The provider stock directory is unavailable")
    result = {}
    for item in rows:
        if not isinstance(item, dict) or item.get("segment") != f"{exchange}_EQ":
            continue
        if exchange == "NSE" and item.get("instrument_type") != "EQ":
            continue
        symbol, key = item.get("trading_symbol", ""), item.get("instrument_key", "")
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9&._-]{0,29}", symbol):
            continue
        if not isinstance(key, str) or not key.startswith(f"{exchange}_EQ|"):
            continue
        identifier = f"LIVE:{exchange}:{symbol}"
        record = {
            "instrument_id": identifier,
            "name": item.get("name") or symbol,
            "trading_symbol": symbol,
            "provider_instrument_key": key,
            "exchange": exchange,
            "currency": "INR",
            "unit": "share",
            "market_family": "equity",
            "aliases": [],
            "sector": "",
            "benchmark_id": "LIVE:NSE:NIFTY50",
            "source": url,
        }
        if identifier not in result:
            result[identifier] = record
        elif result[identifier] != record:
            result[identifier] = None  # Never guess an ambiguous instrument mapping.
    return tuple(record for record in result.values() if record is not None)


def resolve_stocks(settings, holdings):
    """Use the saved server metadata first; explicitly discover unfamiliar holdings."""
    known = {item["instrument_id"]: item for item in get_live_universe(settings)}
    day = datetime.now(timezone.utc).date().isoformat()
    instruments, missing = [], []
    directories = {}
    for row in holdings:
        identifier = f"LIVE:{row['exchange']}:{row['symbol']}"
        item = known.get(identifier)
        if item is None:
            exchange = row["exchange"]
            if exchange not in directories:
                directories[exchange] = {
                    item["instrument_id"]: item for item in catalog(exchange, day)
                }
            item = directories[exchange].get(identifier)
        if item is None:
            missing.append(identifier)
        else:
            instruments.append(item)
    return instruments, missing


def search_stocks(query, exchange):
    query = query.strip().casefold()
    rows = catalog(exchange, datetime.now(timezone.utc).date().isoformat())
    matches = [
        row
        for row in rows
        if query in row["trading_symbol"].casefold() or query in row["name"].casefold()
    ]
    matches.sort(
        key=lambda row: (
            row["trading_symbol"].casefold() != query,
            not row["trading_symbol"].casefold().startswith(query),
            row["trading_symbol"],
        )
    )
    return {"source": "Upstox instrument directory", "matches": matches[:20]}


def preview_paper_account(dependencies, holdings, capital):
    instruments, missing = resolve_stocks(dependencies.settings, holdings)
    if missing:
        raise ValueError("Cannot map selected stocks: " + ", ".join(missing))
    settings = dependencies.settings.model_copy(deep=True)
    base = {item["instrument_id"] for item in get_live_universe(settings.root)}
    settings.portfolio_instruments = [
        item for item in instruments if item["instrument_id"] not in base
    ]
    from .pipeline import Dependencies

    report = sync_live(
        Dependencies(dependencies.storage, settings),
        [item["instrument_id"] for item in instruments],
        lookback_days=14,
        include_news=False,
        include_commodities=False,
    )
    if report["errors"]:
        raise ValueError(
            "Selected prices could not be refreshed. Check Connections before saving the practice portfolio."
        )
    now = datetime.now(timezone.utc)
    observations = dependencies.storage.list_observations()
    rows = []
    for instrument in instruments:
        prices = [
            row
            for row in observations
            if row.instrument_id == instrument["instrument_id"] and row.timestamp <= now
        ]
        latest = max(prices, key=lambda row: row.timestamp, default=None)
        if not latest or (now - latest.timestamp).total_seconds() > 4 * 86400:
            raise ValueError(
                "A recent completed daily price is unavailable for " + instrument["trading_symbol"]
            )
        cost = round(latest.close, 6)
        quantity = math.floor(capital / len(instruments) / cost)
        if not 1 <= quantity <= 100_000_000:
            raise ValueError(
                "The virtual budget cannot buy a whole share of " + instrument["trading_symbol"]
            )
        rows.append(
            {
                "symbol": instrument["trading_symbol"],
                "exchange": instrument["exchange"],
                "quantity": quantity,
                "averageCost": cost,
            }
        )
    invested = sum(row["quantity"] * row["averageCost"] for row in rows)
    return {
        "snapshot": {
            "source": "Custom Indian stocks · paper money",
            "importedAt": now.isoformat(),
            "holdings": rows,
            "paper": {"startingCash": capital, "cash": capital - invested},
        },
        "report": report,
    }
