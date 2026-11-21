"""Optional real-data adapter for the Upstox API (read-only). Explicit syncs download daily candles
and optional news for the live universe, recording the real download time as availability.
Reading universe metadata never touches the network, and every request is bounded and paced.

Official adapter contracts:
https://upstox.com/developer/api-documentation/instruments/
https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/
https://upstox.com/developer/api-documentation/get-news/
https://upstox.com/developer/api-documentation/rate-limiting/

Daily timestamps describe candle starts. We label preceding session dates at
15:30 IST and conservatively exclude the entire current local date. This is a
regular NSE session convention, not a special-session calendar. Availability is
the actual download time, never the historical session date. New downloads
cannot support a historical decision made before their first availability.
News stores only the provider's headline and summary, without crawling links.
"""

import gzip
import hashlib
import io
import json
import sqlite3
import time
from datetime import date, datetime, time as day_time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import requests

from .schemas import Article, MarketObservation, utc

# ---------------------------------------------------------------------------
# Provider endpoints and limits
# ---------------------------------------------------------------------------

MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
API_URL = "https://api.upstox.com"
IST = ZoneInfo("Asia/Kolkata")
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_MASTER_BYTES = 256 * 1024 * 1024
HISTORICAL_START = date(2000, 1, 1)
HISTORICAL_END = date(2020, 12, 31)


# ---------------------------------------------------------------------------
# Live universe metadata (no network access)
# ---------------------------------------------------------------------------


def _universe_document(settings_or_root) -> dict:
    root = (
        Path(settings_or_root)
        if isinstance(settings_or_root, (str, Path))
        else Path(settings_or_root.root)
    )
    try:
        document = json.loads((root / "configs/live_universe.json").read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("instruments"), list):
            raise ValueError
        identifiers = set()
        for item in document["instruments"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("instrument_id"), str)
                or not item["instrument_id"].startswith("LIVE:NSE:")
                or item["instrument_id"] in identifiers
                or item.get("exchange") != "NSE"
                or item.get("market_family") not in {"equity", "benchmark"}
                or not all(
                    item.get(key)
                    for key in ("name", "trading_symbol", "currency", "unit", "source")
                )
            ):
                raise ValueError
            identifiers.add(item["instrument_id"])
        if not document.get("version") or not document.get("source"):
            raise ValueError
        return document
    except (OSError, ValueError, TypeError):
        raise ValueError("Cannot read a valid live universe configuration") from None


def get_live_universe(settings_or_root) -> list[dict]:
    """Read local selection metadata only; provider keys await explicit discovery.

    Accept a Settings object or project root. Each call returns fresh dictionaries
    and never writes files, initializes storage, or fetches provider data.
    """
    return _universe_document(settings_or_root)["instruments"]


# ---------------------------------------------------------------------------
# Bounded, paced HTTP reader
# ---------------------------------------------------------------------------


class _FetchError(ValueError):
    """A fixed diagnostic safe to include in the public report."""


class _Reader:
    def __init__(self, settings, report):
        self.settings = settings
        self.report = report
        self.last_request = None
        self.stopped = False

    def get(self, url, *, params=None, authenticated=True):
        if self.stopped:
            raise _FetchError("Requests stopped after provider authentication/rate-limit failure")
        if self.report["network_requests"] >= self.settings.max_requests:
            raise _FetchError("Live sync request budget exhausted")
        if self.last_request is not None:
            delay = self.settings.min_request_interval_seconds - (
                time.monotonic() - self.last_request
            )
            if delay > 0:
                time.sleep(delay)
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.settings.access_token.get_secret_value()
        self.last_request = time.monotonic()
        self.report["network_requests"] += 1
        size_limit = MAX_MASTER_BYTES if url == MASTER_URL else MAX_RESPONSE_BYTES
        try:
            with requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.settings.timeout_seconds,
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code in {401, 403, 429}:
                    self.stopped = True
                if response.status_code != 200:
                    raise _FetchError(
                        f"Provider HTTP {response.status_code}; response details omitted"
                    )
                content = bytearray()
                for block in response.iter_content(chunk_size=65536):
                    content.extend(block)
                    if len(content) > size_limit:
                        raise _FetchError("Provider response exceeds download size limit")
            if content[:2] == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                    content = compressed.read(size_limit + 1)
                if len(content) > size_limit:
                    raise _FetchError("Provider response exceeds decoded size limit")
            return json.loads(content)
        except requests.Timeout:
            raise _FetchError("Provider request timed out") from None
        except requests.RequestException:
            raise _FetchError("Provider request failed; diagnostic details omitted") from None
        except (ValueError, OSError, EOFError) as exc:
            if isinstance(exc, _FetchError):
                raise
            raise _FetchError("Provider returned malformed JSON/compressed data") from None


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _discover(instrument, master):
    family = instrument["market_family"]
    segment, kind = ("NSE_EQ", "EQ") if family == "equity" else ("NSE_INDEX", "INDEX")
    matches = [
        item
        for item in master
        if isinstance(item, dict)
        and item.get("segment") == segment
        and item.get("exchange") == "NSE"
        and item.get("instrument_type") == kind
        and item.get("trading_symbol") == instrument["trading_symbol"]
    ]
    if len(matches) != 1:
        raise _FetchError("Current instrument master has no unique matching instrument")
    key = matches[0].get("instrument_key")
    if (
        not isinstance(key, str)
        or not key.startswith(segment + "|")
        or len(key.split("|")) != 2
        or not key.split("|")[1].strip()
    ):
        raise _FetchError("Current instrument master returned an invalid instrument key")
    return {
        **instrument,
        "provider_instrument_key": key,
        "provider_name": matches[0].get("name"),
        "mapping_source": MASTER_URL,
    }


