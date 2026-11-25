"""Offline adapter tests. All provider records and credentials here are fictional."""

import gzip
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from pydantic import SecretStr

from market_events import live_data
from market_events.config import Settings
from market_events.market_features import compute_market_features
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
COMPANY = "LIVE:NSE:ASIANPAINT"
BENCHMARK = "LIVE:NSE:NIFTY50"
EQUITY_KEY = "NSE_EQ|FICTIONAL_TEST_KEY"
INDEX_KEY = "NSE_INDEX|Nifty 50"
TOKEN = "mock-token-never-valid"


def master():
    return [
        {
            "segment": "NSE_EQ",
            "exchange": "NSE",
            "instrument_type": "EQ",
            "trading_symbol": "ASIANPAINT",
            "name": "Fictional test company",
            "instrument_key": EQUITY_KEY,
        },
        {
            "segment": "NSE_INDEX",
            "exchange": "NSE",
            "instrument_type": "INDEX",
            "trading_symbol": "NIFTY",
            "name": "Fictional test benchmark",
            "instrument_key": INDEX_KEY,
        },
    ]


def candle(date="2026-10-23", close=105):
    return [f"{date}T00:00:00+05:30", 100, 110, 90, close, 1000, 0]


def news(**changes):
    return {
        "heading": "Asian Paints publishes earnings",
        "summary": "Fictional provider summary for offline validation.",
        "article_link": "https://example.invalid/live-test-news",
        "published_time": int((NOW - timedelta(hours=1)).timestamp() * 1000),
        **changes,
    }


class Response:
    def __init__(self, payload, status=200, *, compressed=False):
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        if compressed:
            self.content = gzip.compress(self.content)
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def iter_content(self, chunk_size):
        yield self.content


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Unexpected network request in offline test")

    monkeypatch.setattr(live_data.requests, "get", reject)
    monkeypatch.setattr(live_data.time, "sleep", lambda delay: None)


@pytest.fixture
def deps(tmp_path):
    # Real live universe, but no reviewed exposure rules: these tests cover the
    # equity/benchmark/news adapter. Linked-commodity sync is tested separately.
    root = tmp_path / "root"
    shutil.copytree(ROOT / "configs", root / "configs")
    (root / "configs/live_exposure_rules.json").unlink()
    settings = Settings(root=root, universe="live", mode="live")
    settings.live_data.access_token = SecretStr(TOKEN)
    with Storage(tmp_path / "live.sqlite") as store:
        yield SimpleNamespace(settings=settings, storage=store)


def provider(
    monkeypatch, *, instruments=None, candles=None, news_items=None, metadata=..., fail=None
):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if fail:
            result = fail(url, kwargs)
            if result is not None:
                return result
        if url == live_data.MASTER_URL:
            return Response(master() if instruments is None else instruments, compressed=True)
        if "/historical-candle/" in url:
            rows = [candle()] if candles is None else candles
            return Response({"status": "success", "data": {"candles": rows}})
        assert url == live_data.API_URL + "/v2/news"
        page = kwargs["params"]["page_number"]
        items = [news()] if news_items is None else news_items
        if callable(items):
            items = items(page)
        return Response(
            {
                "status": "success",
                "data": {EQUITY_KEY: items},
                "metadata": {"page": {"total_pages": 1}} if metadata is ... else metadata,
            }
        )

    monkeypatch.setattr(live_data.requests, "get", get)
    return calls


def test_metadata_is_offline_separate_and_returns_fresh_records():
    settings = Settings(root=ROOT)
    first = live_data.get_live_universe(settings)
    assert len(first) == 7
    assert sum(item["market_family"] == "equity" for item in first) == 5
    commodities = [item for item in first if item["market_family"] == "commodity"]
    assert [item["instrument_id"] for item in commodities] == ["LIVE:MCX:CRUDEOIL"]
    assert commodities[0]["contract_selection"] == "near_month"
    assert all(
        item["instrument_id"].startswith("LIVE:NSE:") for item in first if item not in commodities
    )
    assert all(item["provider_instrument_key"] is None for item in first)
    first[0]["name"] = "Changed caller copy"
    assert live_data.get_live_universe(ROOT)[0]["name"] != "Changed caller copy"


