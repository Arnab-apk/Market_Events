"""Public live workflows keep credentials, namespaces and model actions explicit."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_events.config import LiveDataSettings, ModelSettings, Settings, load_settings
from market_events.pipeline import (
    Dependencies,
    analyse_article,
    analyse_synced_news,
    readiness,
)
from market_events.schemas import Article, MarketObservation
from market_events.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)
COMPANY = {
    "instrument_id": "LIVE:NSE:ASIANPAINT",
    "name": "Asian Paints",
    "aliases": ["AsianPaint"],
    "benchmark_id": "LIVE:NSE:NIFTY50",
}


@pytest.fixture
def live_deps(tmp_path, monkeypatch):
    import market_events.pipeline as pipeline

    monkeypatch.setattr(pipeline, "read_companies", lambda settings: [COMPANY])
    monkeypatch.setattr(pipeline, "read_exposure_rules", lambda settings: [])
    settings = Settings(
        root=ROOT,
        universe="live",
        mode="live",
        slm=ModelSettings(model="test-small"),
        llm=ModelSettings(model="test-large"),
    )
    with Storage(tmp_path / "live.sqlite") as storage:
        yield Dependencies(storage, settings)


def test_live_token_is_excluded_and_environment_alias_has_lower_priority(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "fake-primary-secret")
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "fake-alias-secret")
    settings = load_settings(ROOT)
    assert settings.live_data.access_token.get_secret_value() == "fake-primary-secret"
    assert "access_token" not in settings.snapshot()["live_data"]
    assert "fake-primary-secret" not in json.dumps(settings.snapshot())
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN")
    assert load_settings(ROOT).live_data.access_token.get_secret_value() == "fake-alias-secret"


def test_readiness_is_offline_and_never_exposes_the_token(live_deps, monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError("A readiness check must never perform a network request")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    live_deps.settings.live_data = LiveDataSettings(access_token="fake-secret")
    rows = readiness(live_deps)
    assert {row["capability"] for row in rows} == {
        "market_history",
        "news",
        "technicals",
        "event_models",
    }
    assert all(set(row) == {"capability", "name", "configured", "ready", "reason"} for row in rows)
    assert next(row for row in rows if row["capability"] == "market_history")["ready"]
    assert not next(row for row in rows if row["capability"] == "technicals")["ready"]
    assert "fake-secret" not in json.dumps(rows)
    live_deps.settings.universe = "demo"
    assert not next(row for row in readiness(live_deps) if row["capability"] == "news")["ready"]


def test_batch_has_explicit_mode_namespace_and_limit_guards(live_deps, monkeypatch):
    import market_events.pipeline as pipeline

    calls = []

    def analyse(article_id, cutoff, policy, dependencies):
        calls.append(article_id)
        if article_id.endswith("bad"):
            raise ValueError("Unknown article")
        return SimpleNamespace(run_id="saved", status="completed", error=None)

    monkeypatch.setattr(pipeline, "analyse_article", analyse)
    live_deps.settings.mode = "replay"
    with pytest.raises(ValueError, match="live"):
        analyse_synced_news(live_deps, ["LIVE:NEWS:a"], CUTOFF)
    assert calls == []
    live_deps.settings.mode = "live"
    rows = analyse_synced_news(
        live_deps,
        ["syn-001", "LIVE:NEWS:bad", "LIVE:NEWS:a", "LIVE:NEWS:a", "LIVE:NEWS:b"],
        CUTOFF,
        limit=3,
    )
    assert [row["status"] for row in rows] == ["failed", "failed", "completed", "skipped"]
    assert calls == ["LIVE:NEWS:bad", "LIVE:NEWS:a"]
    assert rows[1]["error"] == "Unknown article"
    with pytest.raises(ValueError, match="Batch limit"):
        analyse_synced_news(live_deps, [], CUTOFF, limit=0)
    with pytest.raises(ValueError, match="timezone"):
        analyse_synced_news(live_deps, [], CUTOFF.replace(tzinfo=None))


def test_demo_article_cannot_be_analysed_in_live_universe(live_deps):
    live_deps.storage.add_articles(
        [
            Article(
                article_id="syn-001",
                source_url="https://example.invalid/test",
                text="Synthetic Asian Paints earnings.",
                published_at=CUTOFF,
                first_seen_at=CUTOFF,
            )
        ]
    )
    run = analyse_article("syn-001", CUTOFF, "slm_delegate", live_deps)
    assert run.status == "ineligible"
    assert "universes differ" in run.error
    assert run.calls == []


def test_live_analysis_saves_technicals_and_cannot_consume_synthetic_prices(live_deps, monkeypatch):
    import requests

    text = "Synthetic protocol test: Asian Paints reports quarterly earnings."
    live_deps.storage.add_articles(
        [
            Article(
                article_id="LIVE:NEWS:test",
                source_url="https://fixtures.invalid/article",
                text=text,
                published_at=CUTOFF - timedelta(hours=1),
                first_seen_at=CUTOFF - timedelta(minutes=55),
            )
        ]
    )
    bars = []
    for index in range(60):
        stamp = CUTOFF - timedelta(days=59 - index, hours=2)
        for instrument, family, price in (
            (COMPANY["instrument_id"], "equity", 100 + index),
            (COMPANY["benchmark_id"], "benchmark", 100 + index / 10),
            ("NSE:ASIANPAINT", "equity", 10000 + index * 500),
        ):
            bars.append(
                MarketObservation(
                    instrument_id=instrument,
                    market_family=family,
                    timestamp=stamp,
                    available_at=stamp + timedelta(minutes=5),
                    open=price,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                    volume=1000,
                    currency="INR",
                    unit="share",
                )
            )
    live_deps.storage.add_observations(bars)
    responses = iter(
        [
            {
                "relevance": "relevant",
                "event_type": "earnings",
                "reason": "Source earnings",
                "source_spans": [text],
            },
            {
                "event_id": "temporary",
                "event_type": "earnings",
                "company_id": COMPANY["instrument_id"],
                "source_spans": [text],
            },
        ]
    )

    def post(session, url, **kwargs):
        assert url == "http://localhost:11434/api/chat"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "model": kwargs["json"]["model"],
                "message": {"content": json.dumps(next(responses))},
            },
        )

    monkeypatch.setattr(requests.Session, "post", post)
    run = analyse_article("LIVE:NEWS:test", CUTOFF, "slm_delegate", live_deps)
    assert run.status == "completed"
    assert run.technicals.history_bars == 60
    assert run.technicals.values["rsi14"] == 100
    assert run.technicals.values["sma20"] == pytest.approx(149.5)
    assert run.technicals.missing == []
    assert run.assessment.inputs["components"] == {
        "equity": pytest.approx(run.features.values["excess_return"] / 0.02)
    }
    allowed = {bar.observation_id for bar in bars if bar.instrument_id.startswith("LIVE:")}
    assert set(run.features.observation_ids + run.technicals.observation_ids) <= allowed
    assert live_deps.storage.get_run(run.run_id).technicals == run.technicals
    assert run.config_snapshot["exposure_rules.json"] == []
    assert "access_token" not in run.config_snapshot["live_data"]


@pytest.mark.parametrize("unsupported", [False, True])
def test_unresolved_company_preserves_inspectable_abstention(live_deps, monkeypatch, unsupported):
    import requests

    text = "Synthetic protocol test: an unspecified issuer reports quarterly earnings."
    live_deps.storage.add_articles(
        [
            Article(
                article_id="LIVE:NEWS:unresolved",
                source_url="https://fixtures.invalid/unresolved",
                text=text,
                published_at=CUTOFF,
                first_seen_at=CUTOFF,
            )
        ]
    )
    responses = iter(
        [
            {
                "relevance": "relevant",
                "event_type": "earnings",
                "reason": "Earnings",
                "source_spans": [text],
            },
            {
                "event_id": "temporary",
                "event_type": "earnings",
                "company_id": None,
                "source_spans": ["Unsupported invented passage" if unsupported else text],
            },
        ]
    )

    def post(session, url, **kwargs):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "model": kwargs["json"]["model"],
                "message": {"content": json.dumps(next(responses))},
            },
        )

    monkeypatch.setattr(requests.Session, "post", post)
    run = analyse_article("LIVE:NEWS:unresolved", CUTOFF, "slm_delegate", live_deps)
    assert run.status == "abstained"
    assert run.extraction.company_id is None
    assert run.extraction.validation_status == ("unsupported" if unsupported else "unresolved")
    assert run.technicals is None
    assert run.error is None
    assert run.assessment.direction == "abstain"
    assert (
        "Company unresolved or inconsistent with market features"
        in run.assessment.abstention_reasons
    )
    assert live_deps.storage.get_run(run.run_id).assessment == run.assessment


def test_actual_adapter_sync_to_explicit_model_batch_preserves_cutoff_and_identity(
    tmp_path, monkeypatch
):
    """Exercise real HTTP parsing, mappings, storage and pipeline; mock transports only."""
    import gzip

    import requests

    from market_events import live_data
    from market_events.config import read_companies
    from market_events.technicals import compute_technicals

    settings = Settings(
        root=ROOT,
        universe="live",
        mode="live",
        live_data=LiveDataSettings(access_token="fake-readonly-token"),
        slm=ModelSettings(model="test-small"),
        llm=ModelSettings(model="test-large"),
    )
    master = [
        {
            "segment": "NSE_EQ",
            "exchange": "NSE",
            "instrument_type": "EQ",
            "trading_symbol": "ASIANPAINT",
            "instrument_key": "NSE_EQ|TEST-ASIAN",
            "name": "ASIAN PAINTS LIMITED",
        },
        {
            "segment": "NSE_INDEX",
            "exchange": "NSE",
            "instrument_type": "INDEX",
            "trading_symbol": "Nifty 50",
            "instrument_key": "NSE_INDEX|Nifty 50",
            "name": "Nifty 50",
        },
    ]
    sessions = []
    day = CUTOFF.date() - timedelta(days=1)
    while len(sessions) < 60:
        if day.weekday() < 5:
            sessions.append(day)
        day -= timedelta(days=1)
    sessions.reverse()

    def candles(benchmark=False):
        rows = []
        for index, session in enumerate(sessions):
            price = 100 + index * (0.1 if benchmark else 1)
            rows.append(
                [
                    f"{session}T00:00:00+05:30",
                    price,
                    price + 1,
                    price - 1,
                    price,
                    0 if benchmark else 1000,
                    0,
                ]
            )
        return {"status": "success", "data": {"candles": list(reversed(rows))}}

    headline = "Asian Paints reports quarterly earnings"
    summary = "Synthetic HTTP fixture: quarterly profit increased."
    news = {
        "status": "success",
        "data": {
            "NSE_EQ|TEST-ASIAN": [
                {
                    "heading": headline,
                    "summary": summary,
                    "article_link": "https://example.invalid/provider/earnings",
                    "published_time": int((CUTOFF - timedelta(hours=1)).timestamp() * 1000),
                }
            ]
        },
        "metadata": {"page": {"total_pages": 1}},
    }
    get_calls, model_calls = [], []

    class StreamResponse:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def iter_content(self, chunk_size):
            yield self.body

    def get(url, **kwargs):
        get_calls.append(url)
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        if url == live_data.MASTER_URL:
            assert "Authorization" not in kwargs["headers"]
            return StreamResponse(gzip.compress(json.dumps(master).encode()))
        assert kwargs["headers"]["Authorization"] == "Bearer fake-readonly-token"
        if "/historical-candle/NSE_EQ%7CTEST-ASIAN/" in url:
            payload = candles()
        elif "/historical-candle/NSE_INDEX%7CNifty%2050/" in url:
            payload = candles(benchmark=True)
        elif url == live_data.API_URL + "/v2/news":
            assert kwargs["params"]["instrument_keys"] == "NSE_EQ|TEST-ASIAN"
            payload = news
        else:
            raise AssertionError(f"Unexpected HTTP request: {url}")
        return StreamResponse(json.dumps(payload).encode())

    def post(session, url, **kwargs):
        model_calls.append(url)
        payload = json.loads(kwargs["json"]["messages"][-1]["content"])
        passage = payload["text"]
        result = (
            {
                "relevance": "relevant",
                "event_type": "earnings",
                "reason": "Reported earnings",
                "source_spans": [passage],
            }
            if len(model_calls) == 1
            else {
                "event_id": "temporary",
                "event_type": "earnings",
                "company_id": COMPANY["instrument_id"],
                "source_spans": [passage],
            }
        )
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "model": kwargs["json"]["model"],
                "message": {"content": json.dumps(result)},
            },
        )

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests.Session, "post", post)
    monkeypatch.setattr(live_data.time, "sleep", lambda seconds: None)
    with Storage(tmp_path / "adapter.sqlite") as storage:
        dependencies = Dependencies(storage, settings)
        report = live_data.sync_live(
            dependencies, [COMPANY["instrument_id"]], lookback_days=180, now=CUTOFF
        )
        assert report["errors"] == []
        assert report["observations_added"] == 120
        assert report["articles_added"] == 1
        assert report["network_requests"] == 4
        assert model_calls == []
        assert len(get_calls) == 4
        assert all(key.startswith("LIVE:") for key in report["article_ids"])
        assert "fake-readonly-token" not in json.dumps(report)
        cutoff = datetime.fromisoformat(report["decision_time"])
        article = storage.get_article(report["article_ids"][0])
        assert article.first_seen_at <= cutoff
        assert all(row.available_at <= cutoff for row in storage.list_observations())
        assert (
            next(
                c
                for c in read_companies(settings)
                if c["instrument_id"] == COMPANY["instrument_id"]
            )["benchmark_id"]
            == "LIVE:NSE:NIFTY50"
        )
        assert (
            compute_technicals(
                storage.list_observations(),
                cutoff - timedelta(microseconds=1),
                COMPANY["instrument_id"],
            ).history_bars
            == 0
        )

        result = analyse_synced_news(dependencies, report["article_ids"], cutoff)
        assert result[0]["status"] == "completed"
        assert len(model_calls) == 2
        assert len(get_calls) == 4
        saved = storage.get_run(result[0]["run_id"])
        assert saved.extraction.company_id == COMPANY["instrument_id"]
        assert saved.technicals.history_bars == 60
        assert saved.technicals.missing == []
        assert saved.features.values["benchmark_return"] is not None
        assert saved.technicals.values["rsi14"] == 100
        assert "fake-readonly-token" not in saved.model_dump_json()

        refreshed = live_data.sync_live(
            dependencies,
            [COMPANY["instrument_id"]],
            lookback_days=180,
            now=CUTOFF + timedelta(minutes=10),
        )
        assert refreshed["errors"] == []
        assert refreshed["observations_added"] == refreshed["articles_added"] == 0
        assert refreshed["article_ids"] == report["article_ids"]
        assert storage.get_article(article.article_id).first_seen_at == article.first_seen_at
        assert all(row.available_at == cutoff for row in storage.list_observations())
        repeated = analyse_synced_news(dependencies, report["article_ids"], cutoff)
        assert repeated[0]["run_id"] == saved.run_id
        assert len(model_calls) == 2


def test_actual_cli_sync_without_token_returns_structured_setup_error(
    tmp_path, monkeypatch, capsys
):
    import importlib

    import requests

    cli = importlib.import_module("market_events.__main__")
    settings = Settings(root=ROOT, live_data=LiveDataSettings())
    monkeypatch.setattr(cli, "load_settings", lambda root: settings.model_copy(deep=True))

    def forbidden(*args, **kwargs):
        raise AssertionError("Missing-token CLI sync must not contact any provider or model")

    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(requests.Session, "post", forbidden)
    status = cli.main(
        [
            "--database",
            str(tmp_path / "missing-token.sqlite"),
            "sync-live",
            "--companies",
            COMPANY["instrument_id"],
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert status == 1
    assert report["network_requests"] == 0
    assert report["observations_added"] == report["articles_added"] == 0
    assert report["article_ids"] == []
    assert datetime.fromisoformat(report["decision_time"]).utcoffset() is not None
    assert report["errors"][0]["stage"] == "configuration"
    assert "UPSTOX_ANALYTICS_TOKEN" in report["errors"][0]["message"]
