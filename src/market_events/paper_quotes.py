"""Read-only latest quotes for the bounded Indian-stock practice universe.

Quotes are transient display data; they never replace immutable daily research bars.
"""

import math
from datetime import datetime, timezone
from functools import lru_cache

from .config import LiveDataSettings
from .live_data import API_URL, MASTER_URL, _Reader, _discover, get_live_universe


@lru_cache(maxsize=2)
def _instruments(root, day):
    report = {"network_requests": 0}
    master = _Reader(LiveDataSettings(), report).get(MASTER_URL, authenticated=False)
    if not isinstance(master, list):
        raise ValueError("Provider instrument list is unavailable")
    return [
        _discover(item, master)
        for item in get_live_universe(root)
        if item["market_family"] == "equity"
    ]


def latest_paper_quotes(settings):
    if not settings.live_data.access_token.get_secret_value():
        raise ValueError("Configure the Upstox Analytics Token for live paper prices")
    now = datetime.now(timezone.utc)
    instruments = _instruments(str(settings.root), now.date().isoformat())
    reader = _Reader(settings.live_data, {"network_requests": 0})
    response = reader.get(
        API_URL + "/v2/market-quote/quotes",
        params={
            "instrument_key": ",".join(item["provider_instrument_key"] for item in instruments)
        },
    )
    if response.get("status") != "success" or not isinstance(response.get("data"), dict):
        raise ValueError("Provider returned an invalid quote snapshot")
    now = datetime.now(timezone.utc)
    by_key = {
        item.get("instrument_token"): item
        for item in response["data"].values()
        if isinstance(item, dict)
    }
    quotes, missing = [], []
    for instrument in instruments:
        item = by_key.get(instrument["provider_instrument_key"], {})
        try:
            price = float(item["last_price"])
            traded = datetime.fromtimestamp(float(item["last_trade_time"]) / 1000, timezone.utc)
            if not math.isfinite(price) or price <= 0 or traded > now:
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            missing.append(instrument["instrument_id"])
            continue
        quotes.append(
            {
                "instrument_id": instrument["instrument_id"],
                "price": price,
                "last_trade_at": traded.isoformat(),
            }
        )
    return {"source": "Upstox", "fetched_at": now.isoformat(), "quotes": quotes, "missing": missing}
