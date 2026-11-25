"""Offline HTTP contracts; isolated Settings, real ledgers, no external services."""

import csv
import hashlib
import io
import json
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

import market_events.api as api_module
from market_events.config import LiveDataSettings, Settings
from market_events.model_client import ModelClient
from market_events.schemas import (
    AnalysisRun,
    Article,
    Assessment,
    EventExtraction,
    EventOutcome,
    MarketObservation,
)
from market_events.storage import Storage

LIVE = "LIVE:NSE:TEST"
SYNTHETIC = "NSE:TEST"
CUTOFF = datetime(2026, 1, 3, 12, tzinfo=timezone.utc)
START = datetime(2020, 12, 28, 10, tzinfo=timezone.utc)
SELECTION = {"company_id": LIVE, "start_date": "2020-12-29", "end_date": "2020-12-31"}


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    """Fail even if an attempted provider/model call gets swallowed by a handler."""
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("external call")
        raise AssertionError("HTTP API tests must never use a provider, socket or model")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(ModelClient, "ask", forbidden)
    yield
    assert not attempts, "An endpoint attempted an external network/model call"


@pytest.fixture
def web(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    live_company = {
        "instrument_id": LIVE,
        "name": "Offline Test Equity",
        "trading_symbol": "TEST",
        "provider_instrument_key": "NSE_EQ|SYNTHETIC",
        "exchange": "NSE",
        "currency": "INR",
        "unit": "share",
        "market_family": "equity",
        "aliases": [],
        "sector": "test",
        "benchmark_id": "LIVE:NSE:INDEX",
        "source": "https://fixtures.invalid/universe",
    }
    benchmark = {
        **live_company,
        "instrument_id": "LIVE:NSE:INDEX",
        "name": "Offline Test Index",
        "trading_symbol": "INDEX",
        "market_family": "benchmark",
        "unit": "index_point",
        "benchmark_id": None,
    }
    (config_dir / "live_universe.json").write_text(
        json.dumps(
            {
                "version": "offline-v1",
                "source": "https://fixtures.invalid/universe",
                "instruments": [live_company, benchmark],
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "companies.json").write_text(
        json.dumps(
            [
                {
                    "instrument_id": SYNTHETIC,
                    "name": "Synthetic Test Equity",
                    "aliases": [],
                    "sector": "test",
                    "benchmark_id": "NSE:INDEX",
                }
            ]
        ),
        encoding="utf-8",
    )
    settings = Settings(
        root=tmp_path,
        database_path=Path("data/local.sqlite"),
        universe="live",
        mode="replay",
        live_data=LiveDataSettings(access_token=""),
    )

    def no_environment_settings(*args, **kwargs):
        pytest.fail("create_app must honor supplied Settings without loading local secrets")

    monkeypatch.setattr(api_module, "load_settings", no_environment_settings)
    # A caller-supplied empty token must remain empty even with an ambient token.
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "unused-fixture-environment-token")
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "unused-fixture-alias-token")
    monkeypatch.setenv("MARKET_EVENTS_WEB_ORIGIN", "http://127.0.0.1:3000")
    app = api_module.create_app(root=tmp_path, settings=settings)
    with TestClient(app) as client:
        yield SimpleNamespace(
            root=tmp_path,
            database=tmp_path / "data/local.sqlite",
            demo_database=tmp_path / "data/web_demo.sqlite",
            settings=settings,
            app=app,
            client=client,
        )


def article(identifier):
    return Article(
        article_id=identifier,
        source_url=f"https://fixtures.invalid/{identifier}",
        text=f"Offline fixture source {identifier} reports earnings.",
        published_at=CUTOFF - timedelta(hours=1),
        first_seen_at=CUTOFF,
    )


def run(identifier, source):
    return AnalysisRun(
        run_id=identifier,
        article_id=source,
        policy="slm_delegate",
        decision_time=CUTOFF,
        created_at=CUTOFF,
        status="ineligible",
        config_snapshot={"fixture": "offline-api"},
        mode="replay",
    )


def price_rows(instrument=LIVE):
    return [
        MarketObservation(
            instrument_id=instrument,
            market_family="equity",
            timestamp=START + timedelta(days=i),
            # Deliberately downloaded after 2020: research must preserve this fact.
            available_at=datetime(2026, 1, 1 + (i == 3), tzinfo=timezone.utc),
            open=opening,
            high=max(opening, close) + 1,
            low=min(opening, close) - 1,
            close=close,
            volume=1000,
            currency="INR",
            unit="share",
        )
        for i, (opening, close) in enumerate(
            [(999, 999), (100, 100), (100, 110), (110, 121), (9999, 9999)]
        )
    ]


@pytest.fixture
def populated(web):
    with Storage(web.database) as store:
        store.add_articles([article("LIVE:NEWS:one"), article("synthetic-one")])
        store.add_observations(price_rows() + price_rows(SYNTHETIC))
        for identifier, source in (
            ("live-run", "LIVE:NEWS:one"),
            ("synthetic-run", "synthetic-one"),
        ):
            store.save_run(run(identifier, source))
            store.save_outcome(EventOutcome(run_id=identifier, status="pending", reason=identifier))
    return web


def test_portfolio_review_validates_model_case_ids_and_leaves_ledger_unchanged(web, monkeypatch):
    web.settings.llm.model = "fixture-model"
    source = "LIVE:NEWS:portfolio"
    saved = run("holding-case", source)
    saved.event_id = "holding-event"
    saved.extraction = EventExtraction(
        event_id=saved.event_id, event_type="uncertain", company_id=LIVE
    )
    saved.assessment = Assessment(
        direction="abstain",
        coverage=0.25,
        rules_version="test",
        explanation="Insufficient evidence",
    )
    with Storage(web.database) as ledger:
        ledger.add_articles([article(source)])
        ledger.save_run(saved)
    before = snapshot(web.database.parent)
    picks = [saved.run_id]

    def choose(self, task, article_input, schema, *, context):
        assert task == "portfolio_review" and article_input is None
        assert self.settings.mode == "live" and self.settings.max_requests == 1
        assert context["topic"] == "gaps"
        assert context["cases"] == [
            {
                "run_id": saved.run_id,
                "decision_time": CUTOFF.isoformat(),
                "direction": "abstain",
                "coverage": 0.25,
                "conflicts": 0,
                "abstention_reasons": 0,
                "missing_inputs": 0,
                "stale_inputs": 0,
            }
        ]
        return schema(run_ids=picks)

    monkeypatch.setattr(ModelClient, "ask", choose)
    payload = {"topic": "gaps", "run_ids": [saved.run_id]}
    result = web.client.post("/api/portfolio-review", json=payload)
    assert result.status_code == 200
    assert result.json() == {"run_ids": [saved.run_id]}
    picks[:] = ["invented-id"]
    assert web.client.post("/api/portfolio-review", json=payload).status_code >= 400
    assert web.client.post("/api/portfolio-review?workspace=demo", json=payload).status_code == 422
    missing = web.client.post("/api/portfolio-review", json={**payload, "run_ids": ["missing"]})
    assert missing.status_code == 404
    assert snapshot(web.database.parent) == before


def snapshot(root):
    """Capture bytes, modification times and directories, including SQLite sidecars."""
    return (
        sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
        {
            p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*")
            if p.is_file()
        },
    )


def forbid_writer(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Read endpoints must never initialize writable Storage")

    monkeypatch.setattr(api_module, "Storage", forbidden)


def prices_csv(rows):
    fields = list(MarketObservation.model_fields)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.model_dump(mode="json"))
    return stream.getvalue()


def test_gets_on_absent_workspaces_do_not_create_database_or_directories(web, monkeypatch):
    forbid_writer(monkeypatch)
    before = snapshot(web.root)
    assert web.client.get("/api/health").json() == {"status": "ok", "history_end": "2020-12-31"}
    for params in ({}, {"universe": "demo"}, {"workspace": "demo", "universe": "live"}):
        response = web.client.get("/api/workspace", params=params)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["exists"] is False
        assert payload["articles"] == payload["runs"] == payload["outcomes"] == []
        assert payload["observations_count"] == 0
        assert payload["history_end"] == "2020-12-31"
        assert web.client.get("/api/comparisons", params=params).status_code == 200
        assert web.client.get("/api/case/missing", params=params).status_code == 404
    assert snapshot(web.root) == before
    assert not web.database.exists() and not web.demo_database.exists()
    assert not (web.root / "data").exists()


def test_existing_database_gets_use_readonly_connections_and_do_not_migrate(populated, monkeypatch):
    web = populated
    # Full tables with a legacy version marker: GET must not run Storage migrations.
    with sqlite3.connect(web.database) as connection:
        connection.execute("PRAGMA user_version = 1")
    before = snapshot(web.root)
    connections = []
    real_connect = sqlite3.connect

    def traced_connect(database, *args, **kwargs):
        connections.append((str(database), kwargs.copy()))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    forbid_writer(monkeypatch)
    for params, own_run in (
        ({"universe": "live"}, "live-run"),
        ({"universe": "demo"}, "synthetic-run"),
    ):
        for path in ("/api/workspace", "/api/comparisons", f"/api/case/{own_run}"):
            response = web.client.get(path, params=params)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
    assert connections
    assert all("mode=ro" in path and options.get("uri") is True for path, options in connections)
    assert snapshot(web.root) == before
    with real_connect(web.database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


@pytest.mark.parametrize(
    "universe,own,opposite,instrument",
    [
        ("live", "live-run", "synthetic-run", LIVE),
        ("demo", "synthetic-run", "live-run", SYNTHETIC),
    ],
)
def test_workspace_and_cases_hide_opposite_namespace(
    populated, universe, own, opposite, instrument
):
    web = populated
    response = web.client.get("/api/workspace", params={"universe": universe})
    assert response.status_code == 200
    payload = response.json()
    assert {r["run_id"] for r in payload["runs"]} == {own}
    assert {o["run_id"] for o in payload["outcomes"]} == {own}
    assert payload["observations_count"] == 5
    assert payload["companies"][0]["instrument_id"] == instrument
    assert payload["companies"][0]["bars"] == 5
    assert payload["companies"][0]["research_bars"] == 4
    assert payload["companies"][0]["latest_close"] == 9999
    assert web.client.get(f"/api/case/{own}", params={"universe": universe}).status_code == 200
    assert web.client.get(f"/api/case/{opposite}", params={"universe": universe}).status_code == 404
    assert web.client.get(f"/api/case/{opposite}", params={"universe": universe}).json() == {
        "detail": "Saved run not found in this universe"
    }


@pytest.mark.parametrize(
    "universe,own,opposite",
    [
        ("live", "live-run", "synthetic-run"),
        ("demo", "synthetic-run", "live-run"),
    ],
)
def test_comparisons_outcomes_and_manifests_are_scoped_to_selected_universe(
    populated,
    universe,
    own,
    opposite,
):
    response = populated.client.get("/api/comparisons", params={"universe": universe})
    assert response.status_code == 200
    payload = response.json()
    assert {r["run_id"] for r in payload["run_manifest"]} == {own}
    assert {r["run_id"] for r in payload["outcomes"]} == {own}
    assert opposite not in json.dumps(payload)
    assert sum(row["runs"] for row in payload["policy_summary"]) == 1


def test_corrupt_database_get_returns_sanitized_error_without_writing(web):
    web.database.parent.mkdir()
    web.database.write_bytes(b"offline-test-not-a-sqlite-file")
    before = snapshot(web.root)
    response = web.client.get("/api/workspace")
    assert response.status_code == 409
    assert response.json() == {"detail": "Workspace database could not be read or updated"}
    assert str(web.root) not in response.text
    assert snapshot(web.root) == before


@pytest.mark.parametrize(
    "path",
    [
        "/api/demo",
        "/api/import",
        "/api/analyse",
        "/api/explain/missing",
        "/api/technicals",
        "/api/history",
        "/api/backtest",
        "/api/monte-carlo",
        "/api/sync/historical",
        "/api/sync/live",
        "/api/analyse-news",
        "/api/outcomes",
    ],
)
def test_get_cannot_invoke_explicit_post_actions(web, path):
    before = snapshot(web.root)
    response = web.client.get(path)
    assert response.status_code == 405
    assert snapshot(web.root) == before


@pytest.mark.parametrize(
    "params",
    [
        {"workspace": "../other"},
        {"universe": "other"},
        {"workspace": "LIVE"},
        {"workspace": "/tmp/ledger"},
    ],
)
def test_workspace_selector_is_an_enum_and_cannot_choose_arbitrary_paths(web, params):
    before = snapshot(web.root)
    assert web.client.get("/api/workspace", params=params).status_code == 422
    assert snapshot(web.root) == before


def test_history_dates_prices_and_download_availability_are_preserved(populated, monkeypatch):
    web = populated
    forbid_writer(monkeypatch)
    before = snapshot(web.root)
    response = web.client.post("/api/history", json=SELECTION)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["requested_start"] == payload["actual_start"] == "2020-12-29"
    assert payload["requested_end"] == payload["actual_end"] == "2020-12-31"
    assert [b["time"] for b in payload["bars"]] == ["2020-12-29", "2020-12-30", "2020-12-31"]
    assert [b["close"] for b in payload["bars"]] == [100, 110, 121]
    assert all(b["available_at"].startswith("2026-") for b in payload["bars"])
    assert all(not points for points in payload["indicators"].values())  # no hidden warmup
    default = web.client.post("/api/history", json={"company_id": LIVE})
    assert default.status_code == 200
    assert default.json()["requested_start"] == "2015-01-01"
    assert default.json()["requested_end"] == "2020-12-31"
    assert len(default.json()["bars"]) == 4  # excludes the stored 2021 bar
    assert snapshot(web.root) == before


def test_history_asof_filters_by_real_availability_and_rejects_empty_selection(populated):
    result = populated.client.post(
        "/api/history", json={**SELECTION, "as_of": "2026-01-01T00:00:00Z"}
    )
    assert result.status_code == 200
    assert [r["time"] for r in result.json()["bars"]] == ["2020-12-29", "2020-12-30"]
    for cutoff in ("2020-12-31T23:59:59Z", "2026-01-01T00:00:00"):
        response = populated.client.post("/api/history", json={**SELECTION, "as_of": cutoff})
        assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["history", "backtest"])
@pytest.mark.parametrize(
    "changes",
    [
        {"end_date": "2021-01-01"},
        {"start_date": "2021-01-01"},
        {"start_date": "1999-12-31"},
        {"start_date": "2020-12-31", "end_date": "2020-12-29"},
        {"end_date": "bad-date"},
        {"as_of": "2026-01-01T00:00:00"},
        {"database_path": "elsewhere.sqlite"},
    ],
)
def test_history_and_backtest_invalid_requests_fail_without_writes(web, endpoint, changes):
    before = snapshot(web.root)
    response = web.client.post(f"/api/{endpoint}", json={**SELECTION, **changes})
    assert response.status_code == 422
    assert snapshot(web.root) == before


@pytest.mark.parametrize("endpoint", ["history", "backtest", "technicals"])
@pytest.mark.parametrize("company", [SYNTHETIC, "LIVE:NSE:UNKNOWN", "LIVE:NSE:INDEX"])
def test_research_routes_require_an_equity_in_active_universe(web, endpoint, company):
    payload = {**SELECTION, "company_id": company}
    if endpoint == "technicals":
        payload = {"company_id": company, "decision_time": CUTOFF.isoformat()}
    response = web.client.post(f"/api/{endpoint}", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "Select a company from the active universe"
    assert not web.database.exists()


def test_backtest_route_uses_requested_window_next_open_costs_and_marked_benchmark(
    populated, monkeypatch
):
    web = populated
    forbid_writer(monkeypatch)
    before = snapshot(web.root)
    response = web.client.post(
        "/api/backtest",
        json={
            **SELECTION,
            "strategy": "buy_hold",
            "initial_capital": 1000,
            "cost_bps": 200,
            "slippage_bps": 100,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    # Independent cash accounting: second-session open=100, fill=101,
    # fee=2% of notional, so 1000 must cover 103.02 per acquired share.
    quantity = 1000 / 103.02
    expected = [1000, quantity * 110, quantity * 121]
    assert [p["value"] for p in result["equity"]] == pytest.approx(expected)
    assert [p["benchmark"] for p in result["equity"]] == pytest.approx(expected)
    assert [p["time"] for p in result["equity"]] == ["2020-12-29", "2020-12-30", "2020-12-31"]
    assert len(result["trades"]) == 1
    fill = result["trades"][0]
    assert fill["time"] == "2020-12-30" and fill["signal_time"] == "2020-12-29"
    assert fill["price"] == 101 and fill["side"] == "buy"
    assert fill["quantity"] == pytest.approx(quantity)
    assert fill["fee"] == pytest.approx(quantity * 101 * 0.02)
    assert fill["slippage_cost"] == pytest.approx(quantity)
    assert result["daily_returns"] == pytest.approx([expected[1] / 1000 - 1, 0.1])
    assert result["metrics"]["closed_trades"] == 0
    assert result["metrics"]["total_return"] == pytest.approx(expected[-1] / 1000 - 1)
    assert result["metrics"]["benchmark_return"] == pytest.approx(expected[-1] / 1000 - 1)
    assert result["open_position"]["cost_basis"] == 1000
    assert result["open_position"]["market_value"] == pytest.approx(expected[-1])
    assert snapshot(web.root) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"strategy": "unknown"},
        {"initial_capital": 0},
        {"cost_bps": -1},
        {"slippage_bps": 10000},
        {"fast_period": 50, "slow_period": 20},
        {"rsi_buy": 80, "rsi_sell": 30},
        {"strategy": "sma_cross"},
    ],
)
def test_backtest_route_rejects_numerical_inputs_and_insufficient_history(populated, changes):
    response = populated.client.post(
        "/api/backtest", json={**SELECTION, "strategy": "buy_hold", **changes}
    )
    assert response.status_code == 422


def test_monte_carlo_http_is_reproducible_readonly_and_has_consistent_quantiles(web, monkeypatch):
    forbid_writer(monkeypatch)
    before = snapshot(web.root)
    payload = {
        "daily_returns": [-0.03, 0.02, 0.01, -0.01, 0.04, -0.02, 0.07],
        "initial_capital": 1000,
        "simulations": 12,
        "horizon": 8,
        "seed": 17,
        "block_size": 3,
    }
    first = web.client.post("/api/monte-carlo", json=payload)
    assert first.status_code == 200, first.text
    result = first.json()
    repeated = web.client.post("/api/monte-carlo", json=payload).json()
    for key in ("paths", "bands", "metrics", "assumptions"):
        assert repeated[key] == result[key]
    # Creation time belongs to the receipt, not the reproducible numerical state.
    assert {k: v for k, v in repeated["manifest"].items() if k != "created_at"} == {
        k: v for k, v in result["manifest"].items() if k != "created_at"
    }
    manifest = result["manifest"]
    assert manifest["schema_version"] == "strategy-lab-v1"
    assert datetime.fromisoformat(manifest["created_at"]).utcoffset() == timedelta(0)
    assert manifest["params"] == {k: v for k, v in payload.items() if k != "daily_returns"}
    assert manifest["input_returns_count"] == len(payload["daily_returns"])
    expected_hash = hashlib.sha256(json.dumps(payload["daily_returns"]).encode()).hexdigest()
    assert manifest["input_returns_fingerprint"] == expected_hash
    changed_seed = web.client.post("/api/monte-carlo", json={**payload, "seed": 18}).json()
    assert changed_seed["paths"] != result["paths"]
    assert changed_seed["manifest"]["input_returns_fingerprint"] == expected_hash
    changed_input = web.client.post(
        "/api/monte-carlo",
        json={
            **payload,
            "daily_returns": [0.01] * 7,
        },
    ).json()
    assert changed_input["manifest"]["input_returns_fingerprint"] != expected_hash
    assert len(result["paths"]) == 12
    assert all(len(path) == 9 and path[0] == 1000 and min(path) > 0 for path in result["paths"])
    assert len(result["bands"]) == 9
    for band in result["bands"]:
        assert band["p05"] <= band["p50"] <= band["p95"]
    terminal = sorted(path[-1] for path in result["paths"])
    assert result["metrics"]["probability_loss"] == sum(v < 1000 for v in terminal) / 12
    assert result["metrics"]["median_terminal"] == pytest.approx((terminal[5] + terminal[6]) / 2)
    assert result["metrics"]["p05_terminal"] == result["bands"][-1]["p05"]
    assert result["metrics"]["p95_terminal"] == result["bands"][-1]["p95"]
    assert snapshot(web.root) == before


def test_research_manifests_identify_selected_bars_dates_and_cost_parameters(populated):
    web = populated
    history = web.client.post("/api/history", json=SELECTION).json()["manifest"]
    payload = {**SELECTION, "strategy": "buy_hold", "cost_bps": 37, "slippage_bps": 19}
    backtest = web.client.post("/api/backtest", json=payload).json()["manifest"]
    selected = price_rows()[1:4]
    expected_hash = hashlib.sha256(
        json.dumps(
            [row.model_dump(mode="json") for row in selected],
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    for manifest in (history, backtest):
        assert manifest["schema_version"] == "strategy-lab-v1"
        assert manifest["instrument_id"] == LIVE
        assert manifest["currency"] == "INR" and manifest["unit"] == "share"
        assert manifest["actual_start"] == "2020-12-29"
        assert manifest["actual_end"] == "2020-12-31"
        assert manifest["params"]["start_date"] == "2020-12-29"
        assert manifest["params"]["end_date"] == "2020-12-31"
        assert manifest["supporting_observation_ids"] == [r.observation_id for r in selected]
        assert manifest["history_fingerprint"] == expected_hash
        assert "availability" in manifest["evidence"]
        assert datetime.fromisoformat(manifest["created_at"]).utcoffset() == timedelta(0)
        assert "unused-fixture" not in json.dumps(manifest)
        assert "database_path" not in manifest and "settings" not in manifest
    assert backtest["params"]["cost_bps"] == 37 and backtest["params"]["slippage_bps"] == 19
    narrowed = web.client.post(
        "/api/history", json={**SELECTION, "start_date": "2020-12-30"}
    ).json()
    assert narrowed["manifest"]["history_fingerprint"] != expected_hash


def test_technicals_route_is_causal_to_availability_and_readonly(web, monkeypatch):
    rows = []
    for i in range(60):
        stamp = datetime(2020, 1, 1, 10, tzinfo=timezone.utc) + timedelta(days=i)
        close = 100 + i
        rows.append(
            MarketObservation(
                instrument_id=LIVE,
                market_family="equity",
                timestamp=stamp,
                available_at=stamp + timedelta(minutes=5),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000,
                currency="INR",
                unit="share",
            )
        )
    # The newest observation is recorded late and must not enter this snapshot.
    rows[-1] = rows[-1].model_copy(update={"available_at": CUTOFF + timedelta(seconds=1)})
    with Storage(web.database) as store:
        store.add_observations(rows)
    forbid_writer(monkeypatch)
    before = snapshot(web.root)
    response = web.client.post(
        "/api/technicals", json={"company_id": LIVE, "decision_time": CUTOFF.isoformat()}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["bars"]) == result["snapshot"]["history_bars"] == 59
    assert result["snapshot"]["values"]["sma20"] == 148.5
    assert result["snapshot"]["values"]["rsi14"] == 100
    assert result["snapshot"]["values"]["macd_line"] == pytest.approx(7)
    assert result["snapshot"]["values"]["atr14"] == pytest.approx(2)
    assert set(result["snapshot"]["observation_ids"]) == {r.observation_id for r in rows[:-1]}
    assert snapshot(web.root) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"daily_returns": []},
        {"daily_returns": [0.1] * 4},
        {"daily_returns": [-1, 0, 0, 0, 0]},
        {"daily_returns": [-2, 0, 0, 0, 0]},
        {"daily_returns": ["NaN", 0, 0, 0, 0]},
        {"daily_returns": ["Infinity", 0, 0, 0, 0]},
        {"daily_returns": [0] * 10001},
        {"simulations": 9},
        {"simulations": 1001},
        {"horizon": 0},
        {"horizon": 1001},
        {"seed": -1},
        {"seed": 2**64},
        {"block_size": 0},
        {"block_size": 6},
        {"initial_capital": 0},
        {"initial_capital": "NaN"},
        {"workspace_path": "other.sqlite"},
    ],
)
def test_monte_carlo_http_validation_has_no_storage_side_effects(web, changes):
    before = snapshot(web.root)
    response = web.client.post(
        "/api/monte-carlo",
        json={
            "daily_returns": [0.01] * 5,
            "simulations": 10,
            "horizon": 3,
            **changes,
        },
    )
    assert response.status_code == 422
    assert snapshot(web.root) == before