def test_sync_resolves_current_master_normalizes_eod_and_returns_stable_contract(deps, monkeypatch):
    calls = provider(monkeypatch, candles=[candle(), candle("2026-10-24"), candle("2026-10-25")])
    report = live_data.sync_live(deps, [COMPANY, COMPANY], now=NOW)
    assert report["requested_company_ids"] == [COMPANY]
    assert report["observations_added"] == 2
    assert report["articles_added"] == 1
    assert report["errors"] == []
    assert report["network_requests"] == len(calls) == 4
    assert report["data_source"] == "imported_historical_data"
    assert report["universe_version"] == "live-nse-mcx-v2"
    assert {item["provider_instrument_key"] for item in report["universe"]} == {
        EQUITY_KEY,
        INDEX_KEY,
    }
    assert set(report) >= {
        "provider",
        "fetched_at",
        "requested_company_ids",
        "observations_added",
        "articles_added",
        "errors",
        "warnings",
        "data_source",
        "network_requests",
        "universe",
        "article_ids",
        "decision_time",
    }
    rows = deps.storage.list_observations()
    assert {row.instrument_id for row in rows} == {COMPANY, BENCHMARK}
    assert all(row.timestamp == datetime(2026, 10, 23, 10, tzinfo=timezone.utc) for row in rows)
    assert all(row.available_at == NOW for row in rows)
    assert report["article_ids"][0].startswith("LIVE:NEWS:")
    article = deps.storage.get_article(report["article_ids"][0])
    assert article.first_seen_at == NOW
    assert article.published_at == NOW - timedelta(hours=1)
    assert datetime.fromisoformat(report["decision_time"]) >= article.first_seen_at
    assert deps.storage.list_runs() == []
    assert any("NSE_EQ%7CFICTIONAL_TEST_KEY/days/1/2026-10-23/" in url for url, _ in calls)
    assert "Authorization" not in calls[0][1]["headers"]
    for _, kwargs in calls:
        assert kwargs["timeout"] == 20
        assert kwargs["allow_redirects"] is False
    assert TOKEN not in json.dumps(report)
    assert TOKEN not in json.dumps(deps.settings.snapshot())


def test_repeat_sync_reuses_first_availability_and_first_seen(deps, monkeypatch):
    provider(monkeypatch)
    first = live_data.sync_live(deps, [COMPANY], now=NOW)
    original_rows = deps.storage.list_observations()
    original_article = deps.storage.get_article(first["article_ids"][0])
    second = live_data.sync_live(deps, [COMPANY], now=NOW + timedelta(days=1))
    assert second["observations_added"] == second["articles_added"] == 0
    assert second["errors"] == []
    assert second["article_ids"] == first["article_ids"]
    assert deps.storage.list_observations() == original_rows
    assert deps.storage.get_article(first["article_ids"][0]) == original_article


def test_price_revisions_report_conflict_without_overwriting(deps, monkeypatch):
    provider(monkeypatch)
    live_data.sync_live(deps, [COMPANY], include_news=False, now=NOW)
    before = deps.storage.list_observations()
    provider(monkeypatch, candles=[candle(close=106)])
    report = live_data.sync_live(deps, [COMPANY], include_news=False, now=NOW + timedelta(days=1))
    assert report["observations_added"] == 0
    assert len(report["errors"]) == 2
    assert all("Conflicting immutable" in error["message"] for error in report["errors"])
    assert deps.storage.list_observations() == before


def test_changed_news_appends_version_linked_to_original(deps, monkeypatch):
    provider(monkeypatch)
    first = live_data.sync_live(deps, [COMPANY], now=NOW)
    original = deps.storage.get_article(first["article_ids"][0])
    provider(monkeypatch, news_items=[news(summary="Corrected provider summary.")])
    second = live_data.sync_live(deps, [COMPANY], now=NOW + timedelta(hours=1))
    corrected = deps.storage.get_article(second["article_ids"][0])
    assert second["articles_added"] == 1
    assert corrected.predecessor_id == original.article_id
    assert corrected.source_version != original.source_version
    assert deps.storage.get_article(original.article_id) == original


def test_downloaded_history_is_ineligible_before_fetch(deps, monkeypatch):
    provider(monkeypatch, candles=[candle("2026-10-22"), candle()])
    live_data.sync_live(deps, [COMPANY], include_news=False, now=NOW)
    features = compute_market_features(
        deps.storage.list_observations(),
        NOW - timedelta(minutes=1),
        company_id=COMPANY,
        benchmark_id=BENCHMARK,
    )
    assert features.observation_ids == []
    assert features.values.get("equity_return") is None


@pytest.mark.parametrize(
    "instruments", [[], master() + [master()[0]], [{**master()[0], "segment": "BSE_EQ"}]]
)
def test_missing_ambiguous_wrong_segment_mappings_never_guess_keys(deps, monkeypatch, instruments):
    calls = provider(monkeypatch, instruments=instruments)
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert any(
        error["company_id"] == COMPANY and error["stage"] == "instrument_master"
        for error in report["errors"]
    )
    assert not any(EQUITY_KEY.replace("|", "%7C") in url for url, _ in calls)
    assert not any(row.instrument_id == COMPANY for row in deps.storage.list_observations())