def _data(payload):
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "success"
        or not isinstance(payload.get("data"), dict)
    ):
        raise _FetchError("Provider returned an unsuccessful or malformed data response")
    return payload["data"]


def _news_article(item, fetched_at, existing):
    if not isinstance(item, dict):
        raise ValueError
    heading, summary, link = (item.get(key) for key in ("heading", "summary", "article_link"))
    if (
        not isinstance(heading, str)
        or not heading.strip()
        or not isinstance(summary, str)
        or not isinstance(link, str)
    ):
        raise ValueError
    parts = urlsplit(link)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError
    published_ms = item.get("published_time")
    if isinstance(published_ms, bool) or not isinstance(published_ms, (int, float)):
        raise ValueError
    published = datetime.fromtimestamp(published_ms / 1000, timezone.utc)
    if published > fetched_at:
        raise ValueError
    text = heading.strip() + ("\n\n" + summary.strip() if summary.strip() else "")
    fingerprint = hashlib.sha256(
        (" ".join(text.split()) + "\n" + published.isoformat()).encode()
    ).hexdigest()
    identifier = (
        "LIVE:NEWS:" + hashlib.sha256((link + "\n" + fingerprint).encode()).hexdigest()[:32]
    )
    if identifier in existing:
        return existing[identifier]
    versions = [article for article in existing.values() if article.source_url == link]
    predecessor = max(versions, key=lambda a: (a.first_seen_at, a.article_id)) if versions else None
    return Article(
        article_id=identifier,
        source_url=link,
        text=text,
        published_at=published,
        first_seen_at=fetched_at,
        source_version=fingerprint,
        predecessor_id=predecessor.article_id if predecessor else None,
    )


# ---------------------------------------------------------------------------
# Live sync: recent daily bars and news
# ---------------------------------------------------------------------------