@pytest.mark.parametrize("kind", ["articles", "prices"])
@pytest.mark.parametrize("universe,accepted", [("live", LIVE), ("demo", SYNTHETIC)])
def test_explicit_import_persists_only_matching_namespace_and_deduplicates(
    web, kind, universe, accepted
):
    if kind == "articles":
        records = [article("LIVE:NEWS:import"), article("synthetic-import")]
        content = "\n".join(record.model_dump_json() for record in records)
        expected_id = records[0 if universe == "live" else 1].article_id
    else:
        content = prices_csv([price_rows()[0], price_rows(SYNTHETIC)[0]])
        expected_id = accepted
    assert not web.database.exists()
    result = web.client.post(
        "/api/import", params={"universe": universe}, json={"kind": kind, "content": content}
    )
    assert result.status_code == 200, result.text
    assert result.json()["added"] == 1
    assert len(result.json()["errors"]) == 1
    assert "namespace" in result.json()["errors"][0]["error"].lower()
    assert web.database.exists()
    with Storage(web.database) as store:
        actual = (
            [r.article_id for r in store.list_articles()]
            if kind == "articles"
            else [r.instrument_id for r in store.list_observations()]
        )
        assert actual == [expected_id]
    again = web.client.post(
        "/api/import", params={"universe": universe}, json={"kind": kind, "content": content}
    )
    assert again.status_code == 200 and again.json()["added"] == 0


