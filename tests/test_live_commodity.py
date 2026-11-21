"""Offline tests for live cross-market readiness: MCX near-month crude and reviewed rules.

Every provider record, key and credential here is fictional. HTTP is mocked; any
unexpected request fails the test. No real network call is ever made.
"""

import gzip
import json
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr

from market_events import live_data
from market_events.config import Settings, read_exposure_review, read_exposure_rules
from market_events.market_features import compute_market_features
from market_events.pipeline import Dependencies, analyse_article, readiness
from market_events.schemas import Article, ExposureRule, MarketObservation
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 25, 6, tzinfo=timezone.utc)  # 11:30 IST, 25 Nov 2026
TOKEN = "mock-token-never-valid"
CRUDE = "LIVE:MCX:CRUDEOIL"
NEAR = "MCX_FO|FICTIONAL-DEC"
NEXT = "MCX_FO|FICTIONAL-JAN"
EQUITY_KEYS = {"ASIANPAINT": "NSE_EQ|TEST-ASIAN", "RELIANCE": "NSE_EQ|TEST-REL"}
INDEX_KEY = "NSE_INDEX|Nifty 50"


def epoch_ms(day):
    return int(datetime.combine(day, datetime.min.time(), IST).timestamp() * 1000)


def nse_master():
    rows = [
        {
            "segment": "NSE_EQ",
            "exchange": "NSE",
            "instrument_type": "EQ",
            "trading_symbol": s,
            "name": s,
            "instrument_key": k,
        }
        for s, k in EQUITY_KEYS.items()
    ]
    rows.append(
        {
            "segment": "NSE_INDEX",
            "exchange": "NSE",
            "instrument_type": "INDEX",
            "trading_symbol": "Nifty 50",
            "name": "Nifty 50",
            "instrument_key": INDEX_KEY,
        }
    )
    return rows


def future(key, expiry, *, underlying="CRUDEOIL", kind="FUT", symbol=None):
    return {
        "segment": "MCX_FO",
        "exchange": "MCX",
        "instrument_type": kind,
        "underlying_symbol": underlying,
        "trading_symbol": symbol or f"{underlying} {kind} {expiry}",
        "name": "CRUDE OIL",
        "instrument_key": key,
        "expiry": expiry,
    }


def mcx_master():
    return [
        future("MCX_FO|FICTIONAL-NOV", epoch_ms(date(2026, 11, 18))),  # expired
        future(NEAR, epoch_ms(date(2026, 12, 17))),  # near month
        future(NEXT, "2027-01-19"),  # ISO expiry form
        future("MCX_FO|FICTIONAL-OPT", epoch_ms(date(2026, 12, 10)), kind="CE"),
        future("MCX_FO|FICTIONAL-GAS", epoch_ms(date(2026, 12, 1)), underlying="NATURALGAS"),
    ]


class Response:
    def __init__(self, payload, compressed=False):
        self.content = json.dumps(payload).encode()
        if compressed:
            self.content = gzip.compress(self.content)
        self.status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def iter_content(self, chunk_size):
        yield self.content