def sync_live(dependencies, company_ids, lookback_days=550, include_news=True, now=None) -> dict:
    """Explicitly fetch selected equities, their benchmark and optional 7-day news.

    All requests are GETs to fixed official hosts. There are no automatic retries;
    request count, interval, timeout, response size and news pages are bounded.
    Identical observations preserve first availability; price revisions report
    conflicts. ``now`` injects an aware clock for deterministic offline tests.
    ``article_ids`` lists only news obtained by this invocation (including reused
    source versions), and ``decision_time`` follows all collected inputs.
    """

    def clock():
        return utc(now) if now is not None else datetime.now(timezone.utc)

    fetched_at = clock()
    report = {
        "provider": "upstox",
        "fetched_at": fetched_at.isoformat(),
        "requested_company_ids": [],
        "observations_added": 0,
        "articles_added": 0,
        "errors": [],
        "warnings": [
            "Historical downloads are available only from their first fetch; never backdate decision evidence.",
            "Daily bars use 15:30 IST regular-session labels; current local date is excluded conservatively.",
        ],
        "data_source": "imported_historical_data",
        "network_requests": 0,
        "universe": [],
        "article_ids": [],
        "decision_time": fetched_at.isoformat(),
    }

    def error(company_id, stage, message):
        report["errors"].append({"company_id": company_id, "stage": stage, "message": message})

    if (
        isinstance(company_ids, str)
        or not isinstance(company_ids, (list, tuple))
        or any(not isinstance(item, str) for item in company_ids)
    ):
        error(None, "validation", "company_ids must be a list of live instrument identifiers")
        return report
    report["requested_company_ids"] = list(dict.fromkeys(company_ids))
    if (
        isinstance(lookback_days, bool)
        or not isinstance(lookback_days, int)
        or not 1 <= lookback_days <= 3650
    ):
        error(None, "validation", "lookback_days must be an integer between 1 and 3650")
        return report
    try:
        document = _universe_document(dependencies.settings)
    except ValueError:
        error(None, "configuration", "Cannot read a valid live universe configuration")
        return report
    report.update(universe_version=document["version"], universe_source=document["source"])
    universe = {item["instrument_id"]: item for item in document["instruments"]}
    selected = []
    for identifier in report["requested_company_ids"]:
        if identifier not in universe or universe[identifier]["market_family"] != "equity":
            error(identifier, "validation", "Unknown live equity identifier")
        else:
            selected.append(identifier)
    if not selected:
        return report
    settings = dependencies.settings.live_data
    if not settings.access_token.get_secret_value().strip():
        error(
            None,
            "configuration",
            "Configure UPSTOX_ANALYTICS_TOKEN or UPSTOX_ACCESS_TOKEN before sync",
        )
        return report
    reader = _Reader(settings, report)
    try:
        master = reader.get(MASTER_URL, authenticated=False)
        if not isinstance(master, list):
            raise _FetchError("Provider instrument master must be a JSON list")
    except _FetchError as exc:
        error(None, "instrument_master", str(exc))
        return report
    targets = list(
        dict.fromkeys(
            selected
            + [
                universe[key].get("benchmark_id")
                for key in selected
                if universe[key].get("benchmark_id")
            ]
        )
    )
    resolved = {}
    for identifier in targets:
        try:
            resolved[identifier] = _discover(universe[identifier], master)
            report["universe"].append(resolved[identifier])
        except (KeyError, _FetchError):
            error(
                identifier,
                "instrument_master",
                "Current instrument master has no unique valid mapping",
            )
    store = dependencies.storage
    observations = {item.observation_id: item for item in store.list_observations()}
    articles = {item.article_id: item for item in store.list_articles()}
    today = fetched_at.astimezone(IST).date()
    start, end = today - timedelta(days=lookback_days), today - timedelta(days=1)
    for identifier, instrument in resolved.items():
        key = quote(instrument["provider_instrument_key"], safe="")
        try:
            data = _data(reader.get(f"{API_URL}/v3/historical-candle/{key}/days/1/{end}/{start}"))
            received = clock()
            candles = data.get("candles")
            if not isinstance(candles, list):
                raise _FetchError("Provider candle response must contain a candles list")
        except _FetchError as exc:
            error(identifier, "prices", str(exc))
            continue
        for candle in candles:
            try:
                if (
                    not isinstance(candle, list)
                    or len(candle) < 6
                    or not isinstance(candle[0], str)
                ):
                    raise ValueError
                session = (
                    utc(datetime.fromisoformat(candle[0].replace("Z", "+00:00")))
                    .astimezone(IST)
                    .date()
                )
                if session >= today or session < start:
                    continue
                close_time = datetime.combine(session, day_time(15, 30), IST)
                observation = MarketObservation(
                    instrument_id=identifier,
                    market_family=instrument["market_family"],
                    timestamp=close_time,
                    available_at=received,
                    open=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=candle[5],
                    currency=instrument["currency"],
                    unit=instrument["unit"],
                )
                old = observations.get(observation.observation_id)
                if old:
                    observation.available_at = old.available_at
                    if observation != old:
                        error(
                            identifier,
                            "prices",
                            f"Conflicting immutable daily bar for {session}; first saved version retained",
                        )
                        continue
                report["observations_added"] += store.add_observations([observation])
                observations[observation.observation_id] = observation
            except (ValueError, TypeError, OverflowError, sqlite3.Error):
                error(
                    identifier,
                    "prices",
                    "Invalid or conflicting daily candle; saved observations retained",
                )
    if include_news:
        report["warnings"].append(
            "News is provider headline/summary only, limited to the past seven days and bounded pages."
        )
        for identifier in selected:
            if identifier not in resolved:
                continue
            for page in range(1, settings.news_max_pages + 1):
                try:
                    payload = reader.get(
                        f"{API_URL}/v2/news",
                        params={
                            "category": "instrument_keys",
                            "instrument_keys": resolved[identifier]["provider_instrument_key"],
                            "page_number": page,
                            "page_size": 100,
                        },
                    )
                    received = clock()
                    data = _data(payload)
                    items = data.get(resolved[identifier]["provider_instrument_key"], [])
                    if not isinstance(items, list):
                        raise _FetchError("Provider news response must contain an article list")
                except _FetchError as exc:
                    error(identifier, "news", str(exc))
                    break
                for item in items:
                    try:
                        article = _news_article(item, received, articles)
                        report["articles_added"] += store.add_articles([article])
                        articles[article.article_id] = article
                        if article.article_id not in report["article_ids"]:
                            report["article_ids"].append(article.article_id)
                    except (ValueError, TypeError, OverflowError, OSError, sqlite3.Error):
                        error(
                            identifier,
                            "news",
                            "Invalid or conflicting news item; saved sources retained",
                        )
                metadata = payload.get("metadata")
                pagination = metadata.get("page") if isinstance(metadata, dict) else None
                pagination = pagination if isinstance(pagination, dict) else {}
                total_pages = pagination.get("total_pages")
                if not items or (isinstance(total_pages, int) and page >= total_pages):
                    break
                if total_pages is None and len(items) < 100:
                    break
                if page == settings.news_max_pages:
                    report["warnings"].append(
                        f"News pagination limit reached for {identifier}; more articles may exist."
                    )
    completed = clock().isoformat()
    report.update(fetched_at=completed, decision_time=completed)
    return report


