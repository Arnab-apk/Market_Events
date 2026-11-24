"""Paper portfolio CLI subcommands and HTTP routes: offline smoke and error contracts."""

import json
import shutil
import socket
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

import market_events.api as api_module
from market_events.__main__ import main
from market_events.config import LiveDataSettings, Settings
from market_events.schemas import PAPER_LABEL, PaperPlan, ScreenResult
from test_paper_portfolio import AS_OF, EXPECTED, load_paper_fixture, rules_root

AS_OF_TEXT = "2020-12-31T15:30:00+05:30"
AAA, BBB = "SYNTHETIC:NSE:AAA", "SYNTHETIC:NSE:BBB"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("paper CLI/API must never use the network")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def workspace(tmp_path):
    root = rules_root(tmp_path)
    database = load_paper_fixture(tmp_path / "data/paper.sqlite")
    return root, database


def cli(root, database, *args):
    return main(["--root", str(root), "--database", str(database), "--universe", "demo", *args])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_paper_screen_prints_a_table_and_json(workspace, capsys):
    root, database = workspace
    assert cli(root, database, "paper-screen", "--as-of", AS_OF_TEXT) == 0
    table = capsys.readouterr().out
    assert PAPER_LABEL in table
    assert AAA in table and "PASS" in table and "FAIL" in table

    assert cli(root, database, "paper-screen", "--as-of", AS_OF_TEXT, "--json") == 0
    result = ScreenResult.model_validate_json(capsys.readouterr().out)
    assert result.shortlist == EXPECTED["shortlist"]


def test_paper_size_saves_a_plan_that_paper_risk_rechecks(workspace, capsys):
    root, database = workspace
    assert cli(root, database, "paper-size", "--as-of", AS_OF_TEXT, "--json") == 0
    captured = capsys.readouterr()
    plan = PaperPlan.model_validate_json(captured.out)
    assert {p.instrument_id: p.quantity for p in plan.proposals} == EXPECTED["quantities"]
    saved = list((root / "runs" / "paper").glob("*.json"))
    assert len(saved) == 1 and str(saved[0].name) in captured.err

    assert cli(root, database, "paper-risk", "--plan", str(saved[0])) == 0
    table = capsys.readouterr().out
    assert PAPER_LABEL in table and "PASS" in table and "BLOCK" not in table


def test_paper_size_table_and_budget_option(workspace, capsys):
    root, database = workspace
    assert cli(root, database, "paper-size", "--as-of", AS_OF_TEXT, "--budget", "50000") == 0
    table = capsys.readouterr().out
    assert PAPER_LABEL in table and "50,000" in table and "buy" in table


def test_paper_rebalance_reads_a_positions_file(workspace, capsys, tmp_path):
    root, database = workspace
    positions = tmp_path / "positions.json"
    positions.write_text(
        json.dumps(
            [{"instrument_id": AAA, "quantity": 40}, {"instrument_id": BBB, "quantity": 40}]
        ),
        encoding="utf-8",
    )
    args = (
        "paper-rebalance",
        "--positions",
        str(positions),
        "--cash",
        "9200",
        "--as-of",
        AS_OF_TEXT,
    )
    assert cli(root, database, *args, "--json") == 0
    plan = PaperPlan.model_validate_json(capsys.readouterr().out)
    assert [p.side for p in plan.proposals][:2] == ["sell", "sell"]
    assert cli(root, database, *args, "--no-save") == 0
    assert "sell" in capsys.readouterr().out


def test_paper_size_on_demo_dates_is_an_empty_plan_not_a_crash(tmp_path, capsys):
    root = rules_root(tmp_path)
    database = tmp_path / "data/empty.sqlite"
    assert cli(root, database, "paper-size", "--as-of", AS_OF_TEXT, "--no-save") == 0
    out = capsys.readouterr().out
    assert PAPER_LABEL in out and "Warning" in out


def test_paper_cli_errors_are_clean(workspace, capsys, tmp_path):
    root, database = workspace
    assert cli(root, database, "paper-size", "--as-of", "2020-12-31T15:30:00") == 1
    assert "timezone" in capsys.readouterr().err
    assert cli(root, database, "paper-risk", "--plan", str(tmp_path / "missing.json")) == 1
    assert "Error" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


