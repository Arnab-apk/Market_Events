"""Read-only latest quotes for the bounded Indian-stock practice universe.

Quotes are transient display data; they never replace immutable daily research bars.
"""

import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import quote

from .config import LiveDataSettings
from .live_data import API_URL, IST, MASTER_URL, _Reader, _discover, get_live_universe
from .stock_catalog import catalog, resolve_stocks


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


def _provider_instruments(settings, holdings, now):
    if holdings is None:
        return _instruments(str(settings.root), now.date().isoformat()), []
    instruments, missing = resolve_stocks(settings, holdings)
    for index, instrument in enumerate(instruments):
        if instrument.get("provider_instrument_key"):
            continue
        match = next(
            (
                row
                for row in catalog(instrument["exchange"], now.date().isoformat())
                if row["instrument_id"] == instrument["instrument_id"]
            ),
            None,
        )
        if match:
            instruments[index] = match
        else:
            missing.append(instrument["instrument_id"])
    return [item for item in instruments if item.get("provider_instrument_key")], missing


def latest_paper_quotes(settings, holdings=None):
    if not settings.live_data.access_token.get_secret_value():
        raise ValueError("Configure the Upstox Analytics Token for live paper prices")
    now = datetime.now(timezone.utc)
    instruments, missing = _provider_instruments(settings, holdings, now)
    reader = _Reader(settings.live_data, {"network_requests": 0})
    by_key = {}
    for start in range(0, len(instruments), 50):
        batch = instruments[start : start + 50]
        response = reader.get(
            API_URL + "/v2/market-quote/quotes",
            params={
                "instrument_key": ",".join(item["provider_instrument_key"] for item in batch),
            },
        )
        if (
            not isinstance(response, dict)
            or response.get("status") != "success"
            or not isinstance(response.get("data"), dict)
        ):
            raise ValueError("Provider returned an invalid quote snapshot")
        by_key.update(
            {
                item.get("instrument_token"): item
                for item in response["data"].values()
                if isinstance(item, dict)
            }
        )
    now = datetime.now(timezone.utc)
    quotes = []
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


def intraday_candles(settings, stock):
    if not settings.live_data.access_token.get_secret_value():
        raise ValueError("Configure the Upstox Analytics Token for intraday charts")
    instruments, _ = _provider_instruments(settings, [stock], datetime.now(timezone.utc))
    if not instruments:
        raise ValueError("Upstox could not match the selected stock")
    reader = _Reader(settings.live_data, {"network_requests": 0})
    key = quote(instruments[0]["provider_instrument_key"], safe="")
    mode = "current session"

    def read(url):
        response = reader.get(url)
        raw = (
            response.get("data", {}).get("candles")
            if isinstance(response, dict) and isinstance(response.get("data"), dict)
            else None
        )
        if not isinstance(raw, list):
            raise ValueError("Provider returned invalid intraday candles")
        bars = {}
        for row in raw[:2000]:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                traded = datetime.fromisoformat(row[0])
                open_, high, low, close, volume = map(float, row[1:6])
                if traded.tzinfo is None or not all(
                    math.isfinite(value) for value in (open_, high, low, close, volume)
                ):
                    continue
                if not 0 < low <= min(open_, close) <= max(open_, close) <= high or volume < 0:
                    continue
                time = int(traded.timestamp())
                bars[time] = {
                    "time": time,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            except (TypeError, ValueError, OverflowError, OSError):
                continue
        return sorted(bars.values(), key=lambda bar: bar["time"])

    bars = read(f"{API_URL}/v3/historical-candle/intraday/{key}/minutes/5")
    if not bars:
        today = datetime.now(IST).date()
        bars = read(
            f"{API_URL}/v3/historical-candle/{key}/minutes/5/{today}/{today - timedelta(days=7)}"
        )
        if bars:
            last_day = datetime.fromtimestamp(bars[-1]["time"], IST).date()
            bars = [
                bar for bar in bars if datetime.fromtimestamp(bar["time"], IST).date() == last_day
            ]
        mode = "last available session"
    return {
        "source": "Upstox",
        "session": mode,
        "bars": bars,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
