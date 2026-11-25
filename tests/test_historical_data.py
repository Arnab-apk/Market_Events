"""Historical adapter contract tests; synthetic responses, no account/network access."""

import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from pydantic import SecretStr

from market_events import live_data
from market_events.config import Settings
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
COMPANY = "LIVE:NSE:ASIANPAINT"
BENCHMARK = "LIVE:NSE:NIFTY50"
TOKEN = "fictional-offline-token"
MASTER = [
    {
        "segment": "NSE_EQ",
        "exchange": "NSE",
        "instrument_type": "EQ",
        "trading_symbol": "ASIANPAINT",
        "instrument_key": "NSE_EQ|OFFLINE_KEY",
    },
    {
        "segment": "NSE_INDEX",
        "exchange": "NSE",
        "instrument_type": "INDEX",
        "trading_symbol": "NIFTY",
        "instrument_key": "NSE_INDEX|Offline index",
    },
]


def candle(session, close=105):
    return [f"{session}T00:00:00+05:30", 100, 110, 90, close, 1000, 0]


class Response:
    def __init__(self, payload, status=200, compressed=False):
        self.content = json.dumps(payload).encode()
        if compressed:
            self.content = gzip.compress(self.content)
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        yield self.content


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Real network access forbidden in historical tests")

    monkeypatch.setattr(requests, "get", reject)
    monkeypatch.setattr(requests.sessions.Session, "request", reject)
    monkeypatch.setattr(live_data.time, "sleep", lambda delay: None)


@pytest.fixture
def deps(tmp_path):
    settings = Settings(root=ROOT, universe="live", mode="live")
    settings.live_data.access_token = SecretStr(TOKEN)
    with Storage(tmp_path / "history.sqlite") as storage:
        yield SimpleNamespace(settings=settings, storage=storage)


def provider(monkeypatch, rows=None, master=MASTER, fail=None):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if fail:
            response = fail(url)
            if response is not None:
                return response
        if url == live_data.MASTER_URL:
            return Response(master, compressed=True)
        assert url.startswith(live_data.API_URL + "/v3/historical-candle/")
        assert "/days/1/" in url
        end, start = url.rsplit("/", 2)[1:]
        items = [candle(start), candle(end)] if rows is None else rows
        if callable(items):
            items = items(url)
        return Response({"status": "success", "data": {"candles": items}})

    monkeypatch.setattr(live_data.requests, "get", get)
    return calls


def test_defaults_end_in_2020_and_report_only_accepted_coverage(deps, monkeypatch):
    calls = provider(
        monkeypatch,
        rows=[
            candle("2014-12-31"),
            candle("2017-01-02"),
            candle("2020-12-31"),
            candle("2021-01-01"),
        ],
    )
    report = live_data.sync_historical(deps, [COMPANY, COMPANY], now=NOW)
    assert report["requested_company_ids"] == [COMPANY]
    assert report["requested_start"] == "2015-01-01"
    assert report["requested_end"] == "2020-12-31"
    assert report["actual_start"] == "2017-01-02"
    assert report["actual_end"] == "2020-12-31"
    assert report["observations_added"] == 4
    assert report["articles_added"] == 0
    assert report["article_ids"] == []
    assert report["errors"] == []
    assert report["data_source"] == "imported_historical_data"
    assert report["network_requests"] == len(calls) == 3
    assert set(report["coverage"]) == {COMPANY, BENCHMARK}
    assert report["coverage"][COMPANY] == {
        "actual_start": "2017-01-02",
        "actual_end": "2020-12-31",
        "bars": 2,
        "chunks_planned": 1,
        "chunks_requested": 1,
        "chunks_completed": 1,
    }
    assert all(url.endswith("/days/1/2020-12-31/2015-01-01") for url, _ in calls[1:])
    assert "NSE_EQ%7COFFLINE_KEY" in calls[1][0]
    assert "NSE_INDEX%7COffline%20index" in calls[2][0]
    assert "Authorization" not in calls[0][1]["headers"]
    assert all(kwargs["allow_redirects"] is False for _, kwargs in calls)
    assert all(kwargs["timeout"] == 20 for _, kwargs in calls)
    rows = deps.storage.list_observations()
    assert all(row.available_at == NOW for row in rows)
    assert {row.timestamp.hour for row in rows} == {10}  # 15:30 IST
    assert all(date(2015, 1, 1) <= row.timestamp.date() <= date(2020, 12, 31) for row in rows)
    assert deps.storage.list_articles() == []
    assert deps.storage.list_runs() == []
    assert TOKEN not in json.dumps(report)