def test_explicit_import_retains_immutable_saved_price_on_conflicting_revision(web):
    original = price_rows()[0]
    changed = original.model_copy(update={"volume": 99999})
    for row, expected_added in ((original, 1), (changed, 0)):
        response = web.client.post(
            "/api/import", json={"kind": "prices", "content": prices_csv([row])}
        )
        assert response.status_code == 200
        assert response.json()["added"] == expected_added
    assert "Immutable record conflict" in response.json()["errors"][0]["error"]
    with Storage(web.database) as store:
        assert store.list_observations() == [original]


def test_demo_workspace_is_a_separate_ledger_and_uses_supplied_settings_copy(web):
    local = web.client.post(
        "/api/import",
        json={"kind": "articles", "content": article("LIVE:NEWS:local").model_dump_json()},
    )
    assert local.status_code == 200 and local.json()["added"] == 1
    before_local = web.database.read_bytes()
    demo = web.client.post(
        "/api/import",
        params={"workspace": "demo", "universe": "live"},
        json={"kind": "articles", "content": article("synthetic-demo").model_dump_json()},
    )
    assert demo.status_code == 200 and demo.json()["added"] == 1
    view = web.client.get("/api/workspace", params={"workspace": "demo", "universe": "live"}).json()
    assert view["universe"] == "demo" and view["mode"] == "replay"
    assert [a["article_id"] for a in view["articles"]] == ["synthetic-demo"]
    assert web.demo_database.exists() and web.database.read_bytes() == before_local
    assert web.settings.database_path == Path("data/local.sqlite")
    assert web.settings.universe == "live" and web.settings.mode == "replay"
    assert web.settings.live_data.access_token.get_secret_value() == ""