def candle(day, close):
    return [f"{day}T00:00:00+05:30", close, close + 1, close - 1, close, 1000, 0]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Unexpected network request in offline test")

    monkeypatch.setattr(live_data.requests, "get", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(live_data.time, "sleep", lambda delay: None)


@pytest.fixture
def deps(tmp_path):
    settings = Settings(root=ROOT, universe="live", mode="live")
    settings.live_data.access_token = SecretStr(TOKEN)
    with Storage(tmp_path / "live.sqlite") as store:
        yield SimpleNamespace(settings=settings, storage=store)


def provider(monkeypatch, master=mcx_master):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == live_data.MASTER_URL:
            return Response(nse_master(), compressed=True)
        if url == live_data.MCX_MASTER_URL:
            return Response(master(), compressed=True)
        if "/historical-candle/" in url:
            close = 6000 if "MCX_FO" in url else 100
            return Response(
                {"status": "success", "data": {"candles": [candle("2026-11-24", close)]}}
            )
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(live_data.requests, "get", get)
    return calls


def test_live_universe_and_reviewed_rules_are_explicit_and_sourced():
    settings = Settings(root=ROOT, universe="live")
    crude = next(i for i in live_data.get_live_universe(settings) if i["instrument_id"] == CRUDE)
    assert crude["exchange"] == "MCX" and crude["market_family"] == "commodity"
    assert crude["contract_selection"] == "near_month" and crude["provider_instrument_key"] is None
    rules = [ExposureRule.model_validate(r) for r in read_exposure_rules(settings)]
    assert {r.company_id for r in rules} == {
        "LIVE:NSE:ASIANPAINT",
        "LIVE:NSE:BERGEPAINT",
        "LIVE:NSE:INDIGO",
    }
    for rule in rules:
        assert rule.commodity_id == CRUDE and rule.direction == -1
        assert rule.known_at == datetime(2026, 11, 21, tzinfo=timezone.utc)
        assert rule.source.startswith("[S] Secondary press source")
        assert "not empirically validated" in rule.source
        assert "%" not in rule.source + rule.relationship  # no unverified cost-share figures
    review = {item["company_id"]: item for item in read_exposure_review(settings)}
    assert "LIVE:NSE:RELIANCE" in review and "ambiguous" in review["LIVE:NSE:RELIANCE"]["reason"]
    # Synthetic demo rules stay separate.
    demo = read_exposure_rules(Settings(root=ROOT, universe="demo"))
    assert all(not r["company_id"].startswith("LIVE:") for r in demo)
    assert read_exposure_review(Settings(root=ROOT, universe="demo")) == []


def test_near_month_is_the_earliest_unexpired_future_on_the_configured_underlying():
    crude = next(i for i in live_data.get_live_universe(ROOT) if i["instrument_id"] == CRUDE)
    contract = live_data._discover_contract(crude, mcx_master(), date(2026, 11, 25))
    assert contract["contract_id"] == contract["provider_instrument_key"] == NEAR
    assert contract["contract_expiry"] == "2026-12-17"
    assert contract["mapping_source"] == live_data.MCX_MASTER_URL
    # After the December expiry the next contract is chosen explicitly (ISO expiry form).
    later = live_data._discover_contract(crude, mcx_master(), date(2026, 12, 18))
    assert later["contract_id"] == NEXT
    tie = mcx_master() + [future("MCX_FO|FICTIONAL-DUP", epoch_ms(date(2026, 12, 17)))]
    with pytest.raises(live_data._FetchError, match="several near-month"):
        live_data._discover_contract(crude, tie, date(2026, 11, 25))
    with pytest.raises(live_data._FetchError, match="no unexpired future"):
        live_data._discover_contract(crude, mcx_master(), date(2027, 2, 1))
    bad = [future("NSE_FO|WRONG", epoch_ms(date(2026, 12, 17)))]
    with pytest.raises(live_data._FetchError, match="invalid instrument key"):
        live_data._discover_contract(crude, bad, date(2026, 11, 25))


def test_sync_fetches_linked_crude_contract_with_contract_id_and_late_close(deps, monkeypatch):
    calls = provider(monkeypatch)
    report = live_data.sync_live(deps, ["LIVE:NSE:ASIANPAINT"], 30, include_news=False, now=NOW)
    assert report["errors"] == []
    urls = [url for url, _ in calls]
    assert urls[:2] == [live_data.MASTER_URL, live_data.MCX_MASTER_URL]
    assert sum("/historical-candle/" in url for url in urls) == 3  # equity, index, crude
    for url, kwargs in calls:
        authenticated = "Authorization" in kwargs["headers"]
        assert authenticated == ("/historical-candle/" in url)
    contract = next(item for item in report["universe"] if item["instrument_id"] == CRUDE)
    assert contract["contract_id"] == NEAR and contract["contract_expiry"] == "2026-12-17"
    crude = [o for o in deps.storage.list_observations() if o.instrument_id == CRUDE]
    assert len(crude) == 1
    bar = crude[0]
    assert bar.market_family == "commodity" and bar.contract_id == NEAR and bar.unit == "barrel"
    assert bar.timestamp.astimezone(IST) == datetime(2026, 11, 24, 23, 55, tzinfo=IST)
    assert bar.available_at == NOW
    assert any("near-month future" in warning for warning in report["warnings"])
    assert TOKEN not in json.dumps(report)


def test_unlinked_or_opted_out_companies_never_request_the_mcx_master(deps, monkeypatch):
    calls = provider(monkeypatch)
    live_data.sync_live(deps, ["LIVE:NSE:RELIANCE"], 30, include_news=False, now=NOW)
    assert live_data.MCX_MASTER_URL not in [url for url, _ in calls]
    calls.clear()
    live_data.sync_live(
        deps, ["LIVE:NSE:ASIANPAINT"], 30, include_news=False, now=NOW, include_commodities=False
    )
    assert live_data.MCX_MASTER_URL not in [url for url, _ in calls]
    assert not any(o.instrument_id == CRUDE for o in deps.storage.list_observations())


def test_contract_roll_is_reported_and_returns_across_it_fail_closed(deps, monkeypatch):
    old = MarketObservation(
        instrument_id=CRUDE,
        market_family="commodity",
        timestamp=datetime(2026, 11, 23, 23, 55, tzinfo=IST),
        available_at=NOW - timedelta(days=1),
        open=5900,
        high=5901,
        low=5899,
        close=5900,
        volume=10,
        currency="INR",
        unit="barrel",
        contract_id="MCX_FO|FICTIONAL-NOV",
    )
    deps.storage.add_observations([old])
    provider(monkeypatch)
    report = live_data.sync_live(deps, ["LIVE:NSE:ASIANPAINT"], 30, include_news=False, now=NOW)
    assert any("earlier bars use MCX_FO|FICTIONAL-NOV" in w for w in report["warnings"])
    features = compute_market_features(deps.storage.list_observations(), NOW, commodity_id=CRUDE)
    assert features.values["commodity_return"] is None  # never spliced across contracts


def test_mcx_master_failure_is_reported_without_dropping_equity_bars(deps, monkeypatch):
    def broken():
        return {"not": "a list"}

    provider(monkeypatch, master=broken)
    report = live_data.sync_live(deps, ["LIVE:NSE:ASIANPAINT"], 30, include_news=False, now=NOW)
    assert [e["stage"] for e in report["errors"]] == ["instrument_master"]
    assert report["errors"][0]["company_id"] == CRUDE
    stored = {o.instrument_id for o in deps.storage.list_observations()}
    assert stored == {"LIVE:NSE:ASIANPAINT", "LIVE:NSE:NIFTY50"}


def bars(instrument, family, closes, close_time, unit, contract=None):
    rows = []
    for day, close in closes:
        stamp = datetime.combine(day, close_time, IST)
        rows.append(
            MarketObservation(
                instrument_id=instrument,
                market_family=family,
                timestamp=stamp,
                available_at=stamp + timedelta(minutes=10),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000,
                currency="INR",
                unit=unit,
                contract_id=contract,
            )
        )
    return rows


class Client:
    """Fake model client: returns fixed structured answers, records no calls."""

    def __init__(self, company, text):
        self.calls, self.run_id, self.company, self.text = [], None, company, text

    def ask(self, task, article, schema, role="llm", context=None):
        return schema.model_validate(
            {
                "relevance": "relevant",
                "event_type": "commodity_supply_disruption",
                "candidate_entities": [self.company],
                "source_spans": [self.text],
                "reason": "fixture",
            }
            if task == "filter"
            else {
                "event_id": "e",
                "event_type": "commodity_supply_disruption",
                "company_id": None,
                "candidate_entities": [self.company],
                "commodity_id": "MCX:CRUDEOIL",
                "direction": "negative",
                "source_spans": [self.text],
                "reason": "fixture",
            }
        )


@pytest.mark.parametrize(
    "company,name,expected",
    [
        ("LIVE:NSE:ASIANPAINT", "Asian Paints", "negative"),
        ("LIVE:NSE:RELIANCE", "Reliance Industries", "abstain"),
    ],
)
def test_live_crude_event_uses_reviewed_rule_or_abstains_when_sign_is_ambiguous(
    tmp_path, company, name, expected
):
    settings = Settings(root=ROOT, universe="live", mode="live")
    days = [date(2026, 12, 1), date(2026, 12, 2)]
    text = f"{name} faces higher input costs after a crude oil supply disruption."
    cutoff = datetime(2026, 12, 3, 4, tzinfo=timezone.utc)
    with Storage(tmp_path / "live.sqlite") as storage:
        storage.add_observations(
            bars(
                company,
                "equity",
                zip(days, [100, 99.4]),
                datetime.min.time().replace(hour=15, minute=30),
                "share",
            )
            + bars(
                "LIVE:NSE:NIFTY50",
                "benchmark",
                zip(days, [100, 100.2]),
                datetime.min.time().replace(hour=15, minute=30),
                "index_point",
            )
            + bars(
                CRUDE,
                "commodity",
                zip(days, [6000, 6090]),
                datetime.min.time().replace(hour=23, minute=55),
                "barrel",
                NEAR,
            )
        )
        storage.add_articles(
            [
                Article(
                    article_id="LIVE:NEWS:fictional-crude",
                    source_url="https://example.invalid/live-crude",
                    text=text,
                    published_at=datetime(2026, 12, 2, 12, tzinfo=timezone.utc),
                    first_seen_at=datetime(2026, 12, 2, 12, tzinfo=timezone.utc),
                )
            ]
        )
        deps = Dependencies(storage, settings, client=Client(name, text))
        run = analyse_article("LIVE:NEWS:fictional-crude", cutoff, "slm_delegate", deps)
    assert run.extraction.commodity_id == CRUDE
    assert "mapped to live instrument LIVE:MCX:CRUDEOIL" in run.extraction.reason
    assert run.features.values["commodity_return"] == pytest.approx(0.015)
    assert run.assessment.direction == expected
    if expected == "negative":
        assert run.exposure.status == "matched"
        assert run.exposure.rule.rule_id == "live-crude-asianpaint"
        assert run.assessment.inputs["components"]["commodity"] == pytest.approx(-0.5)
    else:
        assert run.exposure.status == "missing"
        assert (
            "Missing or ambiguous mandatory reviewed exposure" in run.assessment.abstention_reasons
        )


def test_rules_known_on_review_date_cannot_support_an_earlier_decision(tmp_path):
    settings = Settings(root=ROOT, universe="live")
    rules = [ExposureRule.model_validate(r) for r in read_exposure_rules(settings)]
    from market_events.exposure import find_exposure
    from market_events.schemas import EventExtraction

    event = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id="LIVE:NSE:ASIANPAINT",
        commodity_id=CRUDE,
    )
    before = find_exposure(event, rules, datetime(2026, 11, 20, tzinfo=timezone.utc))
    after = find_exposure(event, rules, datetime(2026, 11, 22, tzinfo=timezone.utc))
    assert before.status == "missing" and after.status == "matched"


def test_readiness_reports_commodity_coverage_offline_and_without_the_token(tmp_path):
    settings = Settings(root=ROOT, universe="live", mode="live")
    settings.live_data.access_token = SecretStr(TOKEN)
    with Storage(tmp_path / "live.sqlite") as storage:
        deps = Dependencies(storage, settings)
        row = next(r for r in readiness(deps) if r["capability"] == "commodity_prices")
        assert row["configured"] and not row["ready"]
        assert CRUDE in row["reason"] and "LIVE:NSE:RELIANCE" in row["reason"]
        storage.add_observations(
            bars(
                CRUDE,
                "commodity",
                [(date(2026, 11, 16), 6000)],  # in the past: readiness uses the real clock
                datetime.min.time().replace(hour=23, minute=55),
                "barrel",
                NEAR,
            )
        )
        row = next(r for r in readiness(deps) if r["capability"] == "commodity_prices")
        assert row["ready"] and NEAR in row["reason"]
        assert TOKEN not in json.dumps(readiness(deps))
        settings.universe = "demo"
        demo = next(r for r in readiness(deps) if r["capability"] == "commodity_prices")
        assert demo["configured"] and not demo["ready"]  # synthetic rules, no synthetic bars here