@pytest.fixture
def web(workspace, monkeypatch):
    root, database = workspace
    monkeypatch.setenv("MARKET_EVENTS_DEMO_DATABASE", str(database))
    monkeypatch.setenv("MARKET_EVENTS_WEB_ORIGIN", "http://127.0.0.1:3000")
    settings = Settings(
        root=root,
        database_path=Path("data/local.sqlite"),
        universe="live",
        mode="replay",
        live_data=LiveDataSettings(access_token=""),
    )
    app = api_module.create_app(root=root, settings=settings)
    with TestClient(app) as client:
        yield client, root


DEMO = {"workspace": "demo", "universe": "demo"}


def test_api_screen_size_and_rebalance(web):
    client, root = web
    screen = client.post("/api/paper/screen", params=DEMO, json={"as_of": AS_OF_TEXT})
    assert screen.status_code == 200, screen.text
    assert screen.json()["shortlist"] == EXPECTED["shortlist"]

    size = client.post("/api/paper/size", params=DEMO, json={"as_of": AS_OF_TEXT})
    assert size.status_code == 200, size.text
    plan = PaperPlan.model_validate(size.json())
    assert {p.instrument_id: p.quantity for p in plan.proposals} == EXPECTED["quantities"]
    assert plan.as_of == AS_OF and plan.label == PAPER_LABEL
    assert not (root / "runs").exists(), "API routes are read-only and save nothing"

    body = {
        "as_of": AS_OF_TEXT,
        "positions": [
            {"instrument_id": AAA, "quantity": 40},
            {"instrument_id": BBB, "quantity": 40},
        ],
        "cash_inr": 9200,
    }
    rebalance = client.post("/api/paper/rebalance", params=DEMO, json=body)
    assert rebalance.status_code == 200, rebalance.text
    assert {v["verdict"] for v in rebalance.json()["verdicts"]} == {"PASS"}


def test_api_budget_and_universe_scoping(web, workspace):
    client, root = web
    sized = client.post(
        "/api/paper/size", params=DEMO, json={"as_of": AS_OF_TEXT, "budget_inr": 50000}
    )
    assert sized.status_code == 200 and sized.json()["budget_inr"] == 50000
    # The same synthetic records in the local workspace are invisible to the live universe.
    shutil.copy(workspace[1], root / "data/local.sqlite")
    live = client.post(
        "/api/paper/size",
        params={"workspace": "local", "universe": "live"},
        json={"as_of": AS_OF_TEXT},
    )
    assert live.status_code == 200, live.text
    assert live.json()["proposals"] == [] and live.json()["warnings"]


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/paper/screen", {"as_of": "2020-12-31T15:30:00"}),
        ("/api/paper/size", {"as_of": AS_OF_TEXT, "budget_inr": -5}),
        ("/api/paper/size", {"as_of": AS_OF_TEXT, "budget_inr": "NaN"}),
        ("/api/paper/size", {"as_of": AS_OF_TEXT, "unknown": 1}),
        (
            "/api/paper/rebalance",
            {
                "as_of": AS_OF_TEXT,
                "positions": [{"instrument_id": AAA, "quantity": -1}],
                "cash_inr": 0,
            },
        ),
        ("/api/paper/rebalance", {"as_of": AS_OF_TEXT, "positions": [], "cash_inr": -1}),
    ],
)
def test_api_rejects_malformed_requests(web, path, body):
    client, _ = web
    assert client.post(path, params=DEMO, json=body).status_code == 422


def test_api_unknown_holding_is_a_clean_422(web):
    client, _ = web
    body = {
        "as_of": AS_OF_TEXT,
        "positions": [{"instrument_id": "SYNTHETIC:NSE:ZZZ", "quantity": 1}],
        "cash_inr": 0,
    }
    response = client.post("/api/paper/rebalance", params=DEMO, json=body)
    assert response.status_code == 422 and "SYNTHETIC:NSE:ZZZ" in response.json()["detail"]