@pytest.mark.parametrize("kind", ["historical", "live"])
def test_explicit_sync_without_token_reports_configuration_error_without_network_or_fake_data(
    web, kind
):
    response = web.client.post(f"/api/sync/{kind}", json={"company_ids": [LIVE]})
    assert response.status_code == 200, response.text
    report = response.json()
    assert (
        report["network_requests"] == report["observations_added"] == report["articles_added"] == 0
    )
    assert any(
        error["stage"] == "configuration" and "token" in error["message"].lower()
        for error in report["errors"]
    )
    assert "unused-fixture" not in response.text
    with Storage(web.database) as store:
        assert store.list_observations() == store.list_articles() == store.list_runs() == []
    if kind == "historical":
        assert report["requested_start"] == "2015-01-01"
        assert report["requested_end"] == "2020-12-31"
        assert report["actual_start"] is report["actual_end"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"end_date": "2021-01-01"},
        {"start_date": "1999-12-31"},
        {"start_date": "2020-12-31", "end_date": "2020-01-01"},
    ],
)
def test_invalid_historical_sync_dates_fail_before_opening_writable_database(web, changes):
    before = snapshot(web.root)
    response = web.client.post("/api/sync/historical", json={"company_ids": [LIVE], **changes})
    assert response.status_code == 422
    assert snapshot(web.root) == before


