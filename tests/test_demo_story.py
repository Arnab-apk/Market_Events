"""End-to-end presentation story (docs/PRESENTATION_PLAN.md) through the HTTP API and CLI.

Offline replay only: an isolated copy of configs, prompts and fixtures, a temporary
ledger, and guards that fail on any socket, provider or live-model call. Every
number asserted here comes from the bundled, explicitly synthetic fixtures.
"""

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

import market_events.api as api_module
from market_events.__main__ import main
from market_events.config import LiveDataSettings, Settings
from market_events.model_client import ModelClient

ROOT = Path(__file__).resolve().parents[1]
DEMO = {"workspace": "demo", "universe": "demo"}
NOON = "2026-01-12T12:00:00Z"
# Equity closes 10:00 UTC (available 10:05); crude closes 11:00 UTC (available 11:05).
BEFORE_CRUDE_SETTLES = "2026-01-12T10:30:00Z"
LAB = "SYNTHETIC:LAB_DEMO"
ENVIRONMENT = (
    "MARKET_EVENTS_MODE",
    "MARKET_EVENTS_UNIVERSE",
    "MARKET_EVENTS_DATABASE",
    "UPSTOX_ANALYTICS_TOKEN",
    "UPSTOX_ACCESS_TOKEN",
    *(
        f"{role}_{field}"
        for role in ("SLM", "LLM")
        for field in ("PROVIDER", "BASE_URL", "MODEL", "API_KEY")
    ),
)