def test_decade_chunks_are_adjacent_inclusive_bounded_and_cover_leap_dates(deps, monkeypatch):
    calls = provider(monkeypatch)
    report = live_data.sync_historical(deps, [COMPANY], start_date=date(2000, 2, 29), now=NOW)
    expected = [
        (date(2000, 2, 29), date(2009, 12, 31)),
        (date(2010, 1, 1), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2020, 12, 31)),
    ]
    assert report["network_requests"] == len(calls) == 7
    for offset in (1, 4):
        intervals = []
        for url, _ in calls[offset : offset + 3]:
            end, start = url.rsplit("/", 2)[1:]
            intervals.append((date.fromisoformat(start), date.fromisoformat(end)))
        assert intervals == expected
        assert all((end - start).days < 3653 for start, end in intervals)
        assert all(
            left[1] + timedelta(days=1) == right[0] for left, right in zip(intervals, intervals[1:])
        )
    assert report["errors"] == []
    assert report["observations_added"] == 12
    assert all(item["chunks_completed"] == 3 for item in report["coverage"].values())


def test_single_day_and_duplicate_candles_count_once(deps, monkeypatch):
    provider(monkeypatch)
    report = live_data.sync_historical(
        deps, [COMPANY], start_date=date(2020, 12, 31), end_date=date(2020, 12, 31), now=NOW
    )
    assert report["observations_added"] == 2
    assert report["coverage"][COMPANY]["bars"] == 1
    assert report["actual_start"] == report["actual_end"] == "2020-12-31"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"end_date": date(2021, 1, 1)},
        {"start_date": date(2021, 1, 1)},
        {"start_date": date(1999, 12, 31)},
        {"start_date": date(2020, 2, 1), "end_date": date(2020, 1, 1)},
        {"start_date": "2015-01-01"},
        {"end_date": datetime(2020, 12, 31, tzinfo=timezone.utc)},
        {"end_date": None},
        {"now": datetime(2020, 12, 31, 12, tzinfo=timezone.utc)},
    ],
)
def test_invalid_dates_rejected_before_network_or_storage(deps, kwargs):
    report = live_data.sync_historical(deps, [COMPANY], **{"now": NOW, **kwargs})
    assert report["network_requests"] == 0
    assert report["errors"][0]["stage"] == "validation"
    assert report["actual_start"] is report["actual_end"] is None
    assert deps.storage.list_observations() == []


@pytest.mark.parametrize("identifiers", [COMPANY, None, [], [1], [BENCHMARK], ["NSE:UNKNOWN"]])
def test_invalid_selection_is_explicit_and_offline(deps, identifiers):
    report = live_data.sync_historical(deps, identifiers, now=NOW)
    assert report["network_requests"] == 0
    assert report["errors"][0]["stage"] == "validation"


def test_missing_token_is_offline_and_redacted(deps):
    deps.settings.live_data.access_token = SecretStr("")
    report = live_data.sync_historical(deps, [COMPANY], now=NOW)
    assert report["errors"][0]["stage"] == "configuration"
    assert report["network_requests"] == 0


def test_naive_clock_rejected_before_network(deps):
    with pytest.raises(ValueError, match="timezone"):
        live_data.sync_historical(deps, [COMPANY], now=NOW.replace(tzinfo=None))


def test_availability_uses_each_actual_response_receipt(deps, monkeypatch):
    provider(monkeypatch)
    times = iter(NOW + timedelta(seconds=i) for i in range(4))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(times)

    monkeypatch.setattr(live_data, "datetime", Clock)
    report = live_data.sync_historical(deps, [COMPANY])
    rows = deps.storage.list_observations()
    assert {row.available_at for row in rows if row.instrument_id == COMPANY} == {
        NOW + timedelta(seconds=1)
    }
    assert {row.available_at for row in rows if row.instrument_id == BENCHMARK} == {
        NOW + timedelta(seconds=2)
    }
    assert (
        report["fetched_at"] == report["decision_time"] == (NOW + timedelta(seconds=3)).isoformat()
    )


def test_identical_repeat_preserves_first_availability_and_revisions_are_immutable(
    deps, monkeypatch
):
    provider(monkeypatch, rows=[candle("2020-12-31")])
    live_data.sync_historical(deps, [COMPANY], now=NOW)
    original = deps.storage.list_observations()
    repeat = live_data.sync_historical(deps, [COMPANY], now=NOW + timedelta(days=1))
    assert repeat["observations_added"] == 0
    assert repeat["errors"] == []
    assert repeat["coverage"][COMPANY]["bars"] == 1
    assert deps.storage.list_observations() == original
    provider(monkeypatch, rows=[candle("2020-12-31", close=106)])
    revised = live_data.sync_historical(deps, [COMPANY], now=NOW + timedelta(days=2))
    assert revised["observations_added"] == 0
    assert sum("Conflicting immutable" in item["message"] for item in revised["errors"]) == 2
    assert all(item["bars"] == 0 for item in revised["coverage"].values())
    assert deps.storage.list_observations() == original