# ---------------------------------------------------------------------------
# Historical research download (ending 2020)
# ---------------------------------------------------------------------------


def sync_historical(
    dependencies,
    company_ids,
    start_date=date(2015, 1, 1),
    end_date=date(2020, 12, 31),
    now=None,
) -> dict:
    """Explicit daily research download ENDING in 2020, including benchmarks.

    Use only V3 daily candles, available from January 2000 with a ten-year
    request limit. Calendar-year chunks never exceed that limit. All requests
    share the live adapter's budget, pacing, size/timeout limits and fail-stop
    behavior; no news, retries, model calls or fallback data are requested.

    Coverage counts only persisted/identical bars accepted by this invocation,
    not preexisting cached history. Extrema do not guarantee gap-free sessions.
    Availability is response receipt time, retaining the first saved timestamp
    for identical observations. ``now`` must be aware and is for offline tests.
    """

    def clock():
        return utc(now) if now is not None else datetime.now(timezone.utc)

    fetched_at = clock()
    report = {
        "provider": "upstox",
        "fetched_at": fetched_at.isoformat(),
        "decision_time": fetched_at.isoformat(),
        "requested_company_ids": [],
        "requested_start": start_date.isoformat() if type(start_date) is date else None,
        "requested_end": end_date.isoformat() if type(end_date) is date else None,
        "actual_start": None,
        "actual_end": None,
        "coverage": {},
        "observations_added": 0,
        "articles_added": 0,
        "article_ids": [],
        "network_requests": 0,
        "universe": [],
        "data_source": "imported_historical_data",
        "errors": [],
        "warnings": [
            "History ends no later than 2020-12-31; availability is actual fetch time, never backdated.",
            "Daily bars use 15:30 IST regular-session labels, not a special-session calendar.",
            "Coverage is accepted download extrema, not proof of gap-free history or listing dates.",
            "Current instrument mappings may omit delisted securities; OHLC adjustment is not verified.",
        ],
    }

    def error(identifier, stage, message):
        report["errors"].append({"company_id": identifier, "stage": stage, "message": message})

    if (
        type(start_date) is not date
        or type(end_date) is not date
        or not HISTORICAL_START <= start_date <= end_date <= HISTORICAL_END
        or end_date >= fetched_at.astimezone(IST).date()
    ):
        error(
            None,
            "validation",
            "Dates must be date objects with 2000-01-01 <= start_date <= end_date <= "
            "2020-12-31, ending before the current IST date",
        )
        return report
    if not isinstance(company_ids, (list, tuple)) or any(
        not isinstance(item, str) for item in company_ids
    ):
        error(None, "validation", "company_ids must be a list of live instrument identifiers")
        return report
    report["requested_company_ids"] = list(dict.fromkeys(company_ids))
    try:
        document = _universe_document(dependencies.settings)
    except ValueError:
        error(None, "configuration", "Cannot read a valid live universe configuration")
        return report
    report.update(universe_version=document["version"], universe_source=document["source"])
    universe = {item["instrument_id"]: item for item in document["instruments"]}
    selected = []
    for identifier in report["requested_company_ids"]:
        if identifier not in universe or universe[identifier]["market_family"] != "equity":
            error(identifier, "validation", "Unknown live equity identifier")
        else:
            selected.append(identifier)
    if not selected:
        if not report["errors"]:
            error(None, "validation", "Select at least one live equity identifier")
        return report

    chunks = []
    first = start_date
    while first <= end_date:
        last = min(end_date, date(first.year + 9, 12, 31))
        chunks.append((first, last))
        first = last + timedelta(days=1)
    targets = list(
        dict.fromkeys(
            selected
            + [
                universe[key]["benchmark_id"]
                for key in selected
                if universe[key].get("benchmark_id")
            ]
        )
    )
    for identifier in targets:
        report["coverage"][identifier] = {
            "actual_start": None,
            "actual_end": None,
            "bars": 0,
            "chunks_planned": len(chunks),
            "chunks_requested": 0,
            "chunks_completed": 0,
        }
    settings = dependencies.settings.live_data
    if not settings.access_token.get_secret_value().strip():
        error(None, "configuration", "Configure an Upstox access token before sync")
        return report
    reader = _Reader(settings, report)
    try:
        master = reader.get(MASTER_URL, authenticated=False)
        if not isinstance(master, list):
            raise _FetchError("Provider instrument master must be a JSON list")
    except _FetchError as exc:
        error(None, "instrument_master", str(exc))
        return report

    store = dependencies.storage
    observations = {item.observation_id: item for item in store.list_observations()}
    for identifier in targets:
        coverage = report["coverage"][identifier]
        try:
            instrument = _discover(universe[identifier], master)
        except (KeyError, _FetchError):
            error(
                identifier,
                "instrument_master",
                "Current instrument master has no unique valid mapping",
            )
            continue
        report["universe"].append(instrument)
        key = quote(instrument["provider_instrument_key"], safe="")
        accepted = set()
        for first, last in chunks:
            before_requests = report["network_requests"]
            try:
                payload = reader.get(f"{API_URL}/v3/historical-candle/{key}/days/1/{last}/{first}")
                received = clock()
                candles = _data(payload).get("candles")
                if not isinstance(candles, list):
                    raise _FetchError("Provider candle response must contain a candles list")
                coverage["chunks_completed"] += 1
            except _FetchError as exc:
                error(identifier, "prices", f"{first} through {last}: {exc}")
                # A budget/auth stop applies to every remaining chunk. Later
                # instruments still receive an explicit diagnostic without GETs.
                if reader.stopped or report["network_requests"] >= settings.max_requests:
                    break
                continue
            finally:
                coverage["chunks_requested"] += report["network_requests"] - before_requests
            chunk_accepted = False
            for candle in candles:
                try:
                    if (
                        not isinstance(candle, list)
                        or len(candle) < 6
                        or not isinstance(candle[0], str)
                        or any(isinstance(value, bool) for value in candle[1:6])
                    ):
                        raise ValueError
                    session = (
                        utc(datetime.fromisoformat(candle[0].replace("Z", "+00:00")))
                        .astimezone(IST)
                        .date()
                    )
                    if not first <= session <= last:
                        continue
                    observation = MarketObservation(
                        instrument_id=identifier,
                        market_family=instrument["market_family"],
                        timestamp=datetime.combine(session, day_time(15, 30), IST),
                        available_at=received,
                        open=candle[1],
                        high=candle[2],
                        low=candle[3],
                        close=candle[4],
                        volume=candle[5],
                        currency=instrument["currency"],
                        unit=instrument["unit"],
                    )
                    old = observations.get(observation.observation_id)
                    if old:
                        observation.available_at = old.available_at
                        if observation != old:
                            error(
                                identifier,
                                "prices",
                                f"Conflicting immutable daily bar for {session}; first saved version retained",
                            )
                            continue
                    report["observations_added"] += store.add_observations([observation])
                    observations[observation.observation_id] = observation
                    accepted.add(session)
                    chunk_accepted = True
                except (ValueError, TypeError, OverflowError, sqlite3.Error):
                    error(
                        identifier,
                        "prices",
                        "Invalid or conflicting daily candle; saved observations retained",
                    )
            if not chunk_accepted:
                error(
                    identifier,
                    "prices",
                    f"No accepted historical candles for {first} through {last}",
                )
        if accepted:
            coverage.update(
                actual_start=min(accepted).isoformat(),
                actual_end=max(accepted).isoformat(),
                bars=len(accepted),
            )

    populated = [item for item in report["coverage"].values() if item["bars"]]
    if populated:
        report["actual_start"] = min(item["actual_start"] for item in populated)
        report["actual_end"] = max(item["actual_end"] for item in populated)
    completed = clock().isoformat()
    report.update(fetched_at=completed, decision_time=completed)
    return report