def isolated_root(tmp_path: Path) -> Path:
    for folder in ("configs", "prompts", "tests/fixtures"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    return tmp_path


def offline(patch, attempts):
    def forbidden(*args, **kwargs):
        attempts.append("external call")
        raise AssertionError("The demo story must never use a socket, provider or live model")

    patch.setattr(requests.sessions.Session, "request", forbidden)
    patch.setattr(socket, "create_connection", forbidden)
    patch.setattr(ModelClient, "_live", forbidden)
    for name in ENVIRONMENT:
        patch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def story(tmp_path_factory):
    attempts = []
    with pytest.MonkeyPatch.context() as patch:
        offline(patch, attempts)
        root = isolated_root(tmp_path_factory.mktemp("story"))
        settings = Settings(
            root=root,
            database_path=Path("data/local.sqlite"),
            universe="live",
            mode="replay",
            live_data=LiveDataSettings(access_token=""),
        )
        patch.setattr(
            api_module,
            "load_settings",
            lambda *a, **k: pytest.fail("The API must use the supplied Settings"),
        )
        with TestClient(api_module.create_app(root=root, settings=settings)) as client:
            loaded = client.post("/api/demo")
            assert loaded.status_code == 200, loaded.text
            yield SimpleNamespace(client=client, root=root, demo=loaded.json())
    assert not attempts, "An endpoint attempted an external network/model call"
    assert not (root / "data/local.sqlite").exists(), "The demo must not touch the local ledger"


def analyse(story, article_id, decision_time=NOON, policy="slm_delegate"):
    response = story.client.post(
        "/api/analyse",
        params=DEMO,
        json={"article_id": article_id, "decision_time": decision_time, "policy": policy},
    )
    assert response.status_code == 200, response.text
    return response.json()


def workspace(story):
    response = story.client.get("/api/workspace", params=DEMO)
    assert response.status_code == 200
    return response.json()


def test_step1_demo_load_is_offline_labelled_synthetic_replay(story):
    assert story.demo["provenance"] == "synthetic_fixture / recorded_replay"
    assert len(story.demo["run_ids"]) == 3
    view = workspace(story)
    assert view["workspace"] == "demo" and view["universe"] == "demo"
    assert view["mode"] == "replay" and "synthetic" in view["provenance"]
    runs = {
        run["article_id"]: run for run in view["runs"] if run["run_id"] in story.demo["run_ids"]
    }
    assert set(runs) == {"syn-001", "syn-002", "syn-003"}
    assert all(run["mode"] == "replay" for run in runs.values())
    assert all(call["mode"] == "replay" for run in runs.values() for call in run["calls"])
    assert {run["status"] for run in runs.values()} == {"completed"}


def test_step2_source_inbox_holds_only_synthetic_evidence_and_reimport_is_idempotent(story):
    view = workspace(story)
    assert len(view["articles"]) == 35
    for article in view["articles"]:
        assert article["text"].startswith("EXPLICITLY SYNTHETIC FIXTURE.")
        assert article["source_url"].startswith("https://example.invalid/")
    companies = {row["instrument_id"]: row for row in view["companies"]}
    for company in ("NSE:ASIANPAINT", "NSE:BERGEPAINT", "NSE:PIDILITIND"):
        assert companies[company]["bars"] == 16
        assert companies[company]["research_bars"] == 0  # 2026 demo never feeds the lab
    content = (ROOT / "tests/fixtures/articles.jsonl").read_text(encoding="utf-8")
    response = story.client.post(
        "/api/import", params=DEMO, json={"kind": "articles", "content": content}
    )
    assert response.status_code == 200
    assert response.json()["added"] == 0 and response.json()["errors"] == []


def test_step3_crude_shock_for_paint_maker_has_signed_components_and_contrasts(story):
    run = analyse(story, "syn-002")
    # The same request as the demo load reuses the saved decision instead of re-running.
    assert run["run_id"] in story.demo["run_ids"]
    assert run["extraction"]["company_id"] == "NSE:BERGEPAINT"
    assert run["extraction"]["commodity_id"] == "MCX:CRUDEOIL"
    assert run["exposure"]["status"] == "matched"
    assert run["exposure"]["rule"]["direction"] == -1
    assert "synthetic" in run["exposure"]["rule"]["source"].lower()
    values = run["features"]["values"]
    assert values["excess_return"] == pytest.approx(0.008)
    assert values["commodity_return"] == pytest.approx(0.015)
    assessment = run["assessment"]
    # Crude up x reviewed -1 exposure: the commodity leg is negative for the paint maker,
    # the equity reaction is positive, so the frozen rules report mixed evidence.
    assert assessment["inputs"]["components"]["equity"] == pytest.approx(0.4)
    assert assessment["inputs"]["components"]["commodity"] == pytest.approx(-0.5)
    assert assessment["evidence_score"] == pytest.approx(0.04)
    assert assessment["direction"] == "neutral" and assessment["coverage"] == 1
    assert assessment["conflicts"] == ["Equity and exposure-adjusted commodity evidence disagree"]
    assert "not a probability" in assessment["explanation"]

    # Contrast 1: same article before the crude session settles -> abstain, not guess.
    early = analyse(story, "syn-002", BEFORE_CRUDE_SETTLES)
    assert early["status"] == "abstained"
    assert early["assessment"]["direction"] == "abstain"
    assert "commodity_return" in early["features"]["missing"]
    assert early["assessment"]["abstention_reasons"] == [
        "Missing or stale mandatory commodity return"
    ]
    # Contrast 2: supported positive equity-only evidence.
    earnings = analyse(story, "syn-001")
    assert earnings["assessment"]["direction"] == "positive"
    assert earnings["assessment"]["evidence_score"] == pytest.approx(0.4)
    # Contrast 3: no clear financial event -> abstain; Contrast 4: irrelevant -> filtered.
    unclear = analyse(story, "syn-005")
    assert unclear["status"] == "abstained"
    assert unclear["assessment"]["abstention_reasons"] == ["Unsupported event family"]
    irrelevant = analyse(story, "syn-004")
    assert irrelevant["status"] == "irrelevant" and irrelevant["assessment"] is None


def test_step4_and_5_saved_case_keeps_evidence_trail_and_separate_later_outcome(story):
    run = analyse(story, "syn-002")
    before = story.client.get(f"/api/case/{run['run_id']}", params=DEMO).json()
    outcomes = story.client.post("/api/outcomes", params=DEMO)
    assert outcomes.status_code == 200
    rows = {row["run_id"]: row for row in outcomes.json()}
    outcome = rows[run["run_id"]]
    assert outcome["status"] == "completed"
    assert outcome["entry_time"] == "2026-01-13T03:45:00Z"  # next session open, 09:15 IST
    assert outcome["exit_time"] == "2026-01-19T10:00:00Z"  # fifth observed session close
    assert outcome["net_return"] == pytest.approx(outcome["gross_return"] - 0.001)
    assert outcome["excess_return"] == pytest.approx(
        outcome["gross_return"] - outcome["benchmark_return"]
    )
    # The abstained early case gets no outcome; abstentions are not scored as trades.
    early = analyse(story, "syn-002", BEFORE_CRUDE_SETTLES)
    assert rows[early["run_id"]]["status"] == "invalid"

    case = story.client.get(f"/api/case/{run['run_id']}", params=DEMO)
    assert case.status_code == 200
    case = case.json()
    assert case["run"] == before["run"], "Computing outcomes must not rewrite the decision"
    assert case["outcome"]["run_id"] == run["run_id"]
    assert case["article"]["article_id"] == "syn-002"
    for span in case["run"]["extraction"]["source_spans"]:
        assert span in case["article"]["text"]
    assert case["missing_observation_ids"] == []
    assert {row["observation_id"] for row in case["observations"]} >= set(
        case["run"]["features"]["observation_ids"]
    )
    assert [call["task"] for call in case["run"]["calls"]] == ["filter", "extraction"]
    assert {call["provider"] for call in case["run"]["calls"]} == {"fixture"}
    assert all(call["input_tokens"] is None for call in case["run"]["calls"])
    # Export: the case download is plain JSON with no credentials.
    text = json.dumps(case)
    assert "api_key" not in text and "access_token" not in text
    # The optional explanation has no recorded replay: a clear 422, never a 500.
    explanation = story.client.post(f"/api/explain/{run['run_id']}", params=DEMO)
    assert explanation.status_code == 422
    assert "No recorded replay" in explanation.json()["detail"]


def test_step6_policy_comparison_is_matched_and_claims_no_unmeasured_cost(story):
    for policy in ("llm_only", "slm_filter", "slm_delegate"):
        run = analyse(story, "syn-002", policy=policy)
        assert run["assessment"]["evidence_score"] == pytest.approx(0.04)
        analyse(story, "syn-005", policy=policy)  # idempotent: reuses saved decisions
    response = story.client.get("/api/comparisons", params=DEMO)
    assert response.status_code == 200
    report = response.json()
    assert "synthetic replay is not real-data validation" in report["provenance"]
    summary = {row["policy"]: row for row in report["policy_summary"]}
    assert set(summary) == {"llm_only", "slm_filter", "slm_delegate"}
    for row in summary.values():
        assert row["mode"] == "replay"
        assert row["input_tokens"] is None and row["output_tokens"] is None
        assert row["usage_complete"] is False
        assert row["estimated_cost"] is None and row["cost_currency"] is None
    cohort = next(
        row
        for row in report["matched_inputs"]
        if row["article_id"] == "syn-002" and row["decision_time"].startswith("2026-01-12T12")
    )
    assert cohort["all_three_policies"] and cohort["same_saved_configuration"]
    agreement = report["extraction_agreement"]
    assert agreement["label"] == "Synthetic sanity check on authored articles, not a benchmark"
    groups = {row["policy"]: row for row in agreement["groups"]}
    assert set(groups) == {"llm_only", "slm_filter", "slm_delegate"}
    delegate = groups["slm_delegate"]
    assert delegate["filter_recall"] == 1.0
    # syn-005 (no clear financial event) is forwarded as uncertain: an honest false positive.
    assert delegate["filter_confusion"]["fp"] == 1 and delegate["filter_precision"] < 1
    assert delegate["field_accuracy"]["event_type"] < 1
    assert 0 < delegate["abstention_rate"] < 1


def test_step7_strategy_lab_backtest_cost_stress_and_monte_carlo_on_labelled_history(story):
    view = workspace(story)
    lab = next(row for row in view["companies"] if row["instrument_id"] == LAB)
    assert lab["synthetic"] is True and "not performance evidence" in lab["source"]
    assert lab["research_bars"] == 1566
    study = {"company_id": LAB, "start_date": "2015-01-01", "end_date": "2020-12-31"}
    history = story.client.post("/api/history", params=DEMO, json=study)
    assert history.status_code == 200, history.text
    history = history.json()
    assert len(history["bars"]) == 1566
    assert history["actual_start"] == "2015-01-01" and history["actual_end"] == "2020-12-31"
    assert history["indicators"]["sma50"] and history["indicators"]["rsi14"]
    assert history["manifest"]["instrument_id"] == LAB

    base = {**study, "strategy": "sma_cross", "cost_bps": 10, "slippage_bps": 5}
    result = story.client.post("/api/backtest", params=DEMO, json=base)
    assert result.status_code == 200, result.text
    result = result.json()
    metrics = result["metrics"]
    assert metrics["total_fees"] > 0 and metrics["total_slippage"] > 0
    assert 0 <= metrics["probabilistic_sharpe"] <= 1
    assert any("not deflated" in note for note in result["assumptions"])
    # Same pre-chosen configuration at 2x costs: never better.
    stressed = story.client.post(
        "/api/backtest", params=DEMO, json={**base, "cost_bps": 20, "slippage_bps": 10}
    ).json()
    assert stressed["metrics"]["total_return"] < metrics["total_return"]

    request = {"daily_returns": result["daily_returns"], "simulations": 100, "horizon": 60}
    first = story.client.post("/api/monte-carlo", json=request)
    assert first.status_code == 200
    second = story.client.post("/api/monte-carlo", json=request).json()
    assert first.json()["metrics"] == second["metrics"]  # seeded and reproducible
    assert len(second["bands"]) == 61
    assert any("not probabilities" in note for note in second["assumptions"])


def test_lab_history_never_enters_event_evidence_or_the_live_universe(story):
    study = {"company_id": LAB, "start_date": "2015-01-01", "end_date": "2020-12-31"}
    history = story.client.post("/api/history", params=DEMO, json=study).json()
    lab_ids = set(history["manifest"]["supporting_observation_ids"])
    assert len(lab_ids) == 1566
    view = workspace(story)
    assert view["runs"]
    for run in view["runs"]:
        ids = set((run["features"] or {}).get("observation_ids", []))
        ids |= set((run["technicals"] or {}).get("observation_ids", []))
        assert not ids & lab_ids
        assert (run["extraction"] or {}).get("company_id") != LAB
    assert story.client.post("/api/history", json=study).status_code == 422  # live universe
    # The 2026 demo equities stay excluded from the 2020-capped lab.
    demo_company = {**study, "company_id": "NSE:BERGEPAINT"}
    assert story.client.post("/api/history", params=DEMO, json=demo_company).status_code == 422


def test_cli_replays_the_same_story_and_exports(tmp_path, monkeypatch, capsys):
    attempts = []
    offline(monkeypatch, attempts)
    root = isolated_root(tmp_path)
    database = tmp_path / "data/cli.sqlite"
    base = ["--root", str(root), "--database", str(database), "--universe", "demo"]
    assert main(base + ["demo"]) == 0
    capsys.readouterr()
    assert main(base + ["analyse", "syn-002", "--decision-time", NOON, "--policy", "llm_only"]) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["mode"] == "replay" and run["assessment"]["direction"] == "neutral"
    assert main(base + ["analyse", "syn-002", "--decision-time", BEFORE_CRUDE_SETTLES]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "abstained"
    assert main(base + ["outcomes"]) == 0
    assert all(
        row["status"] in {"completed", "invalid"} for row in json.loads(capsys.readouterr().out)
    )
    output = tmp_path / "export.json"
    assert main(base + ["export", "--output", str(output)]) == 0
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert "synthetic" in exported["provenance"].lower()
    assert {row["article_id"] for row in exported["runs"]} == {"syn-001", "syn-002", "syn-003"}
    assert exported["outcomes"]
    report = tmp_path / "experiments.json"
    assert main(base + ["experiments", "--output", str(report)]) == 0
    experiments = json.loads(report.read_text(encoding="utf-8"))
    assert experiments["extraction_agreement"]["label"].startswith("Synthetic sanity check")
    assert not attempts
    assert datetime.fromisoformat(run["decision_time"].replace("Z", "+00:00")) == datetime(
        2026, 1, 12, 12, tzinfo=timezone.utc
    )


def test_api_adds_plain_language_and_featured_story_without_persisting_them(story):
    run = analyse(story, "syn-002")
    assert "Berger Paints beat its benchmark by 0.8%" in run["plain_summary"]
    assert "crude oil rose 1.5%" in run["plain_summary"]
    assert run["plain_summary"].endswith("so the evidence is mixed (neutral).")
    assert run["score_formula"].startswith("0.6 × (+0.40 equity vs benchmark)")
    early = analyse(story, "syn-002", BEFORE_CRUDE_SETTLES)
    assert early["plain_summary"].startswith("No assessment for Berger Paints")
    case = story.client.get(f"/api/case/{run['run_id']}", params=DEMO).json()
    assert case["run"]["plain_summary"] == run["plain_summary"]
    view = workspace(story)
    assert all("plain_summary" in saved for saved in view["runs"])
    featured = {a["article_id"]: a for a in view["articles"] if a["featured"]}
    assert {k: v["story_role"] for k, v in featured.items()} == {
        "syn-001": "earnings",
        "syn-002": "crude_shock",
        "syn-003": "order",
        "syn-004": "irrelevant",
        "syn-005": "unconfirmed",
    }
    assert [entry["article_id"] for entry in view["demo_story"]][0] == "syn-002"
    assert all(a["story_role"] is None for a in view["articles"] if not a["featured"])
    # Display-only: the ledger record has no plain-language fields.
    from market_events.storage import Storage

    with Storage(story.root / "data/web_demo.sqlite") as store:
        assert "plain_summary" not in store.get_run(run["run_id"]).model_dump_json()
    live = story.client.get("/api/workspace").json()
    assert live["demo_story"] == [] and all(not a["featured"] for a in live["articles"])


def test_backtest_walk_forward_shows_in_and_out_of_sample_side_by_side(story):
    base = {
        "company_id": LAB,
        "start_date": "2019-01-01",
        "end_date": "2020-12-31",
        "strategy": "sma_cross",
    }
    plain = story.client.post("/api/backtest", params=DEMO, json=base).json()
    assert "walk_forward" not in plain  # backward compatible when not requested
    response = story.client.post(
        "/api/backtest", params=DEMO, json={**base, "walk_forward_split": "2020-01-01"}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["metrics"] == plain["metrics"]  # full-window result unchanged
    split = result["walk_forward"]
    assert split["split_date"] == "2020-01-01"
    assert split["in_sample"]["actual_end"] == "2019-12-31"
    assert split["out_of_sample"]["actual_start"] == "2020-01-01"
    assert split["in_sample"]["bars"] + split["out_of_sample"]["bars"] == len(plain["equity"])
    for side in ("in_sample", "out_of_sample"):
        assert {"total_return", "sharpe", "probabilistic_sharpe", "max_drawdown"} <= set(
            split[side]["metrics"]
        )
    for bad in ("2019-01-01", "2021-01-01"):
        rejected = story.client.post(
            "/api/backtest", params=DEMO, json={**base, "walk_forward_split": bad}
        )
        assert rejected.status_code == 422


def test_lab_history_extension_keeps_earlier_bars_so_reloading_the_demo_is_safe(story):
    # A ledger loaded before the 2015-2018 extension already holds the 2019-2020 bars.
    # Those rows are unchanged, so loading the demo again must not hit an immutable conflict.
    again = story.client.post("/api/demo")
    assert again.status_code == 200, again.text
    rows = (ROOT / "tests/fixtures/synthetic_lab_history.csv").read_text().splitlines()[1:]
    last_2018 = next(r for r in reversed(rows) if r.split(",")[2].startswith("2018"))
    first_2019 = next(r for r in rows if r.split(",")[2].startswith("2019"))
    assert last_2018.split(",")[7] == first_2019.split(",")[4]  # continuous price path
    assert rows[0].split(",")[2] == "2015-01-01T10:00:00Z" and len(rows) == 1566