@pytest.mark.parametrize("params", [{"workspace": "demo"}, {"universe": "demo"}])
def test_provider_sync_is_rejected_outside_live_local_workspace(web, params):
    before = snapshot(web.root)
    for kind in ("historical", "live"):
        response = web.client.post(f"/api/sync/{kind}", params=params, json={"company_ids": [LIVE]})
        assert response.status_code == 422
    assert snapshot(web.root) == before


@pytest.mark.parametrize(
    "params,source,mode",
    [
        ({"universe": "live"}, "synthetic-one", "replay"),
        ({"universe": "demo"}, "LIVE:NEWS:one", "replay"),
        ({"workspace": "demo"}, "synthetic-one", "live"),
    ],
)
def test_analysis_namespace_and_demo_mode_guards_run_before_writable_storage(
    web, params, source, mode
):
    before = snapshot(web.root)
    response = web.client.post(
        "/api/analyse",
        params=params,
        json={
            "article_id": source,
            "decision_time": CUTOFF.isoformat(),
            "mode": mode,
        },
    )
    assert response.status_code == 422
    assert snapshot(web.root) == before


def test_saved_analysis_explanation_and_outcome_actions_are_explicit_and_scoped(
    populated, monkeypatch
):
    web = populated
    calls = []

    def analyse(source, decision_time, policy, deps, repeat_run=False):
        calls.append(("analyse", source, deps.settings.mode, repeat_run))
        saved = run("new-live-run", source)
        deps.storage.save_run(saved)
        return saved

    def explain(identifier, deps):
        calls.append(("explain", identifier))
        return "Explicit offline explanation"

    def outcomes(deps, identifier):
        calls.append(("outcomes", identifier))
        outcome = EventOutcome(run_id=identifier, status="pending", reason="explicit calculation")
        deps.storage.save_outcome(outcome)
        return [outcome]

    monkeypatch.setattr(api_module, "analyse_article", analyse)
    monkeypatch.setattr(api_module, "explain_run", explain)
    monkeypatch.setattr(api_module, "compute_outcomes", outcomes)
    assert web.client.get("/api/workspace").status_code == 200
    assert web.client.get("/api/comparisons").status_code == 200
    assert calls == []
    response = web.client.post(
        "/api/analyse",
        json={
            "article_id": "LIVE:NEWS:one",
            "decision_time": CUTOFF.isoformat(),
            "mode": "live",
            "repeat_run": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["run_id"] == "new-live-run"
    assert calls == [("analyse", "LIVE:NEWS:one", "live", True)]
    assert web.client.post("/api/explain/synthetic-run").status_code == 404
    assert web.client.post("/api/explain/live-run").json() == {
        "text": "Explicit offline explanation"
    }
    response = web.client.post("/api/outcomes")
    assert response.status_code == 200
    assert {row["run_id"] for row in response.json()} == {"live-run", "new-live-run"}
    assert ("outcomes", "synthetic-run") not in calls
    assert web.settings.mode == "replay"


def test_demo_generation_requires_post_and_passes_separate_replay_destination(web, monkeypatch):
    calls = []

    def recorded_demo(root, database_path, mode, settings=None):
        calls.append((root, database_path, mode))
        # The app passes its own demo configuration, so local .env is never re-read.
        assert settings is not None and settings is not web.settings
        assert (settings.universe, settings.mode) == ("demo", "replay")
        assert settings.database_path == web.demo_database
        return [SimpleNamespace(run_id="recorded-run")]

    monkeypatch.setattr(api_module, "run_demo", recorded_demo)
    assert web.client.get("/api/workspace", params={"workspace": "demo"}).status_code == 200
    assert calls == []
    response = web.client.post("/api/demo")
    assert response.status_code == 200
    assert response.json()["run_ids"] == ["recorded-run"]
    assert calls == [(web.root, web.demo_database, "replay")]
    assert web.settings.universe == "live" and web.settings.database_path == Path(
        "data/local.sqlite"
    )


@pytest.mark.parametrize("origin", ["https://other.invalid", "null", "http://127.0.0.1:3001"])
def test_cross_origin_mutations_are_rejected_before_writes(web, origin):
    before = snapshot(web.root)
    response = web.client.post(
        "/api/import",
        headers={"origin": origin},
        json={
            "kind": "articles",
            "content": article("LIVE:NEWS:origin").model_dump_json(),
        },
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin mutation refused"}
    assert snapshot(web.root) == before


@pytest.mark.parametrize("origin", ["http://127.0.0.1:3000", "http://localhost:3000"])
def test_same_origin_explicit_import_is_accepted(web, origin):
    response = web.client.post(
        "/api/import",
        headers={"origin": origin},
        json={
            "kind": "articles",
            "content": article("LIVE:NEWS:origin").model_dump_json(),
        },
    )
    assert response.status_code == 200 and response.json()["added"] == 1


@pytest.mark.parametrize("length", ["10000001", "-1", "not-a-number"])
def test_declared_oversized_or_invalid_body_is_refused_without_mutation(web, length):
    before = snapshot(web.root)
    response = web.client.post(
        "/api/import",
        headers={"content-length": length},
        json={
            "kind": "articles",
            "content": article("LIVE:NEWS:body-limit").model_dump_json(),
        },
    )
    assert response.status_code == 413
    assert snapshot(web.root) == before