def test_missing_token_and_invalid_inputs_do_not_call_network(deps):
    deps.settings.live_data.access_token = SecretStr("")
    cases = [([COMPANY], 550), (["NSE:ASIANPAINT"], 550), ([COMPANY], 0), (COMPANY, 550), ([], 550)]
    for identifiers, days in cases:
        report = live_data.sync_live(deps, identifiers, lookback_days=days, now=NOW)
        assert report["network_requests"] == 0
        assert report["article_ids"] == []
        assert datetime.fromisoformat(report["decision_time"]).tzinfo is not None


@pytest.mark.parametrize("status", [401, 403, 429])
def test_authentication_and_rate_limit_stop_requests_with_redacted_report(
    deps, monkeypatch, status
):
    calls = provider(
        monkeypatch,
        fail=lambda url, _: (
            Response({"error": TOKEN}, status) if url != live_data.MASTER_URL else None
        ),
    )
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert len(calls) == report["network_requests"] == 2
    assert report["observations_added"] == report["articles_added"] == 0
    assert report["article_ids"] == []
    assert TOKEN not in json.dumps(report)
    assert any(str(status) in error["message"] for error in report["errors"])


@pytest.mark.parametrize("exception", [requests.Timeout(TOKEN), requests.ConnectionError(TOKEN)])
def test_network_exceptions_do_not_echo_credentials(deps, monkeypatch, exception):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(live_data.requests, "get", fail)
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert report["network_requests"] == 1
    assert report["errors"][0]["stage"] == "instrument_master"
    assert TOKEN not in json.dumps(report)


def test_request_budget_is_enforced_without_hidden_retries(deps, monkeypatch):
    calls = provider(monkeypatch)
    deps.settings.live_data.max_requests = 2
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert len(calls) == report["network_requests"] == 2
    assert report["observations_added"] == 1
    assert report["article_ids"] == []
    assert any("budget" in error["message"] for error in report["errors"])


@pytest.mark.parametrize("metadata", [None, [], {"page": None}, {"page": []}, {"page": "broken"}])
def test_malformed_pagination_metadata_does_not_discard_report(deps, monkeypatch, metadata):
    calls = provider(monkeypatch, metadata=metadata)
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert report["articles_added"] == 1
    assert len(report["article_ids"]) == 1
    assert len(calls) == 4


def test_news_pagination_is_bounded_and_reports_incompleteness(deps, monkeypatch):
    calls = provider(
        monkeypatch,
        news_items=lambda page: [news(article_link=f"https://example.invalid/page-{page}")],
        metadata={"page": {"total_pages": 20}},
    )
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert len(calls) == 3 + deps.settings.live_data.news_max_pages
    assert report["articles_added"] == deps.settings.live_data.news_max_pages
    assert any("pagination limit" in warning for warning in report["warnings"])


def test_malformed_provider_rows_are_isolated(deps, monkeypatch):
    provider(
        monkeypatch,
        candles=[None, ["bad timestamp"], candle(close=500), candle()],
        news_items=[
            None,
            news(published_time=True),
            news(published_time=int((NOW + timedelta(days=1)).timestamp() * 1000)),
            news(),
        ],
    )
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert report["observations_added"] == 2
    assert report["articles_added"] == 1
    assert len(report["errors"]) == 9


def test_master_has_a_separate_bounded_decoded_limit(deps, monkeypatch):
    provider(monkeypatch)
    monkeypatch.setattr(live_data, "MAX_RESPONSE_BYTES", 250)
    monkeypatch.setattr(live_data, "MAX_MASTER_BYTES", 4096)
    report = live_data.sync_live(deps, [COMPANY], include_news=False, now=NOW)
    assert len(report["universe"]) == 2
    assert not any(error["stage"] == "instrument_master" for error in report["errors"])


def test_oversized_master_is_rejected_before_any_data_write(deps, monkeypatch):
    calls = provider(monkeypatch)
    monkeypatch.setattr(live_data, "MAX_MASTER_BYTES", 32)
    report = live_data.sync_live(deps, [COMPANY], now=NOW)
    assert len(calls) == 1
    assert "size limit" in report["errors"][0]["message"]
    assert deps.storage.list_observations() == []


def test_naive_injected_clock_is_rejected_without_network(deps):
    with pytest.raises(ValueError, match="timezone"):
        live_data.sync_live(deps, [COMPANY], now=datetime(2026, 10, 24))