def test_budget_exhaustion_reports_partial_coverage_without_retry(deps, monkeypatch):
    calls = provider(monkeypatch)
    deps.settings.live_data.max_requests = 2
    report = live_data.sync_historical(deps, [COMPANY], start_date=date(2000, 1, 1), now=NOW)
    assert len(calls) == report["network_requests"] == 2
    assert report["coverage"][COMPANY]["chunks_planned"] == 3
    assert report["coverage"][COMPANY]["chunks_completed"] == 1
    assert report["coverage"][BENCHMARK]["chunks_requested"] == 0
    assert report["actual_end"] == "2009-12-31"
    assert len(report["errors"]) == 2
    assert all("budget" in item["message"] for item in report["errors"])


@pytest.mark.parametrize("status", [401, 403, 429])
def test_auth_and_rate_limit_failures_stop_all_remaining_requests(deps, monkeypatch, status):
    calls = provider(
        monkeypatch,
        fail=lambda url: (
            Response({"secret": TOKEN}, status) if url != live_data.MASTER_URL else None
        ),
    )
    report = live_data.sync_historical(deps, [COMPANY], start_date=date(2000, 1, 1), now=NOW)
    assert len(calls) == report["network_requests"] == 2
    assert report["observations_added"] == 0
    assert report["actual_start"] is None
    assert any(str(status) in item["message"] for item in report["errors"])
    assert TOKEN not in json.dumps(report)


def test_failed_chunk_continues_without_retry_and_preserves_other_coverage(deps, monkeypatch):
    def fail(url):
        if url.endswith("/2009-12-31/2000-01-01"):
            raise requests.Timeout(TOKEN)

    calls = provider(monkeypatch, fail=fail)
    report = live_data.sync_historical(deps, [COMPANY], start_date=date(2000, 1, 1), now=NOW)
    assert len(calls) == 7
    assert report["coverage"][COMPANY]["chunks_requested"] == 3
    assert report["coverage"][COMPANY]["chunks_completed"] == 2
    assert report["actual_start"] == "2010-01-01"
    assert report["actual_end"] == "2020-12-31"
    assert len(report["errors"]) == 2
    assert TOKEN not in json.dumps(report)


@pytest.mark.parametrize("rows", [[], [candle("2021-01-01")], None, {}])
def test_empty_outside_and_malformed_history_are_explicit(deps, monkeypatch, rows):
    provider(monkeypatch, rows=lambda url: rows)
    report = live_data.sync_historical(deps, [COMPANY], now=NOW)
    assert report["observations_added"] == 0
    assert report["actual_start"] is report["actual_end"] is None
    assert len(report["errors"]) == 2
    assert all(item["bars"] == 0 for item in report["coverage"].values())


def test_malformed_rows_are_isolated_and_ist_date_bounds_are_enforced(deps, monkeypatch):
    provider(
        monkeypatch,
        rows=[
            None,
            ["bad timestamp"],
            candle("2020-12-30", close=500),
            ["2020-12-30T00:00:00", 100, 110, 90, 105, 1000],
            ["2020-12-30T00:00:00+05:30", True, 110, 90, 105, 1000],
            ["2020-12-31T20:00:00Z", 100, 110, 90, 105, 1000],  # 2021 IST
            ["2014-12-31T20:00:00Z", 100, 110, 90, 105, 1000],  # 2015 IST
            candle("2020-12-31"),
        ],
    )
    report = live_data.sync_historical(deps, [COMPANY], now=NOW)
    assert report["observations_added"] == 4
    assert len(report["errors"]) == 10
    assert report["actual_start"] == "2015-01-01"
    assert report["actual_end"] == "2020-12-31"


def test_only_chunk_local_rows_are_accepted(deps, monkeypatch):
    provider(monkeypatch, rows=[candle("2010-01-01")])
    report = live_data.sync_historical(deps, [COMPANY], start_date=date(2000, 1, 1), now=NOW)
    assert report["observations_added"] == 2
    assert len(report["errors"]) == 4  # No accepted history in first/last chunks.
    assert report["coverage"][COMPANY]["bars"] == 1


@pytest.mark.parametrize("master", [[], MASTER + [MASTER[0]], {"unexpected": MASTER}])
def test_missing_ambiguous_or_malformed_master_never_guesses_equity_keys(deps, monkeypatch, master):
    calls = provider(monkeypatch, master=master)
    report = live_data.sync_historical(deps, [COMPANY], now=NOW)
    assert report["coverage"][COMPANY]["bars"] == 0
    assert any(item["stage"] == "instrument_master" for item in report["errors"])
    assert not any("NSE_EQ%7C" in url for url, _ in calls)


def test_empty_retry_does_not_claim_cached_coverage(deps, monkeypatch):
    provider(monkeypatch)
    live_data.sync_historical(deps, [COMPANY], now=NOW)
    original = deps.storage.list_observations()
    provider(monkeypatch, rows=[])
    report = live_data.sync_historical(deps, [COMPANY], now=NOW + timedelta(days=1))
    assert report["actual_start"] is report["actual_end"] is None
    assert report["errors"]
    assert deps.storage.list_observations() == original
